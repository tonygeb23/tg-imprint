"""Every toolbar button has a name, in every theme and every label mode.

    python tests/test_toolbar_names.py

The drawn toolbar carries its words inside the bitmap and the icons mode has
none, so the button text a screen reader gets from a toolbar was empty. The
0.3.0 audit read name None off every button in dark, yellow on black and icons
only. This reads the real tree through UI Automation.
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-tb-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-tb-local-")

import wx  # noqa: E402

from tgimprint.ui import keymap, theme, toolbar  # noqa: E402

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  ok   %s" % name)
    else:
        failed += 1
        print("  FAIL %s  %s" % (name, detail))


try:
    import comtypes.client as cc
    cc.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as U
except ImportError:
    print("skipped: comtypes is not installed, so the tree cannot be read")
    sys.exit(0)

app = wx.App(False)
auto = cc.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}", interface=U.IUIAutomation)
walker = auto.RawViewWalker
wanted = [toolbar.TIPS.get(a, keymap.entry(a).plain_label.rstrip("."))
          for a in toolbar.LAYOUT if a not in (None, "style")]


def buttons(element, out):
    child = walker.GetFirstChildElement(element)
    while child:
        try:
            if child.CurrentLocalizedControlType in ("button", "check box", "toggle button", "menu item", "split button"):
                out.append(child.CurrentName or "")
        except Exception:
            pass
        buttons(child, out)
        child = walker.GetNextSiblingElement(child)
    return out


class Frame(wx.Frame):
    def __init__(self):
        super().__init__(None, size=(1400, 300))
        self.ids = {}

    def id_of(self, action):
        return self.ids.setdefault(action, wx.NewIdRef())


for palette_name in ("normal", "dark", "yellow_on_black"):
    for mode in ("icons_labels", "icons", "labels"):
        frame = Frame()
        bar = toolbar.EditorToolBar(frame, frame.id_of, mode=mode, pal=theme.palette(palette_name))
        frame.SetToolBar(bar)
        frame.Show()
        for _ in range(8):
            wx.Yield()
            time.sleep(0.02)
        found = buttons(auto.ElementFromHandle(int(bar.GetHandle())), [])
        check("%s, %s: every tool is named" % (palette_name, mode),
              all(n in found for n in wanted) and "" not in found, (found, wanted))
        frame.Destroy()
        wx.Yield()

print("\n%d/%d checks passed" % (passed, passed + failed))
sys.exit(1 if failed else 0)
