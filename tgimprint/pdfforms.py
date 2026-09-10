"""PDF forms: fill in the fields a form already has, and put fields on a
form that has none.

Two beta testers asked for this. HarmonicaPlayer wanted to open a PDF that
already has editable fields and fill it in. Chris Smart wanted the harder
half: a healthcare form that is readable text and nothing else, with no
edit fields at all, so that filling it in means printing it and finding a
sighted person to dictate a medical history to.

    open_form(path) -> FormDocument
    FormDocument: fields, has_fields, page_count, path, problem,
                  set_value(field_id, value) -> (ok, message)
                  save(out_path=None, flatten=False) -> (ok, message)
                  close()
    Field: id, name, label, kind, value, choices, required, read_only,
           page, rect, tooltip
    propose_fields(source, page=None) -> list[Proposal]
    Proposal: page, rect, label, confidence, source, kind, name
    add_fields(path, proposals, out_path=None) -> (ok, message, added)
    sign_with_text(path, field_or_rect, name, out_path=None) -> (ok, message)
    sign_with_image(path, field_or_rect, image_bytes, out_path=None) -> (ok, message)
    describe_form(doc) -> str
    render_page_png(path, page_index, dpi=150) -> PageImage
    ai_proposals(source, page_index, ask, dpi=150) -> (list[Proposal], str)
    from_ai(page_index, boxes) -> list[Proposal]

**Page numbers here are 1 based**, as they are in pdfimport and as a user
hears them. `page_index` in the AI functions is a page number too: 1 is the
first page.

**This module edits the original PDF in place.** It never goes near
pdfimport, which rebuilds a document as HTML: that would throw away the
visual formatting Chris needs kept. Everything here is PyMuPDF widget work
on the pages that are already there, saved incrementally so the rest of the
file is left exactly as it was.

A signature here is a typed name or a picture of a signature drawn onto the
page. It is not a cryptographic digital signature and this module never
claims one. docs/FORMS.md says so in the words the user reads.

Nothing here touches wx, nothing prints, and no public function raises: a
call that cannot do its job returns a sentence, or an empty list, or a
FormDocument carrying .problem. Everything is safe to run on a worker
thread. One thread per FormDocument.

Measured on this machine, 2026-09-09, PyMuPDF 1.27.2.3 and pikepdf 10.5.1:

- `fitz.Widget()` with field_type, field_name, field_label and field_value,
  then `page.add_widget(w)`, writes a real AcroForm field. field_label
  becomes /TU, which is the string a screen reader announces, and pikepdf
  reads it back. The page text and the drawings are untouched.
- A widget added with border_width 0 writes /BS /W 0 and no /MK, and its
  appearance stream draws nothing, so the page still looks the same.
- `widget.field_value` then `widget.update()` writes the value. **A read
  only field accepts a write through PyMuPDF without complaining**, so the
  read only rule is enforced here, in set_value.
- A radio group written properly (kids under one parent field) reads back
  through PyMuPDF with the parent's name and /TU, and setting one kid's
  field_value to its on state sets the parent /V and clears the other kids.
  PyMuPDF cannot create such a group itself: `on_state` set before
  add_widget is ignored and every kid ends up with the on state "Yes".
  Reading and filling real forms is what matters, and that works.
- A checkbox reads back as the string "Yes" or "Off", or whatever the form
  chose ("1" is common), so Field.value for a tick box is a bool here.
- `doc.bake(annots=False, widgets=True)` bakes the values into the page
  content and removes the AcroForm. That is flatten.
- `page.get_text("rawdict")` gives a bounding box per character, which is
  what finds a run of underscores exactly. `page.get_drawings()` gives
  stroked lines as items ('l', p1, p2) and rectangles as ('re', rect, n).
- `page.insert_textbox` returns a negative number when the text does not
  fit, so a signature that is too big for its space is caught before it is
  drawn.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field as _dcfield

import fitz  # PyMuPDF

# ----------------------------------------------------------------- strings
# docs/STRINGS.md, Worker A, "PDF forms". The first four are word for word
# the sentences pdfimport already uses for the same situations, so Tony
# reads them once.

MSG_NOT_PDF = "That file is not a PDF."
MSG_NO_FILE = "That file could not be found."
MSG_PASSWORD = "This PDF is protected by a password, so it cannot be opened."
MSG_CANNOT_OPEN = "The PDF could not be opened. %s"

MSG_CLOSED = "This form is closed. Open it again to make changes."
MSG_NO_FIELD = "There is no field by that name in this form."
MSG_READ_ONLY = "%s cannot be changed. Whoever made this form locked it."
MSG_SIGNATURE_FIELD = ("%s is a signature field. Use Sign to put a typed name or a picture "
                       "of your signature in it.")
MSG_BUTTON_FIELD = "%s is a button, so there is nothing to fill in."
MSG_TOO_LONG = "%s holds at most %d characters and that is %d."
MSG_NOT_AN_OPTION = "%s does not offer that. The choices are %s."
MSG_SINGLE_LINE = "%s is a single line, so the line breaks became spaces. It now reads %s."
MSG_SET = "%s is now %s."
MSG_SET_EMPTY = "%s is now empty."
MSG_TICKED = "%s is ticked."
MSG_UNTICKED = "%s is not ticked."
MSG_CLEARED = "%s is set to none of them."
MSG_FLATTENED = "The answers are printed onto the page now, so there is nothing left to fill in."

MSG_SAVED = "Saved. The form holds what you typed."
MSG_SAVED_COPY = "Saved a copy as %s."
MSG_SAVED_FLAT = ("Saved with the answers printed onto the page. The fields are gone, so "
                  "nobody can change what you wrote, and nobody can correct it either.")
MSG_SAVE_FAILED = "The form could not be saved. %s"
MSG_NOTHING_CHANGED = "Nothing has changed, so nothing was saved."

MSG_ADDED = ("Added %d fields. Check every one of them: TG Imprint worked out where the "
             "blanks are by looking at the page, and it can be wrong.")
MSG_ADDED_ONE = ("Added one field. Check it: TG Imprint worked out where the blank is by "
                 "looking at the page, and it can be wrong.")
MSG_ADDED_NONE = "No fields were added."
MSG_NO_PROPOSALS = "No blanks were found on this form, so there was nothing to add."

MSG_SIGNED_TEXT = "Your name is written in %s. This is a typed name, not a digital signature."
MSG_SIGNED_IMAGE = ("Your signature picture is in %s. This is a picture, not a digital "
                    "signature.")
MSG_SIGN_NO_ROOM = "The signature does not fit in that space."
MSG_SIGN_BAD_IMAGE = ("That file is not a picture TG Imprint can read. PNG, JPEG, GIF, BMP "
                      "and WebP pictures work.")
MSG_SIGN_NO_TARGET = ("There is nowhere to put the signature. Choose a signature field, or "
                      "the space to sign in.")
MSG_SIGN_EMPTY = "There is no name to write."

MSG_NO_PAGE = "This PDF has no page %s."
MSG_NO_FIELDS = ("This PDF has no form fields. TG Imprint can look for the blanks and put "
                 "fields on it for you.")
LABEL_UNNAMED = "Blank %d on page %d"

DESC_HEAD = "This form has %s on %s: %s."
DESC_FILLED = "%s filled in, %s still empty."
DESC_LOCKED = "%s cannot be changed."

# ------------------------------------------------------------------- kinds

KIND_TEXT = "text"
KIND_MULTILINE = "multiline text"
KIND_CHECKBOX = "checkbox"
KIND_RADIO = "radio"
KIND_CHOICE = "choice"
KIND_SIGNATURE = "signature"
KIND_BUTTON = "button"

#: Singular and plural, for describe_form. NVDA says "radio button", so the
#: spoken name for a radio group is the one the user already hears.
_KIND_WORDS = {
    KIND_TEXT: ("text box", "text boxes"),
    KIND_MULTILINE: ("box for several lines", "boxes for several lines"),
    KIND_CHECKBOX: ("tick box", "tick boxes"),
    KIND_RADIO: ("radio group", "radio groups"),
    KIND_CHOICE: ("list to choose from", "lists to choose from"),
    KIND_SIGNATURE: ("signature", "signatures"),
    KIND_BUTTON: ("button", "buttons"),
}
_KIND_ORDER = [KIND_TEXT, KIND_MULTILINE, KIND_CHECKBOX, KIND_RADIO,
               KIND_CHOICE, KIND_SIGNATURE, KIND_BUTTON]

#: The sources propose_fields can name, most reliable first. "box" covers
#: both a rectangle drawn on the page and a pair of brackets in the text,
#: because they mean the same thing to the reader.
SOURCES = ("underscores", "line", "box", "colon", "ai")

# How sure each source is, before the label is taken into account.
CONF_UNDERSCORES = 0.90
CONF_LINE_COLON = 0.80
CONF_LINE_ABOVE = 0.62
CONF_LINE_BARE = 0.35
CONF_BRACKETS = 0.80
CONF_BOX_SMALL = 0.75
CONF_BOX_LARGE = 0.58
CONF_COLON = 0.50
CONF_GRID = 0.60
CONF_AI = 0.70

# Geometry, in PDF points (72 to the inch).
MIN_UNDERSCORES = 3
MIN_RULE_WIDTH = 40.0
MIN_UPRIGHT = 14.0
MAX_RULE_THICKNESS = 2.5
MIN_FIELD_WIDTH = 20.0
MIN_FIELD_HEIGHT = 8.0
MIN_BOX_SIDE = 6.0
MAX_TICK_SIDE = 22.0
DEFAULT_LINE_HEIGHT = 14.0
MIN_LINE_HEIGHT = 11.0
MAX_LINE_HEIGHT = 26.0
LABEL_GAP_LEFT = 60.0
LABEL_GAP_ABOVE = 26.0
COLON_MIN_ROOM = 60.0
#: The smallest side from_ai will take, the same number describe.py uses,
#: so a box the describer kept is never quietly dropped here and its list
#: of proposals still lines up one to one with the boxes it was given.
MIN_BLANK_SIDE = 2.0
OVERLAP_LIMIT = 0.45
PAGE_RULE_SHARE = 0.88

_UNDERSCORE = "_"
_OPEN_BRACKETS = "[(\u3010\uff08"
_CLOSE_BRACKETS = "])\u3011\uff09"
_TRAILING_JUNK = re.compile(r"[\s:\u2026._\-\u00b7]+$")
_LEADING_JUNK = re.compile(r"^[\s\u2022\u25e6\u25aa\u25cf\u25cb\u25a0\u2023\u2043\u00b7*\-]+")
_LEADING_NUMBER = re.compile(r"^\(?\d{1,3}[.)]\s+")
_WS = re.compile(r"\s+")
_NAME_BAD = re.compile(r"[^a-z0-9]+")


# ------------------------------------------------------------------ shapes

@dataclass
class Field:
    """One field of the form, as the user meets it.

    `value` is a str for text, a choice and a radio group (the chosen
    option, or "" for none), and a bool for a tick box. `choices` holds the
    options of a choice list or a radio group and is empty otherwise.
    `rect` is (x0, y0, x1, y1) in page points, top left origin, as PyMuPDF
    gives it. `page` is 1 for the first page. `id` is stable for as long as
    the FormDocument is open, and set_value also accepts the field name.
    """

    id: str
    name: str
    label: str
    kind: str
    value: object = ""
    choices: list = _dcfield(default_factory=list)
    required: bool = False
    read_only: bool = False
    page: int = 1
    rect: tuple = (0.0, 0.0, 0.0, 0.0)
    tooltip: str = ""

    @property
    def is_filled(self):
        if self.kind == KIND_CHECKBOX:
            return bool(self.value)
        return bool(str(self.value or "").strip())


@dataclass
class Proposal:
    """Somewhere a field could go on a form that has none.

    `confidence` runs from 0 to 1. `source` is one of SOURCES. `kind` is
    "text", "multiline text" or "checkbox"; nothing else is ever proposed,
    because nothing else can be worked out from the page. `name` is the
    field name add_fields will use, made unique when the fields are added.
    """

    page: int
    rect: tuple
    label: str
    confidence: float = 0.5
    source: str = "line"
    kind: str = KIND_TEXT
    name: str = ""


@dataclass
class PageImage:
    """A page rendered so an AI can look at it. Empty png_bytes means the
    render failed and `problem` is a sentence."""

    png_bytes: bytes = b""
    width_points: float = 0.0
    height_points: float = 0.0
    dpi: int = 150
    page: int = 1
    problem: str = ""


# ---------------------------------------------------------------- opening

def open_form(path):
    """Open a PDF so its form fields can be read and filled in.

    Never raises. A FormDocument always comes back; when it could not be
    opened, `.problem` is a sentence and `.fields` is empty.
    """
    doc = FormDocument.__new__(FormDocument)
    doc._init_empty(path)
    try:
        if not path:
            doc.problem = MSG_NO_FILE
            return doc
        if not os.path.isfile(path):
            doc.problem = MSG_NO_FILE
            return doc
        try:
            handle = fitz.open(path)
        except Exception as exc:                       # noqa: BLE001
            doc.problem = MSG_CANNOT_OPEN % _reason(exc)
            return doc
        if handle.needs_pass:
            handle.close()
            doc.problem = MSG_PASSWORD
            return doc
        if not handle.is_pdf:
            handle.close()
            doc.problem = MSG_NOT_PDF
            return doc
        doc._handle = handle
        doc.page_count = handle.page_count
        doc._collect()
    except Exception as exc:                           # noqa: BLE001
        doc.close()
        doc.problem = MSG_CANNOT_OPEN % _reason(exc)
    return doc


class FormDocument:
    """An open PDF form. One thread at a time; close it when you are done.

    Usable as a context manager, so a worker thread can be sure the file
    handle goes away even when something goes wrong further up.
    """

    def _init_empty(self, path):
        self.path = path or ""
        self.problem = ""
        self.page_count = 0
        self.fields = []
        self.dirty = False
        self.flattened = False
        self._handle = None
        self._by_id = {}
        self._places = {}
        self._pages = {}

    # -- reading ---------------------------------------------------------

    def _page(self, number):
        """A page object, kept alive for as long as this form is open.

        Measured: a widget loaded from a Page that is then thrown away
        fails on update() with "Annot is not bound to a page", so the page
        objects have to outlive the widgets taken from them.
        """
        page = self._pages.get(number)
        if page is None:
            page = self._handle[number]
            self._pages[number] = page
        return page

    @property
    def has_fields(self):
        return bool(self.fields)

    @property
    def is_open(self):
        return self._handle is not None

    def _collect(self):
        """Walk every page and build the Field list, in reading order."""
        self.fields = []
        self._by_id = {}
        self._places = {}
        if self._handle is None:
            return
        self._pages = {}
        for field_id, members in _index_widgets(self._handle, self._page):
            field = _field_from(members, field_id)
            self.fields.append(field)
            self._by_id[field.id] = field
            self._places[field.id] = [(number, w.xref) for number, w in members]

    def _find(self, field_id):
        """A Field from its id, or from its field name when that is unique."""
        if field_id in self._by_id:
            return self._by_id[field_id]
        if isinstance(field_id, Field):
            return self._by_id.get(field_id.id)
        wanted = str(field_id or "")
        hits = [f for f in self.fields if f.name == wanted]
        if len(hits) == 1:
            return hits[0]
        hits = [f for f in self.fields if f.label == wanted]
        if len(hits) == 1:
            return hits[0]
        return None

    def _widgets_for(self, field):
        """The live widgets behind a Field, looked up again by xref so a
        stale annotation object can never be written through."""
        out = []
        for number, xref in self._places.get(field.id, []):
            try:
                widget = self._page(number).load_widget(xref)
            except Exception:                          # noqa: BLE001
                widget = None
            if widget is None:
                try:
                    for candidate in self._page(number).widgets():
                        if candidate.xref == xref:
                            widget = candidate
                            break
                except Exception:                      # noqa: BLE001
                    widget = None
            if widget is not None:
                out.append(widget)
        return out

    # -- writing ---------------------------------------------------------

    def set_value(self, field_id, value):
        """Put a value in one field. Returns (ok, one sentence)."""
        if self.problem:
            return False, self.problem
        if self._handle is None:
            return False, MSG_CLOSED
        if self.flattened:
            return False, MSG_FLATTENED
        field = self._find(field_id)
        if field is None:
            return False, MSG_NO_FIELD
        if field.read_only:
            return False, MSG_READ_ONLY % field.label
        if field.kind == KIND_SIGNATURE:
            return False, MSG_SIGNATURE_FIELD % field.label
        if field.kind == KIND_BUTTON:
            return False, MSG_BUTTON_FIELD % field.label
        widgets = self._widgets_for(field)
        if not widgets:
            return False, MSG_NO_FIELD
        try:
            if field.kind == KIND_CHECKBOX:
                return self._set_checkbox(field, widgets[0], value)
            if field.kind == KIND_RADIO:
                return self._set_radio(field, widgets, value)
            if field.kind == KIND_CHOICE:
                return self._set_choice(field, widgets, value)
            return self._set_text(field, widgets, value)
        except Exception as exc:                       # noqa: BLE001
            return False, MSG_SAVE_FAILED % _reason(exc)

    def _set_text(self, field, widgets, value):
        text = "" if value is None else str(value)
        note = ""
        if field.kind != KIND_MULTILINE and ("\n" in text or "\r" in text):
            text = _WS.sub(" ", text.replace("\r", "\n")).strip()
            note = MSG_SINGLE_LINE
        limit = 0
        try:
            limit = int(widgets[0].text_maxlen or 0)
        except Exception:                              # noqa: BLE001
            limit = 0
        if limit and len(text) > limit:
            return False, MSG_TOO_LONG % (field.label, limit, len(text))
        for widget in widgets:
            widget.field_value = text
            widget.update()
        field.value = text
        self.dirty = True
        if note:
            return True, note % (field.label, _quote(text))
        if not text:
            return True, MSG_SET_EMPTY % field.label
        return True, MSG_SET % (field.label, _quote(text))

    def _set_checkbox(self, field, widget, value):
        on = _truthy(value, widget)
        widget.field_value = bool(on)
        widget.update()
        field.value = bool(on)
        self.dirty = True
        return True, (MSG_TICKED if on else MSG_UNTICKED) % field.label

    def _set_radio(self, field, widgets, value):
        wanted = "" if value is None else str(value).strip()
        if wanted == "" or wanted.lower() in ("off", "none", "no"):
            for widget in widgets:
                if _widget_on(widget):
                    widget.field_value = False
                    widget.update()
            self._fix_radio_parent(widgets, "Off")
            field.value = ""
            self.dirty = True
            return True, MSG_CLEARED % field.label
        chosen = None
        for widget in widgets:
            state = _on_state(widget)
            if state and state.lower() == wanted.lower():
                chosen = widget
                break
        if chosen is None:
            return False, MSG_NOT_AN_OPTION % (field.label, _join(field.choices))
        chosen.field_value = _on_state(chosen)
        chosen.update()
        field.value = _on_state(chosen)
        self._fix_radio_parent(widgets, field.value)
        self.dirty = True
        return True, MSG_SET % (field.label, _quote(field.value))

    def _fix_radio_parent(self, widgets, state):
        """A button field's value has to be a PDF name.

        Measured: PyMuPDF writes the parent field's /V as a string, so a
        radio group filled in here reads back as the text "Female" where
        the PDF specification wants the name /Female. The kid appearance
        state is right, so only the parent needs correcting.
        """
        for widget in widgets:
            parent = getattr(widget, "rb_parent", 0) or 0
            if not parent:
                continue
            try:
                self._handle.xref_set_key(parent, "V", _pdf_name(state))
            except Exception:                          # noqa: BLE001
                pass
            return

    def _set_choice(self, field, widgets, value):
        widget = widgets[0]
        editable = bool((widget.field_flags or 0) & fitz.PDF_CH_FIELD_IS_EDIT)
        multi = bool((widget.field_flags or 0) & fitz.PDF_CH_FIELD_IS_MULTI_SELECT)
        if isinstance(value, (list, tuple)):
            wanted = [str(v) for v in value]
        else:
            wanted = [] if value is None or str(value) == "" else [str(value)]
        if len(wanted) > 1 and not multi:
            return False, MSG_NOT_AN_OPTION % (field.label, _join(field.choices))
        picked = []
        for item in wanted:
            match = _match_choice(item, field.choices)
            if match is None:
                if editable:
                    match = item
                else:
                    return False, MSG_NOT_AN_OPTION % (field.label, _join(field.choices))
            picked.append(match)
        for w in widgets:
            if not picked:
                w.field_value = ""
            elif len(picked) == 1:
                w.field_value = picked[0]
            else:
                w.field_value = list(picked)
            w.update()
        field.value = "" if not picked else (picked[0] if len(picked) == 1 else list(picked))
        self.dirty = True
        if not picked:
            return True, MSG_SET_EMPTY % field.label
        return True, MSG_SET % (field.label, _quote(_join(picked)))

    # -- saving ----------------------------------------------------------

    def save(self, out_path=None, flatten=False):
        """Write the form back. In place when out_path is None.

        An in place save that is not flattening is written incrementally,
        which appends the changes and leaves every other byte of the file
        alone. A copy of the file is kept beside it until the save has
        finished, so a save that goes wrong cannot leave a broken PDF.
        Flattening prints the answers onto the page and takes the fields
        away, so it has to rewrite the whole file.
        """
        if self.problem:
            return False, self.problem
        if self._handle is None:
            return False, MSG_CLOSED
        target = out_path or self.path
        in_place = (not out_path) or _same_file(out_path, self.path)
        if in_place and not self.dirty and not flatten:
            return True, MSG_NOTHING_CHANGED
        try:
            if flatten:
                self._handle.bake(annots=False, widgets=True)
                self.flattened = True
                ok, message = _write_whole(self._handle, target)
                if not ok:
                    return False, message
                self._collect()
                self.dirty = False
                return True, MSG_SAVED_FLAT
            if in_place:
                ok, message = _write_incremental(self._handle, self.path)
                if not ok:
                    return False, message
                self.dirty = False
                return True, MSG_SAVED
            ok, message = _write_whole(self._handle, target)
            if not ok:
                return False, message
            return True, MSG_SAVED_COPY % os.path.basename(target)
        except Exception as exc:                       # noqa: BLE001
            return False, MSG_SAVE_FAILED % _reason(exc)

    def close(self):
        handle = self._handle
        self._handle = None
        self._pages = {}
        if handle is not None:
            try:
                handle.close()
            except Exception:                          # noqa: BLE001
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False


def describe_form(doc):
    """A plain spoken summary of a form, for the status line or a dialog."""
    if doc is None:
        return MSG_NO_FILE
    if getattr(doc, "problem", ""):
        return doc.problem
    fields = list(getattr(doc, "fields", []) or [])
    if not fields:
        return MSG_NO_FIELDS
    counts = {}
    for f in fields:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    parts = []
    for kind in _KIND_ORDER:
        n = counts.get(kind, 0)
        if n:
            one, many = _KIND_WORDS[kind]
            parts.append("%s %s" % (_count(n), one if n == 1 else many))
    pages = int(getattr(doc, "page_count", 1) or 1)
    head = DESC_HEAD % (
        "%s %s" % (_count(len(fields)), "field" if len(fields) == 1 else "fields"),
        "%s %s" % (_count(pages), "page" if pages == 1 else "pages"),
        _join(parts),
    )
    filled = sum(1 for f in fields if f.is_filled)
    empty = len(fields) - filled
    second = DESC_FILLED % (_capital(_count(filled)), _count(empty))
    out = head + " " + second
    locked = sum(1 for f in fields if f.read_only)
    if locked:
        out += " " + DESC_LOCKED % (
            "%s %s" % (_capital(_count(locked)), "field" if locked == 1 else "fields"))
    return out


# --------------------------------------------------------- finding blanks

def propose_fields(source, page=None):
    """Look at a flat form and say where the blanks are.

    `source` is a path or an open FormDocument. `page` limits the search to
    one page number, 1 for the first page. Nothing is written to the file:
    this only proposes.

    Never raises. An empty list comes back when the file cannot be read;
    open_form gives the sentence that says why.
    """
    own = None
    doc = None
    try:
        if isinstance(source, FormDocument):
            if source.problem or source._handle is None:
                return []
            doc = source._handle
            taken = [(f.page, f.rect) for f in source.fields]
        else:
            own = open_form(source)
            if own.problem or own._handle is None:
                return []
            doc = own._handle
            taken = [(f.page, f.rect) for f in own.fields]
        numbers = range(doc.page_count)
        if page is not None:
            try:
                wanted = int(page)
            except Exception:                          # noqa: BLE001
                return []
            if wanted < 1 or wanted > doc.page_count:
                return []
            numbers = [wanted - 1]
        out = []
        for number in numbers:
            try:
                out.extend(_propose_page(doc[number], number + 1, taken))
            except Exception:                          # noqa: BLE001
                continue
        _name_them(out)
        return out
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if own is not None:
            own.close()


def _propose_page(page, number, taken):
    lines = _page_lines(page)
    rules, uprights, boxes = _page_shapes(page)
    right_edge = max([ln.bbox[2] for ln in lines], default=page.rect.x1 - 72.0)
    grid, used_rules = _from_grid(rules, uprights, lines, number)
    plain = [r for r in rules if _key(r) not in used_rules]
    found = []
    found.extend(_from_underscores(lines, number))
    found.extend(_from_brackets(lines, number))
    found.extend(_from_rules(plain, lines, number, page))
    found.extend(_from_boxes(boxes, lines, number))
    found.extend(grid)
    found.extend(_from_colons(lines, number, right_edge))
    already = [rect for page_number, rect in taken if page_number == number]
    kept = _dedupe(found)
    kept = [p for p in kept if not _hits_existing(p, already)]
    kept = _reading_order([(fitz.Rect(*p.rect), p) for p in kept])
    blank = 0
    for proposal in kept:
        if not proposal.label:
            blank += 1
            proposal.label = LABEL_UNNAMED % (blank, number)
    return kept


def _from_underscores(lines, number):
    out = []
    for line in lines:
        runs = _runs_of(line, _UNDERSCORE, MIN_UNDERSCORES)
        for start, end in runs:
            x0 = line.chars[start][1][0]
            x1 = line.chars[end][1][2]
            if x1 - x0 < MIN_FIELD_WIDTH:
                continue
            top, bottom = _line_band(line)
            #: "________ Printed name" labels from the right, so the text
            #: after the run is tried before anything above it.
            label = _label_before(line, start) or _label_left_of(lines, line, x0) \
                or _label_after(line, end) or _label_above(lines, (x0, top, x1, bottom))
            out.append(Proposal(page=number, rect=(x0, top, x1, bottom), label=label,
                                confidence=CONF_UNDERSCORES if label else CONF_UNDERSCORES - 0.2,
                                source="underscores", kind=KIND_TEXT))
    return out


def _from_brackets(lines, number):
    """A pair of brackets beside a word is a tick box, and medical forms
    are full of them."""
    out = []
    for line in lines:
        n = len(line.chars)
        i = 0
        while i < n:
            char, box = line.chars[i]
            if char in _OPEN_BRACKETS:
                j = i + 1
                inside = 0
                while j < n and line.chars[j][0] in " \t\u00a0" and inside < 4:
                    j += 1
                    inside += 1
                if j < n and line.chars[j][0] in _CLOSE_BRACKETS:
                    close = line.chars[j][1]
                    rect = _square((box[0], box[1], close[2], box[3]))
                    label = _label_after(line, j) or _label_before(line, i)
                    out.append(Proposal(page=number, rect=rect, label=label,
                                        confidence=CONF_BRACKETS if label else CONF_BRACKETS - 0.25,
                                        source="box", kind=KIND_CHECKBOX))
                    i = j + 1
                    continue
            i += 1
    return out


def _from_rules(rules, lines, number, page):
    """A ruled line with a label ending in a colon to its left, or a label
    sitting above it, is somewhere to write."""
    out = []
    width = float(page.rect.width or 612.0)
    left = min([ln.bbox[0] for ln in lines], default=72.0)
    right = max([ln.bbox[2] for ln in lines], default=width - 72.0)
    column = max(80.0, right - left)
    for x0, y0, x1, y1 in rules:
        span = x1 - x0
        if span < MIN_RULE_WIDTH:
            continue
        top = min(y0, y1)
        label, kind = _label_for_rule(lines, x0, x1, top)
        if label and kind == "colon":
            score = CONF_LINE_COLON
        elif label and kind == "left":
            score = CONF_LINE_ABOVE
        elif label:
            # The label is above. A rule that also runs most of the way
            # across the column is the underline of a heading, not a blank.
            if span >= column * 0.65:
                continue
            score = CONF_LINE_ABOVE
        else:
            if span >= width * PAGE_RULE_SHARE:
                # A rule right across the page is furniture, not a blank.
                continue
            score = CONF_LINE_BARE
        height = _rule_height(lines, top)
        rect = (x0, top - height, x1, top - 1.0)
        if rect[3] - rect[1] < MIN_FIELD_HEIGHT or rect[2] - rect[0] < MIN_FIELD_WIDTH:
            continue
        out.append(Proposal(page=number, rect=rect, label=label, confidence=score,
                            source="line", kind=KIND_TEXT))
    return out


def _from_boxes(boxes, lines, number):
    out = []
    for x0, y0, x1, y1 in boxes:
        w = x1 - x0
        h = y1 - y0
        if w < MIN_BOX_SIDE or h < MIN_BOX_SIDE:
            continue
        if _box_has_text(lines, (x0, y0, x1, y1)):
            continue
        square = MIN_BOX_SIDE <= w <= MAX_TICK_SIDE and MIN_BOX_SIDE <= h <= MAX_TICK_SIDE \
            and 0.55 <= (w / h if h else 99) <= 1.8
        if square:
            label = _label_right_of(lines, (x0, y0, x1, y1)) \
                or _label_left_of_rect(lines, (x0, y0, x1, y1))
            out.append(Proposal(page=number, rect=(x0, y0, x1, y1), label=label,
                                confidence=CONF_BOX_SMALL if label else CONF_BOX_SMALL - 0.25,
                                source="box", kind=KIND_CHECKBOX))
            continue
        if w < MIN_FIELD_WIDTH or h < MIN_FIELD_HEIGHT:
            continue
        #: A one line box sits beside its label; a tall box sits under it.
        if h <= MAX_LINE_HEIGHT * 1.6:
            label = _label_left_of_rect(lines, (x0, y0, x1, y1)) \
                or _label_above(lines, (x0, y0, x1, y1))
        else:
            label = _label_above(lines, (x0, y0, x1, y1)) \
                or _label_left_of_rect(lines, (x0, y0, x1, y1))
        kind = KIND_MULTILINE if h > DEFAULT_LINE_HEIGHT * 2.2 else KIND_TEXT
        out.append(Proposal(page=number, rect=(x0, y0, x1, y1), label=label,
                            confidence=CONF_BOX_LARGE if label else CONF_BOX_LARGE - 0.2,
                            source="box", kind=kind))
    return out


def _from_colons(lines, number, right_edge):
    """A label, a colon, and then nothing at all to the end of the line."""
    out = []
    for line in lines:
        text = line.text.rstrip()
        if not text.endswith(":"):
            continue
        before = text[:-1].strip()
        if not _has_letters(before):
            continue
        x1 = line.bbox[2]
        room = right_edge - x1
        if room < COLON_MIN_ROOM:
            continue
        if _something_right_of(lines, line):
            continue
        top, bottom = _line_band(line)
        out.append(Proposal(page=number, rect=(x1 + 4.0, top, right_edge, bottom),
                            label=_clean_label(before), confidence=CONF_COLON,
                            source="colon", kind=KIND_TEXT))
    return out


# ------------------------------------------------------------ adding them

def add_fields(path, proposals, out_path=None):
    """Put real form fields on a PDF that has none.

    Every field gets its label as /TU, which is the string a screen reader
    reads out, a field name made from the label, and no border and no fill,
    so the page still looks exactly as it did. Returns (ok, sentence, how
    many were added).
    """
    #: Anything with a page, a rectangle and a label is a proposal here.
    #: The dialog stands in its own object when the user renames one, and a
    #: rename must never be the thing that makes a field disappear.
    proposals = [_as_proposal(p) for p in (proposals or [])]
    proposals = [p for p in proposals if p is not None]
    if not proposals:
        return False, MSG_NO_PROPOSALS, 0
    if not path or not os.path.isfile(path):
        return False, MSG_NO_FILE, 0
    handle = None
    try:
        try:
            handle = fitz.open(path)
        except Exception as exc:                       # noqa: BLE001
            return False, MSG_CANNOT_OPEN % _reason(exc), 0
        if handle.needs_pass:
            return False, MSG_PASSWORD, 0
        if not handle.is_pdf:
            return False, MSG_NOT_PDF, 0
        used = set()
        for number in range(handle.page_count):
            try:
                for widget in handle[number].widgets():
                    if widget.field_name:
                        used.add(widget.field_name)
            except Exception:                          # noqa: BLE001
                continue
        added = 0
        touched = set()
        ordered = sorted(proposals, key=lambda p: (p.page, p.rect[1], p.rect[0]))
        for proposal in ordered:
            number = int(proposal.page) - 1
            if number < 0 or number >= handle.page_count:
                continue
            page = handle[number]
            rect = fitz.Rect(*[float(v) for v in proposal.rect])
            rect.normalize()
            if rect.is_empty or rect.width < 4 or rect.height < 4:
                continue
            name = _unique(proposal.name or _slug(proposal.label), used)
            used.add(name)
            widget = fitz.Widget()
            if proposal.kind == KIND_CHECKBOX:
                widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                widget.field_value = False
            else:
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                widget.field_value = ""
                if proposal.kind == KIND_MULTILINE:
                    widget.field_flags = fitz.PDF_TX_FIELD_IS_MULTILINE
                #: 0 means the viewer sizes the text to the box.
                widget.text_fontsize = 0
            widget.field_name = name
            widget.field_label = proposal.label or name
            widget.border_width = 0
            widget.rect = rect
            try:
                page.add_widget(widget)
            except Exception:                          # noqa: BLE001
                continue
            added += 1
            touched.add(number)
        if not added:
            return False, MSG_ADDED_NONE, 0
        tabs = "/S" if _has_structure(handle) else "/R"
        for number in sorted(touched):
            try:
                handle.xref_set_key(handle[number].xref, "Tabs", tabs)
            except Exception:                          # noqa: BLE001
                pass
        target = out_path or path
        if (not out_path) or _same_file(out_path, path):
            ok, message = _write_incremental(handle, path)
        else:
            ok, message = _write_whole(handle, target)
        if not ok:
            return False, message, 0
        return True, (MSG_ADDED_ONE if added == 1 else MSG_ADDED % added), added
    except Exception as exc:                           # noqa: BLE001
        return False, MSG_SAVE_FAILED % _reason(exc), 0
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:                          # noqa: BLE001
                pass


# -------------------------------------------------------------- signature

def _as_proposal(thing):
    """A Proposal from anything that carries a page, a rectangle and a
    label, whether it is a Proposal, something standing in for one, or a
    plain dictionary. None when there is not enough to place a field."""
    if isinstance(thing, Proposal):
        return thing
    if isinstance(thing, dict):
        get = thing.get
    else:
        def get(key, fallback=None):
            return getattr(thing, key, fallback)
    rect = get("rect")
    try:
        values = [float(v) for v in list(rect)[:4]]
    except Exception:                                  # noqa: BLE001
        return None
    if len(values) != 4:
        return None
    try:
        page = int(get("page") or 1)
    except Exception:                                  # noqa: BLE001
        page = 1
    kind = str(get("kind") or KIND_TEXT)
    if kind not in (KIND_TEXT, KIND_MULTILINE, KIND_CHECKBOX):
        kind = KIND_TEXT
    try:
        score = float(get("confidence") or 0.5)
    except Exception:                                  # noqa: BLE001
        score = 0.5
    source = str(get("source") or "line")
    return Proposal(page=page, rect=tuple(values),
                    label=str(get("label") or "").strip(),
                    confidence=score, source=source, kind=kind,
                    name=str(get("name") or ""))


def confidence_word(value):
    """"high", "medium" or "low", for a dialog that says how sure it is in
    words rather than reading a number out."""
    try:
        score = float(value)
    except Exception:                                  # noqa: BLE001
        return "low"
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def sign_with_text(path, field_or_rect, name, out_path=None):
    """Write a typed name where the form asks for a signature.

    This is a typed name, accepted by most forms in practice. It is not a
    cryptographic digital signature, and neither the message nor the file
    ever says it is.
    """
    if not str(name or "").strip():
        return False, MSG_SIGN_EMPTY
    return _sign(path, field_or_rect, out_path, text=str(name).strip(), image=None)


def sign_with_image(path, field_or_rect, image_bytes, out_path=None):
    """Draw a picture of a signature where the form asks for one.

    A picture, not a cryptographic digital signature.
    """
    if not image_bytes:
        return False, MSG_SIGN_BAD_IMAGE
    return _sign(path, field_or_rect, out_path, text=None, image=image_bytes)


def _sign(path, field_or_rect, out_path, text, image):
    if not path or not os.path.isfile(path):
        return False, MSG_NO_FILE
    handle = None
    try:
        try:
            handle = fitz.open(path)
        except Exception as exc:                       # noqa: BLE001
            return False, MSG_CANNOT_OPEN % _reason(exc)
        if handle.needs_pass:
            return False, MSG_PASSWORD
        if not handle.is_pdf:
            return False, MSG_NOT_PDF
        spot = _where_to_sign(handle, field_or_rect)
        if spot is None:
            return False, MSG_SIGN_NO_TARGET
        number, rect, xref, kind, label = spot
        if number < 0 or number >= handle.page_count:
            return False, MSG_NO_PAGE % (number + 1)
        page = handle[number]
        if text is not None and kind in (KIND_TEXT, KIND_MULTILINE) and xref is not None:
            widget = page.load_widget(xref)
            if widget is not None:
                widget.field_value = text
                widget.update()
                ok, message = _finish_sign(handle, path, out_path)
                if not ok:
                    return False, message
                return True, MSG_SIGNED_TEXT % label
        if image is not None:
            try:
                fitz.Pixmap(image)
            except Exception:                          # noqa: BLE001
                return False, MSG_SIGN_BAD_IMAGE
            try:
                page.insert_image(rect, stream=image, keep_proportion=True)
            except Exception:                          # noqa: BLE001
                return False, MSG_SIGN_BAD_IMAGE
        else:
            if not _draw_name(page, rect, text):
                return False, MSG_SIGN_NO_ROOM
        if xref is not None and kind == KIND_SIGNATURE:
            # Take the empty signature field away, so nothing in the file
            # claims a digital signature that is not there.
            try:
                widget = page.load_widget(xref)
                if widget is not None:
                    page.delete_widget(widget)
            except Exception:                          # noqa: BLE001
                pass
        ok, message = _finish_sign(handle, path, out_path)
        if not ok:
            return False, message
        return True, (MSG_SIGNED_IMAGE if image is not None else MSG_SIGNED_TEXT) % label
    except Exception as exc:                           # noqa: BLE001
        return False, MSG_SAVE_FAILED % _reason(exc)
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:                          # noqa: BLE001
                pass


def _finish_sign(handle, path, out_path):
    if (not out_path) or _same_file(out_path, path):
        return _write_incremental(handle, path)
    return _write_whole(handle, out_path)


def _draw_name(page, rect, text):
    """Times italic, as large as fits. Returns False when it will not."""
    box = fitz.Rect(rect)
    size = min(box.height * 0.72, 24.0)
    while size >= 6.0:
        try:
            room = page.insert_textbox(box, text, fontname="tiit", fontsize=size,
                                       align=fitz.TEXT_ALIGN_LEFT)
        except Exception:                              # noqa: BLE001
            return False
        if room >= 0:
            return True
        size -= 1.0
    return False


def _where_to_sign(handle, target):
    """(page number from 0, rect, widget xref or None, kind, label)."""
    if isinstance(target, Proposal):
        return (int(target.page) - 1, fitz.Rect(*target.rect), None, target.kind,
                target.label or "the space to sign in")
    if isinstance(target, Field):
        return (int(target.page) - 1, fitz.Rect(*target.rect), None, target.kind,
                target.label or target.name)
    if isinstance(target, dict):
        rect = target.get("rect")
        page = int(target.get("page", 1))
        if rect and len(rect) == 4:
            return (page - 1, fitz.Rect(*[float(v) for v in rect]), None, KIND_SIGNATURE,
                    str(target.get("label") or "the space to sign in"))
        return None
    if isinstance(target, (list, tuple)):
        values = list(target)
        if len(values) == 5:
            page = int(values[0])
            return (page - 1, fitz.Rect(*[float(v) for v in values[1:]]), None,
                    KIND_SIGNATURE, "the space to sign in")
        if len(values) == 4:
            return (0, fitz.Rect(*[float(v) for v in values]), None, KIND_SIGNATURE,
                    "the space to sign in")
        return None
    if isinstance(target, str) and target:
        #: The dialog hands over a Field id ("f7"), and somebody working
        #: from a script hands over a field name. Both have to land on the
        #: same widget, so both are looked up.
        for field_id, members in _index_widgets(handle):
            number, widget = members[0]
            if field_id == target or widget.field_name == target:
                return (number, fitz.Rect(widget.rect), widget.xref,
                        _kind_of(widget),
                        _clean_label(widget.field_label or "")
                        or widget.field_name or field_id)
        return None
    return None


# ------------------------------------------------------------ the AI path

def render_page_png(path, page_index, dpi=150):
    """Render one page as a PNG so an AI can be asked to look at it.

    `page_index` is a page number, 1 for the first page. Never raises: a
    PageImage with empty png_bytes and a sentence in `problem` comes back
    when it cannot be done.
    """
    out = PageImage(dpi=int(dpi or 150), page=int(page_index or 1))
    if not path or not os.path.isfile(path):
        out.problem = MSG_NO_FILE
        return out
    handle = None
    try:
        handle = fitz.open(path)
        if handle.needs_pass:
            out.problem = MSG_PASSWORD
            return out
        if not handle.is_pdf:
            out.problem = MSG_NOT_PDF
            return out
        number = int(page_index) - 1
        if number < 0 or number >= handle.page_count:
            out.problem = MSG_NO_PAGE % page_index
            return out
        page = handle[number]
        pix = page.get_pixmap(dpi=int(dpi or 150), alpha=False)
        out.png_bytes = pix.tobytes("png")
        out.width_points = float(page.rect.width)
        out.height_points = float(page.rect.height)
        return out
    except Exception as exc:                           # noqa: BLE001
        out.png_bytes = b""
        out.problem = MSG_CANNOT_OPEN % _reason(exc)
        return out
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:                          # noqa: BLE001
                pass


def ai_proposals(source, page_index, ask, dpi=150):
    """The optional AI path, for Worker C to wire a provider into.

    `ask` is theirs: a callable taking (png_bytes, width_points,
    height_points, page_index) and returning a list of dicts, each with a
    "label" and a "rect" of four numbers in page points, and optionally
    "kind" ("text", "multiline text" or "checkbox") and "confidence".
    The network call, the key, the consent and the prompt are all theirs;
    the rendering and the checking of what comes back are here.

    Returns (list of Proposal, one sentence which is empty when all is
    well). Never raises, and never calls out to anything itself.
    """
    path = source.path if isinstance(source, FormDocument) else source
    image = render_page_png(path, page_index, dpi=dpi)
    if image.problem or not image.png_bytes:
        return [], image.problem or MSG_CANNOT_OPEN % ""
    if ask is None:
        return [], MSG_SIGN_NO_TARGET
    try:
        boxes = ask(image.png_bytes, image.width_points, image.height_points,
                    int(page_index))
    except Exception as exc:                           # noqa: BLE001
        return [], MSG_CANNOT_OPEN % _reason(exc)
    out = from_ai(page_index, boxes)
    _name_them(out)
    return out, ""


def from_ai(page_index, boxes):
    """Turn what an AI said into Proposals. Anything malformed is dropped.

    `boxes` is a list of dicts: "label" a string, "rect" four numbers
    (x0, y0, x1, y1) in page points with the origin at the top left of the
    page, and optionally "kind" and "confidence". `page_index` is a page
    number, 1 for the first page.
    """
    out = []
    try:
        number = int(page_index)
    except Exception:                                  # noqa: BLE001
        return out
    for item in (boxes or []):
        try:
            if not isinstance(item, dict):
                continue
            rect = item.get("rect") or item.get("box")
            if not rect or len(rect) != 4:
                continue
            values = [float(v) for v in rect]
            x0, x1 = min(values[0], values[2]), max(values[0], values[2])
            y0, y1 = min(values[1], values[3]), max(values[1], values[3])
            if x1 - x0 < MIN_BLANK_SIDE or y1 - y0 < MIN_BLANK_SIDE:
                continue
            kind = str(item.get("kind") or KIND_TEXT)
            if kind not in (KIND_TEXT, KIND_MULTILINE, KIND_CHECKBOX):
                kind = KIND_TEXT
            try:
                score = float(item.get("confidence", CONF_AI))
            except Exception:                          # noqa: BLE001
                score = CONF_AI
            score = max(0.0, min(1.0, score))
            out.append(Proposal(page=number, rect=(x0, y0, x1, y1),
                                label=_clean_label(str(item.get("label") or "")),
                                confidence=score, source="ai", kind=kind))
        except Exception:                              # noqa: BLE001
            continue
    blank = 0
    for proposal in out:
        if not proposal.label:
            blank += 1
            proposal.label = LABEL_UNNAMED % (blank, number)
    _name_them(out)
    return out


# ------------------------------------------------------------- page reading

class _Line:
    __slots__ = ("bbox", "text", "chars", "size")

    def __init__(self, bbox, text, chars, size):
        self.bbox = bbox
        self.text = text
        self.chars = chars
        self.size = size


def _page_lines(page):
    """Every horizontal line of text, with a box per character."""
    out = []
    try:
        data = page.get_text("rawdict")
    except Exception:                                  # noqa: BLE001
        return out
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            direction = line.get("dir", (1, 0))
            if abs(float(direction[0]) - 1.0) > 0.01 or abs(float(direction[1])) > 0.01:
                continue                               # sideways text, leave it alone
            chars = []
            size = 0.0
            for span in line.get("spans", []):
                size = max(size, float(span.get("size", 0.0)))
                for char in span.get("chars", []):
                    box = tuple(float(v) for v in char["bbox"])
                    chars.append((char.get("c", ""), box))
            if not chars:
                continue
            text = "".join(c for c, _ in chars)
            if not text.strip():
                continue
            out.append(_Line(tuple(float(v) for v in line["bbox"]), text, chars,
                             size or DEFAULT_LINE_HEIGHT))
    out.sort(key=lambda ln: (round(ln.bbox[1], 1), ln.bbox[0]))
    return out


def _page_shapes(page):
    """(ruled lines across, ruled lines down, rectangles) from the page's
    drawings. A rectangle thin enough to be a rule is counted as one."""
    rules = []
    uprights = []
    boxes = []
    try:
        drawings = page.get_drawings()
    except Exception:                                  # noqa: BLE001
        return rules, uprights, boxes
    for drawing in drawings:
        for item in drawing.get("items", []):
            try:
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    if abs(p1.y - p2.y) <= 1.5 and abs(p1.x - p2.x) >= MIN_RULE_WIDTH:
                        rules.append((min(p1.x, p2.x), min(p1.y, p2.y),
                                      max(p1.x, p2.x), max(p1.y, p2.y)))
                    elif abs(p1.x - p2.x) <= 1.5 and abs(p1.y - p2.y) >= MIN_UPRIGHT:
                        uprights.append((min(p1.x, p2.x), min(p1.y, p2.y),
                                         max(p1.x, p2.x), max(p1.y, p2.y)))
                elif item[0] == "re":
                    rect = item[1]
                    x0, y0 = min(rect.x0, rect.x1), min(rect.y0, rect.y1)
                    x1, y1 = max(rect.x0, rect.x1), max(rect.y0, rect.y1)
                    if (y1 - y0) <= MAX_RULE_THICKNESS and (x1 - x0) >= MIN_RULE_WIDTH:
                        rules.append((x0, y0, x1, y1))
                    elif (x1 - x0) <= MAX_RULE_THICKNESS and (y1 - y0) >= MIN_UPRIGHT:
                        uprights.append((x0, y0, x1, y1))
                    else:
                        boxes.append((x0, y0, x1, y1))
            except Exception:                          # noqa: BLE001
                continue
    return _unique_rects(rules), _unique_rects(uprights), _unique_rects(boxes)


def _key(rect):
    return tuple(round(v, 1) for v in rect)


def _from_grid(rules, uprights, lines, number):
    """A ruled table is a grid of blanks, and a medication table on an
    intake form is one of the commonest shapes there is.

    Only fires when there really is a lattice: two lines across and two
    down that meet. Each empty cell becomes a field, labelled from its
    column heading, or from the first cell of its row when the column has
    no heading. Returns (proposals, the rules the grid used) so a grid line
    is not also proposed as a blank to write on.
    """
    if len(rules) < 2 or len(uprights) < 2:
        return [], set()
    across = sorted(rules, key=lambda r: r[1])
    down = sorted(uprights, key=lambda r: r[0])
    #: Nothing above the top of the lattice is a column heading.
    lattice_top = min(u[1] for u in down)
    out = []
    used = set()
    for top, bottom in zip(across, across[1:]):
        y0 = max(top[1], top[3])
        y1 = min(bottom[1], bottom[3])
        height = y1 - y0
        if height < MIN_FIELD_HEIGHT or height > 120.0:
            continue
        left = max(top[0], bottom[0])
        right = min(top[2], bottom[2])
        if right - left < MIN_RULE_WIDTH:
            continue
        crossings = []
        for x0, uy0, _x1, uy1 in down:
            if x0 < left - 2.0 or x0 > right + 2.0:
                continue
            if uy0 > y0 + 2.0 or uy1 < y1 - 2.0:
                continue                               # does not span this row
            crossings.append(x0)
        if len(crossings) < 2:
            continue
        crossings = sorted(set(round(x, 1) for x in crossings))
        used.add(_key(top))
        used.add(_key(bottom))
        for cx0, cx1 in zip(crossings, crossings[1:]):
            cell = (cx0 + 1.0, y0 + 1.0, cx1 - 1.0, y1 - 1.0)
            if cell[2] - cell[0] < MIN_FIELD_WIDTH:
                continue
            if _box_has_text(lines, cell):
                continue
            label = _column_heading(lines, lattice_top, cx0, cx1, y0) \
                or _row_heading(lines, y0, y1, crossings[0], cx0)
            kind = KIND_MULTILINE if height > DEFAULT_LINE_HEIGHT * 2.2 else KIND_TEXT
            out.append(Proposal(page=number, rect=cell, label=label,
                                confidence=CONF_GRID if label else CONF_GRID - 0.2,
                                source="box", kind=kind))
    return out, used


def _column_heading(lines, lattice_top, cx0, cx1, y0):
    """The text in the topmost cell of this column, above the row and
    inside the table."""
    best = None
    for line in lines:
        centre = (line.bbox[0] + line.bbox[2]) / 2.0
        if centre < cx0 or centre > cx1:
            continue
        if line.bbox[3] > y0 + 2.0 or line.bbox[1] < lattice_top - 2.0:
            continue
        if best is None or line.bbox[1] < best.bbox[1]:
            best = line
    return _clean_label(best.text) if best is not None else ""


def _row_heading(lines, y0, y1, first_x, cx0):
    """The text in the first cell of this row, when the column has no
    heading of its own."""
    if abs(cx0 - first_x) < 1.0:
        return ""
    best = None
    for line in lines:
        centre = (line.bbox[1] + line.bbox[3]) / 2.0
        if centre < y0 or centre > y1:
            continue
        if line.bbox[0] < first_x - 2.0 or line.bbox[2] > cx0 + 2.0:
            continue
        if best is None or line.bbox[0] < best.bbox[0]:
            best = line
    return _clean_label(best.text) if best is not None else ""


def _unique_rects(rects):
    seen = set()
    out = []
    for rect in rects:
        key = tuple(round(v, 1) for v in rect)
        if key in seen:
            continue
        seen.add(key)
        out.append(rect)
    return out


# ------------------------------------------------------------------ labels

def _runs_of(line, char, least):
    """Index pairs of every run of `char` at least `least` long."""
    out = []
    start = None
    for index, (c, _) in enumerate(line.chars):
        if c == char:
            if start is None:
                start = index
        else:
            if start is not None and index - start >= least:
                out.append((start, index - 1))
            start = None
    if start is not None and len(line.chars) - start >= least:
        out.append((start, len(line.chars) - 1))
    return out


def _label_before(line, index):
    """The label just before a blank, when several blanks share a line.

    "Last name: ____   First name: ____" must give the second blank "First
    name", not the whole line, so the text is cut at the last run of
    underscores before it. When nothing is left, as it is for the second
    and third box of a date split into three, the label at the start of the
    line is used again, which is honest: three boxes called Date of birth.
    """
    text = "".join(c for c, _ in line.chars[:index])
    pieces = re.split(r"_{3,}", text)
    label = _clean_label(pieces[-1])
    if label:
        return label
    return _clean_label(pieces[0])


def _label_after(line, index):
    """The first few words after a blank, for a form that labels from the
    right: "[ ] Diabetic" and "________ Printed name"."""
    text = "".join(c for c, _ in line.chars[index + 1:]).strip()
    for piece in re.split(r"\s{2,}", text):
        if piece.strip():
            text = piece
            break
    for opener in _OPEN_BRACKETS:
        text = text.split(opener)[0]
    text = re.split(r"_{3,}", text)[0]
    words = _WS.sub(" ", text).strip().split(" ")
    return _clean_label(" ".join(words[:4]))


def _line_band(line):
    top = line.bbox[1]
    bottom = line.bbox[3]
    height = bottom - top
    if height < MIN_LINE_HEIGHT:
        middle = (top + bottom) / 2.0
        top, bottom = middle - MIN_LINE_HEIGHT / 2.0, middle + MIN_LINE_HEIGHT / 2.0
    elif height > MAX_LINE_HEIGHT:
        bottom = top + MAX_LINE_HEIGHT
    return top, bottom


def _same_row(a_top, a_bottom, b_top, b_bottom):
    overlap = min(a_bottom, b_bottom) - max(a_top, b_top)
    shortest = min(a_bottom - a_top, b_bottom - b_top) or 1.0
    return overlap > shortest * 0.4


def _label_left_of(lines, line, x0):
    return _label_left_of_rect(lines, (x0, line.bbox[1], x0, line.bbox[3]), skip=line)


def _label_left_of_rect(lines, rect, skip=None):
    best = None
    for other in lines:
        if other is skip:
            continue
        if not _same_row(rect[1], rect[3], other.bbox[1], other.bbox[3]):
            continue
        if other.bbox[2] > rect[0] + 2.0:
            continue
        if rect[0] - other.bbox[2] > LABEL_GAP_LEFT:
            continue
        if best is None or other.bbox[2] > best.bbox[2]:
            best = other
    return _clean_label(best.text) if best is not None else ""


def _label_right_of(lines, rect):
    best = None
    for other in lines:
        if not _same_row(rect[1], rect[3], other.bbox[1], other.bbox[3]):
            continue
        if other.bbox[0] < rect[2] - 2.0:
            continue
        if other.bbox[0] - rect[2] > LABEL_GAP_LEFT:
            continue
        if best is None or other.bbox[0] < best.bbox[0]:
            best = other
    if best is None:
        return ""
    words = _WS.sub(" ", best.text).strip().split(" ")
    return _clean_label(" ".join(words[:4]))


def _label_above(lines, rect):
    best = None
    for other in lines:
        gap = rect[1] - other.bbox[3]
        if gap < -2.0 or gap > LABEL_GAP_ABOVE:
            continue
        overlap = min(rect[2], other.bbox[2]) - max(rect[0], other.bbox[0])
        if overlap < (rect[2] - rect[0]) * 0.25:
            continue
        if best is None or other.bbox[3] > best.bbox[3]:
            best = other
    return _clean_label(best.text) if best is not None else ""


def _label_for_rule(lines, x0, x1, top):
    """A label for a ruled line, and where it came from."""
    band_top, band_bottom = top - DEFAULT_LINE_HEIGHT, top + 2.0
    best = None
    for other in lines:
        if not _same_row(band_top, band_bottom, other.bbox[1], other.bbox[3]):
            continue
        if other.bbox[2] > x0 + 2.0:
            continue
        if x0 - other.bbox[2] > LABEL_GAP_LEFT:
            continue
        if best is None or other.bbox[2] > best.bbox[2]:
            best = other
    if best is not None:
        text = best.text.rstrip()
        return _clean_label(text), ("colon" if text.endswith(":") else "left")
    above = _label_above(lines, (x0, top - DEFAULT_LINE_HEIGHT, x1, top))
    if above:
        return above, "above"
    return "", ""


def _rule_height(lines, top):
    for other in lines:
        if abs(other.bbox[3] - top) < DEFAULT_LINE_HEIGHT:
            height = other.bbox[3] - other.bbox[1]
            return max(MIN_LINE_HEIGHT, min(MAX_LINE_HEIGHT, height))
    return DEFAULT_LINE_HEIGHT


def _something_right_of(lines, line):
    for other in lines:
        if other is line:
            continue
        if not _same_row(line.bbox[1], line.bbox[3], other.bbox[1], other.bbox[3]):
            continue
        if other.bbox[0] >= line.bbox[2] - 2.0:
            return True
    return False


def _box_has_text(lines, rect):
    for line in lines:
        cx = (line.bbox[0] + line.bbox[2]) / 2.0
        cy = (line.bbox[1] + line.bbox[3]) / 2.0
        if rect[0] < cx < rect[2] and rect[1] < cy < rect[3]:
            return True
    return False


def _square(rect):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    side = max(8.0, min(12.0, (y1 - y0) * 0.75))
    return (cx - side / 2.0, cy - side / 2.0, cx + side / 2.0, cy + side / 2.0)


def _clean_label(text):
    out = _WS.sub(" ", str(text or "")).strip()
    out = _LEADING_JUNK.sub("", out)
    out = _LEADING_NUMBER.sub("", out)
    out = _TRAILING_JUNK.sub("", out)
    out = out.strip()
    if len(out) > 60:
        out = out[:60].rsplit(" ", 1)[0].strip()
    return out if _has_letters(out) else ""


def _has_letters(text):
    return any(c.isalnum() for c in str(text or ""))


# ---------------------------------------------------------------- tidying

def _hits_existing(proposal, already):
    """Drop a proposal that sits on a field the form already has."""
    for rect in already:
        if _overlap(proposal.rect, rect) > OVERLAP_LIMIT:
            return True
    return False


def _overlap(a, b):
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    shared = (x1 - x0) * (y1 - y0)
    smallest = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    if smallest <= 0:
        return 0.0
    return shared / smallest


def _dedupe(found):
    """Two sources often see the same blank. Keep the surer one."""
    kept = []
    for proposal in sorted(found, key=lambda p: (-p.confidence, p.rect[1], p.rect[0])):
        clash = False
        for already in kept:
            if _overlap(proposal.rect, already.rect) > OVERLAP_LIMIT:
                if not already.label and proposal.label:
                    already.label = proposal.label
                clash = True
                break
        if not clash:
            kept.append(proposal)
    # "Medicines you take:" with a big box under it is one blank, not two.
    # A colon guess is dropped when a surer source already carries its
    # label, wherever on the page that blank turned out to be.
    solid = set(p.label for p in kept if p.source != "colon" and p.label)
    return [p for p in kept if p.source != "colon" or p.label not in solid]


def _reading_order(pairs):
    """Sort (rect, thing) top to bottom, then left to right, in rows."""
    if not pairs:
        return []
    items = [(fitz.Rect(r), t) for r, t in pairs]
    heights = sorted((r.height for r, _ in items if r.height > 0))
    band = (heights[len(heights) // 2] * 0.6) if heights else 8.0
    band = max(4.0, min(20.0, band))
    items.sort(key=lambda pair: (pair[0].y0, pair[0].x0))
    rows = []
    for rect, thing in items:
        if rows and abs(rect.y0 - rows[-1][0]) <= band:
            rows[-1][1].append((rect, thing))
        else:
            rows.append((rect.y0, [(rect, thing)]))
    out = []
    for _, row in rows:
        row.sort(key=lambda pair: pair[0].x0)
        out.extend(thing for _, thing in row)
    return out


def _name_them(proposals):
    used = set()
    for proposal in proposals:
        proposal.name = _unique(proposal.name or _slug(proposal.label), used)
        used.add(proposal.name)


def _slug(label):
    out = _NAME_BAD.sub("_", str(label or "").lower()).strip("_")
    if len(out) > 40:
        out = out[:40].rstrip("_")
    return out or "field"


def _unique(name, used):
    base = name or "field"
    if base not in used:
        return base
    n = 2
    while "%s_%d" % (base, n) in used:
        n += 1
    return "%s_%d" % (base, n)


# --------------------------------------------------------- widget reading

def _index_widgets(handle, page_of=None):
    """[(field id, [(page number from 0, widget), ...]), ...] in the order
    a Field list is built: page by page, reading order within a page, and
    every button of a radio group folded into one field.

    The one place this order is decided, so that a field id given out by an
    open FormDocument means the same thing to `sign_with_text` working on
    the same file from its own handle.
    """
    if page_of is None:
        def page_of(number):
            return handle[number]
    groups = {}
    order = []
    for number in range(handle.page_count):
        try:
            widgets = list(page_of(number).widgets())
        except Exception:                              # noqa: BLE001
            widgets = []
        for widget in _reading_order([(w.rect, w) for w in widgets]):
            if _kind_of(widget) == KIND_RADIO:
                key = ("radio", number, widget.field_name or "")
            else:
                key = ("one", number, widget.xref)
            if key in groups:
                groups[key].append((number, widget))
                continue
            groups[key] = [(number, widget)]
            order.append(key)
    return [("f%d" % index, groups[key]) for index, key in enumerate(order, start=1)]


def _kind_of(widget):
    kind = widget.field_type
    if kind == fitz.PDF_WIDGET_TYPE_CHECKBOX:
        return KIND_CHECKBOX
    if kind == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
        return KIND_RADIO
    if kind in (fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX):
        return KIND_CHOICE
    if kind == fitz.PDF_WIDGET_TYPE_SIGNATURE:
        return KIND_SIGNATURE
    if kind == fitz.PDF_WIDGET_TYPE_BUTTON:
        return KIND_BUTTON
    if (widget.field_flags or 0) & fitz.PDF_TX_FIELD_IS_MULTILINE:
        return KIND_MULTILINE
    return KIND_TEXT


def _field_from(members, field_id):
    number, first = members[0]
    kind = _kind_of(first)
    flags = first.field_flags or 0
    name = first.field_name or ""
    tooltip = first.field_label or ""
    label = _clean_label(tooltip) or _clean_label(name.replace("_", " ")) or name or field_id
    rect = fitz.Rect(first.rect)
    for _, widget in members[1:]:
        rect = rect | fitz.Rect(widget.rect)
    choices = []
    value = ""
    if kind == KIND_RADIO:
        for _, widget in members:
            state = _on_state(widget)
            if state and state not in choices:
                choices.append(state)
            if _widget_on(widget):
                value = state or ""
    elif kind == KIND_CHECKBOX:
        value = _widget_on(first)
    elif kind == KIND_CHOICE:
        choices = list(first.choice_values or [])
        choices = [c[0] if isinstance(c, (list, tuple)) and c else c for c in choices]
        choices = [str(c) for c in choices]
        raw = first.field_value
        if isinstance(raw, (list, tuple)):
            value = [str(v) for v in raw]
        else:
            value = str(raw or "")
    elif kind == KIND_SIGNATURE:
        value = ""
    else:
        raw = first.field_value
        value = "" if raw is None else str(raw)
    return Field(
        id=field_id,
        name=name,
        label=label,
        kind=kind,
        value=value,
        choices=choices,
        required=bool(flags & fitz.PDF_FIELD_IS_REQUIRED),
        read_only=bool(flags & fitz.PDF_FIELD_IS_READ_ONLY),
        page=number + 1,
        rect=(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
        tooltip=tooltip,
    )


def _on_state(widget):
    try:
        state = widget.on_state()
    except Exception:                                  # noqa: BLE001
        state = None
    return str(state) if state else ""


def _widget_on(widget):
    raw = widget.field_value
    if isinstance(raw, bool):
        return raw
    text = str(raw or "")
    if not text or text.lower() in ("off", "false", "no", "none"):
        return False
    return True


def _truthy(value, widget):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in ("", "off", "no", "false", "0", "none", "unticked", "unchecked"):
        return False
    if text in ("on", "yes", "true", "1", "ticked", "checked", "x"):
        return True
    state = _on_state(widget)
    if state and text == state.lower():
        return True
    return True


def _pdf_name(text):
    """A PDF name, with anything awkward written as #hh, as PDF 1.2 asks."""
    out = ["/"]
    for char in str(text or "Off"):
        code = ord(char)
        if code < 33 or code > 126 or char in "#/%()<>[]{}":
            out.append("#%02X" % (code if code < 256 else 63))
        else:
            out.append(char)
    return "".join(out)


