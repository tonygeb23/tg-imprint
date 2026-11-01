"""Icons, drawn rather than loaded, on one grid in one hand.

Every glyph is drawn with a GraphicsContext at the size the DPI asks for, so
it is crisp at 100, 150 and 200 percent and no image file can go missing from
a build. Names are the keymap actions the toolbar shows, plus the marks the
start screen and the side panel use.

The hand: a 24 unit grid, a 1.8 unit round stroke in the ink colour, and one
accent per glyph on the part that says what the tool does. The accent comes
from the palette (theme.py). In Windows High Contrast the palette is the
system's and ink and accent are both the button text colour, so the glyphs
follow whatever the person chose, one colour and no fills, and they are
redrawn on EVT_SYS_COLOUR_CHANGED.

Every icon sits beside its word or carries one in its accessible name. The
colour repeats the word and never replaces it.
"""
import wx

from . import theme

#: The glyphs the toolbar has, in the order it shows them.
NAMES = ("new", "open", "save", "bold", "italic", "bullets", "numbers",
         "insert_link", "insert_picture", "insert_table", "check_document",
         "export_pdf")
#: The word in a drawn toolbar cell, in pixels at 100 percent: the size of the
#: menu text, so the words on a dark bar match the words on a light one.
LABEL_PIXELS = 12.5
#: The marks that are not tools.
MARKS = ("make_accessible", "check_pdf", "repair_pdf", "fill_form", "fix", "review")


def _default_palette():
    return theme.palette("high_contrast")


def _canvas(size):
    bmp = wx.Bitmap(size, size, 32)
    bmp.UseAlpha()
    return bmp


class Kit:
    """What every painter draws with."""

    def __init__(self, gc, u, pal):
        self.gc = gc
        self.u = u
        self.pal = pal
        self.line = max(1.25, 1.8 * u)
        self.pen = self._pen(pal.ink, self.line)
        self.strong = self._pen(pal.accent, max(1.5, 2.2 * u))
        self.fill = gc.CreateBrush(wx.Brush(pal.ink))
        self.accent_fill = gc.CreateBrush(wx.Brush(pal.accent))
        # A fill is one colour too many in high contrast and on yellow.
        self.has_tint = not pal.native and pal.name != "yellow_on_black"
        self.tint = gc.CreateBrush(wx.Brush(pal.tint)) if self.has_tint else None

    def _pen(self, colour, width):
        return self.gc.CreatePen(wx.GraphicsPenInfo(colour).Width(width)
                                 .Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND))

    def line_to(self, x0, y0, x1, y1):
        u = self.u
        self.gc.StrokeLine(x0 * u, y0 * u, x1 * u, y1 * u)

    def poly(self, points, close=False, fill=None):
        u = self.u
        path = self.gc.CreatePath()
        path.MoveToPoint(points[0][0] * u, points[0][1] * u)
        for x, y in points[1:]:
            path.AddLineToPoint(x * u, y * u)
        if close:
            path.CloseSubpath()
        if fill is not None:
            self.gc.SetBrush(fill)
            self.gc.FillPath(path)
        self.gc.StrokePath(path)

    def rounded(self, x, y, w, h, r, fill=None):
        u = self.u
        path = self.gc.CreatePath()
        path.AddRoundedRectangle(x * u, y * u, w * u, h * u, r * u)
        if fill is not None:
            self.gc.SetBrush(fill)
            self.gc.FillPath(path)
        self.gc.StrokePath(path)

    def dot(self, x, y, r, brush):
        u = self.u
        path = self.gc.CreatePath()
        path.AddCircle(x * u, y * u, r * u)
        self.gc.SetBrush(brush)
        self.gc.FillPath(path)

    def letter(self, text, size, colour, face="Georgia", bold=False, italic=False, y=12.0, x=12.0):
        flags = (wx.FONTFLAG_BOLD if bold else 0) | (wx.FONTFLAG_ITALIC if italic else 0)
        self.gc.SetFont(self.gc.CreateFont(max(6.0, size * self.u), face, flags, colour))
        w, h = self.gc.GetTextExtent(text)
        self.gc.DrawText(text, x * self.u - w / 2, y * self.u - h / 2)


def draw(name, size, pal=None):
    """The glyph at `size` pixels square, with alpha."""
    pal = pal if pal is not None else _default_palette()
    bmp = _canvas(size)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
    gc.SetInterpolationQuality(wx.INTERPOLATION_BEST)
    kit = Kit(gc, size / 24.0, pal)
    gc.SetPen(kit.pen)
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    _PAINTERS.get(name, _blank)(kit)
    dc.SelectObject(wx.NullBitmap)
    return bmp


