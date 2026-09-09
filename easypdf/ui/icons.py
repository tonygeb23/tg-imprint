"""Toolbar icons, drawn rather than loaded.

Drawn with a GraphicsContext at the size the DPI asks for, in the system
colours from wx.SystemSettings, so they are crisp at 150 and 200 percent and
hold up in Windows High Contrast (the toolbar redraws them on
EVT_SYS_COLOUR_CHANGED). No image file can go missing from a build.

Every glyph is a few strokes on a 24 unit grid; `draw(name, size)` returns a
wx.Bitmap with alpha. Names are the keymap actions the toolbar shows.
"""
import wx

#: The glyphs the toolbar has, in the order it shows them.
NAMES = ("new", "open", "save", "bold", "italic", "underline", "strike",
         "bullets", "numbers", "quote", "align_left", "align_center",
         "align_right", "align_justify", "insert_link", "insert_picture",
         "insert_table", "export_pdf")


def ink():
    """The stroke colour: the text colour of a button, which High Contrast
    themes set to something readable on their button face."""
    return wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)


def accent():
    """One accent for the export mark: the highlight colour, so it follows
    the theme rather than fighting it."""
    return wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)


def draw(name, size):
    bmp = wx.Bitmap(size, size, 32)
    bmp.UseAlpha()
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
    u = size / 24.0
    line = max(1.5, 2.0 * u)
    colour = ink()
    pen = gc.CreatePen(wx.GraphicsPenInfo(colour).Width(line).Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND))
    gc.SetPen(pen)
    gc.SetBrush(wx.TRANSPARENT_BRUSH)
    fill = gc.CreateBrush(wx.Brush(colour))
    painter = _PAINTERS.get(name, _blank)
    painter(gc, u, pen, fill, colour)
    dc.SelectObject(wx.NullBitmap)
    return bmp


def _page_outline(gc, u):
    path = gc.CreatePath()
    path.MoveToPoint(6 * u, 3 * u)
    path.AddLineToPoint(14 * u, 3 * u)
    path.AddLineToPoint(18 * u, 7 * u)
    path.AddLineToPoint(18 * u, 21 * u)
    path.AddLineToPoint(6 * u, 21 * u)
    path.CloseSubpath()
    gc.StrokePath(path)
    gc.StrokeLine(14 * u, 3 * u, 14 * u, 7 * u)
    gc.StrokeLine(14 * u, 7 * u, 18 * u, 7 * u)


def _new(gc, u, pen, fill, colour):
    _page_outline(gc, u)
    gc.StrokeLine(12 * u, 10 * u, 12 * u, 17 * u)
    gc.StrokeLine(8.5 * u, 13.5 * u, 15.5 * u, 13.5 * u)


def _open(gc, u, pen, fill, colour):
    path = gc.CreatePath()
    path.MoveToPoint(3 * u, 6 * u)
    path.AddLineToPoint(9 * u, 6 * u)
    path.AddLineToPoint(11 * u, 8.5 * u)
    path.AddLineToPoint(20 * u, 8.5 * u)
    path.AddLineToPoint(20 * u, 19 * u)
    path.AddLineToPoint(3 * u, 19 * u)
    path.CloseSubpath()
    gc.StrokePath(path)
    gc.StrokeLine(3 * u, 12 * u, 20 * u, 12 * u)


def _save(gc, u, pen, fill, colour):
    path = gc.CreatePath()
    path.MoveToPoint(4 * u, 4 * u)
    path.AddLineToPoint(17 * u, 4 * u)
    path.AddLineToPoint(20 * u, 7 * u)
    path.AddLineToPoint(20 * u, 20 * u)
    path.AddLineToPoint(4 * u, 20 * u)
    path.CloseSubpath()
    gc.StrokePath(path)
    gc.DrawRectangle(7.5 * u, 4 * u, 8 * u, 5 * u)
    gc.SetBrush(fill)
    gc.DrawRectangle(7.5 * u, 13 * u, 9 * u, 7 * u)


def _bold(gc, u, pen, fill, colour):
    font = wx.Font(wx.FontInfo(int(15 * u)).Bold().FaceName("Georgia"))
    gc.SetFont(font, colour)
    w, h = gc.GetTextExtent("B")
    gc.DrawText("B", (24 * u - w) / 2, (24 * u - h) / 2)


def _italic(gc, u, pen, fill, colour):
    font = wx.Font(wx.FontInfo(int(15 * u)).Italic().FaceName("Georgia"))
    gc.SetFont(font, colour)
    w, h = gc.GetTextExtent("I")
    gc.DrawText("I", (24 * u - w) / 2, (24 * u - h) / 2)


def _underline(gc, u, pen, fill, colour):
    font = wx.Font(wx.FontInfo(int(13 * u)).FaceName("Georgia"))
    gc.SetFont(font, colour)
    w, h = gc.GetTextExtent("U")
    gc.DrawText("U", (24 * u - w) / 2, (22 * u - h) / 2)
    gc.StrokeLine(6 * u, 20 * u, 18 * u, 20 * u)


def _strike(gc, u, pen, fill, colour):
    font = wx.Font(wx.FontInfo(int(13 * u)).FaceName("Georgia"))
    gc.SetFont(font, colour)
    w, h = gc.GetTextExtent("S")
    gc.DrawText("S", (24 * u - w) / 2, (24 * u - h) / 2)
    gc.StrokeLine(5 * u, 12 * u, 19 * u, 12 * u)