def _match_choice(item, choices):
    for choice in choices:
        if str(choice) == item:
            return str(choice)
    for choice in choices:
        if str(choice).strip().lower() == item.strip().lower():
            return str(choice)
    return None


def _has_structure(handle):
    try:
        return handle.xref_get_key(handle.pdf_catalog(), "StructTreeRoot")[0] != "null"
    except Exception:                                  # noqa: BLE001
        return False


# ---------------------------------------------------------------- writing

def _write_incremental(handle, path):
    """Append the changes to the file, keeping every other byte as it was.

    A copy is kept beside the file until the save is done, so a save that
    goes wrong cannot leave half a PDF behind.
    """
    keep = None
    try:
        folder = os.path.dirname(os.path.abspath(path)) or "."
        handle_fd, keep = tempfile.mkstemp(prefix=".tgimprint-", suffix=".pdf", dir=folder)
        os.close(handle_fd)
        shutil.copyfile(path, keep)
    except Exception:                                  # noqa: BLE001
        keep = None
    try:
        handle.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    except Exception as exc:                           # noqa: BLE001
        if keep:
            try:
                shutil.copyfile(keep, path)
            except Exception:                          # noqa: BLE001
                pass
        _remove(keep)
        return False, MSG_SAVE_FAILED % _reason(exc)
    _remove(keep)
    return True, ""


