"""The TG Imprint window.

`create_frame(open_path=None)` is what main.py calls. The frame owns one
document, one WebView2 editor (web_editor.EditorView), the menus and the
toolbar generated from keymap.py, a status bar whose first field is wide
enough for a sentence, and the three speech channels CONVENTIONS.md asks
for. Everything slow (open, save, import, export, checking, the update
check) runs on a thread and comes back through wx.CallAfter.

The contract with main.py, from docs/briefs/worker-b.md:

- announce(text), announce_help(text), announce_answer(text): spoken as the
  speech level says; the status bar always.
- The update flow, copied from Drop Deck: a background check about four
  seconds after start, Help then Check for updates, the download dialog,
  then Velopack applies it and restarts the app. Every branch answers in a
  dialog.
- open_document(path): the unsaved changes prompt, then the load, scheduled
  with wx.CallAfter so the second launch's WM_COPYDATA returns at once.
- Crash recovery reads paths.PREVIOUS_RUN_CRASHED; the frame closes
  normally and never calls os._exit.

Worker A's modules (docfile, htmlclean, pdfexport, pdfcheck, pdfimport,
pdfengine) and Worker C's (describe_dialog) are imported lazily inside the
methods that use them, so this module loads and its tests run before they
exist; where one is missing the user gets a status line, not a crash.
"""
import base64
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from html import escape

import wx

from .. import appicon
from .. import constants as C
from .. import paths
from .. import speech
from .. import updatedialog
from .. import settings as settings_mod
from ..settings import Settings
from . import dialogs
from . import keymap
from . import toolbar as toolbar_mod
from .web_editor import EditorView, EVT_EDITOR_MESSAGE, sanitise

#: docs/STRINGS.md, Worker B. Every sentence the window shows or speaks.
S = {
    "first_run": ("Welcome to TG Imprint. Start typing. F1 lists the keys and "
                  "Ctrl+Shift+E makes the PDF."),
    "words": "%s words",
    "one_word": "1 word",
    "no_words": "No words yet",
    "untitled": "Untitled",
    "style_normal": "Normal text",
    "style_heading": "Heading %d",
    "style_bullet": "Bullet list item",
    "style_number": "Numbered list item",
    "style_quote": "Quote",
    "style_cell": "Table cell",
    "style_header_cell": "Table header cell",
    "style_picture": "Picture: %s",
    "style_picture_none": "Picture without a description",
    "style_picture_decorative": "Decorative picture",
    "in_link": ", in a link",
    "bold_on": "Bold on", "bold_off": "Bold off",
    "italic_on": "Italic on", "italic_off": "Italic off",
    "underline_on": "Underline on", "underline_off": "Underline off",
    "strike_on": "Strikethrough on", "strike_off": "Strikethrough off",
    "code_on": "Code on", "code_off": "Code off",
    "code_nothing": "Select the text to make into code first.",
    "list_on_bullets": "Bullet list", "list_on_numbers": "Numbered list",
    "list_off": "List removed",
    "quote_on": "Quote", "quote_off": "Quote removed",
    "align": {"left": "Aligned left", "center": "Centred", "right": "Aligned right",
              "justify": "Justified"},
    "indent": "List level increased", "outdent": "List level decreased",
    "next_cell": "Next cell", "previous_cell": "Previous cell", "row_added": "Row added",
    "zoom": "Text size %d percent",
    "display_applied": "Display settings applied.",
    "toolbar_labels_set": "Toolbar: %s.",
    "title_set": "Title set to %s.",
    "title_cleared": "Title cleared.",
    "heading_at": "Heading %d: %s",
    "no_more_headings": "No more headings",
    "no_headings_before": "No headings before this",
    "undo": "Undo", "redo": "Redo", "cut": "Cut", "copied": "Copied",
    "selected_all": "All selected",
    "pasted": "Pasted.",
    "pasted_with_notes": "Pasted. %s",
    "nothing_to_paste": "Nothing on the clipboard to paste.",
    "picture_pasted": "Picture pasted. It needs a description.",
    "new_document": "New document.",
    "opened": "Opened %s.",
    "opened_from": "Opened from %s. Save will write a TG Imprint document.",
    "opening": "Opening %s.",
    "open_failed": "Could not open %s. %s",
    "saved": "Saved %s.",
    "saving": "Saving %s.",
    "save_failed": "Could not save %s. %s",
    "web_page_saved": "Saved the web page %s.",
    "closed": "Document closed.",
    "modified_marker": "",
    "export_title_needed": "The PDF needs a title first.",
    "export_cancelled": "Export cancelled: a title is needed.",
    "exporting": "Making the PDF.",
    "export_start": "Making %s.",
    "export_done": "PDF written: %s",
    "export_failed": "The PDF could not be made. %s",
    "export_no_engine": ("No PDF engine was found. %s The document can still be saved "
                         "as a web page from the File menu."),
    "pdfua_claimed": "The PDF/UA identifier was written: every check passed.",
    "pdfua_not_claimed": ("The PDF was written without the PDF/UA claim. %s"),
    "export_module_missing": "The PDF export is not part of this build yet.",
    "check_module_missing": "The accessibility checker is not part of this build yet.",
    "import_module_missing": "Opening %s files is not part of this build yet.",
    "docfile_missing": ("The document module is not part of this build yet, so this "
                        "file was read without it."),
    "describer_missing": "The describer is not part of this build yet.",
    "printing": "Sending the PDF to the printer.",
    "printed": "The PDF was sent to the printer.",
    "print_fallback": ("No printer would take the PDF, so it has been opened instead. "
                       "Print it from there."),
    "checking": "Checking %s.",
    "check_done": "Checked %s.",
    "check_failed": "The PDF could not be checked. %s",
    "no_picture_here": "No picture at the caret. Ctrl+Shift+Alt+P lists every picture.",
    "no_object_here": "No picture or empty table at the caret.",
    "picture_updated": "Picture updated.",
    "picture_inserted": "Picture inserted.",
    "picture_removed": "Picture removed.",
    "table_removed": "Table removed.",
    "remove_picture_q": ("Remove this picture from the document?\n\nDescription: %s\n\n"
                         "Ctrl+Z puts it back."),
    "remove_table_q": "Remove this empty table from the document? Ctrl+Z puts it back.",
    "description_added": "Description added.",
    "link_inserted": "Link inserted.",
    "link_updated": "Link updated.",
    "table_inserted": "Table inserted, %d rows and %d columns. The caret is in the first cell.",
    "title_prompt": "Document title:",
    "properties_applied": "Document properties applied.",
    "pictures_need_alt": "%d picture%s need%s a description.",
    "pictures_offer": ("%d picture%s in this document ha%s no description. Open the "
                       "Pictures list now to add them?"),
    "no_pictures": "No pictures in the document.",
    "no_headings": "No headings in the document yet.",
    "heading_jump": "Heading %d: %s",
    "find_nothing": "Type something to find.",
    "found": "Found. %s",
    "not_found": "Not found.",
    "guide_missing": "The user guide is not published yet.",
    "guide_opening": "Opening the user guide in your browser.",
    "donate_opening": "Opening the donate page in your browser.",
    "checking_updates": "Checking for a new version.",
    "newest_version": "You have the newest version.",
    "update_skipped": "Update skipped. Help, check for updates when you are ready.",
    "downloading": "Downloading version %s.",
    "download_stopped": "The download was stopped. Nothing was changed.",
    "download_failed": "Download failed. %s",
    "updating": "Updating. %s will close and open again by itself.",
    "updated_to": "Updated to version %s.",
    "recovered": "Recovered %s. Save it somewhere safe.",
    "snapshots_deleted": "The recovered documents were deleted.",
    "autosaved": "Autosaved.",
    "about": ("%s %s\n%s\n\n%s\n\nPDF engine: %s\nUpdates: %s\n\nA TG Studios program. "
              "Questions and reports to %s. Tested with NVDA.\n\n%s"),
    "engine_none": "none found. Install Microsoft Edge or Google Chrome to make PDFs.",
    "engine_unknown": "not checked (the engine module is not part of this build yet).",
    "context_menu_no_page": "",
    "check_report_title": "Accessibility check",
    "forms_module_missing": "Filling in PDF forms is not part of this build yet.",
    "form_opening": "Opening %s.",
    "form_open_failed": "That PDF could not be opened as a form. %s",
    "export_report_title": "PDF written",
    "open_notes_title": "Notes from opening this file",
}

#: Window titles and file dialog titles, listed in docs/STRINGS.md with
#: everything else the window shows (defect 10 of the round 2 review).
TITLES = {
    "open": "Open a document",
    "save_as": "Save as",
    "save_as_web": "Save as web page",
    "export": "Export PDF",
    "check": "Check a PDF",
    "pictures_missing": "Pictures without descriptions",
    "remove_picture": "Remove picture",
    "remove_table": "Remove table",
    "could_not_open": "Could not open",
    "could_not_export": "The PDF could not be made",
    "form_open": "Choose a PDF form",
}

#: Above this many characters a pasted fragment is cleaned on a thread.
#: Measured 2026-09-09 with htmlclean.normalise on Word style paragraphs:
#: 3 KB took 2.4 milliseconds, 33 KB took 20, and 164 KB, about fifty pages,
#: took 99. Forty thousand characters is about 25 milliseconds, which is
#: under a blink, and everything larger goes off the UI thread.
PASTE_ON_THREAD_CHARS = 40000

UPDATE_CHECK_DELAY_MS = 4000
AUTOSAVE_MS = C.AUTOSAVE_SECONDS * 1000


def create_frame(open_path=None):
    """What main.py calls. Builds the window, shows nothing itself."""
    return MainFrame(open_path=open_path)


