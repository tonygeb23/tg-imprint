"""Capture docs/screenshots/, at 100 percent and at 150 percent.

    python tests/shots.py 150 [name ...]
    python tests/shots.py 100 [name ...]

Not a test: nothing here is asserted. It builds the window and each dialog
with made up data and writes a PNG per window into docs/screenshots/.

Two things it gets right that the first round did not:

- **The scale is real.** This machine's desktop runs at 150 percent. A
  process that declares itself per monitor aware (context -4) lays out at
  150 percent and everything it draws is 150 percent; a process that
  declares nothing (context -1) is told the screen is 96 dots per inch, so
  it lays out at 100 percent and Windows scales the result on its way to
  the glass. Capturing the screen in that second process gives back the 100
  percent bitmap. So "150" is the aware run and "100" is the unaware one,
  and the two really differ: 30 pixel toolbar icons against 20 (defect 5 of
  the round 2 review).
- **No strip of desktop.** A window's GetScreenRect includes the invisible
  resize border, about eight pixels a side, which is why the first captures
  had desktop down the left edge (defect 19). The visible frame comes from
  DwmGetWindowAttribute, DWMWA_EXTENDED_FRAME_BOUNDS.
"""
import ctypes
import ctypes.wintypes
import os
import sys
import tempfile
import time

SCALE = sys.argv[1] if len(sys.argv) > 1 else "150"
WANTED = [a.lower() for a in sys.argv[2:]]

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.PrintWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC, ctypes.wintypes.UINT]
u32.PrintWindow.restype = ctypes.wintypes.BOOL
u32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
u32.WindowFromPoint.restype = ctypes.wintypes.HWND
u32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
u32.GetAncestor.restype = ctypes.wintypes.HWND
# Every one of these takes a window handle, which is 64 bits. Without the
# argtypes ctypes passes it as a C int and the top half is thrown away, so
# the call lands on no window at all and says nothing about it.
u32.SetWindowPos.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HWND,
                             ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.wintypes.UINT]
u32.SetWindowPos.restype = ctypes.wintypes.BOOL
u32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
u32.SetForegroundWindow.restype = ctypes.wintypes.BOOL
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4 if SCALE == "150" else -1))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-shot-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-shot-local-")
SHOTS = os.path.join(HERE, "docs", "screenshots")

import wx  # noqa: E402

from tgimprint import constants as C  # noqa: E402
from tgimprint import updatedialog  # noqa: E402
from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import dialogs, forms_dialog, keymap, main_window  # noqa: E402
from tgimprint.ui.doc_properties_dialog import DocPropertiesDialog  # noqa: E402
from tgimprint.ui.find_dialog import FindDialog  # noqa: E402
from tgimprint.ui.hyperlink_dialog import LinkDialog  # noqa: E402
from tgimprint.ui.image_dialog import PictureDialog  # noqa: E402
from tgimprint.ui.pictures_dialog import PicturesDialog  # noqa: E402
from tgimprint.ui.preferences_dialog import PreferencesDialog  # noqa: E402
from tgimprint.ui.structure_dialog import StructureDialog  # noqa: E402
from tgimprint.ui.table_dialog import TableDialog  # noqa: E402

DOT = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
       "DwAChwGA60e6kgAAAABJRU5ErkJggg==")
SPEC = {"src": DOT, "alt": "A dot", "caption": "The dot", "width": "half",
        "place": "centre", "altSource": "ai:anthropic", "decorative": False}
BODY = ("<h1>The Ridgeway in a day</h1><p>Eighty seven miles of chalk track, "
        "and a forecast that changed twice on the way to the station.</p>"
        "<h2>What went in the pack</h2><ul><li>Two litres of water</li>"
        "<li>A paper map, because the phone died at Ogbourne</li></ul>"
        "<p>The first climb out of Avebury is the one everybody warns you "
        "about, and everybody is right about it.</p>")


class DWM(ctypes.Structure):
    _fields_ = [("left", ctypes.wintypes.LONG), ("top", ctypes.wintypes.LONG),
                ("right", ctypes.wintypes.LONG), ("bottom", ctypes.wintypes.LONG)]