def _write_whole(handle, target):
    """Write the whole file, through a temporary file and a rename, so the
    file at `target` is never a half written PDF."""
    folder = os.path.dirname(os.path.abspath(target)) or "."
    temp = None
    try:
        os.makedirs(folder, exist_ok=True)
        handle_fd, temp = tempfile.mkstemp(prefix=".tgimprint-", suffix=".pdf", dir=folder)
        os.close(handle_fd)
        handle.save(temp, deflate=True, garbage=3, encryption=fitz.PDF_ENCRYPT_KEEP)
        os.replace(temp, target)
        temp = None
        return True, ""
    except Exception as exc:                           # noqa: BLE001
        _remove(temp)
        return False, MSG_SAVE_FAILED % _reason(exc)


def _remove(path):
    if not path:
        return
    try:
        os.remove(path)
    except Exception:                                  # noqa: BLE001
        pass


def _same_file(a, b):
    if not a or not b:
        return False
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except Exception:                                  # noqa: BLE001
        return False


# ----------------------------------------------------------------- wording

def _reason(exc):
    text = str(exc or "").strip()
    text = _WS.sub(" ", text)
    if not text:
        return "The reason was not given."
    if len(text) > 160:
        text = text[:157].rstrip() + "..."
    if not text.endswith("."):
        text += "."
    return text[0].upper() + text[1:]


def _quote(text):
    out = str(text or "").strip()
    if len(out) > 80:
        out = out[:77].rstrip() + "..."
    return out


def _join(items):
    items = [str(i) for i in items if str(i or "").strip()]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _count(n):
    if n == 0:
        return "none"
    return "one" if n == 1 else str(n)


def _capital(text):
    text = str(text or "")
    return text[:1].upper() + text[1:] if text else text
