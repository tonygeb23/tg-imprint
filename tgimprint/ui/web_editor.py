"""The editor control: a WebView2 holding the editor page, driven asynchronously.

Two rules, both measured (CLAUDE.md, CHALLENGE.md W2):

- **Never a synchronous RunScript once the editor exists.** It hung for
  ever in two of four focused runs with NVDA running. Every call here goes
  through `call(method, *args, callback=None)`, which uses RunScriptAsync
  and continues in the callback when EVT_WEBVIEW_SCRIPT_RESULT arrives. A
  request id is embedded in what the script returns, so results are matched
  by id and never by order or by client data (the wx binding refuses a
  string as client data).
- **Only sanitised HTML enters the page.** `load_body` runs Worker A's
  `htmlclean.normalise` on whatever it is given, and the page itself carries
  a Content Security Policy. Every navigation after the first load is vetoed.

The page pushes its own state (selection, modified, words, keys, paste,
context menu) over the message bridge; the window subscribes with
`on_message`.
"""
import json
import time

import wx
import wx.html2 as webview

from .. import constants as C
from .. import editor_page
from . import keymap

#: The event the window binds to hear about state, keys and so on.
EVT_EDITOR_MESSAGE_TYPE = wx.NewEventType()
EVT_EDITOR_MESSAGE = wx.PyEventBinder(EVT_EDITOR_MESSAGE_TYPE, 1)


class EditorMessage(wx.PyCommandEvent):
    def __init__(self, wid, data):
        super().__init__(EVT_EDITOR_MESSAGE_TYPE, wid)
        self.data = data


def sanitise(body_html):
    """Worker A's normaliser, imported lazily so this module loads without it.

    Until htmlclean exists the fallback keeps the page safe the other way
    round: it escapes everything, so a received file cannot carry markup in
    at all. Returns (clean_html, warnings).
    """
    try:
        from .. import htmlclean
    except ImportError:
        from html import escape
        text = escape(body_html or "")
        return ("<p>%s</p>" % text if text.strip() else "<p><br></p>",
                ["The HTML cleaner is not part of this build, so the text was "
                 "loaded without any formatting."])
    try:
        clean, warnings = htmlclean.normalise(body_html or "")
    except Exception as exc:                          # a cleaner that raises
        from html import escape
        return ("<p>%s</p>" % escape(body_html or ""),
                ["The HTML could not be cleaned: %s" % exc])
    return clean or "<p><br></p>", list(warnings or [])


