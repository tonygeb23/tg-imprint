"""
Find / Replace dialog for the WebEditor backend.

Uses the WebEditor's JS-side window.find() wrappers (Chromium/Edge
WebView2 supports the legacy `window.find` API natively, including
match-case).  Mirrors the modeless behaviour of FindReplaceDialog.
"""
from __future__ import annotations

import wx


class WebFindDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, web_editor) -> None:
        super().__init__(
            parent,
            title="Find and Replace",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._editor = web_editor
        self._build_ui()
        self.Fit()
        self.SetMinSize((420, self.GetSize().height))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        vbox  = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=2, cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        find_lbl = wx.StaticText(panel, label="&Find:")
        self._find_ctrl = wx.TextCtrl(panel)
        self._find_ctrl.SetName("Find what")
        grid.Add(find_lbl,         0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._find_ctrl,  1, wx.EXPAND)

        repl_lbl = wx.StaticText(panel, label="&Replace with:")
        self._repl_ctrl = wx.TextCtrl(panel)
        self._repl_ctrl.SetName("Replace with")
        grid.Add(repl_lbl,         0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._repl_ctrl,  1, wx.EXPAND)

        vbox.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        self._case_cb = wx.CheckBox(panel, label="Match &case")
        vbox.Add(self._case_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._status = wx.StaticText(panel, label="")
        self._status.SetForegroundColour(wx.Colour(80, 80, 80))
        vbox.Add(self._status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        find_next  = wx.Button(panel, label="Find &Next")
        find_prev  = wx.Button(panel, label="Find &Previous")
        repl_btn   = wx.Button(panel, label="Re&place")
        repl_all   = wx.Button(panel, label="Replace &All")
        close_btn  = wx.Button(panel, wx.ID_CLOSE, label="&Close")

        btn_row.Add(find_next, 0, wx.RIGHT, 6)
        btn_row.Add(find_prev, 0, wx.RIGHT, 6)
        btn_row.Add(repl_btn,  0, wx.RIGHT, 6)
        btn_row.Add(repl_all,  0, wx.RIGHT, 6)
        btn_row.AddStretchSpacer()
        btn_row.Add(close_btn, 0)
        vbox.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)

        find_next.Bind(wx.EVT_BUTTON, self._on_find_next)
        find_prev.Bind(wx.EVT_BUTTON, self._on_find_prev)
        repl_btn.Bind( wx.EVT_BUTTON, self._on_replace)
        repl_all.Bind( wx.EVT_BUTTON, self._on_replace_all)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Hide())
        self.Bind(     wx.EVT_CLOSE,  lambda e: self.Hide())

        find_next.SetDefault()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_find(self) -> None:
        self._repl_ctrl.Hide()
        self.Show()
        self.Raise()
        self._find_ctrl.SetFocus()

    def show_replace(self) -> None:
        self._repl_ctrl.Show()
        self.Show()
        self.Raise()
        self._find_ctrl.SetFocus()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _needle(self) -> str:
        return self._find_ctrl.GetValue()

    def _case(self) -> bool:
        return self._case_cb.GetValue()

    def _on_find_next(self, event) -> None:
        if self._editor.find_next(self._needle(), self._case()):
            self._status.SetLabel("")
        else:
            self._status.SetLabel("Not found.")

    def _on_find_prev(self, event) -> None:
        if self._editor.find_prev(self._needle(), self._case()):
            self._status.SetLabel("")
        else:
            self._status.SetLabel("Not found.")

    def _on_replace(self, event) -> None:
        if self._editor.replace_selection(self._repl_ctrl.GetValue()):
            self._editor.find_next(self._needle(), self._case())
        else:
            self._editor.find_next(self._needle(), self._case())

    def _on_replace_all(self, event) -> None:
        n = 0
        # Walk through the document from the top.
        self._editor._js_call("exec", "selectAll")
        # Collapse selection to start, then iterate find_next + replace.
        self._editor.web.RunScript(
            "(function(){const s=window.getSelection();"
            "if(s.rangeCount){const r=s.getRangeAt(0);r.collapse(true);"
            "s.removeAllRanges();s.addRange(r);}})();"
        )
        while self._editor.find_next(self._needle(), self._case()):
            if not self._editor.replace_selection(self._repl_ctrl.GetValue()):
                break
            n += 1
            if n > 10000:               # safety stop
                break
        self._status.SetLabel(f"Replaced {n} occurrence{'' if n == 1 else 's'}.")
