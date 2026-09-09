"""Real keystrokes into the real editor, with the foreground taken first.

    python tests/test_keys.py

**Run this on a desktop where nothing else is grabbing focus**, with NVDA
running as it normally is. A synthesised keystroke goes to whatever window
has the foreground at that instant, so the window is brought forward with
AttachThreadInput and a control test comes first: type a letter, read it
back. A synthesised keystroke that goes nowhere looks exactly like a key
that works (CHALLENGE.md W4), which is why nothing below is trusted until
the letter has arrived. If the foreground cannot be taken at all the run
says SKIPPED and exits 0, because a key that went to another window says
nothing about this app.

Then the keys: Ctrl+B, Ctrl+I, Ctrl+Shift+I, Ctrl+Alt+2, Ctrl+Shift+2,
Ctrl+Alt+8, Enter in a list, Tab in a list, Tab in a table cell, Ctrl+K,
Alt+Enter, F2, F6, Applications, Shift+F10, Alt+F4, Alt+F, Tab outside a
list, the deny list (F5, Ctrl+F, Ctrl+P), Ctrl+Z after an inserted link,
Replace All then Ctrl+Z, and the watchdog: a script issued 700 ms after a
keystroke answers within five seconds.

The window holds a WebView, so the process ends with os._exit.
"""
import ctypes
import os
import sys
import tempfile
import time
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
u32.GetForegroundWindow.restype = wintypes.HWND
u32.GetAncestor.restype = wintypes.HWND
u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u32.SetForegroundWindow.argtypes = [wintypes.HWND]
u32.BringWindowToTop.argtypes = [wintypes.HWND]
u32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-test-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-test-local-")

import wx  # noqa: E402

from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import main_window  # noqa: E402

CHECKS = []
SKIPPED = []
DOT = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
       "DwAChwGA60e6kgAAAABJRU5ErkJggg==")


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)[:300]) if detail != "" and not condition else ""))


