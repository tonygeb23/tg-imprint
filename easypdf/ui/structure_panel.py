"""
Document Structure Navigator.

A modeless panel (shown as a separate, always-on-top window) listing all
headings in the document.  NVDA users can Tab to it and use arrow keys to
browse the outline, then press Enter to jump to any heading.

Design notes for NVDA:
- wx.ListBox is an MSAA LIST control — NVDA reads items by role, position,
  and content (e.g. "H2: Introduction, 3 of 7").
- Each item text is prefixed with the heading level so NVDA reads it
  without needing any special announcement.
- Tab from the navigator back to the editor via Escape or Tab.
- Auto-refresh on Show so the list is always current.
"""
from __future__ import annotations

import wx


_LEVEL_INDENT = "    "   # 4 spaces per heading level for visual indentation


class StructureNavigator(wx.Frame):
    """
    Modeless document outline window.

    Opened via View → Document Structure (Alt+F6 shortcut defined in
    main_window).  Stays on top of the main window.

    Usage:
        nav = StructureNavigator(main_window, editor)
        nav.Show()          # refresh + show
    """

    def __init__(self, parent: wx.Frame, editor) -> None:
        super().__init__(
            parent,
            title="Document Structure",
            style=(
                wx.DEFAULT_FRAME_STYLE
                | wx.FRAME_FLOAT_ON_PARENT   # stays above main window
                & ~wx.MAXIMIZE_BOX
                & ~wx.RESIZE_BORDER
            ),
            size=(320, 480),
        )
        self._editor = editor
        # List of char positions corresponding to each list item
        self._positions: list[int] = []

        self._build_ui()
        self.Centre(wx.BOTH)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)

        # Instruction label — NVDA reads this as the panel is entered
        instr = wx.StaticText(
            panel,
            label=(
                "Document headings. "
                "Use Up/Down arrows to browse, Enter to jump to heading, "
                "Escape to return to editor."
            ),
        )
        instr.SetName("Structure navigator instructions")
        instr.Wrap(300)

        # Heading list
        self._listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self._listbox.SetName("Document headings list")

        # Buttons
        jump_btn    = wx.Button(panel, label="&Jump to Heading\tEnter")
        refresh_btn = wx.Button(panel, label="&Refresh")
        close_btn   = wx.Button(panel, wx.ID_CLOSE, label="&Close")

        jump_btn.SetName("Jump to selected heading")
        refresh_btn.SetName("Refresh heading list")
        close_btn.SetName("Close structure navigator")

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.Add(jump_btn,    0, wx.RIGHT, 6)
        btn_row.Add(refresh_btn, 0, wx.RIGHT, 6)
        btn_row.AddStretchSpacer()
        btn_row.Add(close_btn,   0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(instr,          0, wx.ALL, 8)
        sizer.Add(self._listbox,  1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(btn_row,        0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # Bindings
        jump_btn.Bind(   wx.EVT_BUTTON,         self._on_jump)
        refresh_btn.Bind(wx.EVT_BUTTON,         self._on_refresh)
        close_btn.Bind(  wx.EVT_BUTTON,         lambda e: self.Hide())
        self.Bind(       wx.EVT_CLOSE,          lambda e: self.Hide())

        # Enter on list item = jump; double-click = jump
        self._listbox.Bind(wx.EVT_LISTBOX_DCLICK, self._on_jump)
        self._listbox.Bind(wx.EVT_KEY_DOWN,       self._on_list_key)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Scan the editor and repopulate the heading list."""
        self._listbox.Clear()
        self._positions.clear()

        # Editor (RICHEDIT) returns (line_no, char_pos, style); WebEditor
        # returns (index, dom_id, style).  We adapt to both.
        is_web = self._editor.ctrl is None

        for first, second, style in self._editor.heading_positions():
            level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
            if is_web:
                text = self._editor.heading_text(first)
                target = second           # dom_id
            else:
                text = self._editor.ctrl.GetLineText(first).strip()
                target = second           # char position
            indent = _LEVEL_INDENT * (level - 1)
            label  = f"{indent}H{level}: {text[:70]}"
            self._listbox.Append(label)
            self._positions.append(target)

        if self._listbox.GetCount() == 0:
            self._listbox.Append("(No headings found — apply Heading styles to text)")
            self._positions.append(-1)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_jump(self, event=None) -> None:
        idx = self._listbox.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._positions):
            return
        target = self._positions[idx]
        if target == -1:
            return
        if self._editor.ctrl is None:
            # WebEditor — jump by DOM id
            self._editor.go_to_heading(target)
        else:
            ctrl = self._editor.ctrl
            ctrl.SetInsertionPoint(target)
            ctrl.ShowPosition(target)
            ctrl.SetFocus()

    def _on_refresh(self, event=None) -> None:
        self.refresh()
        if self._listbox.GetCount() > 0:
            self._listbox.SetSelection(0)
        self._listbox.SetFocus()

    def _on_list_key(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN:
            self._on_jump()
        elif key == wx.WXK_ESCAPE:
            if self._editor.ctrl is not None:
                self._editor.ctrl.SetFocus()
            else:
                self._editor.SetFocus()
        else:
            event.Skip()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_and_refresh(self) -> None:
        self.refresh()
        if self._listbox.GetCount() > 0:
            self._listbox.SetSelection(0)
        self.Show()
        self.Raise()
        self._listbox.SetFocus()