def visible_rect(window):
    """The frame you can see, without the invisible resize border."""
    box = DWM()
    try:
        ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.wintypes.HWND(int(window.GetHandle())), ctypes.c_uint(9),
            ctypes.byref(box), ctypes.sizeof(box))
    except Exception:
        ok = -1
    if ok == 0 and box.right > box.left:
        return wx.Rect(box.left, box.top, box.right - box.left, box.bottom - box.top)
    return window.GetScreenRect()


HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040


def on_top(window, yes):
    """Keep whatever else the machine is doing out of the picture.

    A capture on 2026-09-09 came back with another program's window across
    the middle of the Preferences dialog, because this is a screen grab.
    Topmost plus the foreground call keeps the shot to this program.
    """
    try:
        mine = ctypes.wintypes.HWND(int(window.GetHandle()))
        u32.SetWindowPos(mine, ctypes.wintypes.HWND(HWND_TOPMOST if yes else HWND_NOTOPMOST),
                         0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        if yes:
            u32.SetForegroundWindow(mine)
    except Exception:
        pass


def settle(window, ticks=14):
    for _ in range(ticks):
        wx.Yield()
        time.sleep(0.05)
    window.Raise()
    wx.Yield()


def paint(window, skip_webview=False):
    """Make the window draw itself before it is copied.

    A dialog that has only just been shown gives back a half painted
    rectangle: on 2026-09-09 the Display page came back with its text fields
    drawn and every label missing. Refreshing each child and turning the
    loop again fills it in.
    """
    for child in [window] + list(window.GetChildren()):
        # Refreshing the panel that holds the WebView2 wipes what it drew and
        # it does not come back inside this loop, so the main window is left
        # alone and only settled.
        if skip_webview and type(child).__name__ in ("EditorView", "WebView"):
            continue
        try:
            child.Refresh()
            child.Update()
        except Exception:
            pass
    settle(window, 8)


def print_window(window, rect):
    """Ask the window to draw itself into a bitmap of its own.

    A screen grab picks up whatever else is on the machine: two captures on
    2026-09-09 came back with somebody else's browser across the middle,
    because this desktop is in use. PrintWindow with PW_RENDERFULLCONTENT
    asks the window itself, so nothing in front of it can get in. It returns
    None when the window will not draw that way, which is the case for the
    WebView2 surface, and the caller falls back to the screen.
    """
    outer = window.GetScreenRect()
    whole = wx.Bitmap(outer.width, outer.height)
    memory = wx.MemoryDC(whole)
    ok = u32.PrintWindow(ctypes.wintypes.HWND(int(window.GetHandle())),
                         ctypes.wintypes.HDC(int(memory.GetHandle())), 2)
    memory.SelectObject(wx.NullBitmap)
    if not ok:
        return None
    # The window draws itself from its own top left, which is outside the
    # frame you can see by the width of the invisible resize border, so the
    # visible frame is cut out of it afterwards (defect 19).
    cut = wx.Rect(max(0, rect.x - outer.x), max(0, rect.y - outer.y),
                  min(rect.width, outer.width), min(rect.height, outer.height))
    cut.width = min(cut.width, outer.width - cut.x)
    cut.height = min(cut.height, outer.height - cut.y)
    return whole.GetSubBitmap(cut)


def blank(bitmap):
    """True when nothing was drawn: every corner and the middle the same."""
    image = bitmap.ConvertToImage()
    w, h = image.GetWidth(), image.GetHeight()
    spots = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3), (w // 2, h // 2)]
    seen = {tuple(image.GetRed(x, y) for _ in (0,)) + (image.GetGreen(x, y),
            image.GetBlue(x, y)) for x, y in spots}
    return len(seen) <= 1


GA_ROOT = 2


def ours(window, rect):
    """True when this window really is the one on top of that rectangle.

    The machine this runs on is somebody's desktop, and twice on 2026-09-09 a
    browser came forward between the topmost call and the copy, so the
    capture held a web page rather than the program. Five points of the
    rectangle are asked who is in front of them; anything else and the
    capture is not taken.
    """
    mine = int(window.GetHandle())
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    for px, py in ((x + 4, y + 4), (x + w - 5, y + 4), (x + 4, y + h - 5),
                   (x + w - 5, y + h - 5), (x + w // 2, y + h // 2)):
        found = u32.WindowFromPoint(ctypes.wintypes.POINT(int(px), int(py)))
        try:
            root = u32.GetAncestor(found, GA_ROOT)
        except Exception:
            root = found
        if int(root or 0) != mine:
            return False
    return True


def shoot(window, name, screen=False):
    """`screen` is for the main window: the WebView2 surface is composed by
    another process and draws nothing into a PrintWindow bitmap, so the
    editor came back white. That one is copied off the screen instead."""
    if WANTED and name not in WANTED:
        return
    on_top(window, True)
    settle(window)
    paint(window, skip_webview=screen)
    rect = visible_rect(window)
    bitmap = None if screen else print_window(window, rect)
    if bitmap is None or blank(bitmap):
        clear = False
        for _try in range(6):
            if ours(window, rect):
                clear = True
                break
            on_top(window, True)
            settle(window, 10)
            rect = visible_rect(window)
        if not clear:
            print("  %-34s SKIPPED, something else is in front of it" % name)
            on_top(window, False)
            return
        settle(window, 6)
        rect = visible_rect(window)
        bitmap = wx.Bitmap(rect.width, rect.height)
        memory = wx.MemoryDC(bitmap)
        screen_dc = wx.ScreenDC()
        memory.Blit(0, 0, rect.width, rect.height, screen_dc, rect.x, rect.y)
        memory.SelectObject(wx.NullBitmap)
    out = os.path.join(SHOTS, "%s-%s.png" % (name, SCALE))
    on_top(window, False)
    bitmap.SaveFile(out, wx.BITMAP_TYPE_PNG)
    print("  %-34s %4d x %4d  %s" % (name, rect.width, rect.height, os.path.basename(out)))


def shoot_dialog(dialog, name):
    dialog.Show()
    shoot(dialog, name)
    dialog.Destroy()
    wx.Yield()



# --------------------------------------------------------------- the run --
#
# Everything below runs inside app.MainLoop(), one step per timer tick, not
# in a wx.Yield loop. Measured 2026-09-09: under wx.Yield the WebView2 never
# reports itself ready, so the editor stayed empty and every capture of the
# window showed a grey panel and "No words yet"; and the toolbar's fit timer
# never fired either, so the bar kept the shape it was built with.

class Field:
    def __init__(self, fid, label, kind, value, page, choices=None, required=False):
        self.id, self.label, self.name = fid, label, fid
        self.kind, self.value, self.page = kind, value, page
        self.choices, self.required, self.rect, self.tooltip = choices or [], required, None, ""


class Doc:
    has_fields, problem, page_count = True, "", 2

    def __init__(self):
        self.fields = [
            Field("f1", "Full name", "text", "Tony Gebhard", 1, required=True),
            Field("f2", "Address, first line", "text", "", 1, required=True),
            Field("f3", "Town", "text", "", 1),
            Field("f4", "I have read the terms", "checkbox", False, 2),
            Field("f5", "How you would like a reply", "choice", "Email", 2,
                  choices=["Email", "Letter", "Telephone"]),
            Field("f6", "Signature", "signature", "", 2)]


class Proposal:
    def __init__(self, page, label, confidence):
        self.page, self.label, self.confidence = page, label, confidence
        self.rect, self.source = (72, 500, 300, 18), "line"


app = wx.App(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
# A window that runs off the top of the screen loses its title bar out of
# every capture, so the size is whatever fits this display with room to
# spare, not a fixed number of pixels.
screen_w, screen_h = wx.GetDisplaySize()
frame.SetSize(wx.Size(min(frame.FromDIP(1180), screen_w - 120),
                      min(frame.FromDIP(760), screen_h - 140)))
frame.Centre()
frame.Show()

STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def dialog_step(make, name):
    def go():
        dialog = make()
        dialog.Show()
        shoot(dialog, name)
        dialog.Destroy()
    STEPS.append(go)


def start():
    frame.editor.load_clean_body(BODY)
    frame.meta["title"] = "The Ridgeway in a day"
    frame._update_title()
    print("\n%s percent, scale factor %s, window %s"
          % (SCALE, frame.GetDPIScaleFactor(), frame.GetSize()))


step(start)
step(lambda: shoot(frame, "main-window", screen=True))

for _mode, _name in (("icons", "toolbar-icons"), ("icons_labels", "toolbar-icons-labels"),
                     ("labels", "toolbar-labels")):
    step(lambda m=_mode: (frame.settings.__setitem__("toolbar_labels_mode", m),
                          frame._fit_toolbar()))
    step(lambda n=_name: shoot(frame, n, screen=True))
step(lambda: (frame.settings.__setitem__("toolbar_labels_mode", "icons_labels"),
              frame._fit_toolbar()))

dialog_step(lambda: PreferencesDialog(frame, frame, settings, page="Display"),
            "preferences-display")
for _theme, _name in (("dark", "editor-dark"), ("yellow_on_black", "editor-yellow-on-black")):
    step(lambda t=_theme: (frame.settings.__setitem__("page_theme", t),
                           frame.settings.__setitem__("editor_zoom", 130),
                           frame.apply_display()))
    step(lambda n=_name: shoot(frame, n, screen=True))
step(lambda: (frame.settings.__setitem__("page_theme", "normal"),
              frame.settings.__setitem__("editor_zoom", 100),
              frame.apply_display()))

dialog_step(lambda: forms_dialog.FormDialog(frame, frame, Doc(), "Application form.pdf"),
            "fill-form")
dialog_step(lambda: forms_dialog.FieldDialog(frame, Doc().fields[1], 1), "fill-form-field")
dialog_step(lambda: forms_dialog.SignatureDialog(frame, "Signature"), "fill-form-signature")
dialog_step(lambda: forms_dialog.ProposalsDialog(frame, frame, [
    Proposal(1, "Name", "high"), Proposal(1, "Date of birth", "high"),
    Proposal(2, "", "low")]), "fill-form-blanks")

dialog_step(lambda: PreferencesDialog(frame, frame, settings), "preferences")


def prefs_on(index):
    dialog = PreferencesDialog(frame, frame, settings)
    dialog.tabs.SetSelection(index)
    return dialog


dialog_step(lambda: prefs_on(2), "preferences-document-defaults")
dialog_step(lambda: prefs_on(3), "preferences-ai")
dialog_step(lambda: DocPropertiesDialog(frame, {"title": "The Ridgeway in a day",
                                                "author": "Tony Gebhard", "lang": "en-US",
                                                "subject": "A walk", "page_size": "letter",
                                                "margin_inches": 1.0}), "document-properties")
dialog_step(lambda: PictureDialog(frame, frame, spec=None), "insert-picture")
dialog_step(lambda: PictureDialog(frame, frame, spec=SPEC), "picture-properties")
dialog_step(lambda: LinkDialog(frame, text="the map", href="https://example.com",
                               editing=False), "insert-link")
dialog_step(lambda: TableDialog(frame), "insert-table")
dialog_step(lambda: FindDialog(frame, frame), "find-and-replace")
dialog_step(lambda: StructureDialog(frame, frame, [
    {"index": 0, "level": 1, "text": "The Ridgeway in a day"},
    {"index": 1, "level": 2, "text": "What went in the pack"}]), "structure")
dialog_step(lambda: PicturesDialog(frame, frame, [
    SPEC, dict(SPEC, alt="", needsAlt=True, altSource="pdf")]), "pictures")
dialog_step(lambda: dialogs.KeyboardHelpDialog(frame, keymap.render_text()),
            "keyboard-shortcuts")
dialog_step(lambda: dialogs.TextDialog(
    frame, "PDF written",
    "The PDF/UA identifier was written: every check passed.\n"
    "C:/Users/tony/Documents/The Ridgeway in a day.pdf, 3 pages, made with Edge.\n\n"
    "Accessibility checks for The Ridgeway in a day.pdf\n9 of 9 checks passed.",
    buttons=(("Open &PDF", "open"), ("Open &folder", "folder"), ("&Close", "close")),
    field_label="&Report", size=(640, 380)), "export-report")
dialog_step(lambda: updatedialog.UpdateDialog(frame, C.APP_NAME, C.APP_VERSION,
                                              new_version="0.2.0",
                                              notes="The Display page."), "update-available")
dialog_step(lambda: dialogs.RecoveryDialog(frame, [
    ("snap.imprint", "walk.imprint", "2026-09-09 16:20", "The Ridgeway in a day")]), "recover")
step(lambda: print("done"))


def turn():
    if not STEPS:
        sys.stdout.flush()
        os._exit(0)
    try:
        STEPS.pop(0)()
    except Exception as exc:
        print("  step failed: %s" % exc)
    wx.CallLater(250, turn)


wx.CallLater(2500, turn)          # the WebView2 needs the loop to itself first
app.MainLoop()
os._exit(0)
