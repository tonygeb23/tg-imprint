"""
Find & Replace dialog.

Designed for keyboard-first use so NVDA users can navigate fully without
a mouse.  Tab order: Find field → Replace field → Match Case → Whole Word →
Find Next → Replace → Replace All → Close.

The dialog is modeless (stays open while editing) so the user can keep
the document in focus and press Find Next repeatedly.
"""
from __future__ import annotations

import re
import wx


class FindReplaceDialog(wx.Dialog):
    """
    Modeless Find & Replace dialog backed by a wx.TextCtrl (RICHEDIT).

    Usage:
        dlg = FindReplaceDialog(parent, editor.ctrl)
        dlg.Show()   # modeless — does not block
    """

    def __init__(self, parent: wx.Window, text_ctrl: wx.TextCtrl) -> None:
        super().__init__(
            parent,
            title="Find and Replace",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self._ctrl       = text_ctrl
        self._last_find  = -1   # position of last successful find
        self._found_len  = 0

        self._build_ui()
        self.Fit()
        self.SetMinSize((400, self.GetSize().height))
        self.Centre(wx.BOTH)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=8)
        grid.AddGrowableCol(1, 1)

        # Find
        find_lbl = wx.StaticText(panel, label="Fi&nd:")
        self._find_ctrl = wx.TextCtrl(panel)
        self._find_ctrl.SetName("Find text field")
        grid.Add(find_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._find_ctrl, 1, wx.EXPAND)

        # Replace
        replace_lbl = wx.StaticText(panel, label="Re&place with:")
        self._replace_ctrl = wx.TextCtrl(panel)
        self._replace_ctrl.SetName("Replace with text field")
        grid.Add(replace_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._replace_ctrl, 1, wx.EXPAND)

        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)

        # Options
        opt_box = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "Options")
        self._case_cb      = wx.CheckBox(panel, label="Match &case")
        self._whole_word_cb= wx.CheckBox(panel, label="&Whole word only")
        self._case_cb.SetName("Match case checkbox")
        self._whole_word_cb.SetName("Whole word only checkbox")
        opt_box.Add(self._case_cb,       0, wx.ALL, 6)
        opt_box.Add(self._whole_word_cb, 0, wx.ALL, 6)
        outer.Add(opt_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Status label (shows "Not found", match count, etc.)
        self._status_lbl = wx.StaticText(panel, label="")
        self._status_lbl.SetName("Search status")
        outer.Add(self._status_lbl, 0, wx.LEFT | wx.BOTTOM, 12)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._find_btn        = wx.Button(panel, label="Find &Next")
        self._replace_btn     = wx.Button(panel, label="&Replace")
        self._replace_all_btn = wx.Button(panel, label="Replace &All")
        close_btn             = wx.Button(panel, wx.ID_CLOSE, label="&Close")

        self._find_btn.SetName("Find Next button")
        self._replace_btn.SetName("Replace button")
        self._replace_all_btn.SetName("Replace All button")
        close_btn.SetName("Close dialog button")

        btn_sizer.Add(self._find_btn,        0, wx.RIGHT, 6)
        btn_sizer.Add(self._replace_btn,     0, wx.RIGHT, 6)
        btn_sizer.Add(self._replace_all_btn, 0, wx.RIGHT, 6)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(close_btn, 0)
        outer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # Bindings
        self._find_btn.Bind(        wx.EVT_BUTTON, self._on_find_next)
        self._replace_btn.Bind(     wx.EVT_BUTTON, self._on_replace)
        self._replace_all_btn.Bind( wx.EVT_BUTTON, self._on_replace_all)
        close_btn.Bind(             wx.EVT_BUTTON, lambda e: self.Hide())
        self.Bind(wx.EVT_CLOSE,     lambda e: self.Hide())

        # Enter in either text field triggers Find Next
        self._find_ctrl.Bind(   wx.EVT_TEXT_ENTER, self._on_find_next)
        self._replace_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_find_next)

        # Reset search position when query changes
        self._find_ctrl.Bind(wx.EVT_TEXT, self._on_query_changed)

        self._find_ctrl.SetFocus()

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def _query(self) -> str:
        return self._find_ctrl.GetValue()

    def _full_text(self) -> str:
        return self._ctrl.GetValue()

    def _find_from(self, start: int) -> int:
        """Return position of next match starting at *start*, or -1."""
        query = self._query()
        if not query:
            return -1
        text  = self._full_text()
        if not self._case_cb.IsChecked():
            search_text  = text.lower()
            search_query = query.lower()
        else:
            search_text  = text
            search_query = query

        pos = search_text.find(search_query, start)

        if self._whole_word_cb.IsChecked() and pos != -1:
            # Verify word boundaries
            before = pos == 0 or not search_text[pos - 1].isalnum()
            after  = (pos + len(search_query) >= len(search_text)
                      or not search_text[pos + len(search_query)].isalnum())
            if not (before and after):
                # Try next occurrence
                return self._find_from(pos + 1)

        return pos

    def _select(self, pos: int, length: int) -> None:
        self._ctrl.SetSelection(pos, pos + length)
        self._ctrl.ShowPosition(pos)
        self._last_find = pos
        self._found_len = length

    def _set_status(self, msg: str) -> None:
        self._status_lbl.SetLabel(msg)
        self._status_lbl.GetParent().Layout()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_query_changed(self, event: wx.CommandEvent) -> None:
        self._last_find = -1
        self._set_status("")
        event.Skip()

    def _on_find_next(self, event=None) -> None:
        query = self._query()
        if not query:
            self._set_status("Type something to search for.")
            return

        start = self._last_find + 1 if self._last_find >= 0 else 0
        pos   = self._find_from(start)

        if pos == -1 and start > 0:
            # Wrap around
            pos = self._find_from(0)
            if pos != -1:
                self._set_status("Wrapped to top of document.")
            else:
                self._set_status(f'"{query}" not found.')
                self._last_find = -1
                return
        elif pos == -1:
            self._set_status(f'"{query}" not found.')
            return
        else:
            self._set_status("")

        self._select(pos, len(query))
        # Bring document to front so NVDA reads the selected text
        self._ctrl.SetFocus()
        wx.CallAfter(self.Raise)

    def _on_replace(self, event=None) -> None:
        """Replace the current selection if it matches, then find next."""
        query   = self._query()
        replace = self._replace_ctrl.GetValue()
        if not query:
            return

        s, e = self._ctrl.GetSelection()
        selected = self._ctrl.GetRange(s, e)
        compare_sel   = selected   if self._case_cb.IsChecked() else selected.lower()
        compare_query = query      if self._case_cb.IsChecked() else query.lower()

        if compare_sel == compare_query:
            self._ctrl.Replace(s, e, replace)
            self._last_find = s - 1   # find next from same position
            self._set_status("Replaced.")
        self._on_find_next()

    def _on_replace_all(self, event=None) -> None:
        query   = self._query()
        replace = self._replace_ctrl.GetValue()
        if not query:
            return

        text  = self._full_text()
        flags = 0 if self._case_cb.IsChecked() else re.IGNORECASE
        import re
        if self._whole_word_cb.IsChecked():
            pattern = re.compile(r"\b" + re.escape(query) + r"\b", flags)
        else:
            pattern = re.compile(re.escape(query), flags)

        new_text, count = pattern.subn(replace, text)
        if count:
            self._ctrl.SetValue(new_text)
            self._last_find = -1
            self._set_status(f"Replaced {count} occurrence(s).")
        else:
            self._set_status(f'"{query}" not found.')

    # ------------------------------------------------------------------
    # Public — called by main window
    # ------------------------------------------------------------------

    def show_find(self) -> None:
        """Show dialog with focus on the Find field."""
        self._replace_ctrl.Show()
        self._replace_btn.Show()
        self._replace_all_btn.Show()
        self.Fit()
        self._find_ctrl.SetFocus()
        self._find_ctrl.SelectAll()
        self.Show()
        self.Raise()

    def show_replace(self) -> None:
        """Same — dialog always shows replace field."""
        self.show_find()
