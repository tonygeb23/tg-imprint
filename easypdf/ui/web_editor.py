"""
WebView-based accessible editor.

Why a WebView?
--------------
Win32 RICHEDIT exposes character-level MSAA only — it has no concept of
heading / list / link structure roles, so NVDA can never announce
"heading level 1" inside the editor.

A WebView2 (Edge/Chromium) hosting a `contenteditable` HTML document
exposes the full DOM via UI Automation.  NVDA reads `<h1>` as
"heading level 1", `<ul><li>` as "bulleted list, N items", `<a href>`
as "link", `<img alt>` as "graphic [alt]" — all without any custom
accessibility code on our side.

The same HTML feeds straight into WeasyPrint for the PDF/UA-1 export,
so the editor and the export now share a single source of truth.

API surface
-----------
WebEditor mirrors the public methods of `ui.editor.Editor` so that
MainWindow, FormattingToolbar, and the dialog code can use it
interchangeably.  The few RICHEDIT-specific bits (raw `ctrl` access for
Find/Replace) are gated in MainWindow via `isinstance(...)`.
"""
from __future__ import annotations

import json
import os
import re
from html import escape as _esc
from pathlib import Path
from typing import Callable

import wx
import wx.html2 as webview


# ---------------------------------------------------------------------------
# HTML / JS scaffold
# ---------------------------------------------------------------------------

# Stylesheet mirrors core/html_builder._CSS so on-screen rendering matches PDF.
_EDITOR_CSS = """
html, body { margin: 0; padding: 0; background: #d8d8d8; }
body { font-family: Calibri, "Segoe UI", Arial, sans-serif; }
#editor {
  background: #ffffff;
  color: #000000;
  margin: 24px auto;
  padding: 1in;
  max-width: 8.5in;
  min-height: 11in;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  font-size: 11pt;
  line-height: 1.5;
  outline: none;
}
#editor h1 { font-size: 26pt; font-weight: bold; margin: 18pt 0 6pt; }
#editor h2 { font-size: 20pt; font-weight: bold; margin: 14pt 0 4pt; }
#editor h3 { font-size: 16pt; font-weight: bold; margin: 12pt 0 4pt; }
#editor h4 { font-size: 14pt; font-weight: bold; margin: 10pt 0 4pt; }
#editor h5 { font-size: 13pt; font-weight: bold; font-style: italic; margin: 8pt 0 2pt; }
#editor h6 { font-size: 12pt; font-style: italic; margin: 8pt 0 2pt; }
#editor p  { margin: 0 0 8pt; }
#editor ul, #editor ol { margin: 4pt 0 8pt; padding-left: 2em; }
#editor li { margin-bottom: 4pt; }
#editor a  { color: #0000b4; text-decoration: underline; }
#editor blockquote {
  margin: 8pt 0 8pt 2em; padding: 0 0 0 1em;
  border-left: 3px solid #cccccc;
  font-style: italic; color: #444444;
}
#editor figure { margin: 8pt 0; text-align: center; }
#editor figure img { max-width: 100%; height: auto; }
#editor figcaption { font-size: 9pt; color: #555555; margin-top: 4pt; }
#editor code { font-family: "Courier New", Courier, monospace; }
"""

