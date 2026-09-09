"""The Easy PDF mark, drawn rather than loaded.

A page with a folded corner, three lines of text on it, the top line lit in
the TG Studios amber: a document whose heading is what matters. The case,
the rim and the lit colour are shared with the other TG Studios marks so the
family reads as one on a taskbar, and the page shape is what tells this one
apart from the Prompt Vault's door and Drop Deck's pads.

Drawn with a GraphicsContext at whatever size is asked for, so it is crisp at
any display scale and there is no image file to go missing from a build. The
same function feeds the window icon, the About box and tools/build_release.py,
which bakes it into the .ico that stamps the executable and the installer.

The bitmap(), icon(), bundle() and write_ico() shapes are the same as Drop
Deck's appicon.py on purpose; only the drawing differs.
"""
import io
import struct

import wx

# Hex strings, not wx.Colour objects. Constructing a wx.Colour at import time
# raises PyNoAppError, because a colour needs the app to exist first, and this
# module is imported before wx.App in at least one path.
BODY = "#1c2436"                # the case, shared with the other TG Studios marks
LIT = "#e8b33f"                 # the heading line
PAGE = "#f4f6fa"                # the sheet
INK = "#8a97ad"                 # body text lines, and the rim
FOLD = "#c9d1de"                # the turned-down corner
RIM = "#8a97ad"                 # so the case reads on a dark taskbar

# Windows asks for all of these somewhere: title bar, alt-tab, taskbar,
# Explorer's Extra Large view.
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def bitmap(size):
    """The mark at `size` pixels, with an alpha channel."""
    bmp = wx.Bitmap(size, size, 32)
    bmp.UseAlpha()
    dc = wx.MemoryDC(bmp)
    gc = wx.GraphicsContext.Create(dc)
    gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
    u = size / 32.0

    # A rim, not just a fill. The case is 1.05:1 against a dark-mode taskbar
    # and without an outline the whole silhouette disappears.
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(RIM)).Width(max(1.0, u))))
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(BODY))))
    gc.DrawRoundedRectangle(1 * u, 1 * u, 30 * u, 30 * u, 7 * u)
    gc.SetPen(wx.TRANSPARENT_PEN)

    # The sheet: a tall rectangle with its top-right corner cut off.
    left, top, right, bottom = 8 * u, 6 * u, 24 * u, 26 * u
    cut = 5 * u
    page = gc.CreatePath()
    page.MoveToPoint(left, top)
    page.AddLineToPoint(right - cut, top)
    page.AddLineToPoint(right, top + cut)
    page.AddLineToPoint(right, bottom)
    page.AddLineToPoint(left, bottom)
    page.CloseSubpath()
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(PAGE))))
    gc.FillPath(page)

    # The turned-down corner.
    fold = gc.CreatePath()
    fold.MoveToPoint(right - cut, top)
    fold.AddLineToPoint(right - cut, top + cut)
    fold.AddLineToPoint(right, top + cut)
    fold.CloseSubpath()
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(FOLD))))
    gc.FillPath(fold)

    # Below about 20 pixels three lines close up into a smear, so the small
    # mark carries the heading line only.
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(LIT))))
    gc.DrawRoundedRectangle(left + 2.5 * u, top + 7 * u, 9 * u, 3 * u, 1 * u)
    if size >= 20:
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(INK))))
        gc.DrawRoundedRectangle(left + 2.5 * u, top + 12.5 * u, 11 * u, 1.8 * u, 0.9 * u)
        gc.DrawRoundedRectangle(left + 2.5 * u, top + 16.5 * u, 11 * u, 1.8 * u, 0.9 * u)

    dc.SelectObject(wx.NullBitmap)
    return bmp


def icon(size=32):
    ico = wx.Icon()
    ico.CopyFromBitmap(bitmap(size))
    return ico


def bundle():
    out = wx.IconBundle()
    for s in ICO_SIZES:
        i = wx.Icon()
        i.CopyFromBitmap(bitmap(s))
        out.AddIcon(i)
    return out


def write_ico(path):
    """Bake every size into a .ico file.

    Assembled by hand because wx will not save a multi-size icon and every
    library that would is a build dependency this project does not otherwise
    need. The format is small: a 6-byte header, one 16-byte directory entry per
    image, then the data. Vista and later accept whole PNGs as entries.
    """
    images = []
    for size in ICO_SIZES:
        stream = io.BytesIO()
        bitmap(size).ConvertToImage().SaveFile(stream, wx.BITMAP_TYPE_PNG)
        images.append((size, stream.getvalue()))

    header = struct.pack("<HHH", 0, 1, len(images))
    entries, blobs = [], []
    offset = len(header) + 16 * len(images)
    for size, data in images:
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,     # width, 0 means 256
            0 if size >= 256 else size,     # height
            0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)

    with open(path, "wb") as fh:
        fh.write(header + b"".join(entries) + b"".join(blobs))
    return path