# ----------------------------------------------------------------- glyphs --

def _page(kit, x=5, right=19):
    corner = right - 5
    kit.poly([(x, 3), (corner, 3), (right, 8), (right, 21), (x, 21)], close=True)
    kit.poly([(corner, 3), (corner, 8), (right, 8)])


def _new(kit):
    _page(kit)
    kit.gc.SetPen(kit.strong)
    kit.line_to(12, 11, 12, 18)
    kit.line_to(8.5, 14.5, 15.5, 14.5)


def _open(kit):
    kit.poly([(3, 19), (3, 5.5), (9, 5.5), (11, 8), (20, 8), (20, 11)])
    kit.gc.SetPen(kit.strong if not kit.has_tint else kit.pen)
    kit.poly([(3, 19), (6, 11), (22, 11), (19, 19)], close=True, fill=kit.tint)


def _save(kit):
    kit.poly([(4, 4), (17, 4), (20, 7), (20, 20), (4, 20)], close=True)
    kit.poly([(8, 4), (8, 9), (15, 9), (15, 4)])
    kit.gc.SetPen(kit.strong)
    kit.poly([(8, 20), (8, 14), (16, 14), (16, 20)])


def _bold(kit):
    kit.letter("B", 21, kit.pal.ink, bold=True)


def _italic(kit):
    kit.letter("I", 21, kit.pal.ink, italic=True)


def _rows(kit, left, ys, right=21):
    for y in ys:
        kit.line_to(left, y, right, y)


def _bullets(kit):
    for y in (6, 12, 18):
        kit.dot(5, y, 2.1, kit.accent_fill)
    _rows(kit, 10.5, (6, 12, 18))


def _numbers(kit):
    kit.letter("1", 11.5, kit.pal.accent, face="Segoe UI", bold=True, x=5.5, y=7.2)
    kit.letter("2", 11.5, kit.pal.accent, face="Segoe UI", bold=True, x=5.5, y=17.2)
    _rows(kit, 11, (7.5, 16.5))


def _link(kit):
    kit.rounded(2.5, 8.5, 12, 7, 3.5)
    kit.gc.SetPen(kit.strong)
    kit.gc.SetBrush(wx.TRANSPARENT_BRUSH)
    kit.rounded(9.5, 8.5, 12, 7, 3.5)


def _picture(kit):
    kit.rounded(3, 4, 18, 16, 2)
    kit.dot(15.5, 9.5, 2.1, kit.accent_fill)
    kit.poly([(3.5, 18.5), (9, 12), (13, 16), (15.5, 13.5), (20.5, 18.5)])


def _table(kit):
    if kit.has_tint:
        kit.gc.SetPen(wx.TRANSPARENT_PEN)
        kit.gc.SetBrush(kit.tint)
        kit.gc.DrawRectangle(3 * kit.u, 4 * kit.u, 18 * kit.u, 5.5 * kit.u)
        kit.gc.SetPen(kit.pen)
    kit.gc.SetBrush(wx.TRANSPARENT_BRUSH)
    kit.rounded(3, 4, 18, 16, 2)
    kit.line_to(3, 9.5, 21, 9.5)
    kit.line_to(3, 14.75, 21, 14.75)
    kit.line_to(9, 9.5, 9, 20)
    kit.line_to(15, 9.5, 15, 20)


def _check(kit):
    u = kit.u
    path = kit.gc.CreatePath()
    path.AddCircle(12 * u, 12 * u, 9 * u)
    kit.gc.StrokePath(path)
    kit.gc.SetPen(kit.strong)
    kit.poly([(7.8, 12.4), (10.8, 15.4), (16.4, 9)])


def _export(kit):
    _page(kit, x=4, right=17)
    kit.gc.SetPen(kit.strong)
    kit.line_to(9, 14, 21, 14)
    kit.poly([(17.5, 10.5), (21, 14), (17.5, 17.5)])


def _make_accessible(kit):
    _page(kit)
    kit.gc.SetPen(kit.strong)
    kit.poly([(8.5, 14.5), (11, 17), (15.5, 11.5)])


def _analyse(kit):
    u = kit.u
    path = kit.gc.CreatePath()
    path.AddCircle(10.5 * u, 10.5 * u, 6.8 * u)
    kit.gc.StrokePath(path)
    kit.gc.SetPen(kit.strong)
    kit.line_to(15.6, 15.6, 21, 21)


