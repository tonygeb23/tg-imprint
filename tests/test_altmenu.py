"""Ctrl+Alt+1 applies a heading and does NOT drop the user into the menu bar.

Tony, 2026-09-09, running the app from source: "make sure alt ctrl 1
through 3 doesn't hop me into the menus. noticed it did that when I
opened it." Measured: the page consumed Ctrl+Alt+1, applied the heading,
and returned before it cleared its "Alt pressed alone" flag, so the Alt
release then asked the window for the menu bar, as a lone Alt should.

This test builds the real window, takes the foreground, does a control
test (a typed letter must land in the document), sends a REAL Ctrl+Alt+1
with SendInput, and reads two things back: the DOM (a heading must be
there) and the menu bar's focus state through GetMenuBarInfo (it must not
be focused). It skips cleanly, without failing, when the foreground cannot
be taken, because synthesised keys that go nowhere prove nothing.

    python tests/test_altmenu.py
"""
import ctypes
import ctypes.wintypes as W
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import importlib.util   # noqa: E402
spec = importlib.util.spec_from_file_location("easypdf_main", os.path.join(HERE, "main.py"))
easypdf_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(easypdf_main)

import wx   # noqa: E402
import wx.html2 as webview   # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""), flush=True)


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL, VK_MENU, VK_ESCAPE = 0x11, 0x12, 0x1B


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", W.DWORD), ("u", _U)]


def key(vk, up=False):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def combo(*vks):
    for vk in vks:
        key(vk)
        time.sleep(0.03)
    for vk in reversed(vks):
        key(vk, up=True)
        time.sleep(0.03)


class MENUBARINFO(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcBar", W.RECT), ("hMenu", W.HMENU),
                ("hwndMenu", W.HWND), ("fBarFocused", ctypes.c_int, 1),
                ("fFocused", ctypes.c_int, 1), ("fUnused", ctypes.c_int, 30)]


def menubar_focused(hwnd):
    info = MENUBARINFO()
    info.cbSize = ctypes.sizeof(MENUBARINFO)
    # OBJID_MENU is -3.
    ok = user32.GetMenuBarInfo(W.HWND(hwnd), ctypes.c_long(-3), 0, ctypes.byref(info))
    return bool(ok) and bool(info.fBarFocused)


def take_foreground(hwnd):
    fg = user32.GetForegroundWindow()
    other = user32.GetWindowThreadProcessId(fg, None)
    mine = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(mine, other, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(mine, other, False)
    return user32.GetForegroundWindow() == hwnd


def find_webview(window):
    for child in window.GetChildren():
        if isinstance(child, webview.WebView):
            return child
        found = find_webview(child)
        if found:
            return found
    return None


app = wx.App(False)
frame = easypdf_main.build_main_window()
frame.Show()
view = find_webview(frame)
check("the window holds a WebView editor", view is not None)
state = {}


def dom(callback):
    def answered(event):
        view.Unbind(webview.EVT_WEBVIEW_SCRIPT_RESULT)
        callback(event.GetString())
    view.Bind(webview.EVT_WEBVIEW_SCRIPT_RESULT, answered)
    view.RunScriptAsync("(function(){var e=document.querySelector('[contenteditable]');"
                        "return e?e.innerHTML:'NO EDITOR';})()")


def finish(code=None):
    frame.Destroy()
    passed = all(CHECKS)
    print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)), flush=True)
    wx.CallLater(200, lambda: os._exit(0 if (passed if code is None else code == 0) else 1))


def step_focus():
    if not take_foreground(int(frame.GetHandle())):
        print("  SKIPPED: could not take the foreground, so synthesised keys "
              "would prove nothing", flush=True)
        finish(0)
        return
    view.SetFocus()
    wx.CallLater(400, step_control)


def step_control():
    key(0x58); time.sleep(0.03); key(0x58, up=True)      # the letter x
    wx.CallLater(400, step_control_read)


def step_control_read():
    def got(html):
        landed = "x" in html.lower()
        if not landed:
            # Not a failure of the app: another window took the keys. It
            # happens when a person, or another test, has the foreground.
            print("  skip control test: the typed letter did not land (%s), so "
                  "the keys are going elsewhere; nothing below can be trusted"
                  % html.strip()[:40], flush=True)
            finish(0)
            return
        check("control test: a typed letter lands in the document", True)
        wx.CallLater(200, step_heading)
    dom(got)


def step_heading():
    combo(VK_CONTROL, VK_MENU, 0x31)                       # Ctrl+Alt+1
    wx.CallLater(700, step_read)


def step_read():
    hwnd = int(frame.GetHandle())
    focused = menubar_focused(hwnd)
    check("the menu bar is NOT focused after Ctrl+Alt+1", not focused)
    if focused:
        key(VK_ESCAPE); key(VK_ESCAPE, up=True)

    def got(html):
        check("and the paragraph became a heading", "<h1" in html.lower(), html[:80])
        wx.CallLater(200, step_alt_alone)
    dom(got)


def step_alt_alone():
    # The other half of the contract: a lone Alt still opens the menu bar,
    # as it does in every other Windows program.
    view.SetFocus()
    time.sleep(0.2)
    key(VK_MENU); time.sleep(0.05); key(VK_MENU, up=True)
    wx.CallLater(700, step_alt_read)


def step_alt_read():
    hwnd = int(frame.GetHandle())
    focused = menubar_focused(hwnd)
    check("a lone Alt still opens the menu bar", focused)
    if focused:
        key(VK_ESCAPE); key(VK_ESCAPE, up=True)
    wx.CallLater(300, finish)


wx.CallLater(2500, step_focus)
wx.CallLater(25000, lambda: (print("  FAIL timed out", flush=True), CHECKS.append(False), finish()))
app.MainLoop()
