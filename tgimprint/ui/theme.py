"""The look of the window around the page: one palette per page theme.

The editor page draws its own colours in CSS (editor_page.py). Everything
native round it, the toolbar, the side panel, the start screen and the status
bar, takes its colours from here, so a theme is the whole window and not a
dark page in a pale frame.

Three things this file exists to keep straight:

- **Windows High Contrast wins.** `palette()` returns the system palette
  whenever high contrast is on, or the page theme says to follow Windows.
  `native` is then True and nothing here sets a colour on anything: every
  control goes back to whatever the person chose in Windows.
- **Colour only ever repeats a word.** Rust and peach mark the same things
  the labels already say. Nothing here carries meaning by itself.
- **Measured limits of native Windows controls, 2026-11-01** (probe on
  wxPython 4.2.5, Windows 11): a wx.ToolBar takes a background colour and
  ignores a foreground colour, so its labels stay black on dark; a
  wx.StatusBar the same; the menu bar takes neither; a coloured wx.Button
  turns owner drawn and honours both, and keeps its role and its name; the
  title bar follows DwmSetWindowAttribute. So on a dark theme toolbar words
  are drawn into the tool bitmaps (toolbar.py) and the status bar wears a
  painted skin over the native one (status_bar.py), and the menu bar stays
  the colour Windows draws it. SetMenuInfo with a background brush was tried
  too: under a visual style the bar ignores it.

Contrast, ink on chrome, worked out with the WCAG formula and asserted in
tests/test_display.py: normal 17.6:1, dark 14.8:1, yellow on black 19.6:1.
"""
import ctypes
import ctypes.wintypes as wintypes

import wx

RUST = "#8a3a12"
PEACH = "#ff9e6b"
SLATE = "#2f5d7c"
CREAM = "#fdfdfc"
INK = "#16171a"

#: Every colour is a hex string here, so tests can work out the contrast
#: without a window. `tint` is only ever a fill behind something darker: at
#: about 2:1 on cream it carries nothing by itself.
THEMES = {
    "normal": {"chrome": CREAM, "ink": INK, "muted": "#565961", "rule": "#ddd9d2",
               "raised": "#f4f1ec", "accent": RUST, "tint": PEACH, "second": SLATE,
               "selected": "#f7e3d6", "selected_ink": INK, "drawn_labels": False},
    "dark": {"chrome": "#1b1c20", "ink": "#f2efea", "muted": "#b9bac0", "rule": "#34363d",
             "raised": "#26282e", "accent": PEACH, "tint": RUST, "second": "#8fb8d4",
             "selected": "#8a3a12", "selected_ink": "#ffffff", "drawn_labels": True},
    "yellow_on_black": {"chrome": "#000000", "ink": "#ffff00", "muted": "#ffff00",
                        "rule": "#ffff00", "raised": "#000000", "accent": "#ffff00",
                        "tint": "#000000", "second": "#ffff00", "selected": "#ffff00",
                        "selected_ink": "#000000", "drawn_labels": True},
}

#: The canvas behind the page, so a resize never flashes the wrong colour.
CANVAS = {"normal": "#eeeae3", "dark": INK, "yellow_on_black": "#000000"}


class Palette:
    """What the window paints with. `native` means paint nothing at all."""

    def __init__(self, name, values, native=False):
        self.name = name
        self.native = native
        self.drawn_labels = bool(values.get("drawn_labels"))
        for key in ("chrome", "ink", "muted", "rule", "raised", "accent", "tint", "second",
                    "selected", "selected_ink"):
            setattr(self, key, wx.Colour(values[key]))
        self.canvas = wx.Colour(CANVAS.get(name, values["chrome"]))

    def __eq__(self, other):
        return isinstance(other, Palette) and (self.name, self.native) == (other.name, other.native)

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.name, self.native))


class _HighContrast(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD),
                ("lpszDefaultScheme", wintypes.LPWSTR)]


def high_contrast():
    """True when Windows is in a high contrast mode, asked of Windows itself."""
    try:
        info = _HighContrast()
        info.cbSize = ctypes.sizeof(info)
        # SPI_GETHIGHCONTRAST, and HCF_HIGHCONTRASTON is the low bit.
        if ctypes.windll.user32.SystemParametersInfoW(0x0042, info.cbSize,
                                                      ctypes.byref(info), 0):
            return bool(info.dwFlags & 1)
    except Exception:
        pass
    return False


def _system_palette():
    colour = wx.SystemSettings.GetColour

    def hex_of(which):
        return colour(which).GetAsString(wx.C2S_HTML_SYNTAX)

    face = hex_of(wx.SYS_COLOUR_BTNFACE)
    text = hex_of(wx.SYS_COLOUR_BTNTEXT)
    highlight = hex_of(wx.SYS_COLOUR_HIGHLIGHT)
    return Palette("system", {
        "chrome": face, "ink": text, "muted": text, "rule": text, "raised": face,
        "accent": text, "tint": face, "second": text, "selected": highlight,
        "selected_ink": hex_of(wx.SYS_COLOUR_HIGHLIGHTTEXT)}, native=True)


