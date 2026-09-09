"""
Main application window for Easy PDF.

Accessibility design notes
--------------------------
NVDA focus mode activates automatically when the RICHEDIT control is
focused (it's a native edit control).  The status bar (panes 0-3) is
readable with NVDA+End.  All menus are navigable with standard
Windows menu keys — NVDA announces every menu item label and shortcut.

Complete keyboard map (also in Help → Keyboard Shortcuts):
  Ctrl+B / Ctrl+Shift+I / Ctrl+U   Bold / Italic / Underline
  Ctrl+Shift+K                      Strikethrough
  Ctrl+L / Ctrl+E / Ctrl+R / Ctrl+J Align Left / Center / Right / Justify
  Ctrl+Alt+1-6                      Heading 1-6
  Ctrl+Alt+0                        Normal paragraph
  Ctrl+Alt+8 / 9                    Bullet / Numbered list
  Ctrl+Q                            Block quote
  Ctrl+Shift+F                      Font dialog
  Ctrl+I                            Insert image
  Ctrl+F / Ctrl+H                   Find / Find & Replace
  F6 / Shift+F6                     Next / Previous heading
  Alt+F6                            Document structure navigator
  Ctrl+P                            Print (exports PDF and opens in viewer)
  Ctrl+E                            (see above — Align Center)
  Ctrl+Shift+E                      Export PDF
"""
from __future__ import annotations

import os
import sys
import tempfile
import subprocess
import wx

from easypdf.ui.editor import Editor
from easypdf.ui.web_editor import WebEditor
from easypdf.ui.toolbar import FormattingToolbar
from easypdf.ui.image_dialog import ImageDialog
from easypdf.ui.hyperlink_dialog import HyperlinkDialog
from easypdf.ui.find_replace_dialog import FindReplaceDialog
from easypdf.ui.doc_properties_dialog import DocPropertiesDialog
from easypdf.ui.structure_panel import StructureNavigator
from easypdf.core.rtc_parser import parse_document
from easypdf.core.pdf_export import export_pdf, export_html_to_pdf
from easypdf.core.pdf_validator import validate_pdf