def _lines(gc, u, lefts, y0=6, step=6, right=20):
    for i, left in enumerate(lefts):
        y = (y0 + i * step) * u
        gc.StrokeLine(left * u, y, right * u, y)


def _bullets(gc, u, pen, fill, colour):
    gc.SetBrush(fill)
    for i in range(3):
        y = (6 + i * 6) * u
        gc.DrawEllipse(3.5 * u, y - 1.6 * u, 3.2 * u, 3.2 * u)
    _lines(gc, u, [10, 10, 10])


def _numbers(gc, u, pen, fill, colour):
    font = wx.Font(wx.FontInfo(int(7 * u)).Bold().FaceName("Segoe UI"))
    gc.SetFont(font, colour)
    for i, digit in enumerate("123"):
        y = (6 + i * 6) * u
        w, h = gc.GetTextExtent(digit)
        gc.DrawText(digit, 3 * u, y - h / 2)
    _lines(gc, u, [10, 10, 10])


def _quote(gc, u, pen, fill, colour):
    gc.StrokeLine(5 * u, 5 * u, 5 * u, 19 * u)
    _lines(gc, u, [10, 10, 10], y0=7, step=5, right=19)


def _align(gc, u, kind):
    widths = {"left": [(4, 20), (4, 14), (4, 20), (4, 12)],
              "center": [(4, 20), (7, 17), (4, 20), (8, 16)],
              "right": [(4, 20), (10, 20), (4, 20), (12, 20)],
              "justify": [(4, 20), (4, 20), (4, 20), (4, 20)]}[kind]
    for i, (a, b) in enumerate(widths):
        y = (5.5 + i * 4.3) * u
        gc.StrokeLine(a * u, y, b * u, y)


def _align_left(gc, u, pen, fill, colour):
    _align(gc, u, "left")


def _align_center(gc, u, pen, fill, colour):
    _align(gc, u, "center")


def _align_right(gc, u, pen, fill, colour):
    _align(gc, u, "right")


def _align_justify(gc, u, pen, fill, colour):
    _align(gc, u, "justify")


def _link(gc, u, pen, fill, colour):
    path = gc.CreatePath()
    path.AddRoundedRectangle(3 * u, 9 * u, 11 * u, 6 * u, 3 * u)
    gc.StrokePath(path)
    path2 = gc.CreatePath()
    path2.AddRoundedRectangle(10 * u, 9 * u, 11 * u, 6 * u, 3 * u)
    gc.StrokePath(path2)


def _picture(gc, u, pen, fill, colour):
    gc.DrawRectangle(3 * u, 4 * u, 18 * u, 16 * u)
    path = gc.CreatePath()
    path.MoveToPoint(3.5 * u, 19 * u)
    path.AddLineToPoint(9 * u, 12 * u)
    path.AddLineToPoint(13 * u, 16 * u)
    path.AddLineToPoint(16 * u, 13 * u)
    path.AddLineToPoint(20.5 * u, 19 * u)
    gc.StrokePath(path)
    gc.SetBrush(fill)
    gc.DrawEllipse(14 * u, 6.5 * u, 3.5 * u, 3.5 * u)


def _table(gc, u, pen, fill, colour):
    gc.DrawRectangle(3 * u, 4 * u, 18 * u, 16 * u)
    gc.StrokeLine(3 * u, 9.5 * u, 21 * u, 9.5 * u)
    gc.StrokeLine(3 * u, 14.75 * u, 21 * u, 14.75 * u)
    gc.StrokeLine(9 * u, 4 * u, 9 * u, 20 * u)
    gc.StrokeLine(15 * u, 4 * u, 15 * u, 20 * u)


def _export(gc, u, pen, fill, colour):
    _page_outline(gc, u)
    strong = gc.CreatePen(wx.GraphicsPenInfo(accent()).Width(max(2.0, 2.6 * u))
                          .Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND))
    gc.SetPen(strong)
    path = gc.CreatePath()
    path.MoveToPoint(9 * u, 14.5 * u)
    path.AddLineToPoint(11.5 * u, 17 * u)
    path.AddLineToPoint(16 * u, 11.5 * u)
    gc.StrokePath(path)
    gc.SetPen(pen)


def _blank(gc, u, pen, fill, colour):
    gc.DrawRectangle(4 * u, 4 * u, 16 * u, 16 * u)


_PAINTERS = {
    "new": _new, "open": _open, "save": _save, "bold": _bold, "italic": _italic,
    "underline": _underline, "strike": _strike, "bullets": _bullets,
    "numbers": _numbers, "quote": _quote, "align_left": _align_left,
    "align_center": _align_center, "align_right": _align_right,
    "align_justify": _align_justify, "insert_link": _link,
    "insert_picture": _picture, "insert_table": _table, "export_pdf": _export,
}


def sheet(size=24, columns=9):
    """Every icon on one bitmap, for a look at them all at once."""
    rows = (len(NAMES) + columns - 1) // columns
    pad = 6
    out = wx.Bitmap(columns * (size + pad) + pad, rows * (size + pad) + pad, 32)
    dc = wx.MemoryDC(out)
    dc.SetBackground(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)))
    dc.Clear()
    for index, name in enumerate(NAMES):
        x = pad + (index % columns) * (size + pad)
        y = pad + (index // columns) * (size + pad)
        dc.DrawBitmap(draw(name, size), x, y, True)
    dc.SelectObject(wx.NullBitmap)
    return out