# JS shipped with the page.  Posts selection-state and modified events back to
# wx via window.wxBridge.postMessage (registered Python-side).
_EDITOR_JS = r"""
(function () {
  const ed = document.getElementById('editor');

  function post(obj) {
    try { window.wxBridge.postMessage(JSON.stringify(obj)); } catch (e) {}
  }

  function blockOf(node) {
    let n = node && node.nodeType === 1 ? node : (node && node.parentElement);
    while (n && n !== ed && !/^(H[1-6]|P|LI|BLOCKQUOTE|FIGURE|FIGCAPTION)$/.test(n.tagName)) {
      n = n.parentElement;
    }
    return n === ed ? null : n;
  }

  function styleName(block) {
    if (!block) return 'Normal';
    const t = block.tagName;
    if (/^H[1-6]$/.test(t)) return 'Heading ' + t[1];
    if (t === 'BLOCKQUOTE') return 'Block Quote';
    if (t === 'LI') {
      const list = block.closest('ol,ul');
      return list && list.tagName === 'OL' ? 'Numbered List' : 'Bullet List';
    }
    return 'Normal';
  }

  function alignOf(block) {
    if (!block) return 'left';
    const a = (getComputedStyle(block).textAlign || 'left').toLowerCase();
    if (a.startsWith('center')) return 'center';
    if (a.startsWith('right'))  return 'right';
    if (a.startsWith('justify'))return 'justify';
    return 'left';
  }

  function reportSelection() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const block = blockOf(sel.anchorNode);
    post({
      type: 'selstate',
      style: styleName(block),
      alignment: alignOf(block),
      bold:          document.queryCommandState('bold'),
      italic:        document.queryCommandState('italic'),
      underline:     document.queryCommandState('underline'),
      strikethrough: document.queryCommandState('strikethrough'),
    });
  }

  document.addEventListener('selectionchange', reportSelection);
  ed.addEventListener('input',  () => post({ type: 'modified' }));
  ed.addEventListener('focus',  reportSelection);

  // ---- Public API exposed for Python to RunScript() ---------------------
  window.editorAPI = {
    focus()         { ed.focus(); },
    getHTML()       { return ed.innerHTML; },
    setHTML(html)   { ed.innerHTML = html || '<p><br></p>'; },
    wordCount() {
      const t = ed.innerText.trim();
      return t ? t.split(/\s+/).length : 0;
    },
    exec(cmd, val)  { document.execCommand(cmd, false, val == null ? null : val); ed.focus(); reportSelection(); },
    setBlock(tag)   {
      // formatBlock requires angle brackets in some engines
      document.execCommand('formatBlock', false, '<' + tag + '>');
      ed.focus(); reportSelection();
    },
    insertList(ordered) {
      document.execCommand(ordered ? 'insertOrderedList' : 'insertUnorderedList');
      ed.focus(); reportSelection();
    },
    setAlignment(a) {
      const map = { left:'justifyLeft', center:'justifyCenter', right:'justifyRight', justify:'justifyFull' };
      document.execCommand(map[a] || 'justifyLeft');
      ed.focus(); reportSelection();
    },
    insertLink(text, url) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount) {
        const r = sel.getRangeAt(0);
        r.deleteContents();
        const a = document.createElement('a');
        a.href = url;
        a.textContent = text;
        r.insertNode(a);
        // Move caret after the link
        const after = document.createRange();
        after.setStartAfter(a); after.collapse(true);
        sel.removeAllRanges(); sel.addRange(after);
      }
      ed.focus(); reportSelection();
    },
    insertImage(src, alt) {
      const fig = document.createElement('figure');
      const img = document.createElement('img');
      img.src = src;
      img.alt = alt || '';
      if (!alt) img.setAttribute('role', 'presentation');
      fig.appendChild(img);
      if (alt) {
        const cap = document.createElement('figcaption');
        cap.textContent = alt;
        fig.appendChild(cap);
      }
      const sel = window.getSelection();
      if (sel && sel.rangeCount) {
        const r = sel.getRangeAt(0);
        r.deleteContents();
        r.insertNode(fig);
        const after = document.createRange();
        after.setStartAfter(fig); after.collapse(true);
        sel.removeAllRanges(); sel.addRange(after);
      } else {
        ed.appendChild(fig);
      }
      ed.focus(); reportSelection();
    },
    headings() {
      return JSON.stringify(
        [...ed.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h, i) => {
          if (!h.id) h.id = 'h_' + i;
          return { id: h.id, level: +h.tagName[1], text: h.textContent };
        })
      );
    },
    jumpToHeading(id) {
      const h = ed.querySelector('#' + CSS.escape(id));
      if (!h) return;
      const r = document.createRange();
      r.selectNodeContents(h); r.collapse(true);
      const sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      h.scrollIntoView({ block: 'center' });
      ed.focus();
    },
    findNext(text, matchCase) {
      // Uses native window.find() which is supported in Chromium-based WebView2
      return window.find(text, !!matchCase, false, true, false, true, false);
    },
    findPrev(text, matchCase) {
      return window.find(text, !!matchCase, true, true, false, true, false);
    },
    replaceSelection(replacement) {
      const sel = window.getSelection();
      if (!sel || !sel.rangeCount || sel.isCollapsed) return false;
      const r = sel.getRangeAt(0);
      r.deleteContents();
      r.insertNode(document.createTextNode(replacement));
      ed.focus();
      return true;
    },
    setLang(lang) { document.documentElement.lang = lang || 'en-US'; },
  };

  // Fire one report at startup so toolbar / status sync.
  setTimeout(reportSelection, 50);
  post({ type: 'ready' });
})();
"""