class MainWindow(wx.Frame):
    def __init__(self, parent, title="Easy PDF", use_web_editor: bool = False):
        super().__init__(parent, title=title, size=(1040, 740))
        self._use_web_editor = use_web_editor
        self._current_file  = None
        self._last_pdf_path = None   # most recently exported PDF
        self._modified      = False
        self._doc_props     = {"title": "", "author": "", "lang": "en-US"}
        self._find_dlg      = None
        self._structure_nav = None

        self._build_menu()
        self._build_toolbar()
        self._build_editor()
        self._toolbar.set_editor(self._editor)
        self._build_status_bar()
        self._build_accelerators()

        self.Centre()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = wx.MenuBar()

        # ---- File ----
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW,    "&New\tCtrl+N",             "Create a new document")
        file_menu.Append(wx.ID_OPEN,   "&Open…\tCtrl+O",           "Open an existing RTF document")
        file_menu.Append(wx.ID_SAVE,   "&Save\tCtrl+S",            "Save document as RTF")
        file_menu.Append(wx.ID_SAVEAS, "Save &As…\tCtrl+Shift+S",  "Save with a new name")
        file_menu.AppendSeparator()
        self._mi_export = file_menu.Append(wx.ID_ANY, "&Export PDF…\tCtrl+Shift+E",
                                           "Export as PDF/UA-1")
        self._mi_print  = file_menu.Append(wx.ID_ANY, "&Print…\tCtrl+P",
                                           "Print document via PDF viewer")
        self._mi_check  = file_menu.Append(wx.ID_ANY, "Check &Accessibility…",
                                           "Validate an exported PDF for PDF/UA-1 compliance")
        file_menu.AppendSeparator()
        self._mi_props  = file_menu.Append(wx.ID_ANY, "Document &Properties…",
                                           "Set title, author, language for PDF")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit\tAlt+F4", "Exit Easy PDF")
        mb.Append(file_menu, "&File")

        # ---- Edit ----
        edit_menu = wx.Menu()
        edit_menu.Append(wx.ID_UNDO,      "&Undo\tCtrl+Z")
        edit_menu.Append(wx.ID_REDO,      "&Redo\tCtrl+Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_CUT,       "Cu&t\tCtrl+X")
        edit_menu.Append(wx.ID_COPY,      "&Copy\tCtrl+C")
        edit_menu.Append(wx.ID_PASTE,     "&Paste\tCtrl+V")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_SELECTALL, "Select &All\tCtrl+A")
        edit_menu.AppendSeparator()
        self._mi_find    = edit_menu.Append(wx.ID_ANY, "&Find…\tCtrl+F",
                                            "Find text in document")
        self._mi_replace = edit_menu.Append(wx.ID_ANY, "Find and &Replace…\tCtrl+H",
                                            "Find and replace text")
        mb.Append(edit_menu, "&Edit")

        # ---- Format ----
        fmt_menu = wx.Menu()

        # Character formatting
        self._id_bold      = fmt_menu.Append(wx.ID_ANY, "&Bold\tCtrl+B",          "Bold").GetId()
        self._id_italic    = fmt_menu.Append(wx.ID_ANY, "&Italic\tCtrl+Shift+I",  "Italic").GetId()
        self._id_underline = fmt_menu.Append(wx.ID_ANY, "&Underline\tCtrl+U",     "Underline").GetId()
        self._id_strike    = fmt_menu.Append(wx.ID_ANY, "S&trikethrough\tCtrl+Shift+K",
                                             "Strikethrough").GetId()
        fmt_menu.AppendSeparator()

        # Paragraph styles
        self._id_h = {}
        for lvl in range(1, 7):
            item = fmt_menu.Append(
                wx.ID_ANY,
                f"Heading &{lvl}\tCtrl+Alt+{lvl}",
                f"Apply Heading {lvl} paragraph style",
            )
            self._id_h[lvl] = item.GetId()
        fmt_menu.AppendSeparator()
        self._mi_normal      = fmt_menu.Append(wx.ID_ANY, "&Normal\tCtrl+Alt+0",
                                               "Normal paragraph")
        self._mi_bullet      = fmt_menu.Append(wx.ID_ANY, "&Bullet List\tCtrl+Alt+8",
                                               "Bullet list item")
        self._mi_numbered    = fmt_menu.Append(wx.ID_ANY, "N&umbered List\tCtrl+Alt+9",
                                               "Numbered list item")
        self._mi_blockquote  = fmt_menu.Append(wx.ID_ANY, "Block &Quote\tCtrl+Q",
                                               "Block quote")
        fmt_menu.AppendSeparator()

        # Alignment submenu
        align_menu = wx.Menu()
        self._mi_align_left    = align_menu.Append(wx.ID_ANY, "Align &Left\tCtrl+L",
                                                   "Left-align paragraph")
        self._mi_align_center  = align_menu.Append(wx.ID_ANY, "Align &Center\tCtrl+E",
                                                   "Center-align paragraph")
        self._mi_align_right   = align_menu.Append(wx.ID_ANY, "Align &Right\tCtrl+R",
                                                   "Right-align paragraph")
        self._mi_align_justify = align_menu.Append(wx.ID_ANY, "Ali&gn Justify\tCtrl+J",
                                                   "Justify paragraph")
        fmt_menu.AppendSubMenu(align_menu, "&Alignment", "Paragraph text alignment")
        fmt_menu.AppendSeparator()

        # Font dialog
        self._mi_font = fmt_menu.Append(wx.ID_ANY, "&Font…\tCtrl+Shift+F",
                                        "Choose font face, size and style")
        mb.Append(fmt_menu, "&Format")

        # ---- Insert ----
        ins_menu = wx.Menu()
        self._mi_insert_image = ins_menu.Append(wx.ID_ANY, "&Image…\tCtrl+I",
                                                "Insert image with alt text")
        self._mi_insert_link  = ins_menu.Append(wx.ID_ANY, "&Hyperlink…\tCtrl+K",
                                                "Insert a hyperlink (accessible link text + URL)")
        mb.Append(ins_menu, "&Insert")

        # ---- View ----
        view_menu = wx.Menu()
        self._mi_structure    = view_menu.Append(wx.ID_ANY,
                                                 "Document &Structure\tAlt+F6",
                                                 "Show document outline / heading navigator")
        self._mi_next_heading = view_menu.Append(wx.ID_ANY, "&Next Heading\tF6",
                                                 "Move caret to next heading")
        self._mi_prev_heading = view_menu.Append(wx.ID_ANY, "&Previous Heading\tShift+F6",
                                                 "Move caret to previous heading")
        mb.Append(view_menu, "&View")

        # ---- Help ----
        help_menu = wx.Menu()
        self._mi_shortcuts = help_menu.Append(wx.ID_ANY, "&Keyboard Shortcuts\tF1",
                                              "Show all keyboard shortcuts")
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, "&About Easy PDF", "About this application")
        mb.Append(help_menu, "&Help")

        self.SetMenuBar(mb)

        # ---- Bindings ----
        # File
        self.Bind(wx.EVT_MENU, self._on_new,         id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self._on_open,        id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_save,        id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self._on_save_as,     id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self._on_export_pdf,       id=self._mi_export.GetId())
        self.Bind(wx.EVT_MENU, self._on_print,            id=self._mi_print.GetId())
        self.Bind(wx.EVT_MENU, self._on_check_a11y,       id=self._mi_check.GetId())
        self.Bind(wx.EVT_MENU, self._on_doc_props,        id=self._mi_props.GetId())
        self.Bind(wx.EVT_MENU, self._on_exit,        id=wx.ID_EXIT)

        # Edit
        self.Bind(wx.EVT_MENU, self._on_undo,        id=wx.ID_UNDO)
        self.Bind(wx.EVT_MENU, self._on_redo,        id=wx.ID_REDO)
        self.Bind(wx.EVT_MENU, self._on_cut,         id=wx.ID_CUT)
        self.Bind(wx.EVT_MENU, self._on_copy,        id=wx.ID_COPY)
        self.Bind(wx.EVT_MENU, self._on_paste,       id=wx.ID_PASTE)
        self.Bind(wx.EVT_MENU, self._on_select_all,  id=wx.ID_SELECTALL)
        self.Bind(wx.EVT_MENU, self._on_find,        id=self._mi_find.GetId())
        self.Bind(wx.EVT_MENU, self._on_replace,     id=self._mi_replace.GetId())

        # Format — character
        self.Bind(wx.EVT_MENU, lambda e: self._editor.toggle_bold(),          id=self._id_bold)
        self.Bind(wx.EVT_MENU, lambda e: self._editor.toggle_italic(),        id=self._id_italic)
        self.Bind(wx.EVT_MENU, lambda e: self._editor.toggle_underline(),     id=self._id_underline)
        self.Bind(wx.EVT_MENU, lambda e: self._editor.toggle_strikethrough(), id=self._id_strike)

        # Format — paragraph style
        self.Bind(wx.EVT_MENU, self._on_normal_style, id=self._mi_normal.GetId())
        self.Bind(wx.EVT_MENU, self._on_bullet,       id=self._mi_bullet.GetId())
        self.Bind(wx.EVT_MENU, self._on_numbered,     id=self._mi_numbered.GetId())
        self.Bind(wx.EVT_MENU, self._on_blockquote,   id=self._mi_blockquote.GetId())
        for lvl, mid in self._id_h.items():
            self.Bind(wx.EVT_MENU,
                      lambda e, l=lvl: self._editor.apply_paragraph_style(f"Heading {l}"),
                      id=mid)

        # Format — alignment
        self.Bind(wx.EVT_MENU, lambda e: self._editor.apply_alignment("left"),
                  id=self._mi_align_left.GetId())
        self.Bind(wx.EVT_MENU, lambda e: self._editor.apply_alignment("center"),
                  id=self._mi_align_center.GetId())
        self.Bind(wx.EVT_MENU, lambda e: self._editor.apply_alignment("right"),
                  id=self._mi_align_right.GetId())
        self.Bind(wx.EVT_MENU, lambda e: self._editor.apply_alignment("justify"),
                  id=self._mi_align_justify.GetId())

        # Format — font dialog
        self.Bind(wx.EVT_MENU, self._on_font_dialog, id=self._mi_font.GetId())

        # Insert
        self.Bind(wx.EVT_MENU, self._on_insert_image,   id=self._mi_insert_image.GetId())
        self.Bind(wx.EVT_MENU, self._on_insert_link,    id=self._mi_insert_link.GetId())

        # View
        self.Bind(wx.EVT_MENU, self._on_show_structure,  id=self._mi_structure.GetId())
        self.Bind(wx.EVT_MENU, self._on_next_heading,    id=self._mi_next_heading.GetId())
        self.Bind(wx.EVT_MENU, self._on_prev_heading,    id=self._mi_prev_heading.GetId())

        # Help
        self.Bind(wx.EVT_MENU, self._on_shortcuts,       id=self._mi_shortcuts.GetId())
        self.Bind(wx.EVT_MENU, self._on_about,           id=wx.ID_ABOUT)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _build_toolbar(self):
        self._toolbar = FormattingToolbar(self)
        self.SetToolBar(self._toolbar)

    def _build_editor(self):
        if self._use_web_editor:
            self._editor = WebEditor(self)
        else:
            self._editor = Editor(self)
        self._editor.Bind(wx.EVT_TEXT, self._on_text_changed)

    def _build_status_bar(self):
        self._status = self.CreateStatusBar(4)
        # Pane 0: word count  1: current style  2: heading context  3: save state
        self._status.SetStatusWidths([-1, 160, 200, 100])
        self._update_status()

        # Caret-tracking events only exist on the legacy RICHEDIT path.
        # The WebEditor reports its state via JS messages instead.
        if isinstance(self._editor, Editor):
            self._editor.ctrl.Bind(wx.EVT_LEFT_UP, self._on_caret_moved)
            self._editor.ctrl.Bind(wx.EVT_KEY_UP,  self._on_caret_moved)
        else:
            from easypdf.ui.web_editor import EVT_WEBEDITOR_STATE
            self._editor.Bind(EVT_WEBEDITOR_STATE, self._on_caret_moved)

    def _build_accelerators(self):
        entries = [
            # Character formatting
            wx.AcceleratorEntry(wx.ACCEL_CTRL,                  ord("B"), self._id_bold),
            wx.AcceleratorEntry(wx.ACCEL_CTRL,                  ord("U"), self._id_underline),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("I"), self._id_italic),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("K"), self._id_strike),
            # Alignment
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("L"), self._mi_align_left.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("E"), self._mi_align_center.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("R"), self._mi_align_right.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("J"), self._mi_align_justify.GetId()),
            # Font dialog
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("F"), self._mi_font.GetId()),
            # Find
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("F"), self._mi_find.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("H"), self._mi_replace.GetId()),
            # Export / Print
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("E"), self._mi_export.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL,                  ord("P"), self._mi_print.GetId()),
            # Heading navigation
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F6,  self._mi_next_heading.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_SHIFT,  wx.WXK_F6,  self._mi_prev_heading.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_ALT,    wx.WXK_F6,  self._mi_structure.GetId()),
            # Keyboard shortcuts help
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F1,  self._mi_shortcuts.GetId()),
            # Hyperlink
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("K"), self._mi_insert_link.GetId()),
        ]
        for lvl in range(1, 7):
            entries.append(wx.AcceleratorEntry(
                wx.ACCEL_CTRL | wx.ACCEL_ALT, ord(str(lvl)), self._id_h[lvl]
            ))
        entries += [
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("0"), self._mi_normal.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("8"), self._mi_bullet.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("9"), self._mi_numbered.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL,                ord("Q"), self._mi_blockquote.GetId()),
            wx.AcceleratorEntry(wx.ACCEL_CTRL,                ord("I"), self._mi_insert_image.GetId()),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(entries))

    # ------------------------------------------------------------------
    # Status / title
    # ------------------------------------------------------------------

    def _update_status(self):
        words = self._editor.word_count()
        self._status.SetStatusText(f"Words: {words}", 0)
        self._status.SetStatusText("Unsaved" if self._modified else "Saved", 3)
        base = os.path.basename(self._current_file) if self._current_file else "Untitled"
        self.SetTitle(("* " if self._modified else "") + f"{base} — Easy PDF")

    def _on_caret_moved(self, event):
        style = self._editor.current_paragraph_style()
        self._status.SetStatusText(style, 1)

        # The "current heading context" pane requires line-level inspection
        # which only the RICHEDIT editor exposes.  WebEditor reports the
        # current style via its selstate message, so for that path we fall
        # back to showing just the style label.
        if isinstance(self._editor, Editor):
            ip  = self._editor.ctrl.GetInsertionPoint()
            ln  = self._editor.ctrl.GetLineNumberFromPosition(ip)
            ctx = self._find_enclosing_heading(ln)
            self._status.SetStatusText(ctx, 2)
        else:
            self._status.SetStatusText("", 2)

        self._toolbar.sync_to_editor()
        event.Skip()

    def _find_enclosing_heading(self, ln: int) -> str:
        if not isinstance(self._editor, Editor):
            return ""
        for i in range(ln, -1, -1):
            s = self._editor._style_for_line(i)
            if s.startswith("Heading"):
                text = self._editor.ctrl.GetLineText(i)
                return f"In: {text[:30]}"
        return ""

    def _on_text_changed(self, event):
        self._modified = True
        self._update_status()
        event.Skip()

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def _on_new(self, event):
        if not self._confirm_discard():
            return
        self._editor.clear()
        self._current_file = None
        self._modified     = False
        self._doc_props    = {"title": "", "author": "", "lang": "en-US"}
        self._update_status()

    def _doc_format(self):
        """(extension, wildcard) for the active editor's native save format."""
        if isinstance(self._editor, Editor):
            return "rtf", "RTF files (*.rtf)|*.rtf"
        return "html", "Easy PDF documents (*.html;*.epdf)|*.html;*.epdf"

    def _on_open(self, event):
        if not self._confirm_discard():
            return
        ext, wildcard = self._doc_format()
        with wx.FileDialog(
            self, "Open document",
            wildcard=wildcard + "|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._load_file(dlg.GetPath())

    def _on_save(self, event):
        if self._current_file:
            self._save_file(self._current_file)
        else:
            self._on_save_as(event)

    def _on_save_as(self, event):
        ext, wildcard = self._doc_format()
        with wx.FileDialog(
            self, "Save document as",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                if not path.lower().endswith("." + ext):
                    path += "." + ext
                self._save_file(path)

    def _on_export_pdf(self, event):
        if not self._doc_props.get("title"):
            wx.MessageBox(
                "Please set the document title before exporting.\n"
                "Go to File → Document Properties.",
                "Title required for PDF/UA",
                wx.OK | wx.ICON_INFORMATION,
            )
            self._on_doc_props(None)
            if not self._doc_props.get("title"):
                return

        default = ""
        if self._current_file:
            default = os.path.splitext(os.path.basename(self._current_file))[0] + ".pdf"
        elif self._doc_props.get("title"):
            default = self._doc_props["title"] + ".pdf"

        with wx.FileDialog(
            self, "Export as PDF",
            defaultFile=default,
            wildcard="PDF files (*.pdf)|*.pdf",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            pdf_path = dlg.GetPath()
            if not pdf_path.lower().endswith(".pdf"):
                pdf_path += ".pdf"

        self._do_export(pdf_path)

    def _on_print(self, event):
        if not self._doc_props.get("title"):
            self._on_doc_props(None)
            if not self._doc_props.get("title"):
                return

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        if self._do_export(tmp.name, silent=True):
            try:
                if sys.platform == "win32":
                    os.startfile(tmp.name)
                else:
                    subprocess.Popen(["xdg-open", tmp.name])
            except Exception as exc:
                wx.MessageBox(
                    f"Could not open PDF viewer:\n{exc}\n\nFile saved at:\n{tmp.name}",
                    "Print", wx.OK | wx.ICON_INFORMATION,
                )

    def _do_export(self, path: str, silent: bool = False) -> bool:
        title  = self._doc_props.get("title",  "Untitled")
        lang   = self._doc_props.get("lang",   "en-US")
        author = self._doc_props.get("author", "")

        try:
            if isinstance(self._editor, Editor):
                # RICHEDIT path: parse the buffer into the Document model.
                doc = parse_document(self._editor, title=title, lang=lang, author=author)
                export_pdf(doc, path)
            else:
                # WebEditor path: ship the editor's HTML straight to
                # WeasyPrint — no Document round-trip needed.
                body = self._editor.get_html()
                export_html_to_pdf(body, path, title=title, lang=lang, author=author)

            self._last_pdf_path = path
            if not silent:
                self._status.SetStatusText("PDF/UA exported", 3)
                wx.MessageBox(f"PDF saved:\n{path}", "Export complete",
                              wx.OK | wx.ICON_INFORMATION)
            return True
        except Exception as exc:
            wx.MessageBox(f"Export failed:\n{exc}", "Export error", wx.OK | wx.ICON_ERROR)
            return False

    def _on_doc_props(self, event):
        with DocPropertiesDialog(self, self._doc_props) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._doc_props = dlg.get_result()
                self._modified  = True
                self._update_status()

    def _on_check_a11y(self, event):
        """Validate an exported PDF and show an accessibility report."""
        path = self._last_pdf_path
        if not path or not os.path.isfile(path):
            # Ask user to pick a PDF
            with wx.FileDialog(
                self, "Select PDF to check",
                wildcard="PDF files (*.pdf)|*.pdf|All files (*.*)|*.*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                path = dlg.GetPath()

        report = validate_pdf(path)
        self._show_a11y_report(report)

    def _show_a11y_report(self, report) -> None:
        ok, total = report.score
        caption = f"Accessibility Report — {ok}/{total} passed"

        dlg = wx.Dialog(self, title=caption, size=(580, 420),
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        dlg.SetMinSize((440, 300))

        txt = wx.TextCtrl(
            dlg, value=report.format_report(),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL,
        )
        txt.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE,
                            wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        txt.SetName("Accessibility report")

        btn = wx.Button(dlg, wx.ID_OK, "Close")
        btn.SetDefault()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(txt, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 8)
        dlg.SetSizer(sizer)
        dlg.Layout()
        dlg.ShowModal()
        dlg.Destroy()

    def _on_exit(self, event):
        self.Close()

    def _on_close(self, event):
        if self._confirm_discard():
            for dlg in (self._find_dlg, self._structure_nav):
                if dlg:
                    dlg.Destroy()
            event.Skip()

    # ------------------------------------------------------------------
    # Edit
    # ------------------------------------------------------------------

    # Edit-menu actions: the RICHEDIT control exposes Undo/Cut/etc. directly.
    # The WebView surface implements them via JS exec commands.
    def _on_undo(self, event):       self._edit_cmd("undo")
    def _on_redo(self, event):       self._edit_cmd("redo")
    def _on_cut(self, event):        self._edit_cmd("cut")
    def _on_copy(self, event):       self._edit_cmd("copy")
    def _on_paste(self, event):      self._edit_cmd("paste")
    def _on_select_all(self, event): self._edit_cmd("selectAll")

    def _edit_cmd(self, name: str) -> None:
        if isinstance(self._editor, Editor):
            ctrl = self._editor.ctrl
            {
                "undo":      ctrl.Undo,
                "redo":      ctrl.Redo,
                "cut":       ctrl.Cut,
                "copy":      ctrl.Copy,
                "paste":     ctrl.Paste,
                "selectAll": ctrl.SelectAll,
            }[name]()
        else:
            # WebEditor — use the document.execCommand API the page exposes
            self._editor._js_call("exec", {
                "selectAll": "selectAll",
            }.get(name, name))

    def _on_find(self, event):
        if isinstance(self._editor, Editor):
            self._ensure_find_dlg().show_find()
        else:
            self._show_web_find(replace=False)

    def _on_replace(self, event):
        if isinstance(self._editor, Editor):
            self._ensure_find_dlg().show_replace()
        else:
            self._show_web_find(replace=True)

    def _ensure_find_dlg(self) -> FindReplaceDialog:
        if not self._find_dlg:
            self._find_dlg = FindReplaceDialog(self, self._editor.ctrl)
        return self._find_dlg

    def _show_web_find(self, replace: bool) -> None:
        from easypdf.ui.web_find_dialog import WebFindDialog
        if not self._find_dlg:
            self._find_dlg = WebFindDialog(self, self._editor)
        if replace:
            self._find_dlg.show_replace()
        else:
            self._find_dlg.show_find()

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def _on_normal_style(self, event):  self._editor.apply_paragraph_style("Normal")
    def _on_bullet(self, event):        self._editor.apply_paragraph_style("Bullet List")
    def _on_numbered(self, event):      self._editor.apply_paragraph_style("Numbered List")
    def _on_blockquote(self, event):    self._editor.apply_paragraph_style("Block Quote")

    def _on_font_dialog(self, event):
        """Open the system font dialog and apply the chosen font to the selection."""
        if self._editor.ctrl is None:
            # WebEditor — drive execCommand fontName / fontSize directly.
            fd = wx.FontData()
            fd.EnableEffects(True)
            with wx.FontDialog(self, fd) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                font = dlg.GetFontData().GetChosenFont()
            self._editor._js_call("exec", "fontName", font.GetFaceName())
            # execCommand fontSize accepts 1..7; pick by approximation.
            pt = font.GetPointSize() or 11
            self._editor._js_call("exec", "fontSize",
                                  str(min(7, max(1, round(pt / 6)))))
            return

        ip   = self._editor.ctrl.GetInsertionPoint()
        attr = wx.TextAttr()
        self._editor.ctrl.GetStyle(ip, attr)

        fd = wx.FontData()
        fd.SetInitialFont(attr.GetFont() if attr.HasFont() else self._editor.ctrl.GetFont())
        fd.EnableEffects(True)

        with wx.FontDialog(self, fd) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                chosen_font = dlg.GetFontData().GetChosenFont()
                s, e = self._editor.ctrl.GetSelection()
                if s == e:
                    s, e = self._editor._effective_range()
                new_attr = wx.TextAttr()
                self._editor.ctrl.GetStyle(s, new_attr)
                new_attr.SetFont(chosen_font)
                self._editor.ctrl.SetStyle(s, e, new_attr)
                self._editor.ctrl.SetDefaultStyle(new_attr)
                self._editor.ctrl.SetFocus()

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    def _on_insert_image(self, event):
        with ImageDialog(self) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path, alt_text = dlg.get_result()
                self._editor.insert_image(path, alt_text)
                self._modified = True
                self._update_status()

    def _on_insert_link(self, event):
        if self._editor.ctrl is None:
            pre = ""    # WebEditor: dialog will use its own selection logic
        else:
            s, e = self._editor.ctrl.GetSelection()
            pre  = self._editor.ctrl.GetRange(s, e) if s != e else ""
        with HyperlinkDialog(self, pre) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                display_text, url = dlg.get_result()
                self._editor.insert_link(display_text, url)
                self._modified = True
                self._update_status()

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    def _on_show_structure(self, event):
        if not self._structure_nav:
            self._structure_nav = StructureNavigator(self, self._editor)
        self._structure_nav.show_and_refresh()

    def _on_next_heading(self, event):
        style = self._editor.go_to_next_heading()
        self._status.SetStatusText(style if style else "No next heading", 1)

    def _on_prev_heading(self, event):
        style = self._editor.go_to_prev_heading()
        self._status.SetStatusText(style if style else "No previous heading", 1)

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _on_shortcuts(self, event):
        msg = (
            "Easy PDF — Keyboard Shortcuts\n"
            "==============================\n\n"
            "Character formatting\n"
            "  Ctrl+B                 Bold\n"
            "  Ctrl+Shift+I           Italic\n"
            "  Ctrl+U                 Underline\n"
            "  Ctrl+Shift+K           Strikethrough\n"
            "  Ctrl+Shift+F           Font dialog\n\n"
            "Paragraph alignment\n"
            "  Ctrl+L                 Align Left\n"
            "  Ctrl+E                 Align Center\n"
            "  Ctrl+R                 Align Right\n"
            "  Ctrl+J                 Justify\n\n"
            "Paragraph styles\n"
            "  Ctrl+Alt+1–6           Heading 1–6\n"
            "  Ctrl+Alt+0             Normal paragraph\n"
            "  Ctrl+Alt+8             Bullet list\n"
            "  Ctrl+Alt+9             Numbered list\n"
            "  Ctrl+Q                 Block quote\n\n"
            "Navigation\n"
            "  F6 / Shift+F6          Next / Previous heading\n"
            "  Alt+F6                 Document structure navigator\n\n"
            "Edit\n"
            "  Ctrl+F                 Find\n"
            "  Ctrl+H                 Find and Replace\n\n"
            "File\n"
            "  Ctrl+N / O / S         New / Open / Save\n"
            "  Ctrl+Shift+E           Export PDF\n"
            "  Ctrl+P                 Print\n\n"
            "Insert\n"
            "  Ctrl+I                 Insert image\n"
            "  Ctrl+K                 Insert hyperlink\n\n"
            "NVDA tips\n"
            "  NVDA+F                 Check formatting at caret\n"
            "  NVDA+End               Read status bar\n"
            "  Alt+F6                 Heading outline for navigation"
        )
        wx.MessageBox(msg, "Keyboard Shortcuts — Easy PDF", wx.OK | wx.ICON_INFORMATION)

    def _on_about(self, event):
        wx.MessageBox(
            "Easy PDF\n"
            "Accessible PDF authoring — PDF/UA-1 output for NVDA.\n\n"
            "Press F1 for a full list of keyboard shortcuts.",
            "About Easy PDF",
            wx.OK | wx.ICON_INFORMATION,
        )

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _save_file(self, path: str):
        try:
            self._editor.save(path)
            self._current_file = path
            self._modified     = False
            self._update_status()
        except Exception as exc:
            wx.MessageBox(f"Could not save:\n{exc}", "Save error", wx.OK | wx.ICON_ERROR)

    def _load_file(self, path: str):
        try:
            self._editor.load(path)
            self._current_file = path
            self._modified     = False
            self._update_status()
        except Exception as exc:
            wx.MessageBox(f"Could not open:\n{exc}", "Open error", wx.OK | wx.ICON_ERROR)

    def _confirm_discard(self) -> bool:
        """
        Return True if it is safe to proceed (the caller may destroy or replace
        the document).  Handles three outcomes:

          Save       → saves the file first, then proceeds
          Don't Save → discards changes and proceeds immediately
          Cancel     → aborts the operation, caller should not proceed
        """
        if not self._modified:
            return True

        with wx.MessageDialog(
            self,
            "Do you want to save your changes?",
            "Unsaved changes",
            wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_WARNING,
        ) as dlg:
            dlg.SetYesNoCancelLabels("&Save", "&Don't Save", "&Cancel")
            result = dlg.ShowModal()

        if result == wx.ID_YES:
            self._on_save(None)
            return not self._modified   # True only if save actually completed
        if result == wx.ID_NO:
            return True                 # discard and proceed
        return False                    # Cancel — abort the operation
