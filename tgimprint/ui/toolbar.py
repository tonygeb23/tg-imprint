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

#: The short label each tool shows when labels are on. A toolbar label is
#: read by a screen reader from the accessible name, not from this, so these
#: are for the eye: as short as they can be and still mean something.
SHORT = {"insert_link": "Link", "insert_picture": "Picture",
         "insert_table": "Table", "export_pdf": "PDF",
         "align_left": "Left", "align_center": "Centre",
         "align_right": "Right", "align_justify": "Justify",
         "strike": "Strike", "bullets": "Bullets", "numbers": "Numbers",
         "normal": "Normal", "underline": "Under"}

#: The tools that keep their label when the bar is squeezed.
#:
#: Measured 2026-09-09 on a 1920 by 1080 display, maximised, with the client
#: area 1280 wide at 100 percent and 1920 at 150:
#:
#:                     100 percent   150 percent
#:   icons only            640           686
#:   icons with labels    1162          1640
#:   squeezed              946          1280
#:   labels only          1162          1640
#:
#: Words alone are no narrower than words under icons: with TB_NOICONS wx
#: still sizes every button to the widest label, and it only saves height.
#:
#: So the full labelled bar fits a maximised window at both scales, and the
#: squeeze is for a window somebody has made smaller. Then these eight tools
#: keep their words and the rest fall back to their icon.
KEEP_LABEL = ("new", "open", "save", "bold", "bullets", "align_left",
              "insert_picture", "export_pdf")

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
    """The bar, in the shape the Display page asks for.

    `mode` is "icons", "icons_labels" or "labels" (settings.TOOLBAR_LABEL_MODES).
    Somebody who cannot make out a 20 pixel glyph asked for words, so the
    choice is honoured: the bar is never silently turned back into icons.
    When the labelled bar is wider than the window, `squeeze` is what gives
    instead, and every tool keeps its tooltip and its accessible name
    whatever is drawn.
    """

    def __init__(self, frame, id_of, mode="icons_labels", squeeze=0):
        mode = mode if mode in ("icons", "icons_labels", "labels") else "icons_labels"
        style = wx.TB_HORIZONTAL | wx.TB_FLAT
        if mode != "icons":
            style |= wx.TB_TEXT
        if mode == "labels":
            style |= wx.TB_NOICONS
        super().__init__(frame, style=style)
        self.frame = frame
        self.id_of = id_of
        self.mode = mode
        self.squeeze = int(squeeze)
        self.show_labels = mode != "icons"
        self._tools = {}
        self._syncing = False
        size = int(round(20 * frame.GetDPIScaleFactor()))
        self._size = size
        self.SetToolBitmapSize(wx.Size(size, size))
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
        """The width every tool needs, as laid out. The window compares this
        with its client width and squeezes the labels when they do not
        fit, rather than throwing the person's choice away."""
        return self.GetBestSize().width

    def label_for(self, action):
        """The word this tool shows, which is "" when it shows none."""
        if self.mode == "icons":
            return ""
        short = SHORT.get(action, keymap.entry(action).plain_label.rstrip("."))
        if self.squeeze and self.mode == "icons_labels" and action not in KEEP_LABEL:
            return ""
        return short

    def _add_tool(self, action):
        entry = keymap.entry(action)
        label = entry.plain_label.rstrip(".")
        kind = wx.ITEM_CHECK if entry.kind == "check" else wx.ITEM_NORMAL
        tip = label + (" (%s)" % entry.primary if entry.primary else "")
        tool = self.AddTool(self.id_of(action), self.label_for(action),
                            icons.draw(action, self._size),
                            shortHelp=tip, kind=kind)
        # The label on the bar can be squeezed away; the name a screen
        # reader reads never is.
        tool.SetLongHelp(tip)
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