def palette(page_theme):
    """The palette for this page theme, or the system's when it must win."""
    if high_contrast() or page_theme == "high_contrast" or page_theme not in THEMES:
        return _system_palette()
    return Palette(page_theme, THEMES[page_theme])


def paint(window, pal, background=None, foreground=None):
    """Colour one window, or hand it back to the system."""
    if pal.native:
        window.SetBackgroundColour(wx.NullColour)
        window.SetForegroundColour(wx.NullColour)
    else:
        window.SetBackgroundColour(background if background is not None else pal.chrome)
        window.SetForegroundColour(foreground if foreground is not None else pal.ink)
    window.Refresh()


def paint_list(listctrl, pal, background=None):
    """A wx.ListCtrl, or a list handed back to the system. Not NullColour:
    measured, a ListCtrl takes that as black, on both colours, and in High
    Contrast the rows vanished into a black box."""
    if pal.native:
        listctrl.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOX))
        listctrl.SetTextColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOXTEXT))
    else:
        listctrl.SetBackgroundColour(background if background is not None else pal.chrome)
        listctrl.SetTextColour(pal.ink)
    listctrl.Refresh()


def paint_button(button, pal):
    """A native wx.Button in the theme.

    On the normal theme it stays exactly the Windows button. On a dark theme
    a coloured wx.Button turns owner drawn and honours both colours; measured,
    its class stays BUTTON, so its role and its name do not change.
    """
    if pal.native or pal.name == "normal":
        button.SetBackgroundColour(wx.NullColour)
        button.SetForegroundColour(wx.NullColour)
    else:
        button.SetBackgroundColour(pal.raised)
        button.SetForegroundColour(pal.ink)
    button.Refresh()


def scrollbars_follow(window, pal):
    """Dark scroll bars on a dark theme. DarkMode_Explorer is a theme class
    Windows has shipped since 1809 and is not documented, so a machine that
    does not have it simply keeps the ordinary ones."""
    try:
        name = "DarkMode_Explorer" if (not pal.native and pal.name != "normal") else "Explorer"
        ctypes.windll.uxtheme.SetWindowTheme(wintypes.HWND(int(window.GetHandle())), name, None)
    except Exception:
        pass


def plain_toolbar(toolbar):
    """Take the visual style off a toolbar. Measured on the dark bar: the
    style's hover is a pale blue fill that buries a light glyph, and with no
    style the hover is a thin outline. The "on" state is drawn into the cell
    (icons.labelled), so nothing is lost."""
    try:
        ctypes.windll.uxtheme.SetWindowTheme(wintypes.HWND(int(toolbar.GetHandle())), "", "")
    except Exception:
        pass


def dark_choice(choice):
    """A wx.Choice ignores its colours under a visual style. DarkMode_CFD is
    the class the common file dialog's combo boxes use; measured, it draws
    the box dark and the text light."""
    try:
        ctypes.windll.uxtheme.SetWindowTheme(wintypes.HWND(int(choice.GetHandle())),
                                             "DarkMode_CFD", None)
    except Exception:
        pass


def _colorref(colour):
    return colour.Red() | (colour.Green() << 8) | (colour.Blue() << 16)


def caption(frame, pal):
    """The title bar to match, on Windows 11. Refused quietly elsewhere."""
    DWMWA_DARK, DWMWA_BORDER, DWMWA_CAPTION, DWMWA_TEXT = 20, 34, 35, 36
    DEFAULT = 0xFFFFFFFF
    try:
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        handle = wintypes.HWND(int(frame.GetHandle()))

        def put(attribute, value):
            number = ctypes.c_uint(value)
            set_attribute(handle, attribute, ctypes.byref(number), ctypes.sizeof(number))

        put(DWMWA_DARK, 1 if (not pal.native and pal.name != "normal") else 0)
        if pal.native:
            for attribute in (DWMWA_BORDER, DWMWA_CAPTION, DWMWA_TEXT):
                put(attribute, DEFAULT)
        else:
            put(DWMWA_CAPTION, _colorref(pal.chrome))
            put(DWMWA_TEXT, _colorref(pal.ink))
            put(DWMWA_BORDER, _colorref(pal.rule))
    except Exception:
        pass


class Silent(wx.Accessible):
    """For a window that is only paint. wx names every plain window "panel",
    and NVDA's read the status bar reads what is inside the status bar, so
    decoration has to answer with nothing and say it is not there."""

    def GetName(self, childId):
        return (wx.ACC_OK, "")

    def GetState(self, childId):
        return (wx.ACC_OK, wx.ACC_STATE_SYSTEM_INVISIBLE)


def silence(window):
    """Stored on the window: wx does not keep the accessible alive itself."""
    accessible = Silent()
    window._tgimprint_accessible = accessible
    window.SetAccessible(accessible)


class Hairline(wx.Window):
    """A one pixel rule. Decoration: it refuses focus and says nothing."""

    def __init__(self, parent, horizontal=True):
        size = wx.Size(-1, 1) if horizontal else wx.Size(1, -1)
        super().__init__(parent, size=size)
        self.SetMinSize(size)
        silence(self)

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False
