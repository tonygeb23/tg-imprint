"""The toolbar: drawn icons, words, tooltips that name the key.

Every tool is a keymap entry, so the label, the tooltip and the handler come
from the same list as the menus. The bitmaps are drawn in the palette's
colours at the size the DPI asks for (icons.py) and redrawn when the colours
change, so they hold up at 150 percent, on the dark themes and in High
Contrast. Toggle state follows the editor's own state messages; the
accessible name of a tool never changes on a value change.

The bar is short on purpose: what a person reaches for while writing, in
groups, and the two things they came here to do at the end. Alignment,
underline, strikethrough and quote left it in 0.3.0 and stayed in the Format
menu with their keys.

On a dark theme the Windows toolbar control will not draw a light label
(theme.py), so the word goes into the bitmap as well as the icon. That is
"drawn" below. The tool's tooltip is the same in both.
"""
import wx

from . import icons
from . import keymap
from . import theme

#: What the bar shows, in order. None is a separator; "style" is the
#: paragraph style choice.
LAYOUT = ("new", "open", "save", None, "style", None, "bold", "italic", None,
          "bullets", "numbers", None, "insert_link", "insert_picture",
          "insert_table", None, "check_document", "export_pdf")

#: The short label each tool shows when labels are on. A toolbar label is
#: read by a screen reader from the accessible name, not from this, so these
#: are for the eye: as short as they can be and still mean something.
SHORT = {"insert_link": "Link", "insert_picture": "Picture",
         "insert_table": "Table", "export_pdf": "Export PDF",
         "check_document": "Check", "bullets": "Bullets", "numbers": "Numbers"}

#: Where the tooltip should say more than the menu label does: Export PDF
#: sits under File, Export as, where its label is only "PDF".
TIPS = {"export_pdf": "Export PDF"}

#: The tools that keep their label when the bar is squeezed.
#:
#: Measured 2026-11-01 on a 1920 by 1080 display, the bar alone, in pixels:
#:
#:                     100 percent   150 percent
#:   icons only            529           598
#:   icons with labels     949          1390
#:   squeezed              661           898
#:   labels only           949          1390
#:
#: The smallest window is 640 by 440 at 100 percent and 960 by 660 at 150, so
#: at 100 percent only the icons fit it, which is why there is a squeeze 2.
#:
#: Words alone are no narrower than words under icons: with TB_NOICONS wx
#: still sizes every button to the widest label, and it only saves height.
#:
#: So the full labelled bar fits any window the side panel is shown in, and
#: the squeeze is for a window somebody has made smaller. Then these tools
#: keep their words and the rest fall back to their icon. Windows sizes every
#: button to the widest word on the bar, so Export PDF says PDF when squeezed.
#: At the very narrowest, squeeze 2, not even those fit and the bar goes to
#: icons rather than clip tools off its end: a tool that is not there cannot
#: be clicked at all, and its tooltip and its menu item still have the word.
KEEP_LABEL = ("new", "open", "save", "check_document", "export_pdf")
SQUEEZED = {"export_pdf": "PDF"}

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


class _ToolNames(wx.Accessible):
    """Each button's name. A toolbar button's name is its text, and a drawn
    tool or an icon has none, so without this a screen reader reads a blank
    button (measured by the 0.3.0 audit). Child ids count every slot on the
    bar, separators included."""

    def __init__(self, names):
        super().__init__()
        self.names = names

    def GetName(self, childId):
        if 0 < childId <= len(self.names) and self.names[childId - 1]:
            return (wx.ACC_OK, self.names[childId - 1])
        return (wx.ACC_NOT_IMPLEMENTED, "")