def _build_page(initial_html: str, lang: str = "en-US") -> str:
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{_esc(lang, quote=True)}">\n'
        "<head><meta charset=\"utf-8\">\n"
        f"<style>{_EDITOR_CSS}</style>\n"
        "</head>\n<body>\n"
        '<main id="editor" contenteditable="true" spellcheck="true" '
        'role="textbox" aria-multiline="true" aria-label="Document content">\n'
        f"{initial_html or '<p><br></p>'}\n"
        "</main>\n"
        f"<script>{_EDITOR_JS}</script>\n"
        "</body></html>\n"
    )


# ---------------------------------------------------------------------------
# WebEditor — wxPython panel
# ---------------------------------------------------------------------------

# Map paragraph-style names (used by Editor) to the HTML block tag we want.
_STYLE_TO_BLOCK = {
    "Heading 1":   "h1",
    "Heading 2":   "h2",
    "Heading 3":   "h3",
    "Heading 4":   "h4",
    "Heading 5":   "h5",
    "Heading 6":   "h6",
    "Normal":      "p",
    "Block Quote": "blockquote",
}


class WebEditor(wx.Panel):
    """
    Drop-in replacement for `ui.editor.Editor` that hosts a WebView2
    contenteditable surface.

    Same public API as Editor where it matters (toggle_*, apply_*, save,
    load, clear, word_count, get_links/get_images, heading helpers).
    `ctrl` is None — features that need the raw RICHEDIT must check.
    """

    # Sentinel so MainWindow can detect Find/Replace path differences
    ctrl = None

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        # Pick the best backend — Edge WebView2 on Windows 11 (preinstalled).
        backend = webview.WebViewBackendDefault
        if hasattr(webview, "WebViewBackendEdge") and webview.WebView.IsBackendAvailable(
            webview.WebViewBackendEdge
        ):
            backend = webview.WebViewBackendEdge

        self.web = webview.WebView.New(self, backend=backend)
        self.web.EnableContextMenu(False)
        self.web.EnableHistory(False)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.web, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Internal state
        self._modified            = False
        self._current_style       = "Normal"
        self._current_alignment   = "left"
        self._char_state          = {"bold": False, "italic": False,
                                     "underline": False, "strikethrough": False}
        self._lang                = "en-US"
        self._text_change_handler: Callable | None = None
        self._ready               = False
        self._pending_html: str | None = None
        self._headings_cache: list[dict] = []

        # JS → Python bridge.  RegisterHandler is the wxPython API for
        # the Edge backend message channel.
        try:
            self.web.AddScriptMessageHandler("wxBridge")
        except Exception:
            # Some wxPython builds expose this differently; fall back.
            pass
        self.web.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_js_message)
        self.web.Bind(webview.EVT_WEBVIEW_LOADED,                  self._on_loaded)

        self._load_blank()

    # ------------------------------------------------------------------
    # WebView lifecycle
    # ------------------------------------------------------------------

    def _load_blank(self) -> None:
        self._ready = False
        self.web.SetPage(_build_page("<p><br></p>", lang=self._lang), "about:blank")

    def _on_loaded(self, event: webview.WebViewEvent) -> None:
        self._ready = True
        if self._pending_html is not None:
            html, self._pending_html = self._pending_html, None
            self._js_call("setHTML", html)
        # Focus the editable region so NVDA enters forms mode immediately.
        self._js_call("focus")

    def _on_js_message(self, event: webview.WebViewEvent) -> None:
        try:
            data = json.loads(event.GetString())
        except Exception:
            return
        kind = data.get("type")
        if kind == "selstate":
            self._current_style     = data.get("style",     "Normal")
            self._current_alignment = data.get("alignment", "left")
            self._char_state = {
                "bold":          bool(data.get("bold")),
                "italic":        bool(data.get("italic")),
                "underline":     bool(data.get("underline")),
                "strikethrough": bool(data.get("strikethrough")),
            }
            wx.PostEvent(self, _StateEvent(self.GetId()))
        elif kind == "modified":
            self._modified = True
            if self._text_change_handler:
                # Synthesise the wx.EVT_TEXT MainWindow listens for.
                evt = wx.CommandEvent(wx.wxEVT_TEXT, self.GetId())
                evt.SetEventObject(self)
                self._text_change_handler(evt)

    # ------------------------------------------------------------------
    # JS helpers
    # ------------------------------------------------------------------

    def _js_call(self, fn: str, *args) -> tuple[bool, str]:
        """Call window.editorAPI.<fn>(...args).  Args are JSON-encoded."""
        payload = ", ".join(json.dumps(a) for a in args)
        return self.web.RunScript(f"window.editorAPI.{fn}({payload});")

    def _js_eval(self, expr: str) -> str:
        ok, result = self.web.RunScript(f"({expr});")
        return result if ok else ""

    # ------------------------------------------------------------------
    # Paragraph styles
    # ------------------------------------------------------------------

    def apply_paragraph_style(self, style_name: str) -> None:
        if style_name == "Bullet List":
            self._js_call("insertList", False)
        elif style_name == "Numbered List":
            self._js_call("insertList", True)
        elif style_name in _STYLE_TO_BLOCK:
            self._js_call("setBlock", _STYLE_TO_BLOCK[style_name])
        self._current_style = style_name

    def current_paragraph_style(self) -> str:
        return self._current_style

    # ------------------------------------------------------------------
    # Character formatting
    # ------------------------------------------------------------------

    def toggle_bold(self)          -> None: self._js_call("exec", "bold")
    def toggle_italic(self)        -> None: self._js_call("exec", "italic")
    def toggle_underline(self)     -> None: self._js_call("exec", "underline")
    def toggle_strikethrough(self) -> None: self._js_call("exec", "strikeThrough")

    # ------------------------------------------------------------------
    # Alignment
    # ------------------------------------------------------------------

    def apply_alignment(self, alignment: str) -> None:
        if alignment not in ("left", "center", "right", "justify"):
            alignment = "left"
        self._js_call("setAlignment", alignment)
        self._current_alignment = alignment

    def current_alignment(self) -> str:
        return self._current_alignment

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insert_link(self, display_text: str, url: str) -> None:
        if display_text and url:
            self._js_call("insertLink", display_text, url)

    def insert_image(self, path: str, alt_text: str) -> None:
        if not path or not os.path.isfile(path):
            return
        src = Path(os.path.abspath(path)).as_uri()
        self._js_call("insertImage", src, alt_text or "")

    # ------------------------------------------------------------------
    # File I/O — uses .html container with metadata in <meta> tags
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        body = self._get_body_html_sync()
        full = (
            "<!DOCTYPE html>\n"
            f'<html lang="{_esc(self._lang, quote=True)}">\n'
            '<head><meta charset="utf-8">\n'
            '<meta name="generator" content="Easy PDF">\n'
            "</head>\n<body>\n"
            f"{body}\n</body>\n</html>\n"
        )
        Path(path).write_text(full, encoding="utf-8")

    def load(self, path: str) -> None:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"<body[^>]*>(.*?)</body>", text, re.S | re.I)
        body = m.group(1) if m else text
        # Strip any wrapping main#editor that we added on save round-trip
        body = re.sub(r'^\s*<main\b[^>]*>(.*)</main>\s*$', r"\1", body, flags=re.S | re.I)
        if self._ready:
            self._js_call("setHTML", body)
        else:
            self._pending_html = body
        self._modified = False

    def clear(self) -> None:
        if self._ready:
            self._js_call("setHTML", "<p><br></p>")
        else:
            self._pending_html = "<p><br></p>"
        self._modified      = False
        self._current_style = "Normal"

    # ------------------------------------------------------------------
    # Inspection / export helpers
    # ------------------------------------------------------------------

    def get_html(self) -> str:
        return self._get_body_html_sync()

    def _get_body_html_sync(self) -> str:
        ok, result = self.web.RunScript("window.editorAPI.getHTML();")
        return result if ok else ""

    def word_count(self) -> int:
        ok, result = self.web.RunScript("String(window.editorAPI.wordCount());")
        if not ok:
            return 0
        try:
            return int(result)
        except (TypeError, ValueError):
            return 0

    def get_links(self) -> list[dict]:
        # Links are real <a> elements in the DOM — no companion list needed.
        # Returned for compatibility with rtc_parser-era callers.
        return []

    def get_images(self) -> list[dict]:
        return []

    # ------------------------------------------------------------------
    # Heading navigation
    # ------------------------------------------------------------------

    def heading_positions(self) -> list[tuple[int, str, str]]:
        """Return [(index, dom_id, "Heading N"), ...] for the structure panel."""
        ok, raw = self.web.RunScript("window.editorAPI.headings();")
        if not ok or not raw:
            return []
        try:
            entries = json.loads(raw)
        except Exception:
            return []
        self._headings_cache = entries
        return [
            (i, h["id"], f"Heading {h['level']}") for i, h in enumerate(entries)
        ]

    def heading_text(self, index: int) -> str:
        if 0 <= index < len(self._headings_cache):
            return self._headings_cache[index].get("text", "")
        return ""

    def go_to_heading(self, dom_id: str) -> None:
        self._js_call("jumpToHeading", dom_id)

    def go_to_next_heading(self) -> str | None:
        # Simpler approach: jump to the heading after the current selection.
        # Implemented Python-side using the cached list isn't reliable; for
        # now use a small JS one-liner that finds the next heading after
        # the caret.
        ok, _ = self.web.RunScript("""
            (function () {
              const sel = window.getSelection();
              if (!sel.rangeCount) return null;
              const cur = sel.getRangeAt(0).startContainer;
              const all = [...document.querySelectorAll('#editor h1,h2,h3,h4,h5,h6')];
              for (const h of all) {
                if (cur.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_FOLLOWING) {
                  if (!h.id) h.id = 'h_jump';
                  window.editorAPI.jumpToHeading(h.id);
                  return 'Heading ' + h.tagName[1];
                }
              }
              return null;
            })();
        """)
        return self._current_style if self._current_style.startswith("Heading") else None

    def go_to_prev_heading(self) -> str | None:
        self.web.RunScript("""
            (function () {
              const sel = window.getSelection();
              if (!sel.rangeCount) return null;
              const cur = sel.getRangeAt(0).startContainer;
              const all = [...document.querySelectorAll('#editor h1,h2,h3,h4,h5,h6')].reverse();
              for (const h of all) {
                if (cur.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_PRECEDING) {
                  if (!h.id) h.id = 'h_jump';
                  window.editorAPI.jumpToHeading(h.id);
                  return;
                }
              }
            })();
        """)
        return self._current_style if self._current_style.startswith("Heading") else None

    # ------------------------------------------------------------------
    # Find / Replace (used by FindReplaceDialog when editor is WebEditor)
    # ------------------------------------------------------------------

    def find_next(self, text: str, match_case: bool = False) -> bool:
        if not text:
            return False
        ok, result = self.web.RunScript(
            f"String(window.editorAPI.findNext({json.dumps(text)}, {str(match_case).lower()}));"
        )
        return ok and result.lower() == "true"

    def find_prev(self, text: str, match_case: bool = False) -> bool:
        if not text:
            return False
        ok, result = self.web.RunScript(
            f"String(window.editorAPI.findPrev({json.dumps(text)}, {str(match_case).lower()}));"
        )
        return ok and result.lower() == "true"

    def replace_selection(self, replacement: str) -> bool:
        ok, result = self.web.RunScript(
            f"String(window.editorAPI.replaceSelection({json.dumps(replacement)}));"
        )
        return ok and result.lower() == "true"

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def set_language(self, lang: str) -> None:
        self._lang = lang or "en-US"
        self._js_call("setLang", self._lang)

    @property
    def is_modified(self) -> bool:
        return self._modified

    def Bind(self, event, handler, source=None, **kwargs):
        if event == wx.EVT_TEXT:
            self._text_change_handler = handler
        else:
            super().Bind(event, handler, source=source, **kwargs)


# ---------------------------------------------------------------------------
# Lightweight wx event for selection-state changes (toolbar sync)
# ---------------------------------------------------------------------------

_wxEVT_WEBEDITOR_STATE = wx.NewEventType()
EVT_WEBEDITOR_STATE    = wx.PyEventBinder(_wxEVT_WEBEDITOR_STATE, 1)


class _StateEvent(wx.PyCommandEvent):
    def __init__(self, wid: int) -> None:
        super().__init__(_wxEVT_WEBEDITOR_STATE, wid)