class MainFrame(wx.Frame):
    def __init__(self, open_path=None, settings=None):
        super().__init__(None, title=C.APP_NAME)
        self.settings = settings if settings is not None else Settings()
        if settings is None:
            self.settings_state = self.settings.load()
        else:
            self.settings_state = "given"
        self.speaker = speech.Speaker()
        self._hints_said = set()
        self.SetIcons(appicon.bundle())

        # The document.
        self.path = None                 # the .imprint path once saved
        self.source_path = None          # what was opened, native or not
        self.imported_from = ""          # "Word", "Markdown"... else ""
        self.meta = self._new_meta()
        self.modified = False
        self.snapshot_path = None
        self._snapshot_hash = None
        self.state = {}
        self.find_text = ""
        self.find_match_case = False
        self.find_dialog = None
        self.last_folder = self.settings.get("last_folder") or ""
        self._guide_available = None
        self._update_box = None
        self._restart_body = None
        self._closing = False
        self._pumping = False

        # Ids and menus from the one list.
        self._ids = {}
        self._action_of = {}
        for entry in keymap.ENTRIES:
            wid = wx.NewIdRef()
            self._ids[entry.action] = wid
            self._action_of[int(wid)] = entry.action
        self._recent_ids = [wx.NewIdRef() for _ in range(C.RECENT_FILES)]
        self._menu_items = {}
        self._build_menus()
        self.SetAcceleratorTable(wx.AcceleratorTable(self._build_accelerators()))
        self.Bind(wx.EVT_MENU, self._dispatch)
        self.Bind(wx.EVT_TOOL, self._dispatch)
        for wid in self._recent_ids:
            self.Bind(wx.EVT_MENU, self._on_recent, id=wid)
        self.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)
        # A native keymap entry is left out of the wx accelerator table, so
        # the Applications key and Shift+F10 reached nothing when focus was
        # on the toolbar (defect 14 of the round 2 review).
        self.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        self._toolbar_widths = {}
        self.toolbar = None
        self._rebuild_toolbar(self.toolbar_mode(), 0)
        self._fit_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda _e: self._fit_toolbar(), self._fit_timer)
        self.Bind(wx.EVT_SIZE, self._on_size)

        self.editor = EditorView(self, page=self._document_page(), lang=self.meta["lang"],
                                 display=self.settings.display())
        self.editor.Bind(EVT_EDITOR_MESSAGE, self._on_editor_message)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.editor, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.status = self.CreateStatusBar(4)
        self.status.SetStatusWidths([-6, -2, -1, -1])
        self._set_style_field({})
        self.status.SetStatusText(S["no_words"], 2)
        self.status.SetStatusText(self.meta["lang"], 3)

        self._restore_geometry()
        self.SetMinSize(self.FromDIP(wx.Size(640, 440)))
        self._fit_toolbar()
        self._sync_view_menu()
        self.toolbar.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self._update_title()
        self.Bind(wx.EVT_CLOSE, self._on_close)

        self._autosave = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_autosave_tick, self._autosave)
        self._autosave.Start(AUTOSAVE_MS)

        wx.CallLater(UPDATE_CHECK_DELAY_MS, self._check_updates_quietly)
        wx.CallAfter(self._after_show, open_path)

    # ----------------------------------------------------------- menus --
    def id_of(self, action):
        return self._ids[action]

    # --------------------------------------------------------- toolbar --
    def _on_size(self, event):
        event.Skip()
        timer = getattr(self, "_fit_timer", None)
        if timer is not None:
            timer.StartOnce(150)

    def toolbar_mode(self):
        """Icons, icons with labels, or labels. The person's choice, kept."""
        mode = self.settings.get("toolbar_labels_mode", settings_mod.DEFAULT_TOOLBAR_LABELS)
        return (mode if mode in settings_mod.TOOLBAR_LABEL_MODES
                else settings_mod.DEFAULT_TOOLBAR_LABELS)

    def _rebuild_toolbar(self, mode, squeeze):
        old = getattr(self, "toolbar", None)
        self.toolbar = toolbar_mod.EditorToolBar(self, self.id_of, mode=mode, squeeze=squeeze)
        self.SetToolBar(self.toolbar)
        if old is not None:
            old.Destroy()
        self._toolbar_widths[(mode, squeeze)] = self.toolbar.needed_width()
        self.toolbar.sync(getattr(self, "state", None) or {})
        self.Layout()

    def _fit_toolbar(self):
        """The chosen shape, squeezed only if the words will not fit.

        The old rule threw the labels away whenever the bar was wider than
        the window, so somebody who cannot make out a 20 pixel glyph could
        not keep the words at all (defect 6 of the round 2 review). Now the
        choice stands and the squeeze is what gives: the eight tools in
        toolbar.KEEP_LABEL keep their words and the rest fall back to their
        icon. The tooltip and the accessible name never change.
        """
        if not self or getattr(self, "toolbar", None) is None:
            return
        mode = self.toolbar_mode()
        width = self.GetClientSize().width
        if width <= 0:
            return
        squeeze = 0
        if mode == "icons_labels":
            full = self._toolbar_widths.get((mode, 0))
            if full is not None and full > width:
                squeeze = 1
        if (mode, squeeze) == (self.toolbar.mode, self.toolbar.squeeze):
            return
        self._rebuild_toolbar(mode, squeeze)
        if squeeze == 0 and self._toolbar_widths.get((mode, 0), 0) > width:
            wx.CallAfter(self._fit_toolbar)          # now it has been measured

    # --------------------------------------------------------- display --
    def display_settings(self):
        return self.settings.display()

    def apply_display(self, speak=""):
        """Put every screen setting where it belongs, at once.

        The editor page takes the text size, the theme, the caret, the focus
        ring, the bold body text and the line spacing; the window takes the
        toolbar labels. None of it reaches an exported PDF, which is always
        black text on a white page.
        """
        if not self:
            return
        self.editor.set_display(self.display_settings())
        self._fit_toolbar()
        self._sync_view_menu()
        if speak:
            self.announce(speak)

    def _set_toolbar_mode(self, mode):
        self.settings["toolbar_labels_mode"] = mode
        self.settings["toolbar_labels"] = mode != "icons"
        self.settings.save()
        self._fit_toolbar()
        self._sync_view_menu()
        index = settings_mod.TOOLBAR_LABEL_MODES.index(mode)
        self.announce(S["toolbar_labels_set"]
                      % settings_mod.TOOLBAR_LABEL_LABELS[index].lower())

    def on_toolbar_icons(self, _event=None):
        self._set_toolbar_mode("icons")

    def on_toolbar_icons_labels(self, _event=None):
        self._set_toolbar_mode("icons_labels")

    def on_toolbar_labels(self, _event=None):
        self._set_toolbar_mode("labels")

    def on_display_options(self, _event=None):
        """View, Display options: Preferences with the Display page open."""
        self.on_preferences(page="Display")

    def _sync_view_menu(self):
        """The toolbar radio items say which shape the bar is in."""
        mode = self.toolbar_mode()
        for action, name in (("toolbar_icons", "icons"),
                             ("toolbar_icons_labels", "icons_labels"),
                             ("toolbar_labels", "labels")):
            for item in self._menu_items.get(action, []):
                try:
                    item.Check(name == mode)
                except Exception:
                    pass

    def _build_menus(self):
        bar = wx.MenuBar()
        for title, items in keymap.MENUS:
            bar.Append(self._make_menu(items), title)
        self.SetMenuBar(bar)

    def _make_menu(self, items, remember=True, collect=False, into=None):
        """The menu, and when `collect` is set the (action, item) pairs in it."""
        menu = wx.Menu()
        made_here = [] if into is None else into
        for item in items:
            if item == "-":
                menu.AppendSeparator()
            elif item == "recent":
                self.recent_menu = wx.Menu()
                self._fill_recent()
                menu.AppendSubMenu(self.recent_menu, "&Recent documents")
            elif isinstance(item, tuple):
                menu.AppendSubMenu(self._make_menu(item[1], remember, into=made_here), item[0])
            else:
                entry = keymap.entry(item)
                kind = {"check": wx.ITEM_CHECK, "radio": wx.ITEM_RADIO}.get(entry.kind, wx.ITEM_NORMAL)
                made = menu.Append(self.id_of(item), keymap.menu_label(entry), entry.help, kind)
                made_here.append((item, made))
                if remember:
                    self._menu_items.setdefault(item, []).append(made)
        return (menu, made_here) if collect else menu

    def _check_items(self, made, state):
        """Set the check and radio items in a menu built without remembering."""
        block = state.get("block") or "p"
        if state.get("quote") and block == "p":
            block = "blockquote"
        style = {"p": "normal", "h1": "heading1", "h2": "heading2", "h3": "heading3",
                 "h4": "heading4", "h5": "heading5", "h6": "heading6", "ul": "bullets",
                 "ol": "numbers", "blockquote": "quote"}.get(block)
        align = "align_" + (state.get("align") or "left")
        for action, item in made:
            if not item.IsCheckable():
                continue
            if action in ("bold", "italic", "underline", "strike", "code"):
                item.Check(bool(state.get(action)))
            elif action == style or action == align:
                item.Check(True)

    def _fill_recent(self):
        for item in list(self.recent_menu.GetMenuItems()):
            self.recent_menu.Delete(item)
        recent = self.settings.recent_existing()
        if not recent:
            item = self.recent_menu.Append(wx.ID_ANY, "No recent documents")
            item.Enable(False)
            return
        for index, path in enumerate(recent[:C.RECENT_FILES]):
            label = "&%d %s" % (index + 1, os.path.basename(path).replace("&", "&&"))
            self.recent_menu.Append(self._recent_ids[index], label, path)

    def _on_menu_open(self, event):
        if event.GetMenu() is not None and event.GetMenu() is self.GetMenuBar().GetMenu(0):
            self._fill_recent()
        event.Skip()

    def _on_recent(self, event):
        index = self._recent_ids.index(event.GetId()) if event.GetId() in self._recent_ids else -1
        recent = self.settings.recent_existing()
        if 0 <= index < len(recent):
            self.open_document(recent[index])

    def _build_accelerators(self):
        """The wx table, used only when focus is outside the editor. Returned
        as a list so tests/test_menus.py can read it back."""
        return keymap.wx_accelerators(self.id_of)

    def handler_for(self, action):
        """The callable that performs `action`, or None."""
        fn = getattr(self, "on_" + action, None)
        if fn is not None:
            return fn
        entry = keymap.BY_ACTION.get(action)
        if entry is not None and entry.scope == "page":
            return lambda _event=None, a=action: self.editor.call("apply", a)
        return None

    def perform(self, action, event=None):
        handler = self.handler_for(action)
        if handler is not None:
            handler(event)

    def _dispatch(self, event):
        if getattr(self, "_pumping", False):
            return                      # a save prompt is pumping the loop
        action = self._action_of.get(event.GetId())
        if action:
            self.perform(action, event)
        else:
            event.Skip()

    # --------------------------------------------------------- speaking --
    #
    # Three channels, all of them writing the status bar's first field:
    #   announce()        what you cannot otherwise know: a failure, a refusal,
    #                     a value you asked for. Silent only at "none".
    #   announce_help()   a confirmation or a hint. Silent below "all".
    #   announce_answer() a direct answer to a key whose only job is to answer.
    #                     Always spoken.
    def speech_level(self):
        return self.settings.get("speech_level", C.DEFAULT_SPEECH_LEVEL)

    def announce(self, text):
        if self.speech_level() != C.SPEECH_NONE:
            self.speaker.say(text)
        self.note(text)

    def announce_help(self, text):
        if self.speech_level() == C.SPEECH_ALL:
            self.speaker.say(text)
        self.note(text)

    def announce_answer(self, text):
        self.speaker.say(text)
        self.note(text)

    def note(self, text):
        status = getattr(self, "status", None)
        if status is not None:
            status.SetStatusText(text, 0)

    def hint(self, key, text):
        """A hint speaks once per session; afterwards it only lands on the bar."""
        if key in self._hints_said:
            self.note(text)
            return
        self._hints_said.add(key)
        self.announce_help(text)

    # ---------------------------------------------------------- startup --
    def _after_show(self, open_path):
        if not self:
            return
        self.editor.focus()
        # Recovery first, so a double click on a document after a crash
        # still offers the snapshot; the document opens if nothing was
        # recovered.
        if paths.PREVIOUS_RUN_CRASHED:
            self._offer_recovery()
        elif restarted_after_update():
            # Velopack restarted the app after an update: the flush before
            # the restart may have left a snapshot of a modified document.
            self._offer_recovery()
        if open_path and not self.modified and not self.path:
            self._load_path(open_path)
        first_run = bool(appupdate_flag("FIRST_RUN")) or not self.settings.get("first_run_done")
        if first_run:
            self.settings["first_run_done"] = True
            self.settings.save()
            wx.CallLater(900, lambda: self.hint("first_run", S["first_run"]) if self else None)
        updated = restarted_after_update()
        if updated:
            wx.CallLater(700, lambda: self.announce_help(S["updated_to"] % updated) if self else None)
        threading.Thread(target=self._probe_guide, daemon=True, name="tgimprint-guide").start()

    def _probe_guide(self):
        """Is the user guide published? A HEAD request, off the UI thread."""
        try:
            request = urllib.request.Request(C.USER_GUIDE_URL, method="HEAD",
                                             headers={"User-Agent": "%s/%s" % (
                                                 C.APP_NAME.replace(" ", ""), C.APP_VERSION)})
            with urllib.request.urlopen(request, timeout=8) as response:
                available = 200 <= response.status < 300
        except Exception:
            available = False
        wx.CallAfter(self._guide_probed, available)

    def _guide_probed(self, available):
        if not self:
            return
        self._guide_available = available
        for item in self._menu_items.get("user_guide", []):
            item.Enable(bool(available))

    def _restore_geometry(self):
        saved = self.settings.get("window") or {}
        # Fit the display: 1100 by 780 DIP is taller than a 1080 pixel
        # screen at 150 percent, so the default is the smaller of that and
        # nine tenths of the display's working area.
        try:
            area = wx.Display(0).GetClientArea()
        except Exception:
            area = wx.Rect(0, 0, 1920, 1080)
        wanted = self.FromDIP(wx.Size(1100, 780))
        default = wx.Size(min(wanted.width, int(area.width * 0.92)),
                          min(wanted.height, int(area.height * 0.90)))
        try:
            width = min(int(saved.get("width", default.width)), area.width)
            height = min(int(saved.get("height", default.height)), area.height)
            self.SetSize(wx.Size(max(500, width), max(380, height)))
            if "x" in saved and "y" in saved:
                point = wx.Point(int(saved["x"]), int(saved["y"]))
                display = wx.Display.GetFromPoint(point)
                if display != wx.NOT_FOUND:
                    self.SetPosition(point)
                else:
                    self.CentreOnScreen()
            else:
                self.CentreOnScreen()
            if saved.get("maximised"):
                self.Maximize(True)
        except Exception:
            self.SetSize(default)
            self.CentreOnScreen()

    def _save_geometry(self):
        try:
            rect = self.GetRect()
            self.settings["window"] = {"x": rect.x, "y": rect.y, "width": rect.width,
                                       "height": rect.height, "maximised": self.IsMaximized()}
        except Exception:
            pass

    # ------------------------------------------------------- document --
    def _new_meta(self):
        return {"title": "", "author": self.settings.get("author", ""),
                "lang": self.settings.get("lang", "en-US"), "subject": "",
                "page_size": self.settings.get("page_size", C.DEFAULT_PAGE_SIZE),
                "margin_inches": self.settings.get("margin_inches", C.DEFAULT_MARGIN_INCHES),
                "font_family": self.settings.get("font_family", C.DEFAULT_FONT_FAMILY),
                "font_points": self.settings.get("font_points", C.DEFAULT_FONT_POINTS)}

    def _document_page(self):
        return {"page_size": self.meta.get("page_size"),
                "margin_inches": self.meta.get("margin_inches"),
                "font_family": self.meta.get("font_family"),
                "font_points": self.meta.get("font_points")}

    def document_name(self):
        if self.path:
            return os.path.basename(self.path)
        if self.source_path:
            return os.path.basename(self.source_path)
        return self.meta.get("title") or S["untitled"]

    def _update_title(self):
        self.SetTitle("%s - %s" % (self.document_name(), C.APP_NAME))

    def mark_modified(self):
        if not self.modified:
            self.modified = True

    def _apply_meta_to_page(self):
        self.editor.set_lang(self.meta.get("lang", "en-US"))
        self.editor.set_page(self._document_page())
        self.status.SetStatusText(self.meta.get("lang", "en-US"), 3)

    def _confirm_discard(self):
        """True when it is safe to replace the document."""
        if not self.modified:
            return True
        answer = dialogs.unsaved_changes(self, self.document_name())
        if answer == "cancel":
            return False
        if answer == "discard":
            return True
        return self._save_now_blocking()

    def _save_now_blocking(self):
        """Save, pumping the loop until the asynchronous save finishes.

        Used only from the unsaved changes prompt, where the caller has to
        know whether it may go on. Nothing here calls the synchronous
        RunScript; the loop is pumped until the callbacks have run.
        """
        outcome = {}
        path = self.path
        if not path:
            path = self._ask_save_path()
            if not path:
                return False
        # wx.Yield() runs every pending event, so while this pumps, the
        # autosave timer, a document handed over by a second launch and any
        # menu event could all run inside the save prompt. _pumping says so
        # and _on_autosave_tick, _open_with_prompt and _dispatch respect it
        # (defect 15 of the round 2 review).
        self._pumping = True
        try:
            self._save_to(path, native=True, done=lambda ok: outcome.setdefault("ok", ok))
            deadline = time.monotonic() + 60
            while "ok" not in outcome and time.monotonic() < deadline:
                wx.Yield()
                wx.MilliSleep(10)
        finally:
            self._pumping = False
        return bool(outcome.get("ok"))

    # -------------------------------------------------------- messages --
    def _on_editor_message(self, event):
        data = event.data or {}
        kind = data.get("type")
        if kind == "state":
            self.state = data
            self.toolbar.sync(data)
            self._sync_menus(data)
            self._set_style_field(data)
        elif kind == "modified":
            self.mark_modified()
        elif kind == "words":
            count = int(data.get("count") or 0)
            self.status.SetStatusText(
                S["no_words"] if count == 0 else S["one_word"] if count == 1
                else S["words"] % "{:,}".format(count), 2)
        elif kind == "did":
            self._on_did(data.get("action"), data.get("result") or {})
        elif kind == "key":
            action = data.get("action")
            if action == "delete_object":
                self._confirm_remove(data.get("object"), data.get("index"))
            elif action:
                self.perform(action)
        elif kind == "contextmenu":
            self._popup_context_menu(data.get("x", 0), data.get("y", 0))
        elif kind == "menu":
            self._open_menu_bar(data.get("key") or "")
        elif kind == "paste":
            self._on_paste_message(data)
        elif kind == "ready":
            pass

    def _sync_menus(self, state):
        for action in ("bold", "italic", "underline", "strike", "code"):
            for item in self._menu_items.get(action, []):
                item.Check(bool(state.get(action)))
        block = state.get("block") or "p"
        if state.get("quote") and block == "p":
            block = "blockquote"
        style = {"p": "normal", "h1": "heading1", "h2": "heading2", "h3": "heading3",
                 "h4": "heading4", "h5": "heading5", "h6": "heading6", "ul": "bullets",
                 "ol": "numbers", "blockquote": "quote"}.get(block)
        if style:
            for item in self._menu_items.get(style, []):
                item.Check(True)
        align = "align_" + {"left": "left", "center": "center", "right": "right",
                            "justify": "justify"}.get(state.get("align") or "left", "left")
        for item in self._menu_items.get(align, []):
            item.Check(True)

    def _set_style_field(self, state):
        block = state.get("block") or "p"
        figure = state.get("figure")
        if block == "figure" and figure:
            if figure.get("decorative"):
                text = S["style_picture_decorative"]
            elif (figure.get("alt") or "").strip():
                text = S["style_picture"] % figure["alt"].strip()
            else:
                text = S["style_picture_none"]
        elif block == "ul":
            text = S["style_bullet"]
        elif block == "ol":
            text = S["style_number"]
        elif block == "td":
            text = S["style_cell"]
        elif block == "th":
            text = S["style_header_cell"]
        elif block in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = S["style_heading"] % int(block[1])
        elif block == "blockquote" or state.get("quote"):
            text = S["style_quote"]
        else:
            text = S["style_normal"]
        if state.get("link"):
            text += S["in_link"]
        self.status.SetStatusText(text, 1)

    def _on_did(self, action, result):
        """A page side action finished; confirm it on the help channel."""
        on = bool(result.get("on"))
        if action in ("bold", "italic", "underline", "strike"):
            self.announce_help(S[action + ("_on" if on else "_off")])
        elif action == "code":
            if result.get("nothing"):
                self.announce(S["code_nothing"])
            else:
                self.announce_help(S["code_on" if on else "code_off"])
        elif action == "normal":
            self.announce_help(S["style_normal"])
        elif action and action.startswith("heading"):
            self.announce_help(S["style_heading"] % int(action[-1]))
        elif action in ("bullets", "numbers"):
            self.announce_help(S["list_on_" + action] if on else S["list_off"])
        elif action == "quote":
            self.announce_help(S["quote_on" if on else "quote_off"])
        elif action and action.startswith("align_"):
            self.announce_help(S["align"].get(result.get("align") or action[6:], ""))
        elif action in ("indent", "outdent"):
            if "moved" in result:
                if result.get("added"):
                    self.announce_help(S["row_added"])
                elif result.get("moved"):
                    self.announce_help(S["next_cell" if action == "indent" else "previous_cell"])
            else:
                self.announce_help(S[action])
        elif action in ("zoom_in", "zoom_out", "zoom_reset"):
            # The page has already changed the size; the setting follows it,
            # so Ctrl+equals is remembered for the next run rather than
            # lasting until the window closes.
            percent = int(result.get("percent") or settings_mod.DEFAULT_ZOOM)
            self.settings["editor_zoom"] = percent
            self.editor.set_zoom(percent)
            self.settings.save()
            self.announce(S["zoom"] % percent)
        elif action in ("next_heading", "previous_heading"):
            if result.get("found"):
                self.announce(S["heading_at"] % (int(result.get("level") or 0),
                                                 result.get("text") or ""))
            else:
                self.announce(S["no_more_headings" if action == "next_heading"
                                else "no_headings_before"])
        elif action in ("undo", "redo", "cut"):
            self.announce_help(S[action])
        elif action == "copy":
            self.announce_help(S["copied"])
        elif action == "select_all":
            self.announce_help(S["selected_all"])

    # ---------------------------------------------------- context menu --
    def _popup_context_menu(self, x, y):
        # remember=False keeps these throwaway items out of _menu_items, so
        # the check and radio items have to be set here from the state the
        # page last reported; without this the menu said Bold unchecked on
        # bold text (defect 13 of the round 2 review).
        menu, made = self._make_menu(keymap.CONTEXT_MENU, remember=False, collect=True)
        self._check_items(made, self.state or {})
        figure = (self.state or {}).get("figure")
        if figure:
            menu.AppendSeparator()
            menu.Append(self.id_of("picture_properties"),
                        keymap.menu_label(keymap.entry("picture_properties")))
            menu.Append(self.id_of("describe_picture"),
                        keymap.menu_label(keymap.entry("describe_picture")))
            menu.Append(self.id_of("delete_object"), "Re&move picture")
        scale = self.editor.scale()
        point = self.editor.web.ClientToScreen(wx.Point(int(x * scale), int(y * scale)))
        self.PopupMenu(menu, self.ScreenToClient(point))
        menu.Destroy()
        self.editor.focus()

    def on_context_menu(self, event=None):
        """The wx side of the Applications key and Shift+F10.

        Bound to EVT_CONTEXT_MENU on the frame and on the toolbar as well as
        being an action, because a native keymap entry is left out of the wx
        accelerator table, so with focus on the toolbar nothing answered the
        Applications key at all (defect 14 of the round 2 review).
        """
        point = None
        try:
            if event is not None and hasattr(event, "GetPosition"):
                point = event.GetPosition()
        except Exception:
            point = None
        menu, made = self._make_menu(keymap.CONTEXT_MENU, remember=False, collect=True)
        self._check_items(made, self.state or {})
        where = self.ScreenToClient(point) if point and point != wx.DefaultPosition \
            else wx.Point(20, 20)
        self.PopupMenu(menu, where)
        menu.Destroy()

    def _open_menu_bar(self, key):
        """Alt, F10 or Alt+letter from inside the editor.

        WebView2 keeps those from the frame (measured: Alt+F reached the
        page and no menu opened), so the page forwards them and this does
        what DefWindowProc would have done: WM_SYSCOMMAND with SC_KEYMENU
        and the mnemonic, which opens that menu, or the menu bar when the
        key is empty.
        """
        import ctypes
        WM_SYSCOMMAND, SC_KEYMENU = 0x0112, 0xF100
        try:
            ctypes.windll.user32.PostMessageW(int(self.GetHandle()), WM_SYSCOMMAND, SC_KEYMENU,
                                              ord(key[:1].lower()) if key else 0)
        except Exception:
            pass

    # ----------------------------------------------------------- paste --
    def _on_paste_message(self, data):
        if data.get("image"):
            self._insert_pasted_picture(data["image"])
            return
        html = data.get("html") or ""
        text = data.get("text") or ""
        if not html and not text:
            self.announce(S["nothing_to_paste"])
            return
        self._paste_content(html, text)

    def _paste_content(self, html, text):
        if not html and text:
            html = text_to_html(text)
        if len(html) > PASTE_ON_THREAD_CHARS:
            # Fifty pages of Word measured 99 milliseconds in the sanitiser,
            # which is a visible stall, so a paste that size is cleaned off
            # the UI thread and inserted in the callback (defect 16).
            def work():
                clean, warnings = sanitise(html)
                wx.CallAfter(self._pasted_clean, clean, warnings)

            threading.Thread(target=work, daemon=True, name="tgimprint-paste").start()
            return
        self._paste_done(self.editor.insert_html(html))

    def _pasted_clean(self, clean, warnings):
        if not self:
            return
        self.editor.call("insertHTML", clean)
        self._paste_done(warnings)

    def _paste_done(self, warnings):
        self.mark_modified()
        if warnings:
            self.announce(S["pasted_with_notes"] % warnings[0])
        else:
            self.announce_help(S["pasted"])

    def on_paste(self, _event=None):
        """Edit, Paste: wx's clipboard, HTML if there is any, then the same path."""
        html = text = ""
        picture = None
        try:
            if wx.TheClipboard.Open():
                try:
                    if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_HTML)):
                        data = wx.HTMLDataObject()
                        if wx.TheClipboard.GetData(data):
                            html = data.GetHTML()
                    if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_BITMAP)) and not html:
                        data = wx.BitmapDataObject()
                        if wx.TheClipboard.GetData(data):
                            picture = data.GetBitmap()
                    if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)):
                        data = wx.TextDataObject()
                        if wx.TheClipboard.GetData(data):
                            text = data.GetText()
                finally:
                    wx.TheClipboard.Close()
        except Exception:
            pass
        if picture is not None and picture.IsOk() and not html and not text:
            stream = wx.MemoryOutputStream()
            picture.ConvertToImage().SaveFile(stream, wx.BITMAP_TYPE_PNG)
            raw = bytes(stream.GetOutputStreamBuffer().GetBufferStart()[:stream.GetLength()]) \
                if hasattr(stream, "GetOutputStreamBuffer") else None
            if raw is None:
                buf = bytearray(stream.GetLength())
                stream.CopyTo(buf, len(buf))
                raw = bytes(buf)
            self._insert_pasted_picture("data:image/png;base64," + base64.b64encode(raw).decode("ascii"))
            return
        if html:
            html = clipboard_html_fragment(html)
        if not html and not text:
            self.announce(S["nothing_to_paste"])
            return
        self._paste_content(html, text)

    def _insert_pasted_picture(self, data_url):
        from .image_dialog import data_uri_bytes
        raw = data_uri_bytes(data_url)
        if not raw:
            self.announce(S["nothing_to_paste"])
            return
        src = data_url
        try:
            from .. import docfile
            got = docfile.embed_image(raw)
            src = got.data_uri
        except ImportError:
            pass
        except Exception as exc:
            self.announce(S["open_failed"] % ("the picture", exc))
            return
        spec = {"src": src, "alt": "", "decorative": False, "caption": "",
                "width": "half", "place": "centre", "altSource": ""}

        def inserted(value, _error):
            self.mark_modified()
            self.announce(S["picture_pasted"])
            index = (value or {}).get("index")
            if index is not None:
                wx.CallAfter(self._edit_figure, int(index), spec)

        self.editor.call("insertFigure", spec, callback=inserted)

    # --------------------------------------------------------- actions --
    def on_new(self, _event=None):
        if not self._confirm_discard():
            return
        self._discard_snapshot()
        self.path = None
        self.source_path = None
        self.imported_from = ""
        self.meta = self._new_meta()
        self.modified = False
        self._apply_meta_to_page()
        self.editor.load_clean_body("<p><br></p>")
        self._update_title()
        self.announce_help(S["new_document"])
        self.editor.focus()

    def on_close_document(self, _event=None):
        if not self._confirm_discard():
            return
        # Answered once. on_new would ask again while modified is still set.
        self.modified = False
        self.on_new()
        self.announce_help(S["closed"])

    def on_open(self, _event=None):
        if not self._confirm_discard():
            return
        with wx.FileDialog(self, TITLES["open"], defaultDir=self.last_folder or paths.documents_dir(),
                           wildcard=C.OPEN_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self._load_path(path)

    def open_document(self, path):
        """A second launch, or Recent. Returns at once; the work is deferred."""
        wx.CallAfter(self._open_with_prompt, path)

    def _open_with_prompt(self, path):
        if not self:
            return
        if getattr(self, "_pumping", False):
            wx.CallLater(200, self._open_with_prompt, path)
            return
        self.Raise()
        if not self._confirm_discard():
            return
        self._load_path(path)

    def _load_path(self, path):
        path = os.path.abspath(path)
        name = os.path.basename(path)
        kind = kind_of(path)
        self.last_folder = os.path.dirname(path)
        self.announce_help(S["opening"] % name)
        busy = None
        if kind == "pdf":
            busy = dialogs.BusyDialog(self, self, "Opening a PDF", S["opening"] % name)
            busy.Show()

        def work():
            try:
                body, meta, warnings = read_document(path, kind,
                                                     progress=(busy.step if busy else None))
                clean, more = sanitise(body)
                warnings = list(warnings) + list(more)
                wx.CallAfter(self._loaded, path, kind, clean, meta, warnings, busy)
            except Exception as exc:
                wx.CallAfter(self._load_failed, path, exc, busy)

        threading.Thread(target=work, daemon=True, name="tgimprint-open").start()

    def _load_failed(self, path, exc, busy):
        if busy:
            busy.finish()
        message = S["open_failed"] % (os.path.basename(path), exc)
        self.announce(message)
        dialogs.show_text(self, TITLES["could_not_open"], message)
        self.editor.focus()

    def _loaded(self, path, kind, clean, meta, warnings, busy):
        if busy:
            busy.finish()
        self._discard_snapshot()
        self.meta = self._new_meta()
        for key in ("title", "author", "lang", "subject", "page_size", "margin_inches"):
            value = (meta or {}).get(key)
            if value not in (None, ""):
                self.meta[key] = value
        source_kind = (meta or {}).get("source_kind") or ("" if kind == "native" else kind)
        if kind == "native":
            self.path = path
            self.source_path = path
            self.imported_from = ""
            self.modified = False
        else:
            self.path = None
            self.source_path = path
            self.imported_from = source_name(source_kind or kind)
            self.modified = True
        self.settings.remember(path)
        self.settings["last_folder"] = self.last_folder
        self.settings.save()
        self._apply_meta_to_page()
        self._update_title()
        self.editor.load_clean_body(clean, callback=lambda _v, _e: self.editor.focus())
        if self.imported_from:
            self.announce(S["opened_from"] % self.imported_from)
        else:
            self.announce_help(S["opened"] % os.path.basename(path))
        needing = count_pictures_needing_alt(clean)
        if warnings:
            dialogs.show_text(self, S["open_notes_title"], "\n".join(warnings), field_label="&Notes")
        if needing:
            plural = "" if needing == 1 else "s"
            self.announce(S["pictures_need_alt"] % (needing, plural, "s" if needing == 1 else ""))
            if dialogs.ask(self, TITLES["pictures_missing"],
                           S["pictures_offer"] % (needing, plural, "s" if needing == 1 else "ve"),
                           yes="&Open the Pictures list", no="&Not now"):
                self.on_pictures()
        self.editor.focus()

    # ------------------------------------------------------------ save --
    def _ask_save_path(self, web=False):
        default = self.path or self.source_path
        if default:
            name = os.path.splitext(os.path.basename(default))[0]
        else:
            name = safe_filename(self.meta.get("title") or S["untitled"])
        ext = ".html" if web else C.DOC_EXTENSION
        with wx.FileDialog(self, TITLES["save_as_web"] if web else TITLES["save_as"],
                           defaultDir=self.last_folder or paths.documents_dir(),
                           defaultFile=name + ext,
                           wildcard=C.WEB_PAGE_WILDCARD if web else C.DOC_WILDCARD,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            path = dialog.GetPath()
        if not path.lower().endswith(ext):
            path += ext
        self.last_folder = os.path.dirname(path)
        return path

    def on_save(self, _event=None):
        if self.path:
            self._save_to(self.path, native=True)
        else:
            self.on_save_as()

    def on_save_as(self, _event=None):
        path = self._ask_save_path()
        if path:
            self._save_to(path, native=True)

    def on_save_web_page(self, _event=None):
        path = self._ask_save_path(web=True)
        if path:
            self._save_to(path, native=False)

    def _save_to(self, path, native, done=None):
        name = os.path.basename(path)
        self.announce_help(S["saving"] % name)
        meta = dict(self.meta)

        def got(body, error):
            if error or body is None:
                message = S["save_failed"] % (name, error or "the document could not be read back")
                self.announce(message)
                if done:
                    done(False)
                return

            def work():
                try:
                    write_document(path, body, meta)
                    wx.CallAfter(self._saved, path, native, done)
                except Exception as exc:
                    wx.CallAfter(self._save_failed, path, exc, done)

            threading.Thread(target=work, daemon=True, name="tgimprint-save").start()

        self.editor.get_body(got)

    def _saved(self, path, native, done):
        name = os.path.basename(path)
        if native:
            self.path = path
            self.source_path = path
            self.imported_from = ""
            self.modified = False
            self._discard_snapshot()
            self._update_title()
            self.announce_help(S["saved"] % name)
        else:
            self.announce_help(S["web_page_saved"] % name)
        self.settings.remember(path)
        self.settings["last_folder"] = self.last_folder
        self.settings.save()
        if done:
            done(True)

    def _save_failed(self, path, exc, done):
        message = S["save_failed"] % (os.path.basename(path), exc)
        self.announce(message)
        dialogs.show_text(self, "Could not save", message)
        if done:
            done(False)

    # ---------------------------------------------------------- export --
    def _ensure_title(self, then):
        """The PDF needs a title; open the properties with focus in it."""
        if (self.meta.get("title") or "").strip():
            then()
            return
        self.announce(S["export_title_needed"])
        if self._edit_properties(focus="title") and (self.meta.get("title") or "").strip():
            then()
        else:
            self.announce(S["export_cancelled"])

    def on_export_pdf(self, _event=None):
        self._ensure_title(self._export_after_title)

    def _export_after_title(self):
        default = safe_filename(self.meta.get("title") or self.document_name()) + ".pdf"
        with wx.FileDialog(self, TITLES["export"], defaultDir=self.last_folder or paths.documents_dir(),
                           defaultFile=default, wildcard=C.PDF_WILDCARD,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            out = dialog.GetPath()
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        self.last_folder = os.path.dirname(out)
        self._export_to(out, self._export_finished)

    def _export_to(self, out, finished):
        try:
            from .. import pdfexport
        except ImportError:
            self.announce(S["export_module_missing"])
            return
        busy = dialogs.BusyDialog(self, self, "Making the PDF", S["export_start"] % os.path.basename(out))
        busy.Show()
        meta = dict(self.meta)

        def got(body, error):
            if error or body is None:
                busy.finish()
                self.announce(S["export_failed"] % (error or "the document could not be read back"))
                return

            def work():
                try:
                    result = pdfexport.export_html(body, out, meta, progress=busy.step)
                    # The export already checked the file it wrote and hands
                    # the Report back on the result, so checking again here
                    # ran every check twice (defect 9 of the round 2 review).
                    report = getattr(result, "report", None)
                    if report is None:
                        try:
                            from .. import pdfcheck
                            report = pdfcheck.check(out)
                        except ImportError:
                            report = S["check_module_missing"]
                        except Exception as exc:
                            report = S["check_failed"] % exc
                    wx.CallAfter(finished, out, result, report, None, busy)
                except Exception as exc:
                    wx.CallAfter(finished, out, None, "", exc, busy)

            threading.Thread(target=work, daemon=True, name="tgimprint-export").start()

        self.editor.get_body(got)

    def _export_finished(self, out, result, report, error, busy):
        busy.finish()
        if error is not None:
            name = type(error).__name__
            if name == "EngineError":
                message = S["export_no_engine"] % error
            else:
                message = S["export_failed"] % error
            self.announce(message)
            dialogs.show_text(self, TITLES["could_not_export"], message)
            self.editor.focus()
            return
        lines = []
        claimed = bool(getattr(result, "pdfua_claimed", False))
        warnings = list(getattr(result, "warnings", []) or [])
        if claimed:
            lines.append(S["pdfua_claimed"])
        else:
            # The name of the check that stopped the claim comes from the
            # checker's own report, not from hunting for the letters PDF/UA
            # in the warnings (defect 9 of the round 2 review).
            named = ""
            failed = []
            try:
                failed = list(report.failed_names() or [])
            except Exception:
                failed = []
            if failed:
                named = "The check that stopped it: %s." % ", ".join(failed)
            else:
                named = next((w for w in warnings if "PDF/UA" in w), "")
            lines.append(S["pdfua_not_claimed"] % (named or ""))
        pages = getattr(result, "pages", None)
        engine = getattr(result, "engine", "")
        lines.append("%s%s%s" % (out, (", %s pages" % pages) if pages else "",
                                 (", made with %s" % engine) if engine else ""))
        if warnings:
            lines.append("")
            lines.extend(warnings)
        lines.append("")
        try:
            lines.append(report.format_report())
        except AttributeError:
            lines.append(str(report or ""))
        text = "\n".join(lines)
        self.announce(S["export_done"] % os.path.basename(out))
        dialog = dialogs.TextDialog(self, S["export_report_title"], text,
                                    buttons=(("Open &PDF", "open"), ("Open &folder", "folder"),
                                             ("&Close", "close")),
                                    field_label="&Report", size=(640, 380), escape_result="close")
        try:
            dialog.ShowModal()
            choice = dialog.result
        finally:
            dialog.Destroy()
        if choice == "open":
            open_file(out)
        elif choice == "folder":
            open_folder(out)
        self.editor.focus()

    def on_print(self, _event=None):
        self._ensure_title(self._print_after_title)

    def _print_after_title(self):
        out = os.path.join(tempfile.mkdtemp(prefix="tgimprint-print-"),
                           safe_filename(self.meta.get("title") or "document") + ".pdf")
        self._export_to(out, self._print_finished)

    def _print_finished(self, out, result, report, error, busy):
        busy.finish()
        if error is not None:
            message = S["export_failed"] % error
            self.announce(message)
            dialogs.show_text(self, TITLES["could_not_export"], message)
            return
        self.announce_help(S["printing"])
        try:
            os.startfile(out, "print")
            self.announce(S["printed"])
        except Exception:
            open_file(out)
            self.announce(S["print_fallback"])

    def on_check_pdf(self, _event=None):
        try:
            from .. import pdfcheck
        except ImportError:
            self.announce(S["check_module_missing"])
            return
        with wx.FileDialog(self, TITLES["check"], defaultDir=self.last_folder or paths.documents_dir(),
                           wildcard=C.PDF_WILDCARD, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        name = os.path.basename(path)
        self.announce_help(S["checking"] % name)

        def work():
            try:
                text = pdfcheck.check(path).format_report()
                wx.CallAfter(self._checked, name, text, None)
            except Exception as exc:
                wx.CallAfter(self._checked, name, "", exc)

        threading.Thread(target=work, daemon=True, name="tgimprint-check").start()

    def _checked(self, name, text, error):
        if error is not None:
            message = S["check_failed"] % error
            self.announce(message)
            dialogs.show_text(self, S["check_report_title"], message)
            return
        self.announce(S["check_done"] % name)
        dialogs.show_text(self, "%s: %s" % (S["check_report_title"], name), text, field_label="&Report")
        self.editor.focus()

    # ------------------------------------------------------ properties --
    def on_properties(self, _event=None):
        if (self.state or {}).get("figure"):
            self.on_picture_properties()
        else:
            self._edit_properties()

    def _edit_properties(self, focus="title"):
        from .doc_properties_dialog import DocPropertiesDialog
        dialog = DocPropertiesDialog(self, self.meta, focus=focus)
        try:
            accepted = dialog.ShowModal() == wx.ID_OK and dialog.result is not None
            if accepted:
                self.meta.update(dialog.result)
                self.mark_modified()
                self._apply_meta_to_page()
                self._update_title()
                self.announce_help(S["properties_applied"])
        finally:
            dialog.Destroy()
        self.editor.focus()
        return accepted

    def on_rename(self, _event=None):
        if (self.state or {}).get("figure"):
            self.on_picture_properties()
            return
        with wx.TextEntryDialog(self, S["title_prompt"], "Document title",
                                self.meta.get("title") or "") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                self.editor.focus()
                return
            title = dialog.GetValue().strip()
        self.meta["title"] = title
        self.mark_modified()
        self._update_title()
        self.announce_help(S["title_set"] % title if title else S["title_cleared"])
        self.editor.focus()

    def on_preferences(self, _event=None, page=None):
        """Preferences. `page` names the tab to open on, "Display" from View.

        The Display page changes the screen while the dialog is open, so
        somebody who cannot read the current size can see the new one before
        committing. Cancel puts back what was there.
        """
        from .preferences_dialog import PreferencesDialog
        before = {key: self.settings.get(key) for key in settings_mod.DISPLAY_KEYS}
        dialog = PreferencesDialog(self, self, self.settings, page=page)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                self.settings.save()
                for key in ("font_family", "font_points"):
                    self.meta[key] = self.settings.get(key)
                self._apply_meta_to_page()
                self.apply_display()
            else:
                self.settings.update(before)
                self.apply_display()
        finally:
            dialog.Destroy()
        self.editor.focus()

    def on_fill_form(self, _event=None):
        """Tools, Fill in a PDF form (Ctrl+Shift+F). The whole flow is in
        forms_dialog, which imports Worker A's pdfforms lazily."""
        from . import forms_dialog
        forms_dialog.fill_in_a_pdf_form(self)
        self.editor.focus()

    # ---------------------------------------------------------- insert --
    def on_insert_link(self, _event=None):
        def got(value, _error):
            from .hyperlink_dialog import LinkDialog
            link = (value or {}).get("link")
            selected = (value or {}).get("selected") or ""
            dialog = LinkDialog(self, text=(link or {}).get("text") or selected,
                                href=(link or {}).get("href") or "", editing=bool(link))
            try:
                if dialog.ShowModal() == wx.ID_OK and dialog.result:
                    text, href = dialog.result
                    self.editor.call("insertLink", text, href)
                    self.mark_modified()
                    self.announce_help(S["link_updated" if link else "link_inserted"])
            finally:
                dialog.Destroy()
            self.editor.focus()

        self.editor.call("linkAtCaret", callback=got)

    def on_insert_picture(self, _event=None):
        from .image_dialog import PictureDialog
        dialog = PictureDialog(self, self, spec=None, imported=False)
        try:
            if dialog.ShowModal() == wx.ID_OK and dialog.result:
                spec = dialog.result
                self.editor.call("insertFigure", spec)
                self.mark_modified()
                self.announce_help(S["picture_inserted"])
        finally:
            dialog.Destroy()
        self.editor.focus()

    def on_insert_table(self, _event=None):
        from .table_dialog import TableDialog
        dialog = TableDialog(self)
        try:
            if dialog.ShowModal() == wx.ID_OK and dialog.result:
                rows, cols, header = dialog.result
                self.editor.call("insertTable", rows, cols, header)
                self.mark_modified()
                self.announce_help(S["table_inserted"] % (rows, cols))
        finally:
            dialog.Destroy()
        self.editor.focus()

    def on_picture_properties(self, _event=None):
        def got(value, _error):
            if not value:
                self.announce(S["no_picture_here"])
                return
            self._edit_figure(int(value["index"]), value)

        self.editor.call("figureAtCaret", callback=got)

    def _edit_figure(self, index, spec):
        from .image_dialog import PictureDialog
        dialog = PictureDialog(self, self, spec=spec, imported=bool(self.imported_from),
                               context=self._context_for(index, spec))
        try:
            if dialog.ShowModal() == wx.ID_OK and dialog.result:
                self.editor.call("updateFigure", index, dialog.result)
                self.mark_modified()
                self.announce_help(S["picture_updated"])
        finally:
            dialog.Destroy()
        self.editor.focus()

    def _context_for(self, index, spec=None):
        """What the describer is told about where the picture sits.

        The document title alone is not context (defect 18 of the round 2
        review). The caption, the heading above the picture and the text of
        the block in front of it are what make a description specific; the
        page reports all three with the figure.
        """
        spec = spec or {}
        parts = []
        title = (self.meta.get("title") or "").strip()
        if title:
            parts.append("Document title: %s" % title)
        heading = (spec.get("heading") or "").strip()
        if heading:
            parts.append("Under the heading: %s" % heading)
        caption = (spec.get("caption") or "").strip()
        if caption:
            parts.append("Caption: %s" % caption)
        before = (spec.get("before") or "").strip()
        if before:
            parts.append("The text before the picture: %s" % before)
        return "\n".join(parts)

    def _confirm_remove(self, kind, index):
        if kind == "figure":
            figure = (self.state or {}).get("figure") or {}
            question = S["remove_picture_q"] % (figure.get("alt") or "none")
            title = TITLES["remove_picture"]
        elif kind == "table":
            question = S["remove_table_q"]
            title = TITLES["remove_table"]
        else:
            self.announce(S["no_object_here"])
            return
        if dialogs.ask(self, title, question, yes="&Remove", no="&Keep it"):
            self.editor.call("removeObject", kind, int(index))
            self.mark_modified()
            self.announce_help(S["picture_removed" if kind == "figure" else "table_removed"])
        self.editor.focus()

    def on_delete_object(self, _event=None):
        """The menu item: the page decides what is at the caret."""
        def got(value, _error):
            if value:
                self._confirm_remove("figure", int(value["index"]))
                return

            def table(t, _e):
                if t:
                    self._confirm_remove("table", int(t["index"]))
                else:
                    self.announce(S["no_object_here"])

            self.editor.call("tableAtCaret", callback=table)

        self.editor.call("figureAtCaret", callback=got)

    # -------------------------------------------------------- describe --
    def on_describe_picture(self, _event=None):
        def got(value, _error):
            if not value:
                self.announce(S["no_picture_here"])
                return
            self._describe_figure(int(value["index"]), value)

        self.editor.call("figureAtCaret", callback=got)

    def _describe_figure(self, index, spec, after=None):
        try:
            from .describe_dialog import DescribeImageDialog
        except ImportError:
            self.announce(S["describer_missing"])
            return
        from .image_dialog import data_uri_bytes
        raw = data_uri_bytes(spec.get("src", ""))
        dialog = DescribeImageDialog(self, raw, current_alt=spec.get("alt", ""),
                                     context=self._context_for(index, spec),
                                     imported=bool(self.imported_from),
                                     provider=self.settings.get("ai_provider") or "",
                                     model=self.settings.get("ai_model") or "")
        try:
            dialog.ShowModal()
            text = getattr(dialog, "result", None)
            provider = getattr(dialog, "provider_used", "") or ""
        finally:
            dialog.Destroy()
        if text:
            new = dict(spec)
            new.update({"alt": text.strip(), "decorative": False,
                        "altSource": "ai:%s" % provider if provider else "ai"})
            self.editor.call("updateFigure", index, new)
            self.mark_modified()
            self.announce_help(S["description_added"])
        if after:
            after()
        else:
            self.editor.focus()

    def on_describe_document(self, _event=None):
        try:
            from .describe_dialog import DescribeDocumentDialog
        except ImportError:
            self.announce(S["describer_missing"])
            return
        from .image_dialog import data_uri_bytes

        def got_body(body, error):
            if error or body is None:
                self.announce(S["export_failed"] % (error or ""))
                return

            def got_pictures(pictures, _e):
                images = [data_uri_bytes(p.get("src", "")) for p in (pictures or [])]
                dialog = DescribeDocumentDialog(
                    self, body, [i for i in images if i],
                    provider=self.settings.get("ai_provider") or "",
                    model=self.settings.get("ai_model") or "",
                    document_name=os.path.basename(self.path) if self.path else "")
                try:
                    dialog.ShowModal()
                finally:
                    dialog.Destroy()
                self.editor.focus()

            self.editor.call("pictures", callback=got_pictures)

        self.editor.get_body(got_body)

    # ------------------------------------------------------------ view --
    def on_structure(self, _event=None):
        def got(headings, _error):
            from .structure_dialog import StructureDialog
            headings = headings or []
            if not headings:
                self.announce(S["no_headings"])
            dialog = StructureDialog(self, self, headings)
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    index = dialog.result
                    self.editor.call("goToHeading", index, callback=lambda v, _e: (
                        self.announce(S["heading_jump"] % (int(v.get("level") or 0), v.get("text") or ""))
                        if v and v.get("ok") else None))
            finally:
                dialog.Destroy()
            self.editor.focus()

        self.editor.call("headings", callback=got)

    def on_pictures(self, _event=None):
        def got(pictures, _error):
            from .pictures_dialog import PicturesDialog
            pictures = pictures or []
            if not pictures:
                self.announce(S["no_pictures"])
            dialog = PicturesDialog(self, self, pictures)
            try:
                if dialog.ShowModal() != wx.ID_OK or not dialog.result:
                    self.editor.focus()
                    return
                what, index = dialog.result
            finally:
                dialog.Destroy()
            spec = pictures[index]
            if what == "go":
                self.editor.call("goToPicture", index)
                self.editor.focus()
            elif what == "edit":
                self._edit_figure(index, spec)
                wx.CallAfter(self.on_pictures)
            elif what == "describe":
                self._describe_figure(index, spec, after=lambda: wx.CallAfter(self.on_pictures))

        self.editor.call("pictures", callback=got)

    # ------------------------------------------------------------ find --
    def _ensure_find_dialog(self):
        if self.find_dialog is None or not self.find_dialog:
            from .find_dialog import FindDialog
            self.find_dialog = FindDialog(self, self)
        return self.find_dialog

    def on_find(self, _event=None):
        self._ensure_find_dialog().open(replacing=False)

    def on_replace(self, _event=None):
        self._ensure_find_dialog().open(replacing=True)

    def find_in_document(self, text, forward, match_case, done=None):
        def got(value, error):
            result = value or {"found": False}
            if done:
                done(result)
            else:
                if result.get("found"):
                    self.announce(S["found"] % (result.get("context") or ""))
                else:
                    self.announce(S["not_found"])

        self.editor.call("find", text, bool(forward), bool(match_case), callback=got)

    def on_find_next(self, _event=None):
        if not self.find_text:
            self.on_find()
            return
        self.find_in_document(self.find_text, True, self.find_match_case)

    def on_find_previous(self, _event=None):
        if not self.find_text:
            self.on_find()
            return
        self.find_in_document(self.find_text, False, self.find_match_case)

    # ------------------------------------------------------------ help --
    def on_keyboard_help(self, _event=None):
        dialog = dialogs.KeyboardHelpDialog(self, keymap.render_text())
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        self.editor.focus()

    def on_user_guide(self, _event=None):
        if self._guide_available:
            self.announce_help(S["guide_opening"])
            webbrowser.open(C.USER_GUIDE_URL)
        else:
            self.announce(S["guide_missing"])

    def on_donate(self, _event=None):
        self.announce_help(S["donate_opening"])
        webbrowser.open(C.DONATE_URL)

    def on_about(self, _event=None):
        engine = S["engine_unknown"]
        try:
            from .. import pdfengine
            found = pdfengine.engines()
            engine = (", ".join("%s %s" % (e.name, e.version) for e in found)
                      if found else S["engine_none"])
        except ImportError:
            pass
        except Exception as exc:
            engine = "could not be checked: %s" % exc
        try:
            from .. import appupdate
            channel = appupdate.channel_state()
        except Exception as exc:
            channel = "could not be checked: %s" % exc
        text = S["about"] % (C.APP_NAME, C.APP_VERSION, C.TAGLINE, C.VENDOR, engine, channel,
                             C.FEEDBACK_EMAIL, C.HOME_URL)
        dialogs.show_text(self, "About %s" % C.APP_NAME, text, field_label="&About")
        self.editor.focus()

    def on_exit(self, _event=None):
        self.Close()

    # --------------------------------------------------------- updates --
    def _check_updates_quietly(self):
        """Silent unless something is there. On a worker thread."""
        if not self:
            return

        def work():
            from .. import appupdate
            try:
                available, info, _message = appupdate.auto_check(paths.config_dir())
            except Exception:
                return
            if available and info:
                wx.CallAfter(self._offer_update, info)

        threading.Thread(target=work, daemon=True, name="tgimprint-update").start()

    def on_check_updates(self, _event=None):
        self.announce_help(S["checking_updates"])

        def work():
            from .. import appupdate
            try:
                available, info, message = appupdate.auto_check(paths.config_dir(), force=True)
            except Exception as exc:
                available, info, message = False, None, "Could not check. %s" % exc
            wx.CallAfter(self._update_check_done, available, info, message)

        threading.Thread(target=work, daemon=True, name="tgimprint-update").start()

    def _update_check_done(self, available, info, message):
        if not self:
            return
        if available and info:
            self._offer_update(info)
            return
        problem = ""
        # Not a substring of a sentence: the up to date sentence is the one
        # in S, and anything else is a real problem (defect 11 of the round 2
        # review). appupdate should hand back a status of its own; noted for
        # the coordinator.
        if message and message.strip() != S["newest_version"]:
            problem = message
        self.announce_help(message or S["newest_version"])
        updatedialog.ask_about_update(self, C.APP_NAME, C.APP_VERSION, problem=problem)
        self.editor.focus()

    def _offer_update(self, info):
        from .. import appupdate
        version = info.get("version", "a new version")
        notes = (info.get("notes") or "").strip()
        choice = updatedialog.ask_about_update(self, C.APP_NAME, C.APP_VERSION,
                                               new_version=version, notes=notes)
        if choice != updatedialog.UPDATE:
            self.announce_help(S["update_skipped"])
            self.editor.focus()
            return
        self.announce_help(S["downloading"] % info.get("version", "the update"))
        box = updatedialog.DownloadProgressDialog(
            self, self, "version %s" % info.get("version", "the update"))
        box.Show()
        self._update_box = box

        def work():
            try:
                got = appupdate.download(info, progress=_step)
            except appupdate.Stopped:
                got = (None, S["download_stopped"])
            except Exception as exc:
                got = (None, S["download_failed"] % exc)
            wx.CallAfter(self._download_done, got[0], got[1])

        def _step(done, total):
            if box.cancelled:
                raise appupdate.Stopped()
            box.step(done, total)

        threading.Thread(target=work, daemon=True, name="tgimprint-dl").start()

    def _download_done(self, token, message):
        """Velopack has the package. Apply it and restart, after the flush.

        A portable Velopack copy updates exactly like an installed one, so
        nothing branches here (Tony, 2026-09-09; appupdate.py). The body is
        fetched first, asynchronously, so the flush that runs just before
        the process ends has it to hand and needs no pumping of the loop.
        """
        box = self._update_box
        if box is not None:
            try:
                box.Destroy()
            except Exception:
                pass
            self._update_box = None
        if not token:
            self.announce(message)
            dialogs.show_text(self, "Update failed", message)
            self.editor.focus()
            return
        self._restart_body = None
        if not self.modified:
            self._install_update(token)
            return

        def got(body, _error):
            self._restart_body = body
            self._install_update(token)

        self.editor.get_body(got)

    def _install_update(self, token):
        from .. import appupdate
        self.announce(S["updating"] % C.APP_NAME)
        ok, message = appupdate.run_installer(token, before_restart=self._flush_for_restart)
        # On success the process ends inside run_installer and nothing
        # below runs; a return means Velopack could not start the update.
        if not ok:
            self._closing = False
            self._autosave.Start(AUTOSAVE_MS)
            self.announce(message)
            dialogs.show_text(self, "Update failed", message)
            self.editor.focus()

    def _flush_for_restart(self):
        """What must be on disk before Velopack ends this process.

        Settings, recent files and the window geometry; and, when the
        document is modified, an autosave snapshot from the body fetched in
        _download_done, so the restarted app can offer it back. The clean
        exit marker is the client's own business (it clears it), so a
        normal restart does not nag; the snapshot is offered after an
        update restart by _after_show reading RESTARTED_AFTER_UPDATE.
        """
        self._closing = True
        try:
            self._autosave.Stop()
        except Exception:
            pass
        self._save_geometry()
        self.settings["last_folder"] = self.last_folder
        self.settings.save()
        body = getattr(self, "_restart_body", None)
        if self.modified and body:
            source = self.path or self.source_path or ""
            try:
                from .. import docfile
                docfile.snapshot(body, dict(self.meta), source)
            except ImportError:
                fallback_snapshot(body, dict(self.meta), source)
            except Exception:
                pass

    # ------------------------------------------------- autosave, crash --
    def _on_autosave_tick(self, _event):
        if not self.modified or self._closing or getattr(self, "_pumping", False):
            return
        self.editor.get_body(self._snapshot_body)

    def _snapshot_body(self, body, error):
        if error or body is None or self._closing:
            return
        digest = hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()
        if digest == self._snapshot_hash:
            return
        self._snapshot_hash = digest
        meta = dict(self.meta)
        source = self.path or self.source_path or ""

        def work():
            try:
                from .. import docfile
                where = docfile.snapshot(body, meta, source)
            except ImportError:
                where = fallback_snapshot(body, meta, source)
            except Exception:
                return
            wx.CallAfter(self._snapshot_written, where)

        threading.Thread(target=work, daemon=True, name="tgimprint-autosave").start()

    def _snapshot_written(self, where):
        if not self:
            return
        self.snapshot_path = where
        self.note(S["autosaved"])

    def _discard_snapshot(self):
        where, self.snapshot_path = self.snapshot_path, None
        self._snapshot_hash = None
        if not where:
            return
        try:
            from .. import docfile
            docfile.discard_snapshot(where)
        except ImportError:
            try:
                os.remove(where)
            except OSError:
                pass
        except Exception:
            pass

    def _recoverable(self):
        try:
            from .. import docfile
            return list(docfile.recoverable() or [])
        except ImportError:
            return fallback_recoverable()
        except Exception:
            return []

    def _offer_recovery(self):
        entries = self._recoverable()
        if not entries:
            return
        dialog = dialogs.RecoveryDialog(self, entries)
        try:
            dialog.ShowModal()
            choice = dialog.result
        finally:
            dialog.Destroy()
        if choice == "recover":
            snapshot, source, _when, title = entries[0]
            self._recover(snapshot, source, title)
        elif choice == "delete":
            for snapshot, _s, _w, _t in entries:
                try:
                    from .. import docfile
                    docfile.discard_snapshot(snapshot)
                except Exception:
                    try:
                        os.remove(snapshot)
                    except OSError:
                        pass
            self.announce(S["snapshots_deleted"])
        self.editor.focus()

    def _recover(self, snapshot, source, title):
        """Read the snapshot on a thread, like every other open.

        It used to read and sanitise on the UI thread, which froze the window
        during the one moment somebody most wants an answer (defect 7 of the
        round 2 review).
        """
        self.announce_help(S["opening"] % (title or os.path.basename(snapshot)))

        def work():
            try:
                body, meta, warnings = read_document(snapshot, "native")
                clean, more = sanitise(body)
                wx.CallAfter(self._recovered, snapshot, source, title, clean, meta,
                             list(warnings or []) + list(more or []))
            except Exception as exc:
                wx.CallAfter(self._recover_failed, title, exc)

        threading.Thread(target=work, daemon=True, name="tgimprint-recover").start()

    def _recover_failed(self, title, exc):
        if not self:
            return
        self.announce(S["open_failed"] % (title or "the recovered document", exc))
        self.editor.focus()

    def _recovered(self, snapshot, source, title, clean, meta, warnings):
        if not self:
            return
        self.meta = self._new_meta()
        for key in ("title", "author", "lang", "subject", "page_size", "margin_inches"):
            if (meta or {}).get(key) not in (None, ""):
                self.meta[key] = meta[key]
        if source and source.lower().endswith(C.DOC_EXTENSION):
            self.path = source
            self.source_path = source
        else:
            self.path = None
            self.source_path = source or None
        self.imported_from = ""
        self.modified = True
        self.snapshot_path = snapshot
        self._apply_meta_to_page()
        self._update_title()
        self.editor.load_clean_body(clean)
        self.announce(S["recovered"] % (title or self.document_name()))
        if warnings:
            dialogs.show_text(self, S["open_notes_title"], "\n".join(warnings),
                              field_label="&Notes")

    # ----------------------------------------------------------- close --
    def _on_close(self, event):
        asked = False
        if event.CanVeto():
            if not self._confirm_discard():
                event.Veto()
                return
            asked = True
        self._closing = True
        try:
            self._autosave.Stop()
        except Exception:
            pass
        # A forced close, Windows ending the session among them, cannot be
        # vetoed and asks nothing, so the snapshot is the only copy of the
        # unsaved work: it stays (defect 8 of the round 2 review).
        if asked or not self.modified:
            self._discard_snapshot()
        self._save_geometry()
        self.settings["last_folder"] = self.last_folder
        self.settings.save()
        if self.find_dialog is not None and self.find_dialog:
            try:
                self.find_dialog.Destroy()
            except Exception:
                pass
        # The frame owns the WebView: never Destroy it here (CLAUDE.md).
        event.Skip()


# ------------------------------------------------------------ helpers --

def appupdate_flag(name):
    """appupdate.RESTARTED_AFTER_UPDATE or FIRST_RUN, without the import
    being able to stop the window from opening."""
    try:
        from .. import appupdate
        return getattr(appupdate, name, None)
    except Exception:
        return None


def restarted_after_update():
    """The version string when Velopack restarted the app after an update,
    else an empty string."""
    return str(appupdate_flag("RESTARTED_AFTER_UPDATE") or "")


def kind_of(path):
    """docfile.kind_of, or the extension until Worker A's module exists."""
    try:
        from .. import docfile
        return docfile.kind_of(path)
    except ImportError:
        ext = os.path.splitext(path)[1].lower()
        return {".imprint": "native", ".html": "html", ".htm": "html", ".txt": "text",
                ".md": "markdown", ".markdown": "markdown", ".docx": "docx",
                ".pdf": "pdf"}.get(ext, "html")


def source_name(kind):
    return {"html": "a web page", "text": "a text file", "markdown": "Markdown",
            "docx": "Word", "pdf": "a PDF", "rtf": "Rich Text"}.get(kind, kind or "another format")


def read_document(path, kind, progress=None):
    """(body_html, meta, warnings), through docfile and pdfimport when present."""
    if kind == "pdf":
        try:
            from .. import pdfimport
        except ImportError:
            raise RuntimeError(S["import_module_missing"] % "PDF")
        result = pdfimport.import_pdf(path, progress=progress) if progress else pdfimport.import_pdf(path)
        meta = dict(getattr(result, "meta", {}) or {})
        meta.setdefault("source_kind", "pdf")
        warnings = list(getattr(result, "warnings", []) or [])
        if getattr(result, "is_scanned", False) and not warnings:
            warnings.append("This PDF has no text layer: it is pictures of text, and "
                            "there is no OCR in this release.")
        return getattr(result, "body_html", ""), meta, warnings
    try:
        from .. import docfile
    except ImportError:
        docfile = None
    if docfile is not None:
        got = docfile.load(path)
        body, meta = got[0], got[1]
        warnings = list(got[2]) if len(got) > 2 else []
        return body, dict(meta or {}), warnings
    # Fallbacks until docfile exists: native and html by regex, text by lines.
    if kind in ("native", "html"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        match = re.search(r"<body[^>]*>(.*?)</body>", text, re.S | re.I)
        body = match.group(1) if match else text
        title = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
        meta = {"title": (title.group(1).strip() if title else "")}
        return body, meta, [S["docfile_missing"]]
    if kind == "text":
        with open(path, encoding="utf-8", errors="replace") as fh:
            return text_to_html(fh.read()), {"source_kind": "text"}, [S["docfile_missing"]]
    raise RuntimeError(S["import_module_missing"] % source_name(kind))


def write_document(path, body, meta):
    """docfile.save, or a plain self-contained HTML file until it exists."""
    try:
        from .. import docfile
        docfile.save(path, body, meta)
        return
    except ImportError:
        pass
    head = ("<!DOCTYPE html>\n<html lang=\"%s\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>%s</title>\n<meta name=\"author\" content=\"%s\">\n"
            "<meta name=\"description\" content=\"%s\">\n"
            "<meta name=\"generator\" content=\"%s %s\">\n</head>\n<body>\n"
            % (escape(meta.get("lang", "en")), escape(meta.get("title", "")),
               escape(meta.get("author", "")), escape(meta.get("subject", "")),
               C.APP_NAME, C.APP_VERSION))
    data = head + body + "\n</body>\n</html>\n"
    folder = os.path.dirname(path) or "."
    fd, temp = tempfile.mkstemp(prefix=".tgimprint-", suffix=".tmp", dir=folder)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)
    os.replace(temp, path)


def text_to_html(text):
    """Plain text to paragraphs: blank lines separate them, single newlines
    become line breaks."""
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    out = []
    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        out.append("<p>%s</p>" % "<br>".join(escape(line) for line in block.split("\n")))
    return "".join(out) or "<p><br></p>"


def clipboard_html_fragment(html):
    """The fragment inside Windows' CF_HTML wrapper, or the html as given."""
    start = html.find("<!--StartFragment-->")
    end = html.find("<!--EndFragment-->")
    if start >= 0 and end > start:
        return html[start + len("<!--StartFragment-->"):end]
    match = re.search(r"<body[^>]*>(.*?)</body>", html, re.S | re.I)
    return match.group(1) if match else html


def count_pictures_needing_alt(body_html):
    return len(re.findall(r"<img\b[^>]*\bdata-needs-alt\b", body_html or "", re.I))


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', " ", name or "").strip()
    return (name[:80] or S["untitled"]).strip(". ") or S["untitled"]


def open_file(path):
    try:
        os.startfile(path)
    except Exception:
        pass


def open_folder(path):
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    except Exception:
        try:
            os.startfile(os.path.dirname(path))
        except Exception:
            pass


def fallback_snapshot(body, meta, source):
    """An autosave file until docfile.snapshot exists."""
    folder = paths.autosave_dir()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    where = os.path.join(folder, "snapshot-%s%s" % (stamp, C.DOC_EXTENSION))
    write_document(where, body, dict(meta, source_path=source))
    return where


def fallback_recoverable():
    folder = paths.autosave_dir()
    out = []
    try:
        names = sorted(os.listdir(folder), reverse=True)
    except OSError:
        return out
    for name in names:
        if name.endswith(C.DOC_EXTENSION):
            where = os.path.join(folder, name)
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(where)))
            out.append((where, "", when, name))
    return out
