"""Fill in a PDF form (Ctrl+Shift+F): the fields as a list, not as a picture.

This is the whole point of the feature. Filling in a PDF form with a screen
reader usually means hunting a page image for boxes; here the fields are a
list you walk with Down, each row saying what the field is called, what kind
it is, what is in it now and which page it is on, and Enter or F2 opens a
proper labelled control to change it. Nothing here draws a page.

Worker A's `pdfforms` does the PDF work and is imported lazily inside each
function, so this module loads, and its tests run, before that module
exists. Everything that touches a file happens on a thread with a progress
window; the UI thread never opens, saves or scans a PDF.

The flow, from `fill_in_a_pdf_form(frame)`:

  choose a PDF  ->  open it  ->  it has fields   ->  the list
                                 it has none     ->  offer to look for the
                                                     blanks, approve them,
                                                     add them, then the list
"""
import os
import threading

import wx

from . import dialogs
from .dialogs import add_row, focus_ring, name_field

#: docs/STRINGS.md, Worker B. Every sentence this dialog shows or speaks.
S = {
    "module_missing": ("Filling in PDF forms is not part of this build yet. "
                       "The rest of the program is unaffected."),
    "choose": "Choose a PDF form",
    "opening": "Opening %s.",
    "open_failed": "That PDF could not be opened as a form. %s",
    "no_fields": ("%s has no form fields in it, so there is nothing to fill in "
                  "yet.\n\nTG Imprint can look over the pages for the blank "
                  "lines and boxes a form usually has and offer them to you as "
                  "a list. You decide which ones become fields and what each "
                  "one is called, and the fields are added to a new copy of "
                  "the PDF. The original is not changed.\n\nLook for the "
                  "blanks now?"),
    "no_fields_title": "No form fields",
    "looking": "Looking for the blanks in %s.",
    "propose_failed": "The pages could not be looked over. %s",
    "propose_none": ("Nothing that looks like a blank was found in %s. The PDF "
                     "may be a scan with no text in it, in which case there is "
                     "nothing to go on."),
    "adding": "Adding %d fields.",
    "add_failed": "The fields could not be added. %s",
    "added": "%d fields added to %s. It is open now.",
    "field_row": "%s, %s, %s, page %s",
    "empty": "empty",
    "required": ", needed",
    "edited": "%s is now %s.",
    "cleared": "%s is empty now.",
    "refused": "%s was not changed. %s",
    "progress": "%d of %d fields filled in, %d still empty.",
    "saving": "Saving %s.",
    "saved": "Saved %s.",
    "save_failed": "It could not be saved. %s",
    "flattened": ("Saved %s. The fields in that copy are now part of the page: "
                  "it prints exactly as it looks and nobody can change the "
                  "answers, including you."),
    "unsaved_q": ("You have filled in %d field%s and not saved yet. Close this "
                  "window and lose what you typed?"),
    "unsaved_title": "Not saved",
    "closed_unsaved": "Closed. Nothing was saved.",
    "signing": "Signing.",
    "sign_failed": "The signature could not be put in. %s",
    "signed": "Signed as %s.",
    "sign_needs_save": ("The values you have typed have to be saved into the "
                        "PDF before a signature goes in. Save now and then "
                        "sign?"),
    "sign_needs_field": ("Choose the field to sign in the list first. If the "
                         "form has no signature field, Look for the blanks can "
                         "add one where the signature line is."),
    "sign_note": ("This writes your name, or your picture, onto the page where "
                  "the signature goes. It is a typed or drawn signature, the "
                  "same as signing a printed page with a pen. It is not a "
                  "cryptographic digital signature: it does not prove who "
                  "signed and nothing checks it."),
    "sign_no_name": "Type the name to sign with first.",
    "sign_no_file": "Choose the picture file to sign with first.",
    "sign_not_a_picture": "That file is not a picture the program can read. %s",
    "proposal_row": "Page %s, %s, %s, %s",
    "read_only": "%s cannot be changed: the form locked it.",
    "confidence": {"high": "looks certain", "medium": "probably a blank",
                   "low": "might be a blank"},
    "proposal_heading": "&Blanks found, %d. Approve the ones that are really fields:",
    "proposal_none_left": "None left. Nothing will be added.",
    "label_prompt": "What is this field called? A screen reader reads this name.",
    "label_title": "Name this field",
}

