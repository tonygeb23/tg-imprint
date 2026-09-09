import wx
from ui.editor import _STYLE_CFG

_PARA_STYLES = [
    "Normal",
    "Heading 1", "Heading 2", "Heading 3",
    "Heading 4", "Heading 5", "Heading 6",
    "Bullet List", "Numbered List",
    "Block Quote",
]


class FormattingToolbar(wx.ToolBar):
    """
    Formatting toolbar.

    Every control has SetName() / SetToolTip() so NVDA announces it on
    Tab + arrow-key navigation.

    Layout (left → right):
      [Style] [Size]  |  [Bold] [Italic] [Underline]  |
      [Left] [Center] [Right] [Justify]  |  [Image]
    """

    def __init__(self, parent: wx.Frame) -> None:
        super().__init__(parent, style=wx.TB_HORIZONTAL | wx.TB_TEXT | wx.TB_NOICONS)
        self._parent   = parent
        self._editor   = None
        self._updating = False

        self._build()
        self.Realize()

    def set_editor(self, editor) -> None:
        self._editor = editor

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        _bmp = lambda: wx.ArtProvider.GetBitmap(
            wx.ART_NORMAL_FILE, wx.ART_TOOLBAR, (16, 16)
        )

        # ---- Paragraph style picker ----
        self.AddControl(wx.StaticText(self, label="Style:"))
        self._style_choice = wx.Choice(self, choices=_PARA_STYLES)
        self._style_choice.SetSelection(0)
        self._style_choice.SetName("Paragraph style")
        self._style_choice.SetToolTip(
            "Paragraph style. "
            "Ctrl+Alt+1–6 for Heading 1–6, "
            "Ctrl+Alt+0 Normal, Ctrl+Alt+8 Bullet, Ctrl+Alt+9 Numbered, "
            "Ctrl+Q Block Quote."
        )
        self.AddControl(self._style_choice)

        self.AddSeparator()

        # ---- Font size spinner ----
        self.AddControl(wx.StaticText(self, label="Size:"))
        self._size_ctrl = wx.SpinCtrl(
            self, min=6, max=144, initial=11,
            style=wx.SP_ARROW_KEYS | wx.TE_PROCESS_ENTER,
            size=(56, -1),
        )
        self._size_ctrl.SetName("Font size in points")
        self._size_ctrl.SetToolTip("Font size in points. Type a value or use Up/Down arrow keys.")
        self.AddControl(self._size_ctrl)

        self.AddSeparator()

        # ---- Character formatting toggles ----
        self._id_bold = wx.NewIdRef()
        self.AddTool(self._id_bold, "Bold",
                     _bmp(), shortHelp="Bold — Ctrl+B", kind=wx.ITEM_CHECK)

        self._id_italic = wx.NewIdRef()
        self.AddTool(self._id_italic, "Italic",
                     _bmp(), shortHelp="Italic — Ctrl+Shift+I", kind=wx.ITEM_CHECK)

        self._id_underline = wx.NewIdRef()
        self.AddTool(self._id_underline, "Underline",
                     _bmp(), shortHelp="Underline — Ctrl+U", kind=wx.ITEM_CHECK)

        self._id_strike = wx.NewIdRef()
        self.AddTool(self._id_strike, "Strike",
                     _bmp(), shortHelp="Strikethrough — Ctrl+Shift+K", kind=wx.ITEM_CHECK)

        self.AddSeparator()

        # ---- Paragraph alignment (radio group) ----
        self._id_align_left    = wx.NewIdRef()
        self._id_align_center  = wx.NewIdRef()
        self._id_align_right   = wx.NewIdRef()
        self._id_align_justify = wx.NewIdRef()

        self.AddTool(self._id_align_left,    "Left",
                     _bmp(), shortHelp="Align Left — Ctrl+L",    kind=wx.ITEM_RADIO)
        self.AddTool(self._id_align_center,  "Center",
                     _bmp(), shortHelp="Align Center — Ctrl+E",  kind=wx.ITEM_RADIO)
        self.AddTool(self._id_align_right,   "Right",
                     _bmp(), shortHelp="Align Right — Ctrl+R",   kind=wx.ITEM_RADIO)
        self.AddTool(self._id_align_justify, "Justify",
                     _bmp(), shortHelp="Justify — Ctrl+J",       kind=wx.ITEM_RADIO)
        self.ToggleTool(self._id_align_left, True)   # default state

        self.AddSeparator()

        # ---- Insert image ----
        self._id_image = wx.NewIdRef()
        self.AddTool(self._id_image, "Insert Image",
                     wx.ArtProvider.GetBitmap(wx.ART_ADD_BOOKMARK, wx.ART_TOOLBAR, (16, 16)),
                     shortHelp="Insert image with alt text — Ctrl+I")

        # ---- Bindings ----
        self._parent.Bind(wx.EVT_CHOICE,     self._on_style_choice, self._style_choice)
        self._parent.Bind(wx.EVT_SPINCTRL,   self._on_size_spin,    self._size_ctrl)
        self._parent.Bind(wx.EVT_TEXT_ENTER, self._on_size_enter,   self._size_ctrl)
        self._parent.Bind(wx.EVT_TOOL, self._on_bold,         id=self._id_bold)
        self._parent.Bind(wx.EVT_TOOL, self._on_italic,       id=self._id_italic)
        self._parent.Bind(wx.EVT_TOOL, self._on_underline,    id=self._id_underline)
        self._parent.Bind(wx.EVT_TOOL, self._on_strike,       id=self._id_strike)
        self._parent.Bind(wx.EVT_TOOL, self._on_align_left,   id=self._id_align_left)
        self._parent.Bind(wx.EVT_TOOL, self._on_align_center, id=self._id_align_center)
        self._parent.Bind(wx.EVT_TOOL, self._on_align_right,  id=self._id_align_right)
        self._parent.Bind(wx.EVT_TOOL, self._on_align_justify,id=self._id_align_justify)
        self._parent.Bind(wx.EVT_TOOL, self._on_insert_image, id=self._id_image)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_style_choice(self, event: wx.CommandEvent) -> None:
        if self._editor is None or self._updating:
            return
        sel = self._style_choice.GetString(self._style_choice.GetSelection())
        self._editor.apply_paragraph_style(sel)

    def _on_size_spin(self, event: wx.SpinEvent) -> None:
        if self._editor is None or self._updating:
            return
        self._apply_font_size(self._size_ctrl.GetValue())

    def _on_size_enter(self, event: wx.CommandEvent) -> None:
        if self._editor is None:
            return
        self._apply_font_size(self._size_ctrl.GetValue())
        if self._editor.ctrl is not None:
            self._editor.ctrl.SetFocus()

    def _apply_font_size(self, pt: int) -> None:
        """Apply font size while preserving all other character formatting."""
        if self._editor.ctrl is None:
            # WebEditor — use the standard execCommand fontSize (1-7)
            # mapped roughly to the chosen point size.  For finer control
            # the user can still change size via the Format → Font dialog.
            self._editor._js_call(
                "exec", "fontSize",
                str(min(7, max(1, round(pt / 6)))),
            )
            return
        s, e = self._editor.ctrl.GetSelection()
        if s == e:
            s, e = self._editor._effective_range()
        attr = wx.TextAttr()
        self._editor.ctrl.GetStyle(s, attr)   # read existing first
        attr.SetFontPointSize(pt)
        self._editor.ctrl.SetStyle(s, e, attr)
        default = wx.TextAttr()
        self._editor.ctrl.GetStyle(s, default)
        default.SetFontPointSize(pt)
        self._editor.ctrl.SetDefaultStyle(default)

    def _on_bold(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.toggle_bold()

    def _on_italic(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.toggle_italic()

    def _on_underline(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.toggle_underline()

    def _on_strike(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.toggle_strikethrough()

    def _on_align_left(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.apply_alignment("left")

    def _on_align_center(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.apply_alignment("center")

    def _on_align_right(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.apply_alignment("right")

    def _on_align_justify(self, event: wx.CommandEvent) -> None:
        if self._editor:
            self._editor.apply_alignment("justify")

    def _on_insert_image(self, event: wx.CommandEvent) -> None:
        from ui.image_dialog import ImageDialog
        if self._editor is None:
            return
        with ImageDialog(self._parent) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path, alt_text = dlg.get_result()
                self._editor.insert_image(path, alt_text)

    # ------------------------------------------------------------------
    # Sync controls to caret position
    # ------------------------------------------------------------------

    def sync_to_editor(self) -> None:
        """Update toolbar controls to reflect formatting at the current caret."""
        if self._editor is None:
            return
        self._updating = True
        try:
            style = self._editor.current_paragraph_style()
            if style in _PARA_STYLES:
                self._style_choice.SetSelection(_PARA_STYLES.index(style))

            if self._editor.ctrl is not None:
                # RICHEDIT path — read attribute directly from caret pos
                ip   = self._editor.ctrl.GetInsertionPoint()
                attr = wx.TextAttr()
                if self._editor.ctrl.GetStyle(ip, attr):
                    pt = attr.GetFontPointSize()
                    if pt and pt != self._size_ctrl.GetValue():
                        self._size_ctrl.SetValue(pt)

                    if attr.HasFontWeight():
                        self.ToggleTool(self._id_bold,
                                        attr.GetFontWeight() == wx.FONTWEIGHT_BOLD)
                    if attr.HasFontStyle():
                        self.ToggleTool(self._id_italic,
                                        attr.GetFontStyle() == wx.FONTSTYLE_ITALIC)
                    if attr.HasFontUnderlined():
                        self.ToggleTool(self._id_underline, attr.GetFontUnderlined())
            else:
                # WebEditor — character state was reported via JS bridge
                state = getattr(self._editor, "_char_state", {})
                self.ToggleTool(self._id_bold,      bool(state.get("bold")))
                self.ToggleTool(self._id_italic,    bool(state.get("italic")))
                self.ToggleTool(self._id_underline, bool(state.get("underline")))
                self.ToggleTool(self._id_strike,    bool(state.get("strikethrough")))

            # Alignment radio group
            align = self._editor.current_alignment()
            self.ToggleTool(self._id_align_left,    align == "left")
            self.ToggleTool(self._id_align_center,  align == "center")
            self.ToggleTool(self._id_align_right,   align == "right")
            self.ToggleTool(self._id_align_justify, align == "justify")

        finally:
            self._updating = False
