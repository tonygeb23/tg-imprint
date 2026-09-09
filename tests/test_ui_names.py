"""Every dialog's controls have an accessible name; two source rules.

    python tests/test_ui_names.py

Walks every dialog the window can show, built with fake data: every
focusable control has an accessible name (its own label, a static text
before it, or a _Named accessible object), no dead tab stop (the picture
preview refuses focus), and then two greps: no wx.MessageBox with a
newline in it anywhere under easypdf/ui/, and no synchronous RunScript(
anywhere under easypdf/ui/ or in editor_page.py.

The window holds a WebView, so the process ends with os._exit.
"""
import ctypes
import os
import re
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

from easypdf import constants as C  # noqa: E402
from easypdf import updatedialog  # noqa: E402
from easypdf.settings import Settings  # noqa: E402
from easypdf.ui import dialogs, keymap, main_window  # noqa: E402
from easypdf.ui.doc_properties_dialog import DocPropertiesDialog  # noqa: E402
from easypdf.ui.find_dialog import FindDialog  # noqa: E402
from easypdf.ui.hyperlink_dialog import LinkDialog  # noqa: E402
from easypdf.ui.image_dialog import PictureDialog  # noqa: E402
from easypdf.ui.pictures_dialog import PicturesDialog  # noqa: E402
from easypdf.ui.preferences_dialog import PreferencesDialog  # noqa: E402
from easypdf.ui.structure_dialog import StructureDialog  # noqa: E402
from easypdf.ui.table_dialog import TableDialog  # noqa: E402

CHECKS = []
DOT = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
       "DwAChwGA60e6kgAAAABJRU5ErkJggg==")


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" and not condition else ""))


SELF_LABELLED = (wx.Button, wx.CheckBox, wx.RadioButton, wx.ToggleButton, wx.StaticText,
                 wx.Notebook)
DEFAULT_NAMES = {"text", "choice", "comboBox", "spinCtrl", "listBox", "gauge", "staticBitmap",
                 "panel", "wxSpinCtrl", "spinctrl", "listbox", "combobox", "button", "check"}


def named(control, siblings_before):
    """Why this control has a name, or "" when it has none."""
    if isinstance(control, SELF_LABELLED) and control.GetLabel().strip():
        return "its own label"
    if getattr(control, "_easypdf_accessible", None) is not None:
        return "a _Named accessible object"
    parent = control.GetParent()
    if parent is not None and getattr(parent, "_easypdf_accessible", None) is not None:
        return "its composite's _Named accessible object"
    name = (control.GetName() or "").strip()
    if name and name not in DEFAULT_NAMES:
        return "SetName (%s), with a static before it" % name if siblings_before else "SetName only"
    if siblings_before:
        return "a static text before it"
    return ""


def walk(window, path, problems, statics_seen=None):
    """Every focusable descendant, with what names it."""
    statics_seen = [] if statics_seen is None else statics_seen
    for child in window.GetChildren():
        label = "%s > %s(%s)" % (path, type(child).__name__, (child.GetName() or "")[:30])
        if isinstance(child, wx.StaticText) and child.GetLabel().strip():
            statics_seen.append(child)
        focusable = child.IsEnabled() and child.IsShown() and child.AcceptsFocusFromKeyboard()
        if focusable and not isinstance(child, (wx.Panel, wx.Notebook)) and type(child).__name__ != "WebView":
            why = named(child, bool(statics_seen))
            # A static counts only if it is the nearest label: reset after
            # each focusable control so a later field cannot borrow it.
            if not why or why == "SetName only":
                problems.append(label + (" (" + why + ")" if why else " (no name at all)"))
            statics_seen.clear()
        walk(child, label, problems, statics_seen)


def audit(title, dialog, expect_focus=None):
    problems = []
    walk(dialog, title, problems)
    check("%s: every focusable control is named" % title, not problems, problems)
    if expect_focus is not None:
        check("%s: focus starts in %s" % (title, expect_focus[1]),
              wx.Window.FindFocus() is expect_focus[0] or not dialog.IsShown())
    return problems