class EditorView(wx.Panel):
    """The panel holding the WebView2 and the asynchronous API around it."""

    def __init__(self, parent, page=None, lang="en-US", textbox_role=True,
                 display=None):
        super().__init__(parent)
        self.ready = False
        self.loads = 0
        self._next_id = 1
        self._pending = {}              # id -> (callback, issued_at)
        self._page = dict(page or {})
        self._display = editor_page.clean_display(display)
        self._lang = lang
        self._textbox_role = textbox_role
        self._queued_body = None
        self.last_state = {}
        self.word_count = 0

        self.web = webview.WebView.New(self, backend=webview.WebViewBackendEdge)
        self.web.EnableContextMenu(False)
        self.web.EnableHistory(False)
        try:
            self.web.EnableAccessToDevTools(False)
        except Exception:
            pass
        self.web.AddScriptMessageHandler("tgimprint")
        self.web.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_message)
        self.web.Bind(webview.EVT_WEBVIEW_SCRIPT_RESULT, self._on_result)
        self.web.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
        self.web.Bind(webview.EVT_WEBVIEW_NAVIGATING, self._on_navigating)
        self.web.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self._on_new_window)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.web, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self._set_page("")

    # ------------------------------------------------------------ page --
    def _set_page(self, body_html):
        self.ready = False
        html = editor_page.build_page(keymap.page_bindings(), keymap.DENY_CHORDS,
                                      lang=self._lang, page=self._page,
                                      body_html=body_html,
                                      textbox_role=self._textbox_role,
                                      display=self._display)
        self.web.SetPage(html, "about:blank")

    def _on_loaded(self, event):
        self.loads += 1
        event.Skip()

    def _on_navigating(self, event):
        # The first load is SetPage's own data: URL. Anything after it is a
        # link, a drop or a script trying to leave the editor: refused.
        if self.loads >= 1:
            event.Veto()
            return
        event.Skip()

    def _on_new_window(self, event):
        event.Veto()

    # ---------------------------------------------------------- bridge --
    def _on_message(self, event):
        try:
            data = json.loads(event.GetString())
        except ValueError:
            return
        kind = data.get("type")
        if kind == "ready":
            self.ready = True
            if self._queued_body is not None:
                body, self._queued_body = self._queued_body, None
                self.call("setBody", body)
        elif kind == "state":
            self.last_state = data
        elif kind == "words":
            self.word_count = int(data.get("count") or 0)
        wx.PostEvent(self, EditorMessage(self.GetId(), data))

    def _on_result(self, event):
        text = event.GetString()
        if event.IsError():
            # A script that threw. Find whose it was by draining the oldest
            # request: results arrive in issue order (measured), and an error
            # carries no id.
            if self._pending:
                oldest = min(self._pending, key=lambda k: self._pending[k][1])
                callback, _ = self._pending.pop(oldest)
                if callback is not None:
                    callback(None, "The editor script failed: %s" % text)
            return
        try:
            payload = json.loads(text) if text else {}
        except ValueError:
            payload = {}
        request = payload.get("id") if isinstance(payload, dict) else None
        callback = None
        if request in self._pending:
            callback, _ = self._pending.pop(request)
        elif self._pending and not isinstance(payload, dict):
            oldest = min(self._pending, key=lambda k: self._pending[k][1])
            callback, _ = self._pending.pop(oldest)
        if callback is None:
            return
        if isinstance(payload, dict) and payload.get("ok") is False:
            callback(None, payload.get("error") or "The editor script failed.")
        else:
            value = payload.get("value") if isinstance(payload, dict) else payload
            callback(value, "")

    # ------------------------------------------------------------- API --
    def run(self, expression, callback=None):
        """Evaluate a JavaScript expression; `callback(value, error)` later.

        The expression is wrapped so that whatever it returns comes back as
        JSON under a request id. Never synchronous. Returns the request id.
        """
        request = self._next_id
        self._next_id += 1
        script = ("(function(){ try { var v = (%s); return JSON.stringify({id:%d, ok:true, "
                  "value: v === undefined ? null : v}); } catch (e) { return JSON.stringify("
                  "{id:%d, ok:false, error:String(e && e.message || e)}); } })()"
                  % (expression, request, request))
        self._pending[request] = (callback, time.monotonic())
        self.web.RunScriptAsync(script)
        return request

    def call(self, method, *args, callback=None):
        """window.editor.<method>(*args), asynchronously."""
        expression = "window.editor.%s(%s)" % (
            method, ", ".join(json.dumps(a) for a in args))
        return self.run(expression, callback)

    def pending_count(self):
        return len(self._pending)

    # ------------------------------------------------------- documents --
    def load_body(self, body_html, callback=None):
        """Sanitise, then put the body in the page. Resets the undo history.

        `callback(warnings)` is called once the page has taken it.
        """
        clean, warnings = sanitise(body_html)
        self._put_body(clean, lambda value, error: callback(warnings) if callback else None)
        return warnings

    def load_clean_body(self, clean_html, callback=None):
        """For HTML the caller has already run through the sanitiser on a
        thread (import, open) so the UI thread does not do it twice."""
        self._put_body(clean_html, callback)

    def _put_body(self, clean_html, callback):
        if not self.ready:
            self._queued_body = clean_html
            if callback:
                wx.CallAfter(callback, None, "")
            return
        self.call("setBody", clean_html, callback=callback)

    def get_body(self, callback):
        """callback(body_html or None, error)."""
        self.call("getBody", callback=callback)

    def insert_html(self, html, callback=None):
        """Sanitised insertion at the caret, through insertHTML so undo sees it."""
        clean, warnings = sanitise(html)
        self.call("insertHTML", clean, callback=callback)
        return warnings

    def set_page(self, page):
        self._page = dict(page or {})
        if self.ready:
            self.call("setPage", editor_page.page_css_for(self._page))

    def set_display(self, display, callback=None):
        """The screen settings: text size, page theme, caret, focus ring,
        bold body text and line spacing. All of them are the screen only.

        They are kept here as well as sent, so a page rebuilt after a
        reload starts with them rather than with the defaults.
        """
        self._display = editor_page.clean_display(display)
        if self.ready:
            self.call("setDisplay", self._display, callback=callback)
        elif callback is not None:
            wx.CallAfter(callback, None, "")
        return self._display

    def display(self):
        return dict(self._display)

    def set_zoom(self, percent, callback=None):
        """The text size in percent, applied and remembered here."""
        self._display = editor_page.clean_display(dict(self._display, zoom=percent))
        if self.ready:
            self.call("setZoom", self._display["zoom"], callback=callback)
        return self._display["zoom"]

    def set_lang(self, lang):
        self._lang = lang or "en"
        if self.ready:
            self.call("setLang", self._lang)

    def focus(self):
        self.web.SetFocus()
        if self.ready:
            self.call("focus")

    def scale(self):
        """CSS pixels to device pixels: the window's scale factor."""
        try:
            return float(self.GetDPIScaleFactor())
        except Exception:
            return 1.0