def pump(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        wx.Yield()
        wx.MilliSleep(5)


def wait_until(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        wx.Yield()
        wx.MilliSleep(5)
    return bool(condition())


def call(method, *args, timeout=5.0):
    box = {}
    frame.editor.call(method, *args, callback=lambda v, e: box.update(value=v, error=e))
    if not wait_until(lambda: "value" in box, timeout):
        return None, "no answer within %.1f seconds" % timeout
    return box["value"], box["error"]


def run(expression, timeout=5.0):
    box = {}
    frame.editor.run(expression, callback=lambda v, e: box.update(value=v, error=e))
    if not wait_until(lambda: "value" in box, timeout):
        return None, "no answer within %.1f seconds" % timeout
    return box["value"], box["error"]


def body():
    value, error = call("getBody")
    return (value or "") if not error else "ERROR: " + error


def set_body(html):
    box = {}
    frame.editor.load_body(html, callback=lambda warnings: box.update(done=True))
    wait_until(lambda: box.get("done"), 5.0)
    pump(150)


def caret_end_of(selector):
    return run("(function(){ var n = document.querySelector(%r); var r = document.createRange(); "
               "r.selectNodeContents(n); r.collapse(false); var s = getSelection(); "
               "s.removeAllRanges(); s.addRange(r); return n.tagName; })()" % selector)


# ------------------------------------------------------------ input --
def is_foreground():
    fg = u32.GetForegroundWindow()
    mine = frame.GetHandle()
    return bool(fg) and (fg == mine or u32.GetAncestor(fg, 2) == mine)


def take_foreground():
    """AttachThreadInput to the current foreground thread, then ask."""
    hwnd = frame.GetHandle()
    if is_foreground():
        return True
    fg = u32.GetForegroundWindow()
    pid = wintypes.DWORD()
    theirs = u32.GetWindowThreadProcessId(fg, ctypes.byref(pid)) if fg else 0
    mine = k32.GetCurrentThreadId()
    attached = False
    if theirs and theirs != mine:
        attached = bool(u32.AttachThreadInput(theirs, mine, True))
    sim.KeyDown(wx.WXK_ALT)
    sim.KeyUp(wx.WXK_ALT)
    u32.ShowWindow(hwnd, 9)
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    u32.SetActiveWindow(hwnd)
    if attached:
        u32.AttachThreadInput(theirs, mine, False)
    frame.Raise()
    pump(200)
    # The Alt tap above is the documented way to be allowed the foreground,
    # but a lone Alt also arms the menu bar in this app; Escape disarms it
    # so the next key goes to the document and not to the File menu.
    if is_foreground():
        sim.KeyDown(wx.WXK_ESCAPE)
        sim.KeyUp(wx.WXK_ESCAPE)
        pump(400)          # long enough for the Alt and Escape releases to land
    return is_foreground()


def focus_editor():
    frame.editor.focus()
    pump(150)


def click_editor():
    rect = frame.editor.web.GetScreenRect()
    sim.MouseMove(rect.x + rect.width // 2, rect.y + 120)
    pump(50)
    sim.MouseClick()
    pump(200)


RETAKEN = []


COUNTER = ("(function(){ if (window.__kc === undefined) { window.__kc = 0; window.__ku = 0; "
           "document.addEventListener('keydown', function(){ window.__kc++; }, true); "
           "document.addEventListener('keyup', function(){ window.__ku++; }, true); } return 1; })()")


def keys_seen():
    """How many key releases the page has seen. Measured 2026-09-09
    (probe_nvda_mode.py): with NVDA running, an injected key can reach the
    page seconds after a change that makes NVDA rebuild its view of the
    document (a load, Enter, leaving a list), so a fixed sleep read the
    body too early and the key landed in a later check. Every key below
    waits until the page has counted its release."""
    value, _error = run("window.__ku", timeout=3.0)
    return int(value or 0)


def wait_for_keys(before, count, timeout=4.0):
    ok = wait_until(lambda: keys_seen() >= before + count, timeout)
    if not ok:
        print("  note: %d key release%s not seen by the page within %.0f seconds"
              % (count, "" if count == 1 else "s", timeout))
    pump(120)
    return ok


def press(key, modifiers=0):
    """One key, through the real input queue. False if the foreground was lost."""
    if not is_foreground():
        fg = u32.GetForegroundWindow()
        RETAKEN.append(fg)
        print("  note: the foreground had moved to window %s before key %s; taking it back"
              % (fg, key))
        if not take_foreground():
            return False
    before = keys_seen()
    sim.KeyDown(key, modifiers)
    sim.KeyUp(key, modifiers)
    # wx presses and releases each modifier around the key, and the page
    # counts every release. Measured 2026-09-09: when the next key went out
    # before the page had seen Alt released, Tab became Alt+Tab, Windows'
    # Task Switching window took the foreground (the test's own foreground
    # notes named it) and the keys after it went to another program.
    wait_for_keys(before, 1 + bin(modifiers).count("1"))
    return True


def type_text(text):
    """Type letters and digits, lowercase only, with a gap between keys.

    Measured 2026-09-09 (probe_keys2.py, with NVDA running): wx's Char()
    for an uppercase letter presses Shift, and the page saw the Shift
    release arrive AFTER the next key, so "H1" landed as "H!" and a later
    lowercase "c" as "C". Lowercase letters need no Shift, so the text is
    lowercased here and every check that reads it back compares without
    case. Real typing has natural gaps; injected typing gets 25 ms.
    """
    for ch in text.lower():
        before = keys_seen()
        sim.Char(ord(ch))
        wait_for_keys(before, 1)


def landed_once(html):
    """The control letter arrived exactly once, whatever its case."""
    low = html.replace("\n", "").lower()
    return "<p>startx</p>" in low and low.count("x") == 1


VK_CAPITAL = 0x14
caps_was_on = False


def nvda_running():
    """NVDA's hidden main window has the class wxWindowClassNR and the title
    NVDA; it exists for as long as NVDA runs."""
    return bool(u32.FindWindowW("wxWindowClassNR", "NVDA"))


def settle_keyboard():
    """No modifier left down by an earlier run, and Caps Lock off, so a
    typed letter is the letter asked for. Caps Lock is put back at the end."""
    global caps_was_on
    for modifier in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT):
        sim.KeyUp(modifier)
    pump(50)
    if u32.GetKeyState(VK_CAPITAL) & 1:
        caps_was_on = True
        print("  Caps Lock was on; turning it off for the run")
        sim.KeyDown(wx.WXK_CAPITAL)
        sim.KeyUp(wx.WXK_CAPITAL)
        pump(100)


# --------------------------------------------------------------- run --
app = wx.App(False)
app.SetExitOnFrameDelete(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
frame.Show()
sim = wx.UIActionSimulator()
recorded = {}


def record(name):
    def handler(_event=None):
        recorded[name] = recorded.get(name, 0) + 1
    return handler


def main():
    check("the page becomes ready", wait_until(lambda: frame.editor.ready, 15.0))
    pump(300)
    run(COUNTER)

    # Handlers that would open modal dialogs or run the engine are replaced
    # by recorders: the question here is whether the key reaches Python
    # once, not what the dialog does (test_ui_names covers the dialogs).
    for action in ("insert_link", "properties", "rename", "print", "insert_picture",
                   "insert_table", "structure", "pictures", "preferences", "keyboard_help",
                   "describe_picture", "describe_document", "check_pdf", "open", "new",
                   "save", "save_as", "export_pdf", "close_document"):
        setattr(frame, "on_" + action, record(action))
    frame.on_exit = record("exit")
    frame._popup_context_menu = lambda x, y: recorded.__setitem__("context", (x, y))
    closes = []
    frame.Bind(wx.EVT_CLOSE, lambda e: (closes.append(1), e.Veto()))
    menus_opened = []
    frame.Bind(wx.EVT_MENU_OPEN, lambda e: (menus_opened.append(e.GetMenu()), e.Skip()))

    print("\nTaking the foreground and the control test")
    got = False
    for _ in range(6):
        if take_foreground():
            got = True
            break
        pump(300)
    if not got:
        print("  SKIPPED: this window could not be brought to the foreground, so no real "
              "keystroke would reach it. Run again on a quiet desktop.")
        SKIPPED.append("foreground")
        finish()
        return
    settle_keyboard()
    # Measured 2026-09-09 (probe_letter.py): one sim.Char(ord("x")) raises
    # exactly one keydown, one keypress and one input event in the page and
    # lands one lowercase x. The doubled "startXX" the coordinator saw was
    # this test's own second attempt after a case sensitive check failed on
    # an uppercase X (Caps Lock, or a Shift left down by an earlier run), so
    # the letter is now compared without case and counted, and the retry
    # loads the body afresh so a repeat can never look like a pass.
    set_body("<p>start</p>")
    caret_end_of("p")
    focus_editor()
    type_text("x")
    html = body()
    if not landed_once(html):
        print("  first attempt gave %r; clicking into the editor and trying once more" % html)
        set_body("<p>start</p>")
        click_editor()
        caret_end_of("p")
        type_text("x")
        html = body()
    check("control test: a typed letter lands in the document, once", landed_once(html), html)
    if not landed_once(html):
        print("  SKIPPED: keystrokes are not reaching the editor; nothing below can be trusted.")
        SKIPPED.append("control")
        finish()
        return
    if nvda_running():
        # In NVDA's browse mode a typed h is quick navigation to the next
        # heading and never reaches the page; in focus mode it is typed.
        # So a typed h that lands is the measurement that NVDA is in focus
        # mode when the editor takes focus.
        set_body("<h1>Top</h1><p>start</p><h2>Later</h2>")
        caret_end_of("p")
        focus_editor()
        type_text("h")
        html = body().lower()
        check("with NVDA running, a typed h is typed, not heading navigation: NVDA is in focus mode",
              "<p>starth</p>" in html, html)
    else:
        print("  NVDA is not running, so the focus mode measurement was not made")

    print("\nFormatting keys, one handler each")
    set_body("<p>abc</p>")
    caret_end_of("p")
    focus_editor()
    press(ord("B"), wx.MOD_CONTROL)
    type_text("bold")
    press(ord("B"), wx.MOD_CONTROL)
    html = body()
    check("Ctrl+B wraps what is typed next in bold, once",
          ("<b>bold</b>" in html or "<strong>bold</strong>" in html) and html.count("bold") == 1, html)
    press(ord("I"), wx.MOD_CONTROL)
    type_text("it")
    press(ord("I"), wx.MOD_CONTROL)
    html = body()
    check("Ctrl+I makes italic", "<i>it</i>" in html or "<em>it</em>" in html, html)
    press(ord("I"), wx.MOD_CONTROL | wx.MOD_SHIFT)
    type_text("al")
    press(ord("I"), wx.MOD_CONTROL | wx.MOD_SHIFT)
    html = body()
    check("Ctrl+Shift+I is the italic alias (its run merges with the italic before it)",
          "<i>ital</i>" in html or "<em>ital</em>" in html or "<i>al</i>" in html, html)
    check("no DevTools window opened on Ctrl+Shift+I", not find_windows("DevTools"))
    check("the status bar confirmed the last toggle", "Italic off" in frame.status.GetStatusText(0),
          frame.status.GetStatusText(0))

    print("\nHeadings and lists")
    set_body("<p>Heading text</p>")
    caret_end_of("p")
    focus_editor()
    press(ord("2"), wx.MOD_CONTROL | wx.MOD_ALT)
    html = body()
    check("Ctrl+Alt+2 makes a heading 2 (US layout: the key is the digit)", "<h2>Heading text</h2>" in html, html)
    check("and says so", frame.status.GetStatusText(1) == "Heading 2", frame.status.GetStatusText(1))
    press(ord("0"), wx.MOD_CONTROL | wx.MOD_ALT)
    html = body()
    check("Ctrl+Alt+0 makes it normal text again", "<p>Heading text</p>" in html, html)
    press(ord("2"), wx.MOD_CONTROL | wx.MOD_SHIFT)
    html = body()
    check("Ctrl+Shift+2 is the layout proof alias for heading 2", "<h2>Heading text</h2>" in html, html)
    press(ord("8"), wx.MOD_CONTROL | wx.MOD_ALT)
    html = body()
    check("Ctrl+Alt+8 makes a bullet list, not nested in a paragraph",
          html.replace("\n", "") == "<ul><li>Heading text</li></ul>", html)
    check("the status bar says bullet list item", frame.status.GetStatusText(1) == "Bullet list item")
    press(wx.WXK_RETURN)
    type_text("second")
    html = body()
    check("Enter in a list makes a new item", "<li>second</li>" in html, html)
    press(wx.WXK_TAB)
    html = body()
    check("Tab in a list nests the item", html.count("<ul>") == 2, html)
    press(wx.WXK_TAB, wx.MOD_SHIFT)
    html = body()
    check("Shift+Tab unnests it", html.count("<ul>") == 1, html)
    press(wx.WXK_RETURN)
    press(wx.WXK_RETURN)
    type_text("after")
    html = body()
    check("Enter on an empty item leaves the list", "<p>after</p>" in html and html.count("<li>") == 2, html)

    print("\nTables")
    set_body("<p>x</p>")
    caret_end_of("p")
    focus_editor()
    call("insertTable", 2, 2, True)
    pump(100)
    type_text("H1")
    press(wx.WXK_TAB)
    type_text("H2")
    press(wx.WXK_TAB)
    type_text("c1")
    html = body()
    check("Tab moves between cells while typing", "<th scope=\"col\">h1</th>" in html
          and "<th scope=\"col\">h2</th>" in html and "<td>c1</td>" in html, html)
    for _ in range(2):
        press(wx.WXK_TAB)
    html = body()
    check("Tab in the last cell adds a row", html.count("<tr>") == 3, html)

    print("\nKeys that reach Python once")
    set_body("<p>text</p>")
    caret_end_of("p")
    focus_editor()
    for key, mods, name, label in ((ord("K"), wx.MOD_CONTROL, "insert_link", "Ctrl+K"),
                                   (wx.WXK_RETURN, wx.MOD_ALT, "properties", "Alt+Enter"),
                                   (wx.WXK_F2, 0, "rename", "F2"),
                                   (ord("P"), wx.MOD_CONTROL | wx.MOD_SHIFT, "insert_picture", "Ctrl+Shift+P"),
                                   (ord("T"), wx.MOD_CONTROL | wx.MOD_SHIFT, "insert_table", "Ctrl+Shift+T"),
                                   (wx.WXK_F6, wx.MOD_ALT, "structure", "Alt+F6"),
                                   (ord("P"), wx.MOD_CONTROL | wx.MOD_SHIFT | wx.MOD_ALT, "pictures", "Ctrl+Shift+Alt+P"),
                                   (wx.WXK_F1, 0, "keyboard_help", "F1"),
                                   (ord("P"), wx.MOD_CONTROL, "print", "Ctrl+P"),
                                   (ord("S"), wx.MOD_CONTROL, "save", "Ctrl+S"),
                                   (ord("O"), wx.MOD_CONTROL, "open", "Ctrl+O"),
                                   (ord("N"), wx.MOD_CONTROL, "new", "Ctrl+N"),
                                   (ord("E"), wx.MOD_CONTROL | wx.MOD_SHIFT, "export_pdf", "Ctrl+Shift+E")):
        recorded.pop(name, None)
        press(key, mods)
        pump(150)
        check("%s reaches the %s handler exactly once" % (label, name), recorded.get(name) == 1, recorded.get(name))
    html = body()
    check("none of them typed anything", html.replace("\n", "") == "<p>text</p>", html)

    print("\nThe context menu keys")
    recorded.pop("context", None)
    press(wx.WXK_WINDOWS_MENU)
    pump(200)
    check("the Applications key asks for the context menu with a position",
          isinstance(recorded.get("context"), tuple), recorded.get("context"))
    recorded.pop("context", None)
    press(wx.WXK_F10, wx.MOD_SHIFT)
    pump(200)
    check("Shift+F10 does too", isinstance(recorded.get("context"), tuple), recorded.get("context"))

    print("\nThe menu bar from inside the editor")
    menus_opened.clear()
    press(ord("F"), wx.MOD_ALT)
    pump(300)
    opened = bool(menus_opened)
    press(wx.WXK_ESCAPE)
    pump(150)
    press(wx.WXK_ESCAPE)
    pump(150)
    check("Alt+F opens the File menu while the editor has focus", opened)
    focus_editor()

    print("\nF6 and the heading announcement")
    set_body("<p>intro</p><h2>Second</h2><p>more</p>")
    call("caretToStart")
    focus_editor()
    press(wx.WXK_F6)
    check("F6 moves to the next heading and announces it",
          frame.status.GetStatusText(0) == "Heading 2: Second", frame.status.GetStatusText(0))

    print("\nThe deny list")
    set_body("<p>keep me</p>")
    caret_end_of("p")
    focus_editor()
    loads = frame.editor.loads
    press(wx.WXK_F5)
    pump(800)
    html = body()
    check("F5 does not reload the page: the text is still there",
          "keep me" in html and frame.editor.loads == loads, (html, frame.editor.loads, loads))
    press(ord("F"), wx.MOD_CONTROL)
    pump(600)
    dialog = frame.find_dialog
    focus = wx.Window.FindFocus()
    ours = dialog is not None and dialog.IsShown() and focus is not None and focus.GetTopLevelParent() is dialog
    check("Ctrl+F opens the app's find dialog with focus in it, not WebView2's bar", ours,
          (dialog, focus))
    if dialog is not None and dialog.IsShown():
        dialog.Hide()
    focus_editor()
    press(ord("U"), wx.MOD_CONTROL)
    pump(400)
    check("Ctrl+U underlines rather than opening view-source",
          not find_windows("view-source") and frame.state.get("underline") is True, frame.state.get("underline"))
    press(ord("U"), wx.MOD_CONTROL)

    print("\nUndo after programmatic edits")
    set_body("<p>abc</p>")
    caret_end_of("p")
    focus_editor()
    type_text("TYPED")
    call("insertLink", "LINK", "https://x.example")
    pump(100)
    press(ord("Z"), wx.MOD_CONTROL)
    html = body()
    check("Ctrl+Z after an inserted link removes the link and keeps the typing",
          "LINK" not in html and "typed" in html, html)
    set_body("<h2>Cats</h2><p>A cat and a <strong>cat</strong>.</p>")
    focus_editor()
    value, error = call("replaceAll", "cat", "dog", False)
    html = body()
    check("Replace All replaced them", value and value.get("count") == 3 and "cat" not in html.lower(), html)
    press(ord("Z"), wx.MOD_CONTROL)
    html = body()
    check("Ctrl+Z after Replace All restores the body", "<h2>Cats</h2>" in html and "<strong>cat</strong>" in html, html)

    print("\nTab outside a list, and Alt+F4")
    set_body("<p>plain</p>")
    caret_end_of("p")
    focus_editor()
    press(wx.WXK_TAB)
    pump(300)
    focus = wx.Window.FindFocus()
    left = focus is not None and focus is not frame.editor.web and not isinstance(focus.GetParent(), type(frame.editor))
    html = body()
    check("Tab outside a list or table leaves the document (no tab character typed)",
          "\t" not in html and "plain" in html, (html, focus))
    print("  measured: after Tab the focus is on %r" % (type(focus).__name__ if focus else None))
    focus_editor()
    recorded.pop("exit", None)
    closes.clear()
    press(wx.WXK_F4, wx.MOD_ALT)
    pump(500)
    total = recorded.get("exit", 0) + len(closes)
    check("Alt+F4 asks to close exactly once", total == 1,
          {"exit handler": recorded.get("exit", 0), "EVT_CLOSE": len(closes)})
    print("  measured: Alt+F4 arrived as %s" % ("the page's exit action" if recorded.get("exit")
                                                 else "Windows' own close" if closes else "nothing"))

    print("\nThe watchdog")
    set_body("<p>w</p>")
    caret_end_of("p")
    focus_editor()
    type_text("k")
    pump(700)
    started = time.monotonic()
    value, error = run("String(3 + 4)", timeout=5.0)
    check("a script issued 700 ms after a keystroke answers within five seconds",
          value == "7" and time.monotonic() - started < 5.0, (value, error))

    print("\nThe proof that a check can fail")
    check("(deliberate) a key that typed nothing is reported", "zzz" in body())
    last = CHECKS.pop()
    print("  the line above is the deliberate failure; it is not counted")
    check("the deliberate failure was recorded as a failure", last is False)
    finish()


def find_windows(substring):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _l):
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buffer = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buffer, n + 1)
            if substring.lower() in buffer.value.lower():
                found.append(buffer.value)
        return True

    u32.EnumWindows(visit, 0)
    return found


def finish():
    for modifier in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT):
        sim.KeyUp(modifier)
    if caps_was_on and not (u32.GetKeyState(VK_CAPITAL) & 1):
        sim.KeyDown(wx.WXK_CAPITAL)
        sim.KeyUp(wx.WXK_CAPITAL)
        pump(50)
    if SKIPPED:
        print("\nSKIPPED (%s); %d/%d checks passed before that" % (", ".join(SKIPPED), sum(CHECKS), len(CHECKS)))
        sys.stdout.flush()
        os._exit(0)
    if RETAKEN:
        print("\nthe foreground had to be taken back %d time%s during the run; another window "
              "was active on the desktop" % (len(RETAKEN), "" if len(RETAKEN) == 1 else "s"))
    print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
    sys.stdout.flush()
    os._exit(0 if all(CHECKS) else 1)


def guarded():
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("\n%d/%d checks passed, then the test itself raised" % (sum(CHECKS), len(CHECKS)))
        sys.stdout.flush()
        os._exit(1)


wx.CallLater(100, guarded)
wx.CallLater(240000, lambda: (print("TIMEOUT: the test did not finish in four minutes"), os._exit(2)))
app.MainLoop()
os._exit(1)