app = wx.App(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
frame.Show()
wx.Yield()

print("\nThe main window")
problems = []
walk(frame.toolbar, "toolbar", problems)
check("every toolbar control is named", not problems, problems)
check("the toolbar style choice carries an accessible object",
      getattr(frame.toolbar.style, "_easypdf_accessible", None) is not None)
check("the status bar has four fields", frame.status.GetFieldsCount() == 4)
check("the window has its icons", frame.GetIcons().GetIconCount() == 10)
check("the window title names the app", C.APP_NAME in frame.GetTitle())

print("\nEvery dialog")
d = DocPropertiesDialog(frame, {"title": "T", "author": "A", "lang": "xx-YY", "subject": "S",
                                "page_size": "A4", "margin_inches": 0.75})
audit("Document properties", d)
check("Document properties: an unlisted language lands in the custom field",
      d.language.custom.GetValue() == "xx-YY")
d.Destroy()

d = PictureDialog(frame, frame, spec=None)
audit("Insert picture", d)
check("Insert picture: the preview refuses focus", not d.preview.AcceptsFocus()
      and not d.preview.AcceptsFocusFromKeyboard())
d.Destroy()
spec = {"src": DOT, "alt": "A dot", "caption": "cap", "width": "half", "place": "centre",
        "altSource": "ai:google", "decorative": False}
d = PictureDialog(frame, frame, spec=spec)
audit("Picture properties", d)
check("Picture properties: the description is pre-filled", d.alt.GetValue() == "A dot")
d.Destroy()

d = LinkDialog(frame, text="t", href="https://x", editing=True)
audit("Insert link", d)
d.Destroy()
d = TableDialog(frame)
audit("Insert table", d)
d.Destroy()
d = FindDialog(frame, frame)
audit("Find and replace", d)
d.Destroy()
d = StructureDialog(frame, frame, [{"index": 0, "level": 1, "text": "A"},
                                   {"index": 1, "level": 2, "text": "B"}])
audit("Structure navigator", d)
check("Structure navigator: items are indented by level", d.list.GetString(1).startswith("    Heading 2"))
d.Destroy()
d = PicturesDialog(frame, frame, [spec, dict(spec, alt="", altSource="pdf", needsAlt=True),
                                  dict(spec, alt="", decorative=True, altSource="")])
audit("Pictures", d)
rows = [d.list.GetString(i) for i in range(d.list.GetCount())]
check("Pictures: rows say described by AI, no description, decorative",
      "described by AI" in rows[0] and "no description" in rows[1] and "decorative" in rows[2], rows)
d.Destroy()
d = PreferencesDialog(frame, frame, settings)
audit("Preferences", d)
check("Preferences: the speech choice carries the CONVENTIONS wording",
      tuple(d.speech.GetString(i) for i in range(3)) == C.SPEECH_LABELS)
d.Destroy()
d = dialogs.TextDialog(frame, "Report", "line one\nline two",
                       buttons=(("Open &PDF", "open"), ("&Close", "close")), field_label="&Report")
audit("Text dialog", d)
check("Text dialog: the field is read only with the text in it",
      not d.field.IsEditable() and "line two" in d.field.GetValue())
d.Destroy()
d = dialogs.RecoveryDialog(frame, [("snap.epdf", "doc.epdf", "2026-09-09 10:00", "Doc")])
audit("Recovery", d)
d.Destroy()
d = dialogs.KeyboardHelpDialog(frame, keymap.render_text())
audit("Keyboard help", d)
d.Destroy()
d = dialogs.BusyDialog(frame, frame, "Making the PDF", "Starting")
audit("Progress", d)
d.finish()
d = updatedialog.UpdateDialog(frame, C.APP_NAME, C.APP_VERSION, new_version="9.9.9", notes="notes")
audit("Update available", d)
d.Destroy()
d = updatedialog.DownloadProgressDialog(frame, frame, "version 9.9.9")
audit("Download progress", d)
d.Destroy()

print("\nThe source rules")
ui_dir = os.path.join(HERE, "easypdf", "ui")
offenders = []
for name in sorted(os.listdir(ui_dir)):
    if not name.endswith(".py"):
        continue
    text = open(os.path.join(ui_dir, name), encoding="utf-8").read()
    for match in re.finditer(r"wx\.MessageBox\((.*?)\)", text, re.S):
        if "\\n" in match.group(1):
            offenders.append("%s: %s" % (name, match.group(0)[:80].replace("\n", " ")))
check("no wx.MessageBox with a newline anywhere under easypdf/ui/", not offenders, offenders)
sync = []
for name in sorted(os.listdir(ui_dir)) + ["../editor_page.py"]:
    if not name.endswith(".py"):
        continue
    text = open(os.path.join(ui_dir, name), encoding="utf-8").read()
    for line_no, line in enumerate(text.splitlines(), 1):
        if re.search(r"(?<![A-Za-z_])RunScript\(", line) and "RunScriptAsync" not in line:
            sync.append("%s:%d: %s" % (name, line_no, line.strip()[:80]))
check("no synchronous RunScript( under easypdf/ui/ or in editor_page.py", not sync, sync)
dashes = []
for folder, files in ((ui_dir, os.listdir(ui_dir)), (os.path.join(HERE, "easypdf"), ["editor_page.py", "settings.py"])):
    for name in files:
        if name.endswith(".py"):
            text = open(os.path.join(folder, name), encoding="utf-8").read()
            if chr(8212) in text or chr(8211) in text:
                dashes.append(name)
check("no em or en dash in the UI sources", not dashes, dashes)
strings = open(os.path.join(HERE, "docs", "STRINGS.md"), encoding="utf-8").read()
flat = " ".join(strings.split())
check("docs/STRINGS.md has the Worker B heading with strings under it",
      "## Worker B (UI and accessibility)" in strings
      and " ".join(main_window.S["first_run"].split()) in flat)

print("\nThe proof that a check can fail")
check("(deliberate) a wrong expectation is reported as FAIL", frame.status.GetFieldsCount() == 99)
last = CHECKS.pop()
probe = wx.Dialog(frame, title="probe")
wx.TextCtrl(probe)                       # no label, no name
problems = []
walk(probe, "probe", problems)
probe.Destroy()
check("the walk reports an unnamed text field", bool(problems), problems)
check("the deliberate failure was recorded as a failure", last is False)

frame.Destroy()
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.stdout.flush()
os._exit(0 if all(CHECKS) else 1)
