"""The toolbar: drawn icons, text labels, tooltips that name the key.

Every tool is a keymap entry, so the label, the tooltip and the handler come
from the same list as the menus. The bitmaps are drawn in system colours at
the size the DPI asks for (icons.py) and redrawn when the colours change, so
they hold up at 150 percent and in High Contrast. Toggle state follows the
editor's own state messages; the accessible name of a tool never changes on
a value change.
"""
import wx

from . import icons
from . import keymap

#: What the bar shows, in order. None is a separator; "style" is the
#: paragraph style choice.
LAYOUT = ("new", "open", "save", None, "style", None, "bold", "italic",
          "underline", "strike", None, "bullets", "numbers", "quote", None,
          "align_left", "align_center", "align_right", "align_justify", None,
          "insert_link", "insert_picture", "insert_table", None, "export_pdf")

#: The paragraph style choice, in the order it lists them, each naming the
#: keymap action that applies it and the block names the editor reports.
STYLES = (("Normal text", "normal", ("p",)),
          ("Heading 1", "heading1", ("h1",)),
          ("Heading 2", "heading2", ("h2",)),
          ("Heading 3", "heading3", ("h3",)),
          ("Heading 4", "heading4", ("h4",)),
          ("Heading 5", "heading5", ("h5",)),
          ("Heading 6", "heading6", ("h6",)),
          ("Bullet list", "bullets", ("ul",)),
          ("Numbered list", "numbers", ("ol",)),
          ("Quote", "quote", ("blockquote",)))


class EditorToolBar(wx.ToolBar):
    def __init__(self, frame, id_of, show_labels=True):
        style = wx.TB_HORIZONTAL | wx.TB_FLAT
        if show_labels:
            style |= wx.TB_TEXT
        super().__init__(frame, style=style)
        self.frame = frame
        self.id_of = id_of
        self.show_labels = bool(show_labels)
        self._tools = {}
        self._syncing = False
        size = int(round(20 * frame.GetDPIScaleFactor()))
        self.SetToolBitmapSize(wx.Size(size, size))
        self._size = size
        for item in LAYOUT:
            if item is None:
                self.AddSeparator()
            elif item == "style":
                self._add_style_choice()
            else:
                self._add_tool(item)
        self.Realize()
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self._on_colours)

    def needed_width(self):
        """The width every tool needs, as laid out. Measured 2026-09-09: with
        labels at 150 percent the bar is about 1950 pixels, wider than a
        1920 pixel display even maximised, so the last tools were clipped.
        The window compares this with its client width and rebuilds the
        bar without labels when they do not fit (the labels stay in the
        tooltips and the accessible names)."""
        return self.GetBestSize().width

    def _add_tool(self, action):
        entry = keymap.entry(action)
        label = entry.plain_label.rstrip(".")
        short = {"insert_link": "Link", "insert_picture": "Picture",
                 "insert_table": "Table", "export_pdf": "Export PDF",
                 "align_left": "Left", "align_center": "Centre",
                 "align_right": "Right", "align_justify": "Justify",
                 "strike": "Strike", "bullets": "Bullets", "numbers": "Numbers",
                 "normal": "Normal"}.get(action, label)
        kind = wx.ITEM_CHECK if entry.kind == "check" else wx.ITEM_NORMAL
        tip = label + (" (%s)" % entry.primary if entry.primary else "")
        tool = self.AddTool(self.id_of(action), short, icons.draw(action, self._size),
                            shortHelp=tip, kind=kind)
        self._tools[action] = tool

    def _add_style_choice(self):
        self.style = wx.Choice(self, choices=[s[0] for s in STYLES])
        self.style.SetSelection(0)
        self.style.SetName("Paragraph style")
        self.style.SetToolTip("Paragraph style. Ctrl+Alt+1 to 6 for headings, "
                              "Ctrl+Alt+0 normal text, Ctrl+Alt+8 bullets, "
                              "Ctrl+Alt+9 numbers, Ctrl+Q quote.")
        self.style.Bind(wx.EVT_CHOICE, self._on_style)
        # A choice on a toolbar has no static in front of it, so it gets an
        # accessible object of its own.
        from .dialogs import name_field
        name_field(self.style, "Paragraph style")
        self.AddControl(self.style, "Paragraph style")

    def _on_style(self, _event):
        if self._syncing:
            return
        index = self.style.GetSelection()
        if index < 0:
            return
        action = STYLES[index][1]
        handler = getattr(self.frame, "on_" + action, None)
        if handler is not None:
            handler(None)
            self.frame.editor.focus()

    def _on_colours(self, event):
        for action, tool in self._tools.items():
            try:
                self.SetToolNormalBitmap(tool.GetId(), icons.draw(action, self._size))
            except Exception:
                pass
        self.Refresh()
        event.Skip()

    # ------------------------------------------------------------ state --
    def sync(self, state):
        """Reflect the editor's selection state. Called on every state message."""
        self._syncing = True
        try:
            for action in ("bold", "italic", "underline", "strike"):
                tool = self._tools.get(action)
                if tool is not None:
                    self.ToggleTool(tool.GetId(), bool(state.get(action)))
            block = state.get("block") or "p"
            if state.get("quote") and block == "p":
                block = "blockquote"
            for index, (_label, _action, blocks) in enumerate(STYLES):
                if block in blocks:
                    if self.style.GetSelection() != index:
                        self.style.SetSelection(index)
                    break
        finally:
            self._syncing = False