def _repair(kit):
    # A sticking plaster, on the diagonal: two strokes and a middle.
    kit.poly([(4.5, 14), (14, 4.5), (19.5, 10), (10, 19.5)], close=True)
    kit.gc.SetPen(kit.strong)
    kit.line_to(10, 10, 14, 14)
    kit.line_to(14, 10, 10, 14)


def _fill_form(kit):
    _rows(kit, 3.5, (6, 12), right=20.5)
    kit.gc.SetPen(kit.strong)
    kit.poly([(3.5, 18.5), (8, 18.5)])
    kit.poly([(12, 20), (20.5, 11.5)])


def _fix(kit):
    kit.dot(12, 12, 9.5, kit.accent_fill)
    knockout = wx.Colour(kit.pal.chrome)
    kit.gc.SetPen(kit._pen(knockout, 2.6 * kit.u))
    kit.line_to(12, 7, 12, 13)
    kit.dot(12, 17, 1.6, kit.gc.CreateBrush(wx.Brush(knockout)))


def _review(kit):
    u = kit.u
    path = kit.gc.CreatePath()
    path.AddCircle(12 * u, 12 * u, 8.6 * u)
    kit.gc.SetPen(kit._pen(kit.pal.second, 2.2 * u))
    kit.gc.StrokePath(path)
    kit.dot(12, 12, 2.2, kit.gc.CreateBrush(wx.Brush(kit.pal.second)))


def _blank(kit):
    kit.rounded(4, 4, 16, 16, 2)


_PAINTERS = {
    "new": _new, "open": _open, "save": _save, "bold": _bold, "italic": _italic,
    "bullets": _bullets, "numbers": _numbers, "insert_link": _link,
    "insert_picture": _picture, "insert_table": _table, "check_document": _check,
    "export_pdf": _export, "make_accessible": _make_accessible, "check_pdf": _analyse,
    "repair_pdf": _repair, "fill_form": _fill_form, "fix": _fix, "review": _review,
}


def labelled(name, word, width, height, icon_size, pal, show_icon=True, pressed=False,
             scale=1.0):
    """One toolbar cell with the word drawn in it.

    The Windows toolbar control ignores a foreground colour, so on a dark
    theme a real label is black on near black (measured, theme.py). The word
    goes in the bitmap instead, in the palette's ink. The tool keeps its real
    tooltip and name either way. `pressed` draws the "on" state in the cell,
    because the control's own highlight is a pale blue that buries light ink.
    """
    bmp = wx.Bitmap(width, height, 32)
    bmp.UseAlpha()
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
    ink = pal.ink
    if pressed:
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, width, height, 4 * scale)
        gc.SetBrush(gc.CreateBrush(wx.Brush(pal.selected)))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.FillPath(path)
        ink = pal.selected_ink
    gap = int(round(2 * scale))
    gc.SetFont(gc.CreateFont(LABEL_PIXELS * scale, "Segoe UI", 0, ink))
    text_w, text_h = gc.GetTextExtent(word) if word else (0, 0)
    drawn_h = (icon_size if show_icon else 0) + (gap + text_h if word and show_icon else text_h)
    top = (height - drawn_h) / 2
    if show_icon:
        glyph = pal
        if pressed:
            glyph = _Pressed(pal)
        gc.DrawBitmap(draw(name, icon_size, glyph), (width - icon_size) / 2, top,
                      icon_size, icon_size)
        top += icon_size + gap
    if word:
        gc.DrawText(word, (width - text_w) / 2, top)
    dc.SelectObject(wx.NullBitmap)
    return bmp


class _Pressed:
    """The palette a glyph is drawn with on the "on" highlight."""

    def __init__(self, pal):
        self.__dict__.update(pal.__dict__)
        self.ink = pal.selected_ink
        self.accent = pal.selected_ink
        self.second = pal.selected_ink


def sheet(size=24, columns=9, pal=None):
    """Every icon on one bitmap, for a look at them all at once."""
    pal = pal if pal is not None else _default_palette()
    names = NAMES + MARKS
    rows = (len(names) + columns - 1) // columns
    pad = 8
    out = wx.Bitmap(columns * (size + pad) + pad, rows * (size + pad) + pad, 32)
    dc = wx.MemoryDC(out)
    dc.SetBackground(wx.Brush(pal.chrome))
    dc.Clear()
    for index, name in enumerate(names):
        x = pad + (index % columns) * (size + pad)
        y = pad + (index // columns) * (size + pad)
        dc.DrawBitmap(draw(name, size, pal), x, y, True)
    dc.SelectObject(wx.NullBitmap)
    return out
