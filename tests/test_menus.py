"""Every menu and every key, audited off the real window.

    python tests/test_menus.py

- every menu item, and every keymap entry, has a handler on the frame;
- every accelerator in the returned list has a menu item;
- the CONVENTIONS.md contract keys are present;
- no two entries share a key, and no two items in one menu share a
  mnemonic (Windows cycles between duplicates instead of activating);
- the page's generated key map lists every entry, with the AltGr gate on
  Ctrl+Alt+digit and the physical key gate on the Ctrl+Shift+digit aliases;
- docs/KEYBOARD.md matches keymap.render_markdown() byte for byte.

The window holds a WebView, so the process ends with os._exit.
"""
import ctypes
import os
import sys
import tempfile

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="easypdf-test-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="easypdf-test-local-")

import wx  # noqa: E402

from easypdf.settings import Settings  # noqa: E402
from easypdf.ui import keymap  # noqa: E402
from easypdf.ui import main_window  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" and not condition else ""))


def walk(menu, path=""):
    found = []
    for item in menu.GetMenuItems():
        if item.IsSeparator():
            continue
        sub = item.GetSubMenu()
        if sub is not None:
            found.extend(walk(sub, path + item.GetItemLabelText() + " > "))
            continue
        found.append((path, item))
    return found


app = wx.App(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
bar = frame.GetMenuBar()

print("\nThe menu bar")
titles = [bar.GetMenuLabel(i) for i in range(bar.GetMenuCount())]
check("seven menus: File, Edit, Format, Insert, Tools, View, Help",
      [t.replace("&", "") for t in titles] == ["File", "Edit", "Format", "Insert", "Tools", "View", "Help"],
      titles)
check("every menu has a mnemonic", all("&" in t for t in titles), titles)
letters = [t[t.index("&") + 1].lower() for t in titles if "&" in t]
check("no two menus share one", len(letters) == len(set(letters)), letters)

print("\nEvery item has a handler and a unique mnemonic in its menu")
unbound, no_mnemonic, duplicates = [], [], []
seen_ids = set()
total = 0
for position in range(bar.GetMenuCount()):
    menu = bar.GetMenu(position)
    title = bar.GetMenuLabel(position)
    seen = {}
    for path, item in walk(menu):
        total += 1
        where = "%s > %s%s" % (title, path, item.GetItemLabelText())
        label = item.GetItemLabel().split("\t")[0]
        if item.GetId() in frame._action_of:
            action = frame._action_of[item.GetId()]
            if frame.handler_for(action) is None:
                unbound.append(where)
        elif item.GetId() not in [int(i) for i in frame._recent_ids] and item.IsEnabled():
            unbound.append(where)
        if "&" not in label:
            if item.IsEnabled():                     # a greyed placeholder needs none
                no_mnemonic.append(where)
        else:
            letter = label[label.index("&") + 1].lower()
            key = (path, letter)
            if key in seen:
                duplicates.append("%s and %s share Alt+%s" % (seen[key], where, letter.upper()))
            seen[key] = where
        seen_ids.add(item.GetId())
check("%d items walked" % total, total >= 60, total)
check("every item has a handler", not unbound, unbound)
check("every item has a mnemonic", not no_mnemonic, no_mnemonic)
check("no two items in one menu share a mnemonic", not duplicates, duplicates)

print("\nEvery keymap entry")
entries = keymap.ENTRIES
in_menus = set()
for position in range(bar.GetMenuCount()):
    for _path, item in walk(bar.GetMenu(position)):
        if item.GetId() in frame._action_of:
            in_menus.add(frame._action_of[item.GetId()])
missing = [e.action for e in entries if e.action not in in_menus and e.action != "context_menu"]
check("every entry except the context menu has a menu item", not missing, missing)
handlers = [e.action for e in entries if frame.handler_for(e.action) is None and e.scope != "native"]
check("every non-native entry has a handler", not handlers, handlers)
check("the context menu list names real entries",
      all(isinstance(i, tuple) or i == "-" or i in keymap.BY_ACTION for i in keymap.CONTEXT_MENU))

print("\nThe accelerator list")
table = frame._build_accelerators()
check("_build_accelerators returns a list", isinstance(table, list) and len(table) > 40, len(table))
ids_in_table = {entry.GetCommand() for entry in table}
check("every accelerator points at a menu item", ids_in_table <= seen_ids,
      [frame._action_of.get(i) for i in ids_in_table - seen_ids])
pairs = {}
for entry in table:
    pairs.setdefault((entry.GetFlags(), entry.GetKeyCode()), set()).add(entry.GetCommand())
shared = [k for k, v in pairs.items() if len(v) > 1]
check("no two entries share a key in the wx table", not shared, shared)
chords = {}
for e in entries:
    for text in e.keys + e.page_keys:
        chords.setdefault(keymap.chord(text), []).append(e.action)
shared = {k: v for k, v in chords.items() if len(v) > 1}
check("no two entries share a chord in the page map", not shared, shared)
native = [e.action for e in entries if e.scope == "native"]
check("native entries are kept out of the wx table",
      not any(frame.id_of(a) in ids_in_table for a in native), native)

print("\nThe CONVENTIONS.md contract")
for key, action in keymap.CONTRACT.items():
    e = keymap.entry(action)
    check("%s is %s" % (key, e.plain_label), key in e.keys or key in e.page_keys, e.keys)
check("Ctrl+I is italic and Ctrl+Shift+I is its alias",
      keymap.entry("italic").keys == ("Ctrl+I", "Ctrl+Shift+I"))
check("Ctrl+Shift+P inserts a picture", "Ctrl+Shift+P" in keymap.entry("insert_picture").keys)
check("there is no font dialog and no Ctrl+Shift+F",
      "font" not in keymap.BY_ACTION and not any("Ctrl+Shift+F" in e.keys for e in entries))
check("Alt+F4 exits and nothing else uses it",
      chords.get("alt+f4") == ["exit"], chords.get("alt+f4"))
check("Escape is bound to nothing", "escape" not in chords)

print("\nThe page's generated key map")
bindings = keymap.page_bindings()
bound = {(b["chord"], b.get("code")) for b in bindings}
check("every key of every entry is in the page map",
      all((keymap.chord(t), "Digit" + keymap.chord(t)[-1] if e.digit and "shift" in keymap.chord(t) else None) in bound
          for e in entries for t in e.keys + e.page_keys))
digit_gates = [b for b in bindings if b["chord"].startswith("ctrl+alt+") and b["chord"][-1].isdigit()]
check("Ctrl+Alt+digit is gated on the event's key (the AltGr rule)",
      digit_gates and all(b.get("gate") == "key" for b in digit_gates), digit_gates)
code_gates = [b for b in bindings if b["chord"].startswith("ctrl+shift+") and b["chord"][-1].isdigit()]
check("Ctrl+Shift+digit aliases are gated on the physical key code",
      code_gates and all(b.get("code") == "Digit" + b["chord"][-1] for b in code_gates), code_gates)
check("the deny list still blocks F5, Ctrl+Shift+R and F12",
      {"f5", "ctrl+shift+r", "f12"} <= set(keymap.DENY_CHORDS))
check("nothing in the deny list is also an app key", not (set(keymap.DENY_CHORDS) & set(chords)),
      set(keymap.DENY_CHORDS) & set(chords))
check("Ctrl+F, Ctrl+P, Ctrl+S and Ctrl+O are app keys, so the page swallows them",
      all(c in chords for c in ("ctrl+f", "ctrl+p", "ctrl+s", "ctrl+o")))
scopes = {b["scope"] for b in bindings}
check("scopes are page, app and native only", scopes <= {"page", "app", "native"}, scopes)
conditional = {b["action"] for b in bindings if b["conditional"]}
check("Tab, Shift+Tab and Delete are the conditional keys",
      conditional == {"indent", "outdent", "delete_object"}, conditional)

print("\nThe toolbar")
tools = [a for a in ("new", "open", "save", "bold", "italic", "underline", "strike", "bullets",
                     "numbers", "quote", "align_left", "align_center", "align_right",
                     "align_justify", "insert_link", "insert_picture", "insert_table", "export_pdf")]
check("every toolbar tool is a keymap entry with a handler",
      all(frame.toolbar.FindById(frame.id_of(a)) is not None and frame.handler_for(a) for a in tools))
check("every tool's tooltip names its key",
      all(keymap.entry(a).primary in (frame.toolbar.FindById(frame.id_of(a)).GetShortHelp() or "")
          for a in tools if keymap.entry(a).primary))

print("\ndocs/KEYBOARD.md is generated from the same list")
doc = os.path.join(HERE, "docs", "KEYBOARD.md")
rendered = keymap.render_markdown()
try:
    on_disk = open(doc, encoding="utf-8").read()
except OSError:
    on_disk = ""
check("docs/KEYBOARD.md exists", bool(on_disk))
check("and matches keymap.render_markdown() exactly (regenerate with python easypdf/ui/keymap.py)",
      on_disk == rendered)
check("it documents the AltGr rule", "AltGr" in rendered)
check("it lists every entry", all(e.plain_label in rendered for e in entries))
check("the F1 text lists every key", all(k in keymap.render_text() for e in entries for k in e.keys))
check("no dash in either", not any(ch in rendered + keymap.render_text() for ch in (chr(8212), chr(8211))))

print("\nThe proof that a check can fail")
check("(deliberate) a key that does not exist", "Ctrl+Alt+Shift+F13" in chords)
last = CHECKS.pop()
print("  the line above is the deliberate failure; it is not counted")
check("the deliberate failure was recorded as a failure", last is False)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.stdout.flush()
os._exit(0 if all(CHECKS) else 1)