PDF_WILDCARD = "PDF files (*.pdf)|*.pdf"
IMAGE_WILDCARD = ("Pictures (*.png;*.jpg;*.jpeg;*.gif;*.bmp)|"
                  "*.png;*.jpg;*.jpeg;*.gif;*.bmp|All files (*.*)|*.*")

#: The kinds pdfforms reports, in the words it uses for them itself, so a
#: row in this list and the sentence describe_form speaks agree. The table
#: is here as well as there because this module loads without pdfforms.
KIND_WORDS = {
    "text": "text box", "multiline text": "box for several lines",
    "checkbox": "tick box", "radio": "radio group",
    "choice": "list to choose from", "signature": "signature",
    "button": "button",
}


def kind_word(kind):
    return KIND_WORDS.get((kind or "").lower(), (kind or "field").replace("_", " "))


def confidence_words(value):
    """Worker A's confidence is a number from 0 to 1, not a word."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return S["confidence"].get(str(value or "").lower(), "a guess")
    if number >= 0.8:
        return S["confidence"]["high"]
    if number >= 0.55:
        return S["confidence"]["medium"]
    return S["confidence"]["low"]


def module():
    """Worker A's pdfforms, or None when this build has none."""
    try:
        from .. import pdfforms
    except ImportError:
        return None
    return pdfforms


def on_thread(frame, parent, title, first_line, work, done):
    """Run `work()` on a thread behind a progress window, then `done(value)`.

    `work` returns whatever it likes and may raise; `done` is called on the
    UI thread with (value, error_text). Nothing that touches a file is ever
    run on the UI thread, which is the rule for every long job in this
    program.
    """
    busy = dialogs.BusyDialog(parent, frame, title, first_line)
    busy.Show()

    def run():
        try:
            value, error = work(busy.step), ""
        except Exception as exc:                      # a module that raises
            value, error = None, "%s" % exc
        wx.CallAfter(_finish, busy, done, value, error)

    threading.Thread(target=run, daemon=True, name="tgimprint-form").start()


def _finish(busy, done, value, error):
    try:
        busy.finish()
    except Exception:
        pass
    done(value, error)


# --------------------------------------------------------------- the flow --

