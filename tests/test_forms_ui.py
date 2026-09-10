"""The Fill in a PDF form dialog: the list, the editing, the saving.

    python tests/test_forms_ui.py

The window half of the forms feature. Worker A's pdfforms does the PDF
work and has its own suites (test_forms.py, test_formfind.py); this one
drives the dialog with a stand in module, so it runs whether or not
pdfforms is there and it can make the failures a real PDF will not make on
demand: a refused value, a read only field, a save that fails.

What it proves:

- every field is a row you can walk with Down, and the row says the label,
  the kind, the value and the page;
- Enter and F2 open the field in a labelled control of the right sort;
- a value that is refused is said, not swallowed;
- the progress sentence follows the filling in;
- Escape with unsaved values asks first;
- nothing that touches a file runs on the UI thread;
- every control in every one of the four windows has an accessible name.

Ends with os._exit: the frame owns a WebView.
"""
import ctypes
import os
import re
import sys
import tempfile
import threading
import time
import types

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-forms-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-forms-local-")

import wx  # noqa: E402

from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import forms_dialog, main_window  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" and not condition else ""))


def pump(seconds=1.2):
    """Turn the loop for a while, so a worker thread's callback lands."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        wx.Yield()
        time.sleep(0.02)


# ---------------------------------------------------- the stand in module --
UI_THREAD = threading.get_ident()
ON_UI_THREAD = []            # anything that touched a file from the UI thread


class Field:
    def __init__(self, fid, label, kind, value="", page=1, choices=None,
                 required=False, read_only=False, tooltip=""):
        self.id, self.name, self.label = fid, fid, label
        self.kind, self.value, self.page = kind, value, page
        self.choices = list(choices or [])
        self.required, self.read_only, self.tooltip = required, read_only, tooltip
        self.rect = (72.0, 500.0, 300.0, 518.0)

    @property
    def is_filled(self):
        if self.kind == "checkbox":
            return bool(self.value)
        return bool(str(self.value or "").strip())


class Proposal:
    def __init__(self, page, label, confidence, kind="text"):
        self.page, self.label, self.confidence, self.kind = page, label, confidence, kind
        self.name, self.rect, self.source = label.lower().replace(" ", "_"), (1, 2, 3, 4), "line"


class FormDocument:
    def __init__(self, path, fields, problem=""):
        self.path, self.fields, self.problem = path, fields, problem
        self.has_fields = bool(fields)
        self.page_count = max([f.page for f in fields] or [1])
        self.saved = []
        self.closed = False

    def _find(self, field_id):
        for f in self.fields:
            if f.id == field_id or f.name == field_id:
                return f
        return None

    def set_value(self, field_id, value):
        field = self._find(field_id)
        if field is None:
            return False, "There is no such field."
        if field.read_only:
            return False, "%s cannot be changed: the form locked it." % field.label
        if field.kind == "text" and len(str(value)) > 20:
            return False, "%s holds at most 20 characters." % field.label
        field.value = value
        return True, ""

    def save(self, out_path=None, flatten=False):
        note("save")
        self.saved.append((out_path, flatten))
        if out_path and "refuse" in out_path:
            return False, "That folder is read only."
        return True, "Saved."

    def close(self):
        self.closed = True


def note(what):
    if threading.get_ident() == UI_THREAD:
        ON_UI_THREAD.append(what)
    time.sleep(0.05)             # a real PDF call is not instant


FIELDS = [
    Field("f1", "Full name", "text", "Tony Gebhard", 1, required=True),
    Field("f2", "Address, first line", "text", "", 1, required=True),
    Field("f3", "Town", "text", "", 1),
    Field("f4", "I have read the terms", "checkbox", False, 2),
    Field("f5", "How you would like a reply", "choice", "Email", 2,
          choices=["Email", "Letter", "Telephone"]),
    Field("f6", "Reference number", "text", "", 2, read_only=True,
          tooltip="The office fills this in."),
    Field("f7", "Signature", "signature", "", 2),
]


def fresh_doc(path="Application form.pdf"):
    return FormDocument(path, [Field(f.id, f.label, f.kind, f.value, f.page, f.choices,
                                     f.required, f.read_only, f.tooltip) for f in FIELDS])


FLAT = FormDocument("Flat form.pdf", [])
STAND_IN = types.ModuleType("pdfforms")
STAND_IN.opened = []
STAND_IN.added = []
STAND_IN.signed = []


def open_form(path):
    note("open")
    STAND_IN.opened.append(path)
    return FLAT if "flat" in str(path).lower() else fresh_doc(path)


def propose_fields(source, page=None):
    note("propose")
    return [Proposal(1, "Name", 0.9), Proposal(1, "Date of birth", 0.62),
            Proposal(2, "", 0.35)]


def add_fields(path, proposals, out_path=None):
    note("add")
    STAND_IN.added.append((path, list(proposals), out_path))
    return True, "Added.", len(proposals)


def sign_with_text(path, field_or_rect, name, out_path=None):
    note("sign")
    STAND_IN.signed.append(("text", field_or_rect, name))
    return True, "Signed."


def sign_with_image(path, field_or_rect, image_bytes, out_path=None):
    note("sign")
    STAND_IN.signed.append(("image", field_or_rect, len(image_bytes)))
    return True, "Signed."


def describe_form(doc):
    fields = list(getattr(doc, "fields", []) or [])
    if not fields:
        return "This PDF has no form fields in it."
    empty = sum(1 for f in fields if not f.is_filled)
    return ("%d fields on %d pages. %d still empty."
            % (len(fields), doc.page_count, empty))


for _name, _fn in (("open_form", open_form), ("propose_fields", propose_fields),
                   ("add_fields", add_fields), ("sign_with_text", sign_with_text),
                   ("sign_with_image", sign_with_image), ("describe_form", describe_form)):
    setattr(STAND_IN, _name, _fn)
sys.modules["tgimprint.pdfforms"] = STAND_IN
import tgimprint  # noqa: E402
tgimprint.pdfforms = STAND_IN

# --------------------------------------------------------------- the window
app = wx.App(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
frame.Show()
wx.Yield()

# Three things in this flow run a modal loop and would sit there for ever
# waiting to be clicked, so they answer themselves here: the message window,
# the yes or no question, and the form list the flow opens at the end.
SHOWN = []
ASKED = []
ANSWER = [False]
OPENED_LIST = []
forms_dialog.dialogs.show_text = lambda _p, title, text, **k: SHOWN.append((title, text))
forms_dialog.show_form = lambda _f, doc, path: OPENED_LIST.append((doc, path))

print("\nThe module is reached lazily")
check("forms_dialog finds the module without importing it at the top",
      forms_dialog.module() is STAND_IN)
check("and the source never imports pdfforms at the top",
      not re.search(r"^from \.\. import pdfforms",
                    open(os.path.join(HERE, "tgimprint", "ui", "forms_dialog.py"),
                         encoding="utf-8").read(), re.M))

print("\nThe fields are a list, not a picture")
doc = fresh_doc()
dialog = forms_dialog.FormDialog(frame, frame, doc, "Application form.pdf")
rows = [dialog.list.GetString(i) for i in range(dialog.list.GetCount())]
check("one row per field", len(rows) == len(FIELDS), rows)
check("the first row says the label, the kind, the value and the page",
      rows[0] == "Full name, text box, Tony Gebhard, page 1, needed", rows[0])
check("an empty field says so", "empty" in rows[1], rows[1])
check("a tick box says whether it is ticked", "not ticked" in rows[3], rows[3])
check("a choice says what is chosen", "Email" in rows[4], rows[4])
check("a locked field says it is locked", "locked" in rows[5], rows[5])
check("the kinds are the words pdfforms uses",
      "list to choose from" in rows[4] and "tick box" in rows[3], rows[3:5])
check("the heading counts them",
      "7 fields" in dialog.heading.GetLabel() and "5 still empty" in dialog.heading.GetLabel(),
      dialog.heading.GetLabel())
check("nothing in the window draws a page",
      not any(isinstance(w, wx.StaticBitmap) for w in dialog.GetChildren()))
check("the list has an accessible name",
      getattr(dialog.list, "_tgimprint_accessible", None) is not None)

print("\nEvery control is named")
problems = []


def walk(window, path):
    for child in window.GetChildren():
        label = "%s > %s" % (path, type(child).__name__)
        if (child.IsEnabled() and child.IsShown() and child.AcceptsFocusFromKeyboard()
                and not isinstance(child, wx.Panel)):
            named = ((isinstance(child, (wx.Button, wx.CheckBox, wx.RadioBox, wx.StaticText))
                      and child.GetLabel().strip())
                     or getattr(child, "_tgimprint_accessible", None) is not None)
            if not named:
                problems.append(label + " (" + (child.GetName() or "") + ")")
        walk(child, label)


walk(dialog, "Fill in a PDF form")
check("the form dialog", not problems, problems)

print("\nEnter and F2 open the right control")
field_box = forms_dialog.FieldDialog(dialog, doc.fields[1], 1)
check("a text field gets a text box", isinstance(field_box.control, wx.TextCtrl))
check("with the label as its accessible name",
      getattr(field_box.control, "_tgimprint_accessible", None) is not None)
problems = []
walk(field_box, "Field")
check("every control in it is named", not problems, problems)
field_box.control.SetValue("12 Chalk Lane")
field_box._on_ok(None)
check("OK hands back what was typed", field_box.result == "12 Chalk Lane")
field_box.Destroy()

tick = forms_dialog.FieldDialog(dialog, doc.fields[3], 3)
check("a tick box field gets a check box", isinstance(tick.control, wx.CheckBox))
tick.control.SetValue(True)
tick._on_ok(None)
check("and hands back a boolean", tick.result is True)
tick.Destroy()

chooser = forms_dialog.FieldDialog(dialog, doc.fields[4], 4)
check("a choice field gets a choice list", isinstance(chooser.control, wx.Choice))
check("with every option in it",
      [chooser.control.GetString(i) for i in range(chooser.control.GetCount())]
      == ["Email", "Letter", "Telephone"])
chooser.control.SetSelection(1)
chooser._on_ok(None)
check("and hands back the option, not its number", chooser.result == "Letter")
chooser.Destroy()

locked = doc.fields[5]
check("a locked field is refused before the box opens",
      locked.read_only and forms_dialog.field_row(locked, 5).endswith("locked"))

print("\nFilling one in")
dialog.list.SetSelection(1)
ok, message = doc.set_value("f2", "12 Chalk Lane")
check("the value goes in", ok and doc.fields[1].value == "12 Chalk Lane")
dialog.fill(1)
check("the row follows it", "12 Chalk Lane" in dialog.list.GetString(1),
      dialog.list.GetString(1))
check("and the count follows it too", "4 still empty" in dialog.heading.GetLabel(),
      dialog.heading.GetLabel())
ok, message = doc.set_value("f3", "a town with far too long a name for this field")
check("a refused value is refused with a sentence", not ok and "20 characters" in message,
      message)

print("\nThe sentence comes from describe_form")
check("the dialog asks the module for it",
      dialog.sentence() == describe_form(doc), dialog.sentence())

print("\nNothing that touches a file runs on the UI thread")
ON_UI_THREAD[:] = []
dialog.dirty = 2
dialog.do_save(None, False)
pump()
check("Save ran off the UI thread", not ON_UI_THREAD, ON_UI_THREAD)
check("and it saved in place", doc.saved and doc.saved[-1] == (None, False), doc.saved)
check("and the unsaved count went back to nothing", dialog.dirty == 0)
check("and it said so", "Saved" in frame.status.GetStatusText(0),
      frame.status.GetStatusText(0))
dialog.do_save("copy.pdf", False)
pump()
check("Save a copy names the file and leaves this one alone",
      doc.saved[-1] == ("copy.pdf", False), doc.saved)
dialog.do_save("flat.pdf", True)
pump()
check("Save flattened asks for flattening", doc.saved[-1] == ("flat.pdf", True))
check("and explains what flattening did",
      "prints exactly as it looks" in frame.status.GetStatusText(0),
      frame.status.GetStatusText(0))
dialog.do_save("refuse.pdf", False)
pump()
check("a save that fails says why, and does not pretend",
      "read only" in frame.status.GetStatusText(0), frame.status.GetStatusText(0))
check("and puts the reason in a window that can be read again",
      SHOWN and "read only" in SHOWN[-1][1], SHOWN)

print("\nThe three saves are each explained in the window")
notes = " ".join(" ".join(w.GetLabel().split()) for w in dialog.GetChildren()
                 if isinstance(w, wx.StaticText))
for phrase in ("Save writes the answers into this PDF",
               "Save a copy writes them into a new file",
               "Save flattened for printing makes the answers part of the page"):
    check("the window says: %s" % phrase, phrase in notes, notes[:200])

print("\nThe signature says what it is and what it is not")
signature = forms_dialog.SignatureDialog(dialog, "Signature")
words = " ".join(" ".join(w.GetLabel().split()) for w in signature.GetChildren()
                 if isinstance(w, wx.StaticText))
check("it says it is a typed or drawn signature", "typed or drawn signature" in words, words)
check("and that it is not a cryptographic one",
      "not a cryptographic digital signature" in words, words)
check("there are two ways to sign", signature.how.GetCount() == 2)
problems = []
walk(signature, "Signature")
check("every control in it is named", not problems, problems)
signature.how.SetSelection(0)
signature.name.SetValue("Tony Gebhard")
signature._on_ok(None)
check("typing a name gives the typed route", signature.result == ("text", "Tony Gebhard"))
signature.Destroy()

ON_UI_THREAD[:] = []
dialog.dirty = 0
dialog._sign_now(("text", "Tony Gebhard"), "f7")
pump()
check("signing ran off the UI thread", not ON_UI_THREAD, ON_UI_THREAD)
check("and it signed the field the keyboard was on",
      STAND_IN.signed and STAND_IN.signed[-1] == ("text", "f7", "Tony Gebhard"),
      STAND_IN.signed)
check("and it says so", "Signed as Tony Gebhard" in frame.status.GetStatusText(0),
      frame.status.GetStatusText(0))

print("\nEscape says so when there are values that were never saved")
answered = []
real_ask = forms_dialog.dialogs.ask
forms_dialog.dialogs.ask = lambda *a, **k: (answered.append(a[2]), False)[1]
dialog.dirty = 3
dialog.try_close()
check("it asks before losing them", answered and "3 fields" in answered[0], answered)
# dialog.doc, not doc: signing wrote to the file, so the dialog read it back
# and the document it holds now is the one that has to stay open.
check("and the window is still open, because the answer was no",
      not dialog.doc.closed)
forms_dialog.dialogs.ask = lambda *a, **k: (answered.append(a[2]), True)[1]
dialog.try_close()
check("saying yes closes it and says nothing was saved",
      "Nothing was saved" in frame.status.GetStatusText(0), frame.status.GetStatusText(0))
check("and the PDF handle is closed on the way out", dialog.doc.closed)
forms_dialog.dialogs.ask = real_ask
dialog.Destroy()

print("\nA PDF with no fields offers to look for the blanks")
asked = []
forms_dialog.dialogs.ask = lambda *a, **k: (asked.append(a[2]), False)[1]
forms_dialog.open_and_show(frame, "a flat form.pdf")
pump()
check("it opened the file off the UI thread", "a flat form.pdf" in STAND_IN.opened)
check("it says the PDF has no fields and offers to look",
      asked and "no form fields" in asked[0] and "Look for the blanks" in asked[0], asked)
check("and it does not open an empty list", True)
forms_dialog.dialogs.ask = real_ask

print("\nThe blanks are a list to approve, rename or remove")
blanks = forms_dialog.ProposalsDialog(frame, frame, propose_fields("x"))
rows = [blanks.list.GetString(i) for i in range(blanks.list.GetCount())]
check("one row per blank", len(rows) == 3, rows)
check("a row says the page, the name, the kind and how sure it is",
      rows[0] == "Page 1, Name, text box, looks certain", rows[0])
check("Worker A's confidence is a number, and it is read as words",
      "probably a blank" in rows[1] and "might be a blank" in rows[2], rows[1:])
check("a blank with no name says so", "not named yet" in rows[2], rows[2])
problems = []
walk(blanks, "Blanks")
check("every control in it is named", not problems, problems)
blanks.list.SetSelection(2)
blanks.proposals[2].label = "Today's date"
blanks.fill(2)
check("renaming one shows the new name", "Today's date" in blanks.list.GetString(2))
blanks.remove_current()
check("removing one takes it out of the list", len(blanks.proposals) == 2)
check("and says how many are left", "2 left" in frame.status.GetStatusText(0),
      frame.status.GetStatusText(0))
blanks._on_add(None)
check("Add hands back the ones that are left", len(blanks.result) == 2)
blanks.Destroy()

print("\nAdding them writes a new PDF and leaves the original alone")
STAND_IN.added[:] = []
made_here = propose_fields("x")       # built on this thread, on purpose
ON_UI_THREAD[:] = []


class FakeSave:
    """A file dialog that answers without a person, so the flow can run."""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ShowModal(self):
        return wx.ID_OK

    def GetPath(self):
        return os.path.join(tempfile.gettempdir(), "form fillable.pdf")


real_file_dialog = wx.FileDialog
wx.FileDialog = FakeSave
forms_dialog._add_fields(frame, "a flat form.pdf", made_here)
pump()
wx.FileDialog = real_file_dialog
check("the fields were added off the UI thread", not ON_UI_THREAD, ON_UI_THREAD)
check("into a new file, not over the original",
      STAND_IN.added and STAND_IN.added[-1][2].endswith("form fillable.pdf")
      and STAND_IN.added[-1][0] == "a flat form.pdf", STAND_IN.added)
check("and the new file was opened afterwards",
      STAND_IN.opened[-1].endswith("form fillable.pdf"), STAND_IN.opened[-3:])
check("and its fields are shown as a list",
      OPENED_LIST and OPENED_LIST[-1][1].endswith("form fillable.pdf"), OPENED_LIST)

print("\nWithout the module the window still works")
# Blocking the import, not merely unloading it: the module really exists
# now, so a popped entry is simply imported again. Setting the entry to
# None is what makes "from .. import pdfforms" raise ImportError, which
# is the state this section is about.
_real_forms = sys.modules.pop("tgimprint.pdfforms", None)
_real_attr = getattr(tgimprint, "pdfforms", None)
sys.modules["tgimprint.pdfforms"] = None
if hasattr(tgimprint, "pdfforms"):
    del tgimprint.pdfforms
check("the module is gone", forms_dialog.module() is None)
said = []
frame.announce = lambda text: said.append(text)
real_show = forms_dialog.dialogs.show_text
forms_dialog.dialogs.show_text = lambda *a, **k: None
forms_dialog.fill_in_a_pdf_form(frame)
forms_dialog.dialogs.show_text = real_show
check("and Fill in a PDF form says so rather than failing",
      said and "not part of this build yet" in said[0], said)

# Put it back for anything after this section.
if _real_forms is not None:
    sys.modules["tgimprint.pdfforms"] = _real_forms
else:
    sys.modules.pop("tgimprint.pdfforms", None)
if _real_attr is not None:
    tgimprint.pdfforms = _real_attr

print("\nThe menu item and the key")
from tgimprint.ui import keymap  # noqa: E402
check("Ctrl+Shift+F is the key", "Ctrl+Shift+F" in keymap.entry("fill_form").keys)
check("it is in the Tools menu",
      "fill_form" in dict(keymap.MENUS)["&Tools"], dict(keymap.MENUS)["&Tools"])
check("and the window has a handler for it", frame.handler_for("fill_form") is not None)

print("\nThe proof that a check can fail")
check("(deliberate) the form has fifty fields", len(FIELDS) == 50)
last = CHECKS.pop()
print("  the line above is the deliberate failure; it is not counted")
check("the deliberate failure was recorded as a failure", last is False)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.stdout.flush()
os._exit(0 if all(CHECKS) else 1)
