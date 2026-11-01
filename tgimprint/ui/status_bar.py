"""The status bar: the native one, for NVDA, with a painted skin for the eye.

NVDA's "read the status bar" asks the real status bar control, so that stays
and holds every word. But that control ignores a foreground colour (measured,
theme.py), so on a dark theme its text is black on near black. The skin is one
child window laid over the fields that paints the same text in the palette's
colours.

The skin is decoration: it refuses focus, has no text of its own for a screen
reader to find, and repeats exactly what the native fields already hold. In
Windows High Contrast it is hidden and the native bar is what you see.
"""
import wx

from . import theme

#: The fields after the message, in device independent pixels: paragraph
#: style, word count, language. The message takes whatever is left, because
#: it is the one field that holds a sentence.
FIELD_WIDTHS_DIP = (210, 120, 72)
GRIP_DIP = 18


class _Skin(wx.Window):
    def __init__(self, bar):
        super().__init__(bar, style=wx.BORDER_NONE | wx.FULL_REPAINT_ON_RESIZE)
        self.bar = bar
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        theme.silence(self)

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False

    def _on_paint(self, _event):
        bar = self.bar
        pal = bar.pal
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(pal.chrome))
        dc.Clear()
        width, height = self.GetClientSize()
        dc.SetPen(wx.Pen(pal.rule))
        dc.DrawLine(0, 0, width, 0)
        dc.SetFont(bar.GetFont())
        pad = bar.FromDIP(10)
        for index in range(bar.GetFieldsCount()):
            rect = bar.GetFieldRect(index)
            text = bar.GetStatusText(index)
            if index and text:
                dc.SetPen(wx.Pen(pal.rule))
                dc.DrawLine(rect.x, bar.FromDIP(5), rect.x, height - bar.FromDIP(4))
            right = min(rect.x + rect.width, width) - pad
            room = right - (rect.x + pad)
            if text and room > 0:
                dc.SetTextForeground(pal.ink if index == 0 else pal.muted)
                shown = wx.Control.Ellipsize(text, dc, wx.ELLIPSIZE_END, room)
                _w, text_h = dc.GetTextExtent(shown)
                dc.DrawText(shown, rect.x + pad, (height - text_h) // 2 + 1)


class ImprintStatusBar(wx.StatusBar):
    """Four fields: message, paragraph style, words, language."""

    def __init__(self, frame):
        super().__init__(frame, style=wx.STB_DEFAULT_STYLE)
        self.pal = None
        self.SetFieldsCount(4)
        self.skin = _Skin(self)
        self.set_widths()
        self.Bind(wx.EVT_SIZE, self._on_size)

    def set_widths(self):
        self.SetStatusWidths([-1] + [self.FromDIP(w) for w in FIELD_WIDTHS_DIP])

    def SetStatusText(self, text, i=0):
        super().SetStatusText(text, i)
        if self.pal is not None and not self.pal.native:
            self.skin.Refresh(False)

    def set_palette(self, pal):
        self.pal = pal
        self.skin.Show(not pal.native)
        theme.paint(self, pal)
        self._lay()

    def _lay(self):
        width, height = self.GetClientSize()
        self.skin.SetSize(0, 0, max(0, width - self.FromDIP(GRIP_DIP)), height)
        self.skin.Refresh(False)

    def _on_size(self, event):
        event.Skip()
        if self.pal is not None:
            wx.CallAfter(self._lay_if_alive)

    def _lay_if_alive(self):
        if self:
            self._lay()