class EditorToolBar(wx.ToolBar):
    """The bar, in the shape the Display page asks for.

    `mode` is "icons", "icons_labels" or "labels" (settings.TOOLBAR_LABEL_MODES).
    Somebody who cannot make out a 20 pixel glyph asked for words, so the
    choice is honoured: the bar is never silently turned back into icons.
    When the labelled bar is wider than the window, `squeeze` is what gives
    instead, and every tool keeps its tooltip and its accessible name
    whatever is drawn.
    """

    def __init__(self, frame, id_of, mode="icons_labels", squeeze=0, pal=None):
        mode = mode if mode in ("icons", "icons_labels", "labels") else "icons_labels"
        self.pal = pal if pal is not None else theme.palette("high_contrast")
        self.drawn = self.pal.drawn_labels
        style = wx.TB_HORIZONTAL | wx.TB_FLAT | wx.TB_NODIVIDER
        if mode != "icons" and not self.drawn:
            style |= wx.TB_TEXT
        if mode == "labels" and not self.drawn:
            style |= wx.TB_NOICONS
        super().__init__(frame, style=style)
        self.frame = frame
        self.id_of = id_of
        self.mode = mode
        self.squeeze = int(squeeze)
        self.show_labels = mode != "icons"
        self._tools = {}
        self._syncing = False
        self._pressed = {}
        scale = frame.GetDPIScaleFactor()
        self._scale = scale
        self._size = int(round(22 * scale))
        self._cell = self._cell_size()
        self.SetToolBitmapSize(wx.Size(*self._cell))
        self.SetMargins(int(round(6 * scale)), int(round(3 * scale)))
        if not self.pal.native:
            self.SetBackgroundColour(self.pal.chrome)
        for item in LAYOUT:
            if item is None:
                self.AddSeparator()
            elif item == "style":
                self._add_style_choice()
            else:
                self._add_tool(item)
        self.Realize()
        # Stored on the bar: wx does not take ownership of an accessible.
        self._tgimprint_accessible = _ToolNames(
            ["" if item is None else ("Paragraph style" if item == "style"
                                      else TIPS.get(item, keymap.entry(item).plain_label.rstrip(".")))
             for item in LAYOUT])
        self.SetAccessible(self._tgimprint_accessible)
        if self.drawn:
            theme.plain_toolbar(self)
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self._on_colours)

    def _cell_size(self):
        """The bitmap size: the glyph, or in the drawn shape the glyph and
        the widest word on the bar, because every tool shares one size."""
        if not self.drawn:
            return (self._size, self._size)
        probe = wx.MemoryDC(wx.Bitmap(4, 4))
        gc = wx.GraphicsContext.Create(probe)
        gc.SetFont(gc.CreateFont(icons.LABEL_PIXELS * self._scale, "Segoe UI", 0, wx.BLACK))
        words = [self.label_for(item) for item in LAYOUT if item not in (None, "style")]
        widest = max([gc.GetTextExtent(word)[0] for word in words if word] or [0])
        probe.SelectObject(wx.NullBitmap)
        width = int(max(self._size, widest)) + int(round(14 * self._scale))
        tall = int(round(20 * self._scale))
        if self.mode == "labels":
            return (width, tall + int(round(6 * self._scale)))
        if self.mode == "icons" or not any(words):
            return (self._size + int(round(8 * self._scale)),
                    self._size + int(round(8 * self._scale)))
        return (width, self._size + tall)

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
        if self.squeeze:
            short = SQUEEZED.get(action, short)
        if self.mode == "icons_labels":
            if self.squeeze > 1 or (self.squeeze and action not in KEEP_LABEL):
                return ""
        return short

    def _bitmap(self, action, pressed=False):
        if not self.drawn:
            return icons.draw(action, self._size, self.pal)
        return icons.labelled(action, self.label_for(action), self._cell[0], self._cell[1],
                              self._size, self.pal, show_icon=self.mode != "labels",
                              pressed=pressed, scale=self._scale)

    def _add_tool(self, action):
        entry = keymap.entry(action)
        label = TIPS.get(action, entry.plain_label.rstrip("."))
        kind = wx.ITEM_CHECK if entry.kind == "check" else wx.ITEM_NORMAL
        tip = label + (" (%s)" % entry.primary if entry.primary else "")
        tool = self.AddTool(self.id_of(action), "" if self.drawn else self.label_for(action),
                            self._bitmap(action), shortHelp=tip, kind=kind)
        # The label on the bar can be squeezed away; the name a screen
        # reader reads never is.
        tool.SetLongHelp(tip)
        self._tools[action] = tool

    def _add_style_choice(self):
        self.style = wx.Choice(self, choices=[s[0] for s in STYLES],
                               size=wx.Size(int(round(138 * self._scale)), -1))
        self.style.SetSelection(0)
        self.style.SetName("Paragraph style")
        self.style.SetToolTip("Paragraph style. Ctrl+Alt+1 to 6 for headings, "
                              "Ctrl+Alt+0 normal text, Ctrl+Alt+8 bullets, "
                              "Ctrl+Alt+9 numbers, Ctrl+Q quote.")
        self.style.Bind(wx.EVT_CHOICE, self._on_style)
        if not self.pal.native and self.pal.name != "normal":
            self.style.SetBackgroundColour(self.pal.raised)
            self.style.SetForegroundColour(self.pal.ink)
            theme.dark_choice(self.style)
        # A choice on a toolbar has no static in front of it, so it gets an
        # accessible object of its own. It carries no word on the bar: the
        # value it shows already says what it is.
        from .dialogs import name_field
        name_field(self.style, "Paragraph style")
        self.AddControl(self.style, "")

    def _on_style(self, _event):
        if self._syncing:
            return
        index = self.style.GetSelection()
        if index < 0:
            return
        action = STYLES[index][1]
        self.frame.perform(action)
        self.frame.editor.focus()

    def _on_colours(self, event):
        for action, tool in self._tools.items():
            try:
                self.SetToolNormalBitmap(tool.GetId(), self._bitmap(action))
            except Exception:
                pass
        self.Refresh()
        event.Skip()

    # ------------------------------------------------------------ state --
    def sync(self, state):
        """Reflect the editor's selection state. Called on every state message."""
        self._syncing = True
        try:
            for action in ("bold", "italic"):
                tool = self._tools.get(action)
                if tool is None:
                    continue
                on = bool(state.get(action))
                self.ToggleTool(tool.GetId(), on)
                if self.drawn and self._pressed.get(action, False) != on:
                    self._pressed[action] = on
                    self.SetToolNormalBitmap(tool.GetId(), self._bitmap(action, pressed=on))
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