def fill_in_a_pdf_form(frame, path=None):
    """Tools, Fill in a PDF form. Chooses the file, then opens the list."""
    forms = module()
    if forms is None:
        frame.announce(S["module_missing"])
        dialogs.show_text(frame, S["choose"], S["module_missing"])
        return
    if not path:
        with wx.FileDialog(frame, S["choose"],
                           defaultDir=getattr(frame, "last_folder", "") or "",
                           wildcard=PDF_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
    open_and_show(frame, path)


def open_and_show(frame, path):
    """Open the PDF on a thread and show whichever window fits what is in it."""
    forms = module()
    if forms is None:
        frame.announce(S["module_missing"])
        return
    name = os.path.basename(path)
    frame.announce_help(S["opening"] % name)

    def work(_step):
        return forms.open_form(path)

    def done(doc, error):
        if error or doc is None:
            message = S["open_failed"] % (error or "nothing was returned")
            frame.announce(message)
            dialogs.show_text(frame, S["choose"], message)
            return
        problem = getattr(doc, "problem", "") or ""
        if not getattr(doc, "has_fields", False):
            _offer_proposals(frame, path, problem)
            return
        if problem:
            frame.announce(problem)
        show_form(frame, doc, path)

    on_thread(frame, frame, S["choose"], S["opening"] % name, work, done)


def show_form(frame, doc, path):
    dialog = FormDialog(frame, frame, doc, path)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()


def _offer_proposals(frame, path, problem):
    """The PDF has no fields: say so, and offer to look for the blanks."""
    name = os.path.basename(path)
    question = S["no_fields"] % name
    if problem:
        question = problem + "\n\n" + question
    frame.announce(S["no_fields_title"])
    if not dialogs.ask(frame, S["no_fields_title"], question,
                       yes="&Look for the blanks", no="&Not now"):
        return
    forms = module()
    frame.announce_help(S["looking"] % name)

    def work(_step):
        return list(forms.propose_fields(path) or [])

    def done(proposals, error):
        if error:
            message = S["propose_failed"] % error
            frame.announce(message)
            dialogs.show_text(frame, S["no_fields_title"], message)
            return
        if not proposals:
            message = S["propose_none"] % name
            frame.announce(message)
            dialogs.show_text(frame, S["no_fields_title"], message)
            return
        dialog = ProposalsDialog(frame, frame, proposals)
        try:
            approved = list(dialog.result or []) if dialog.ShowModal() == wx.ID_OK else []
        finally:
            dialog.Destroy()
        if approved:
            _add_fields(frame, path, approved)

    on_thread(frame, frame, S["no_fields_title"], S["looking"] % name, work, done)


def _add_fields(frame, path, proposals):
    forms = module()
    stem = os.path.splitext(os.path.basename(path))[0]
    with wx.FileDialog(frame, "Save the fillable copy as",
                       defaultDir=os.path.dirname(path),
                       defaultFile="%s fillable.pdf" % stem, wildcard=PDF_WILDCARD,
                       style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return
        out = dialog.GetPath()
    if not out.lower().endswith(".pdf"):
        out += ".pdf"
    frame.announce_help(S["adding"] % len(proposals))

    def work(_step):
        return forms.add_fields(path, proposals, out_path=out)

    def done(answer, error):
        ok, message, added = _three(answer, error)
        if not ok:
            message = S["add_failed"] % (message or error or "")
            frame.announce(message)
            dialogs.show_text(frame, S["no_fields_title"], message)
            return
        frame.announce(S["added"] % (added or len(proposals), os.path.basename(out)))
        open_and_show(frame, out)

    on_thread(frame, frame, S["no_fields_title"], S["adding"] % len(proposals), work, done)


def _two(answer, error):
    """(ok, message) out of whatever came back."""
    if error:
        return False, error
    if isinstance(answer, tuple) and len(answer) >= 2:
        return bool(answer[0]), str(answer[1] or "")
    return bool(answer), ""


def _three(answer, error):
    """(ok, message, count) out of whatever came back."""
    if error:
        return False, error, 0
    if isinstance(answer, tuple) and len(answer) >= 3:
        return bool(answer[0]), str(answer[1] or ""), int(answer[2] or 0)
    ok, message = _two(answer, error)
    return ok, message, 0


# ------------------------------------------------------------- the fields --

def finish(dialog, result):
    """End a dialog whether it was shown modally or not.

    EndModal on a dialog that is not modal is a wx assertion, and these
    windows are also built by tests and by the screenshot script, which show
    them without a modal loop.
    """
    if dialog.IsModal():
        dialog.EndModal(result)
    else:
        dialog.Show(False)


def field_of(doc, index):
    fields = list(getattr(doc, "fields", []) or [])
    return fields[index] if 0 <= index < len(fields) else None


def field_value_words(field):
    """What is in the field now, as a phrase a list row can hold."""
    value = getattr(field, "value", None)
    kind = (getattr(field, "kind", "") or "").lower()
    if kind == "checkbox":
        return "ticked" if value in (True, "on", "Yes", "yes", 1) else "not ticked"
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if not text:
        return S["empty"]
    return text if len(text) <= 60 else text[:57] + "..."


def field_is_empty(field):
    filled = getattr(field, "is_filled", None)
    if filled is not None:
        return not filled
    kind = (getattr(field, "kind", "") or "").lower()
    value = getattr(field, "value", None)
    if kind == "checkbox":
        return value in (None, False, "", "Off", "off")
    return not str(value or "").strip()


def field_label(field, index):
    label = (getattr(field, "label", "") or getattr(field, "name", "") or "").strip()
    return label or "Field %d" % (index + 1)


def field_row(field, index):
    text = S["field_row"] % (field_label(field, index), kind_word(getattr(field, "kind", "")),
                             field_value_words(field), getattr(field, "page", "") or "1")
    if getattr(field, "required", False):
        text += S["required"]
    if getattr(field, "read_only", False):
        text += ", locked"
    return text


class FormDialog(wx.Dialog):
    """The fields as a list. Enter or F2 edits the one the keyboard is on."""

    def __init__(self, parent, frame, doc, path):
        super().__init__(parent, title="Fill in a PDF form",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.doc = doc
        self.path = path
        self.dirty = 0
        outer = wx.BoxSizer(wx.VERTICAL)
        self.heading = wx.StaticText(self, label="")
        outer.Add(self.heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.list = wx.ListBox(self, size=self.FromDIP(wx.Size(620, 300)))
        name_field(self.list, "Form fields")
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        note = wx.StaticText(self, label=(
            "Enter or F2 fills in the field the keyboard is on. Save writes the "
            "answers into this PDF. Save a copy writes them into a new file and "
            "leaves this one as it is. Save flattened for printing makes the "
            "answers part of the page, so it prints as it looks and nobody can "
            "change it afterwards."))
        note.Wrap(self.FromDIP(600))
        outer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.edit = wx.Button(self, label="&Fill in this field...")
        self.sign = wx.Button(self, label="Si&gnature...")
        self.save = wx.Button(self, label="&Save")
        self.save_copy = wx.Button(self, label="Save a &copy...")
        self.save_flat = wx.Button(self, label="Save f&lattened for printing...")
        close = wx.Button(self, wx.ID_CANCEL, "&Close")
        for button in (self.edit, self.sign, self.save, self.save_copy,
                       self.save_flat, close):
            row.Add(button, 0, wx.RIGHT, 8)
        outer.Add(row, 0, wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(560, 380)))
        self.CentreOnParent()
        self.edit.SetToolTip("Open the field in a labelled box, tick box or list.")
        self.save.SetToolTip("Write the answers into this PDF, over the file you opened.")
        self.save_copy.SetToolTip("Write the answers into a new PDF and leave this one alone.")
        self.save_flat.SetToolTip("A copy whose answers are part of the page: it prints "
                                  "exactly as it looks and cannot be changed again.")
        self.sign.SetToolTip("A typed or drawn signature on the field the keyboard is "
                             "on. Not a cryptographic signature.")
        self.edit.Bind(wx.EVT_BUTTON, lambda _e: self.edit_current())
        self.sign.Bind(wx.EVT_BUTTON, lambda _e: self.on_sign())
        self.save.Bind(wx.EVT_BUTTON, lambda _e: self.do_save(None, False))
        self.save_copy.Bind(wx.EVT_BUTTON, lambda _e: self.on_save_as(False))
        self.save_flat.Bind(wx.EVT_BUTTON, lambda _e: self.on_save_as(True))
        close.Bind(wx.EVT_BUTTON, lambda _e: self.try_close())
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda _e: self.edit_current())
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        width = 3
        try:
            width = int(frame.settings.get("focus_ring_width", 3))
        except Exception:
            width = 3
        focus_ring(self, [self.list], width)
        self.edit.SetDefault()
        self.fill()
        self.list.SetFocus()

    # ---------------------------------------------------------- the list --
    def fields(self):
        return list(getattr(self.doc, "fields", []) or [])

    def fill(self, select=None):
        fields = self.fields()
        if select is None:
            select = max(0, self.list.GetSelection())
        self.list.Set([field_row(f, i) for i, f in enumerate(fields)]
                      or ["No fields in this PDF."])
        if fields:
            self.list.SetSelection(min(select, len(fields) - 1))
        self.heading.SetLabel("&Fields. " + self.sentence())
        for button in (self.edit, self.sign):
            button.Enable(bool(fields))

    def sentence(self):
        """Worker A's describe_form when it is there, ours when it is not."""
        forms = module()
        try:
            text = forms.describe_form(self.doc)
            if text:
                return text
        except Exception:
            pass
        fields = self.fields()
        empty = sum(1 for f in fields if field_is_empty(f))
        return S["progress"] % (len(fields) - empty, len(fields), empty)

    def _on_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_F2):
            self.edit_current()
            return
        event.Skip()

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.try_close()
            return
        if event.GetKeyCode() == wx.WXK_F2:
            self.edit_current()
            return
        event.Skip()

    # ------------------------------------------------------------ values --
    def edit_current(self):
        index = self.list.GetSelection()
        field = field_of(self.doc, index)
        if field is None:
            return
        if (getattr(field, "kind", "") or "").lower() == "signature":
            self.on_sign()
            return
        if getattr(field, "read_only", False):
            # pdfforms refuses the write too; saying so before the box opens
            # saves typing an answer that is going to be thrown away.
            self.frame.announce(S["read_only"] % field_label(field, index))
            return
        dialog = FieldDialog(self, field, index)
        try:
            answer = dialog.result if dialog.ShowModal() == wx.ID_OK else None
        finally:
            dialog.Destroy()
        if answer is None:
            self.list.SetFocus()
            return
        ok, message = _two(self.doc.set_value(getattr(field, "id", None), answer), "")
        label = field_label(field, index)
        if not ok:
            self.frame.announce(S["refused"] % (label, message))
        else:
            self.dirty += 1
            self.fill(index)
            said = field_value_words(self.fields()[index] if index < len(self.fields()) else field)
            self.frame.announce((S["cleared"] % label) if said == S["empty"]
                                else (S["edited"] % (label, said)))
            self.frame.announce_help(self.sentence())
        self.list.SetFocus()

    # ------------------------------------------------------------- saving --
    def on_save_as(self, flatten):
        stem = os.path.splitext(os.path.basename(self.path))[0]
        suffix = " flattened.pdf" if flatten else " copy.pdf"
        with wx.FileDialog(self, "Save flattened for printing" if flatten else "Save a copy",
                           defaultDir=os.path.dirname(self.path),
                           defaultFile=stem + suffix, wildcard=PDF_WILDCARD,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            out = dialog.GetPath()
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        self.do_save(out, flatten)

    def do_save(self, out, flatten, then=None):
        target = out or self.path
        name = os.path.basename(target)
        self.frame.announce_help(S["saving"] % name)

        def work(_step):
            return self.doc.save(out_path=out, flatten=flatten)

        def done(answer, error):
            ok, message = _two(answer, error)
            if not ok:
                text = S["save_failed"] % (message or error or "")
                self.frame.announce(text)
                dialogs.show_text(self, "Not saved", text)
                return
            if not out:
                self.dirty = 0
            self.frame.announce((S["flattened"] % name) if flatten else (S["saved"] % name))
            if then is not None:
                then()

        on_thread(self.frame, self, "Saving", S["saving"] % name, work, done)

    # ---------------------------------------------------------- signature --
    def on_sign(self):
        index = self.list.GetSelection()
        field = field_of(self.doc, index)
        if field is None:
            self.frame.announce(S["sign_needs_field"])
            return
        dialog = SignatureDialog(self, field_label(field, index))
        try:
            answer = dialog.result if dialog.ShowModal() == wx.ID_OK else None
        finally:
            dialog.Destroy()
        if not answer:
            self.list.SetFocus()
            return
        target = getattr(field, "id", None)
        if self.dirty and not dialogs.ask(self, "Save first", S["sign_needs_save"],
                                          yes="&Save and sign", no="&Cancel"):
            return
        if self.dirty:
            self.do_save(None, False, then=lambda: self._sign_now(answer, target))
            return
        self._sign_now(answer, target)

    def _sign_now(self, answer, target):
        forms = module()
        how, value = answer
        self.frame.announce_help(S["signing"])

        def work(_step):
            if how == "text":
                return forms.sign_with_text(self.path, target, value)
            with open(value, "rb") as handle:
                data = handle.read()
            return forms.sign_with_image(self.path, target, data)

        def done(got, error):
            ok, message = _two(got, error)
            if not ok:
                text = S["sign_failed"] % (message or error or "")
                self.frame.announce(text)
                dialogs.show_text(self, "Not signed", text)
                return
            self.frame.announce(S["signed"] % (value if how == "text"
                                               else os.path.basename(value)))
            self._reopen()

        on_thread(self.frame, self, "Signing", S["signing"], work, done)

    def _reopen(self):
        """Read the file back after it changed under us, on a thread."""
        forms = module()

        def work(_step):
            return forms.open_form(self.path)

        def done(doc, error):
            if error or doc is None:
                return
            self.close_document()
            self.doc = doc
            self.dirty = 0
            self.fill()

        on_thread(self.frame, self, "Reading it back", S["opening"] % os.path.basename(self.path),
                  work, done)

    # ------------------------------------------------------------ closing --
    def close_document(self):
        closer = getattr(self.doc, "close", None)
        if closer is not None:
            try:
                closer()
            except Exception:
                pass

    def try_close(self):
        if self.dirty:
            plural = "" if self.dirty == 1 else "s"
            if not dialogs.ask(self, S["unsaved_title"], S["unsaved_q"] % (self.dirty, plural),
                               yes="&Close and lose them", no="&Go back"):
                self.list.SetFocus()
                return
            self.frame.announce(S["closed_unsaved"])
        self.close_document()
        finish(self, wx.ID_CANCEL)


class FieldDialog(wx.Dialog):
    """One field, in the control its kind asks for, with a real label."""

    def __init__(self, parent, field, index):
        self.field = field
        self.result = None
        label = field_label(field, index)
        super().__init__(parent, title=label,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        kind = (getattr(field, "kind", "") or "text").lower()
        self.kind = kind
        value = getattr(field, "value", None)
        choices = [str(c) for c in (getattr(field, "choices", None) or [])]
        outer = wx.BoxSizer(wx.VERTICAL)
        where = wx.StaticText(self, label="%s. %s, page %s.%s" % (
            label, kind_word(kind), getattr(field, "page", "") or "1",
            " This one is needed." if getattr(field, "required", False) else ""))
        where.Wrap(self.FromDIP(460))
        outer.Add(where, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        tooltip = (getattr(field, "tooltip", "") or "").strip()
        if tooltip:
            hint = wx.StaticText(self, label="The form says: %s" % tooltip)
            hint.Wrap(self.FromDIP(460))
            outer.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        if kind == "checkbox":
            self.control = wx.CheckBox(self, label="&%s" % label)
            self.control.SetValue(value in (True, "on", "Yes", "yes", 1))
            name_field(self.control, label)
            outer.Add(self.control, 0, wx.EXPAND | wx.ALL, 12)
        elif choices:
            self.control = wx.Choice(self, choices=choices)
            self.control.SetSelection(choices.index(str(value)) if str(value) in choices else 0)
            add_row(self, grid, "&%s:" % label, self.control, name=label)
            outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        else:
            style = wx.TE_MULTILINE if kind == "multiline" else 0
            self.control = wx.TextCtrl(self, value="" if value is None else str(value),
                                       style=style,
                                       size=self.FromDIP(wx.Size(360, 90 if style else -1)))
            add_row(self, grid, "&%s:" % label, self.control, name=label)
            outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        sizer, _made = dialogs.button_row(self, [
            (wx.ID_OK, "&OK", self._on_ok), (wx.ID_CANCEL, "&Cancel", None)])
        outer.Add(sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.FindWindow(wx.ID_OK).SetDefault()
        self.control.SetFocus()

    def _on_ok(self, _event):
        if self.kind == "checkbox":
            self.result = bool(self.control.GetValue())
        elif isinstance(self.control, wx.Choice):
            index = self.control.GetSelection()
            self.result = self.control.GetString(index) if index >= 0 else ""
        else:
            self.result = self.control.GetValue()
        finish(self, wx.ID_OK)


class SignatureDialog(wx.Dialog):
    """Type a name or choose a picture, and say plainly what this is not."""

    def __init__(self, parent, field_name):
        super().__init__(parent, title="Signature",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        outer = wx.BoxSizer(wx.VERTICAL)
        where = wx.StaticText(self, label="Signing the field called %s." % field_name)
        where.Wrap(self.FromDIP(460))
        outer.Add(where, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.how = wx.RadioBox(self, label="How to sign",
                               choices=["&Type my name", "&Use a picture of my signature"],
                               majorDimension=1, style=wx.RA_SPECIFY_COLS)
        name_field(self.how, "How to sign")
        outer.Add(self.how, 0, wx.EXPAND | wx.ALL, 12)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.name = add_row(self, grid, "&Name to sign with:", wx.TextCtrl(self),
                            name="Name to sign with")
        self.file = add_row(self, grid, "&Picture file:", wx.TextCtrl(self),
                            name="Picture file")
        outer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.browse = wx.Button(self, label="&Choose a picture...")
        outer.Add(self.browse, 0, wx.LEFT | wx.TOP, 12)
        note = wx.StaticText(self, label=S["sign_note"])
        note.Wrap(self.FromDIP(460))
        outer.Add(note, 0, wx.ALL, 12)
        sizer, _made = dialogs.button_row(self, [
            (wx.ID_OK, "&Sign", self._on_ok), (wx.ID_CANCEL, "&Cancel", None)])
        outer.Add(sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.browse.Bind(wx.EVT_BUTTON, self._on_browse)
        self.how.Bind(wx.EVT_RADIOBOX, lambda _e: self._sync())
        self.FindWindow(wx.ID_OK).SetDefault()
        self._sync()
        self.name.SetFocus()

    def _sync(self):
        typed = self.how.GetSelection() == 0
        self.name.Enable(typed)
        self.file.Enable(not typed)
        self.browse.Enable(not typed)

    def _on_browse(self, _event):
        with wx.FileDialog(self, "Choose a picture of your signature",
                           wildcard=IMAGE_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.file.SetValue(dialog.GetPath())
        self.file.SetFocus()

    def _on_ok(self, _event):
        if self.how.GetSelection() == 0:
            name = self.name.GetValue().strip()
            if not name:
                dialogs.show_text(self, "Signature", S["sign_no_name"])
                self.name.SetFocus()
                return
            self.result = ("text", name)
        else:
            path = self.file.GetValue().strip()
            if not path or not os.path.isfile(path):
                dialogs.show_text(self, "Signature", S["sign_no_file"])
                self.file.SetFocus()
                return
            self.result = ("image", path)
        finish(self, wx.ID_OK)


class ProposalsDialog(wx.Dialog):
    """The blanks the scan found, as a list to approve, rename or remove."""

    def __init__(self, parent, frame, proposals):
        super().__init__(parent, title="Blanks found in this PDF",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.proposals = list(proposals)
        self.result = None
        outer = wx.BoxSizer(wx.VERTICAL)
        self.heading = wx.StaticText(self, label="")
        outer.Add(self.heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.list = wx.ListBox(self, size=self.FromDIP(wx.Size(600, 280)))
        name_field(self.list, "Blanks found")
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        note = wx.StaticText(self, label=(
            "These are guesses from the words on the page. Rename the ones whose "
            "name is wrong, remove anything that is not really a field, and Add "
            "the fields writes the rest into a new copy of the PDF."))
        note.Wrap(self.FromDIP(580))
        outer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.rename = wx.Button(self, label="&Rename...")
        self.remove = wx.Button(self, label="Re&move")
        add = wx.Button(self, wx.ID_OK, "&Add the fields")
        cancel = wx.Button(self, wx.ID_CANCEL, "&Cancel")
        for button in (self.rename, self.remove, add, cancel):
            row.Add(button, 0, wx.RIGHT, 8)
        outer.Add(row, 0, wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(520, 340)))
        self.CentreOnParent()
        self.rename.Bind(wx.EVT_BUTTON, lambda _e: self.rename_current())
        self.remove.Bind(wx.EVT_BUTTON, lambda _e: self.remove_current())
        add.Bind(wx.EVT_BUTTON, self._on_add)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda _e: self.rename_current())
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        add.SetDefault()
        self.fill()
        self.list.SetFocus()

    def fill(self, select=0):
        self.list.Set([self.row(p) for p in self.proposals]
                      or [S["proposal_none_left"]])
        if self.proposals:
            self.list.SetSelection(min(select, len(self.proposals) - 1))
        self.heading.SetLabel(S["proposal_heading"] % len(self.proposals))
        for button in (self.rename, self.remove):
            button.Enable(bool(self.proposals))

    def row(self, proposal):
        words = confidence_words(getattr(proposal, "confidence", ""))
        label = (getattr(proposal, "label", "") or "").strip() or "not named yet"
        return S["proposal_row"] % (getattr(proposal, "page", "") or "1", label,
                                    kind_word(getattr(proposal, "kind", "text")), words)

    def _on_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_F2):
            self.rename_current()
            return
        if code == wx.WXK_DELETE:
            self.remove_current()
            return
        event.Skip()

    def rename_current(self):
        index = self.list.GetSelection()
        if not self.proposals or index < 0:
            return
        proposal = self.proposals[index]
        with wx.TextEntryDialog(self, S["label_prompt"], S["label_title"],
                                getattr(proposal, "label", "") or "") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                self.list.SetFocus()
                return
            label = dialog.GetValue().strip()
        try:
            proposal.label = label
        except Exception:
            self.proposals[index] = _relabelled(proposal, label)
        self.fill(index)
        self.list.SetFocus()

    def remove_current(self):
        index = self.list.GetSelection()
        if not self.proposals or index < 0:
            return
        gone = self.proposals.pop(index)
        self.frame.announce("Removed %s. %d left." % (self.row(gone), len(self.proposals)))
        self.fill(index)
        self.list.SetFocus()

    def _on_add(self, _event):
        self.result = list(self.proposals)
        finish(self, wx.ID_OK)


class _Relabelled:
    """A stand in for a proposal whose label cannot be written to.

    add_fields takes anything with a page, a rectangle and a label, which
    Worker A wrote it to do on purpose: renaming a proposal must never be
    the thing that makes the field disappear.
    """

    def __init__(self, proposal, label):
        for name in ("page", "rect", "confidence", "source", "kind", "name"):
            setattr(self, name, getattr(proposal, name, None))
        self.label = label


def _relabelled(proposal, label):
    return _Relabelled(proposal, label)
