"""PDF forms: filling one in, and putting fields on one that has none.

Every fixture is built here with PyMuPDF and pikepdf, so nothing binary
ships in the tree, and everything written is read back with **pikepdf**,
not only with the library that wrote it.

    python tests/test_forms.py
    python tests/test_forms.py --prove-fail

The medical intake form built in "A flat form, measured" is the one the
numbers in docs/FORMS.md come from.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # noqa: E402
import pikepdf  # noqa: E402

from tgimprint import pdfforms  # noqa: E402

PROVE_FAIL = "--prove-fail" in sys.argv
CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


WORK = tempfile.mkdtemp(prefix="tgimprint forms é ")


def where(name):
    return os.path.join(WORK, name)


# ------------------------------------------------------------- the fixtures

def build_made_form(path):
    """A form with one of everything, the way a real form is put together.

    PyMuPDF cannot write a radio group whose buttons have different export
    values, so the group is built with pikepdf, which is also how every
    real form has one.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Patient name:", fontsize=11)
    page.insert_text((72, 140), "Allergies:", fontsize=11)
    page.insert_text((72, 190), "Diabetic", fontsize=11)
    page.insert_text((72, 230), "Sex", fontsize=11)
    page.insert_text((72, 270), "State", fontsize=11)
    page.insert_text((72, 310), "Record number", fontsize=11)
    page.insert_text((72, 350), "Signature", fontsize=11)
    page.insert_text((72, 400), "Initials", fontsize=11)
    page.add_text_annot(fitz.Point(520, 80), "A note from the clinic")

    def widget(kind, name, label, rect, **rest):
        w = fitz.Widget()
        w.field_type = kind
        w.field_name = name
        w.field_label = label
        w.rect = fitz.Rect(*rect)
        for key, value in rest.items():
            setattr(w, key, value)
        page.add_widget(w)

    widget(fitz.PDF_WIDGET_TYPE_TEXT, "patient_name", "Patient name",
           (170, 88, 400, 106), field_value="",
           field_flags=fitz.PDF_FIELD_IS_REQUIRED)
    widget(fitz.PDF_WIDGET_TYPE_TEXT, "allergies", "Allergies",
           (170, 126, 400, 172), field_value="",
           field_flags=fitz.PDF_TX_FIELD_IS_MULTILINE)
    widget(fitz.PDF_WIDGET_TYPE_CHECKBOX, "diabetic", "Diabetic",
           (170, 178, 184, 192), field_value=False)
    widget(fitz.PDF_WIDGET_TYPE_COMBOBOX, "state", "State",
           (170, 258, 320, 276), choice_values=["Washington", "Oregon", "Idaho"],
           field_value="Washington")
    widget(fitz.PDF_WIDGET_TYPE_TEXT, "record_id", "Record number",
           (170, 298, 320, 316), field_value="MRN-1234",
           field_flags=fitz.PDF_FIELD_IS_READ_ONLY)
    widget(fitz.PDF_WIDGET_TYPE_SIGNATURE, "signature", "Signature",
           (170, 338, 400, 372))
    widget(fitz.PDF_WIDGET_TYPE_TEXT, "initials", "Initials",
           (170, 388, 240, 406), field_value="", text_maxlen=3)
    doc.save(path)
    doc.close()
    _add_radio_group(path, "sex", "Sex", ["Male", "Female"], 170, 218, 792)
    return path


def _add_radio_group(path, name, label, states, x, top, page_height):
    """A proper radio group: one parent field, one kid per button, each
    kid with its own on state in its appearance dictionary.

    `top` is measured from the top of the page, as PyMuPDF reports a
    rectangle; a PDF /Rect is measured from the bottom.
    """
    y = page_height - top - 14
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        parent = pdf.make_indirect(pikepdf.Dictionary(
            FT=pikepdf.Name("/Btn"), T=name, TU=label,
            Ff=pdfforms.fitz.PDF_BTN_FIELD_IS_RADIO, V=pikepdf.Name("/Off")))
        kids = []
        for index, state in enumerate(states):
            on = pdf.make_stream(b"q 0 0 0 rg 3 3 8 8 re f Q")
            off = pdf.make_stream(b"q Q")
            for stream in (on, off):
                stream.Type = pikepdf.Name("/XObject")
                stream.Subtype = pikepdf.Name("/Form")
                stream.BBox = pikepdf.Array([0, 0, 14, 14])
                stream.Resources = pikepdf.Dictionary()
            kid = pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name("/Annot"), Subtype=pikepdf.Name("/Widget"),
                Rect=pikepdf.Array([x + index * 60, y, x + index * 60 + 14, y + 14]),
                F=4, Parent=parent, AS=pikepdf.Name("/Off"),
                AP=pikepdf.Dictionary(N=pikepdf.Dictionary(**{state: on, "Off": off}))))
            kids.append(kid)
        parent.Kids = pikepdf.Array(kids)
        page.Annots = pikepdf.Array(list(page.get("/Annots", [])) + kids)
        fields = list(pdf.Root.AcroForm.get("/Fields", []))
        pdf.Root.AcroForm.Fields = pikepdf.Array(fields + [parent])
        pdf.save(path + ".tmp")
    os.replace(path + ".tmp", path)


def build_flat_form(path):
    """A medical intake form with no fields at all: underscores, ruled
    lines with a colon label, drawn tick boxes, bracket tick boxes, a big
    box for a long answer, and a colon with nothing after it."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 60
    page.insert_text((72, y), "RIVERSIDE FAMILY CLINIC", fontsize=15)
    y += 18
    page.insert_text((72, y), "New Patient Intake Form", fontsize=12)
    y += 8
    page.draw_line(fitz.Point(72, y), fitz.Point(540, y), width=1.0)
    y += 26
    page.insert_text((72, y), "PATIENT INFORMATION", fontsize=11)
    y += 22
    page.insert_text((72, y),
                     "Last name: ______________________   First name: ____________________",
                     fontsize=10)
    y += 22
    page.insert_text((72, y),
                     "Date of birth: ______/______/______     "
                     "Sex:  [ ] Male  [ ] Female  [ ] Other", fontsize=10)
    y += 26
    page.insert_text((72, y), "Street address:", fontsize=10)
    page.draw_line(fitz.Point(150, y + 2), fitz.Point(540, y + 2), width=0.7)
    y += 22
    page.insert_text((72, y), "City:", fontsize=10)
    page.draw_line(fitz.Point(100, y + 2), fitz.Point(300, y + 2), width=0.7)
    page.insert_text((320, y), "State:", fontsize=10)
    page.draw_line(fitz.Point(352, y + 2), fitz.Point(420, y + 2), width=0.7)
    page.insert_text((436, y), "ZIP:", fontsize=10)
    page.draw_line(fitz.Point(460, y + 2), fitz.Point(540, y + 2), width=0.7)
    y += 22
    page.insert_text((72, y), "Home telephone:", fontsize=10)
    page.draw_line(fitz.Point(156, y + 2), fitz.Point(320, y + 2), width=0.7)
    page.insert_text((340, y), "Mobile:", fontsize=10)
    page.draw_line(fitz.Point(380, y + 2), fitz.Point(540, y + 2), width=0.7)
    y += 30
    page.insert_text((72, y), "MEDICAL HISTORY", fontsize=11)
    y += 20
    page.insert_text((92, y), "Have you ever been treated for any of the following?",
                     fontsize=10)
    y += 20
    for row in (["Diabetes", "Asthma", "High blood pressure"],
                ["Heart disease", "Cancer", "Epilepsy"]):
        for index, word in enumerate(row):
            x = 92 + index * 160
            page.draw_rect(fitz.Rect(x, y - 9, x + 10, y + 1), width=0.7)
            page.insert_text((x + 16, y), word, fontsize=10)
        y += 20
    y += 10
    page.insert_text((72, y), "List all medicines you take, with the dose:", fontsize=10)
    y += 8
    page.draw_rect(fitz.Rect(72, y, 540, y + 70), width=0.7)
    y += 84
    page.insert_text((72, y), "Allergies:", fontsize=10)
    y += 22
    page.insert_text((72, y), "Name of your usual pharmacy:", fontsize=10)
    y += 30
    page.insert_text((72, y), "EMERGENCY CONTACT", fontsize=11)
    y += 22
    page.insert_text((72, y), "Name: ______________________________", fontsize=10)
    y += 20
    page.insert_text((72, y), "Relationship to you: ________________", fontsize=10)
    y += 20
    page.insert_text((72, y), "Telephone: __________________________", fontsize=10)
    y += 36
    page.insert_text((72, y), "I confirm that the information above is correct.", fontsize=10)
    y += 30
    page.insert_text((72, y), "Signature:", fontsize=10)
    page.draw_line(fitz.Point(126, y + 2), fitz.Point(380, y + 2), width=0.7)
    page.insert_text((400, y), "Date:", fontsize=10)
    page.draw_line(fitz.Point(430, y + 2), fitz.Point(540, y + 2), width=0.7)
    doc.save(path)
    doc.close()
    return path


def build_blank_page(path):
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(path)
    doc.close()
    return path


def tiny_png(width=48, height=16, rgb=(20, 20, 200)):
    import struct
    import zlib

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I",
                                                                zlib.crc32(body) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def annots_of(path, page=0):
    with pikepdf.open(path) as pdf:
        return [dict(a) for a in pdf.pages[page].get("/Annots", [])]


def value_of(path, name, page=0):
    """A field's value, read back with pikepdf, kid or parent."""
    with pikepdf.open(path) as pdf:
        for annot in pdf.pages[page].get("/Annots", []):
            own = annot.get("/T")
            parent = annot.get("/Parent")
            if own is not None and str(own) == name:
                return annot.get("/V")
            if parent is not None and parent.get("/T") is not None \
                    and str(parent.get("/T")) == name:
                return parent.get("/V")
    return None


MADE = build_made_form(where("made.pdf"))
FLAT = build_flat_form(where("flat.pdf"))
BLANK = build_blank_page(where("blank.pdf"))
DAMAGED = where("damaged.pdf")
open(DAMAGED, "wb").write(b"%PDF-1.7\nthis is not a PDF at all, it is a sentence\n")
NOT_PDF = where("notes.pdf")
open(NOT_PDF, "w", encoding="utf-8").write("Just some text with a .pdf name.\n")


# --------------------------------------------------------- reading a form

print("\nReading a form that already has fields")
doc = pdfforms.open_form(MADE)
check("it opened with no problem", doc.problem == "", doc.problem)
check("it says it has fields", doc.has_fields is True)
check("one page", doc.page_count == 1, doc.page_count)
names = [f.name for f in doc.fields]
check("every field is there once, the two radio buttons as one field",
      names == ["patient_name", "allergies", "diabetic", "sex", "state",
                "record_id", "signature", "initials"], names)
kinds = [f.kind for f in doc.fields]
check("the kinds are read from the file, not guessed",
      kinds == ["text", "multiline text", "checkbox", "radio", "choice",
                "text", "signature", "text"], kinds)
check("fields come back in reading order, top of the page first",
      [round(f.rect[1]) for f in doc.fields] == sorted(round(f.rect[1]) for f in doc.fields),
      [round(f.rect[1]) for f in doc.fields])
by_name = {f.name: f for f in doc.fields}
check("the tooltip is the label a screen reader reads",
      by_name["patient_name"].label == "Patient name"
      and by_name["patient_name"].tooltip == "Patient name")
check("a required field says so", by_name["patient_name"].required is True)
check("a read only field is reported, not left out",
      by_name["record_id"].read_only is True and by_name["record_id"].value == "MRN-1234")
check("the choice list carries its options",
      by_name["state"].choices == ["Washington", "Oregon", "Idaho"], by_name["state"].choices)
check("the radio group carries the names of its buttons",
      by_name["sex"].choices == ["Male", "Female"], by_name["sex"].choices)
check("the radio group's label comes from the parent field",
      by_name["sex"].label == "Sex" and by_name["sex"].page == 1)
check("the radio group's rectangle covers both buttons",
      by_name["sex"].rect[2] - by_name["sex"].rect[0] > 60,
      by_name["sex"].rect)
check("a tick box reads back as a yes or no, not the string Off",
      by_name["diabetic"].value is False)
check("an empty text field is empty and an unfilled one is not counted as filled",
      by_name["patient_name"].value == "" and by_name["patient_name"].is_filled is False)

summary = pdfforms.describe_form(doc)
check("describe_form counts the fields and the pages",
      summary.startswith("This form has 8 fields on one page:"), summary)
check("describe_form names the kinds in plain words",
      "3 text boxes" in summary and "one tick box" in summary
      and "one radio group" in summary and "one signature" in summary, summary)
check("describe_form says how many are filled in",
      "2 filled in, 6 still empty." in summary, summary)
check("describe_form says what cannot be changed",
      summary.endswith("One field cannot be changed."), summary)


# --------------------------------------------------------- filling it in

print("\nFilling it in")
ok, message = doc.set_value("patient_name", "Chris Smart")
check("a text field takes a value", ok and "Chris Smart" in message, message)
ok, message = doc.set_value("allergies", "Penicillin\nLatex")
check("a field for several lines keeps the line breaks",
      ok and doc._find("allergies").value == "Penicillin\nLatex", message)
ok, message = doc.set_value("initials", "CS")
check("a short field takes a short value", ok, message)
ok, message = doc.set_value("initials", "Christopher")
check("a value longer than the field allows is refused, with the numbers",
      (not ok) and "at most 3 characters" in message and "11" in message, message)
ok, message = doc.set_value("diabetic", True)
check("a tick box can be ticked", ok and "is ticked" in message, message)
ok, message = doc.set_value("sex", "Female")
check("a radio group takes one of its own buttons", ok, message)
ok, message = doc.set_value("sex", "Neither")
check("a radio group refuses anything else, and says what it offers",
      (not ok) and "Male and Female" in message, message)
ok, message = doc.set_value("state", "Oregon")
check("a choice list takes one of its options", ok, message)
ok, message = doc.set_value("state", "Bolivia")
check("a choice list refuses anything else, and lists the options",
      (not ok) and "Washington, Oregon and Idaho" in message, message)
ok, message = doc.set_value("record_id", "anything")
check("a read only field is refused in a sentence, not silently ignored",
      (not ok) and "cannot be changed" in message, message)
ok, message = doc.set_value("signature", "Chris Smart")
check("a signature field is refused, and says to use Sign",
      (not ok) and "signature field" in message, message)
ok, message = doc.set_value("no_such_field", "x")
check("an unknown field is refused", (not ok) and message == pdfforms.MSG_NO_FIELD, message)
ok, message = doc.set_value("patient_name", "Chris\nSmart")
check("a line break in a single line field becomes a space, and it says so",
      ok and "line breaks became spaces" in message
      and doc._find("patient_name").value == "Chris Smart", message)
doc.set_value("patient_name", "Chris Smart")

COPY = where("filled copy.pdf")
ok, message = doc.save(COPY)
check("saving a copy says which file it wrote", ok and "filled copy.pdf" in message, message)
doc.close()

print("\nWhat pikepdf finds in the saved copy")
with pikepdf.open(COPY) as pdf:
    acroform = "/AcroForm" in pdf.Root
    tooltips = {}
    for annot in pdf.pages[0].get("/Annots", []):
        holder = annot if annot.get("/T") is not None else annot.get("/Parent")
        if holder is not None and holder.get("/T") is not None:
            tooltips[str(holder.get("/T"))] = holder.get("/TU")
check("the AcroForm survived the save", acroform)
check("every field still carries its /TU, which is what NVDA speaks",
      all(tooltips.get(n) is not None for n in
          ["patient_name", "allergies", "diabetic", "sex", "state", "record_id"]),
      tooltips)
check("the text value is in the file", str(value_of(COPY, "patient_name")) == "Chris Smart")
check("the lines of the multiline value are in the file",
      "Penicillin" in str(value_of(COPY, "allergies"))
      and "Latex" in str(value_of(COPY, "allergies")))
check("the tick box is on", str(value_of(COPY, "diabetic")) == "/Yes")
check("the radio group's parent holds the chosen button, as a PDF name",
      str(value_of(COPY, "sex")) == "/Female", repr(value_of(COPY, "sex")))
check("the choice list holds the chosen option", str(value_of(COPY, "state")) == "Oregon")
check("the read only field still holds what it always held",
      str(value_of(COPY, "record_id")) == "MRN-1234")

copy_doc = fitz.open(COPY)
copy_text = copy_doc[0].get_text()
sticky = [a.info.get("content") for a in copy_doc[0].annots()]
copy_doc.close()
check("the page's own text is untouched by filling the form in",
      all(word in copy_text for word in
          ["Patient name:", "Allergies:", "Diabetic", "Sex", "State", "Signature"]))
check("the note the clinic left on the page is still there",
      "A note from the clinic" in sticky, sticky)
check("the original file was not touched when saving a copy",
      value_of(MADE, "patient_name") is None)


# ------------------------------------------------------------- in place

print("\nSaving in place")
IN_PLACE = where("in place.pdf")
shutil.copyfile(MADE, IN_PLACE)
before = os.path.getsize(IN_PLACE)
before_bytes = open(IN_PLACE, "rb").read()
doc = pdfforms.open_form(IN_PLACE)
ok, message = doc.save()
check("an in place save with nothing changed says so and writes nothing",
      ok and message == pdfforms.MSG_NOTHING_CHANGED
      and open(IN_PLACE, "rb").read() == before_bytes, message)
doc.set_value("patient_name", "Ana Quispe")
ok, message = doc.save()
doc.close()
check("an in place save reports it saved", ok and message == pdfforms.MSG_SAVED, message)
after_bytes = open(IN_PLACE, "rb").read()
check("the save was incremental: the file grew and every original byte is still there",
      len(after_bytes) > before and after_bytes.startswith(before_bytes),
      (before, len(after_bytes)))
check("the value is in the file that was saved in place",
      str(value_of(IN_PLACE, "patient_name")) == "Ana Quispe")
check("no temporary file was left behind",
      not any(n.startswith(".tgimprint-") for n in os.listdir(WORK)), os.listdir(WORK))


# ------------------------------------------------------------- flattening

print("\nFlattening")
FLATTENED = where("flattened.pdf")
doc = pdfforms.open_form(COPY)
ok, message = doc.save(FLATTENED, flatten=True)
check("flattening says what it did and what it cost",
      ok and "printed onto the page" in message and "nobody can correct it" in message, message)
check("the open document knows it is flattened now",
      doc.flattened is True and doc.has_fields is False)
ok, message = doc.set_value("patient_name", "too late")
check("nothing can be filled in after flattening, and it says why",
      (not ok) and "nothing left to fill in" in message, message)
doc.close()
flat_doc = fitz.open(FLATTENED)
flat_widgets = len(list(flat_doc[0].widgets()))
flat_text = flat_doc[0].get_text()
flat_doc.close()
with pikepdf.open(FLATTENED) as pdf:
    still_form = "/AcroForm" in pdf.Root
check("no widgets are left", flat_widgets == 0, flat_widgets)
check("no AcroForm is left", still_form is False)
check("the value is baked into the page text", "Chris Smart" in flat_text, flat_text[:80])
check("the page's own text is still there too", "Patient name:" in flat_text)


# ------------------------------------------------------------- signatures

print("\nSignatures, which are a typed name or a picture and nothing more")
SIGNED = where("signed.pdf")
ok, message = pdfforms.sign_with_text(COPY, "signature", "Chris Smart", SIGNED)
check("signing with a name says plainly it is not a digital signature",
      ok and "not a digital signature" in message, message)
signed_doc = fitz.open(SIGNED)
signed_page = signed_doc[0]
signed_words = [w for w in signed_page.get_text("words")
                if w[4] in ("Chris", "Smart") and 336 < w[1] < 374]
sig_widgets = [w.field_name for w in signed_page.widgets()]
signed_doc.close()
check("the name is drawn inside the signature rectangle",
      len(signed_words) == 2 and all(168 < w[0] < 400 and 336 < w[1] < 374
                                     for w in signed_words), signed_words)
check("the empty signature field is gone, so the file claims no signature it does not have",
      "signature" not in sig_widgets, sig_widgets)

SIGNED_IMAGE = where("signed image.pdf")
ok, message = pdfforms.sign_with_image(COPY, "signature", tiny_png(), SIGNED_IMAGE)
check("signing with a picture says plainly it is not a digital signature",
      ok and "not a digital signature" in message, message)
image_doc = fitz.open(SIGNED_IMAGE)
image_page = image_doc[0]
boxes = [image_page.get_image_bbox(i) for i in image_page.get_images(full=True)]
image_doc.close()
check("the picture lands inside the rectangle it was given",
      len(boxes) == 1 and fitz.Rect(170, 338, 400, 372).contains(boxes[0]), boxes)
ok, message = pdfforms.sign_with_image(COPY, "signature", b"not a picture at all",
                                       where("bad.pdf"))
check("a file that is not a picture is refused in a sentence",
      (not ok) and "not a picture" in message, message)
ok, message = pdfforms.sign_with_text(COPY, "signature", "   ", where("bad2.pdf"))
check("an empty name is refused", (not ok) and message == pdfforms.MSG_SIGN_EMPTY, message)
with pdfforms.open_form(COPY) as held:
    sig_id = [f.id for f in held.fields if f.kind == "signature"][0]
ok, message = pdfforms.sign_with_text(COPY, sig_id, "Chris Smart", where("signed by id.pdf"))
check("the field id the dialog hands over lands on the same field as its name",
      ok and "Signature" in message, (sig_id, message))
ok, message = pdfforms.sign_with_text(COPY, "no_such_field", "Chris", where("bad3.pdf"))
check("signing somewhere that does not exist is refused",
      (not ok) and message == pdfforms.MSG_SIGN_NO_TARGET, message)
ok, message = pdfforms.sign_with_text(COPY, (1, 72, 700, 300, 722), "Chris Smart",
                                      where("signed rect.pdf"))
check("a page and a rectangle can be signed instead of a field", ok, message)
rect_doc = fitz.open(where("signed rect.pdf"))
rect_words = [w for w in rect_doc[0].get_text("words") if w[4] == "Smart" and w[1] > 690]
rect_doc.close()
check("the name went where the rectangle said", len(rect_words) == 1, rect_words)
ok, message = pdfforms.sign_with_text(COPY, (1, 72, 700, 82, 706),
                                      "A signature far too long for that space",
                                      where("bad4.pdf"))
check("a signature that will not fit is refused rather than drawn over the page",
      (not ok) and message == pdfforms.MSG_SIGN_NO_ROOM, message)


# ------------------------------------------------------ a form with none

print("\nA flat form, measured")
flat = pdfforms.open_form(FLAT)
check("a form with no fields opens with no problem", flat.problem == "", flat.problem)
check("it says it has no fields", flat.has_fields is False)
check("describe_form offers to put fields on it",
      pdfforms.describe_form(flat) == pdfforms.MSG_NO_FIELDS)
flat.close()

before_flat = open(FLAT, "rb").read()
proposals = pdfforms.propose_fields(FLAT)
check("proposing changes nothing in the file at all",
      open(FLAT, "rb").read() == before_flat)
labels = [p.label for p in proposals]
sources = {}
for p in proposals:
    sources[p.source] = sources.get(p.source, 0) + 1
check("every blank on the intake form is found and nothing else is",
      len(proposals) == 28, len(proposals))
check("all four sources are used",
      sources.get("underscores") == 8 and sources.get("line") == 8
      and sources.get("box") == 10 and sources.get("colon") == 2, sources)
check("a blank after a label on the same line is labelled from that label",
      labels[:2] == ["Last name", "First name"], labels[:2])
check("a second blank on a line does not take the whole line as its label",
      "Last name: ______________________ First name" not in labels)
check("a ruled line with a colon label to its left is found",
      "Street address" in labels and "City" in labels and "ZIP" in labels)
check("bracket tick boxes beside a word are found as tick boxes",
      [p.kind for p in proposals if p.label in ("Male", "Female", "Other")]
      == ["checkbox"] * 3)
check("drawn square tick boxes beside a word are found as tick boxes",
      [p.kind for p in proposals if p.label in ("Diabetes", "Cancer", "Epilepsy")]
      == ["checkbox"] * 3)
check("a big empty box under its label is a box for several lines",
      [p.kind for p in proposals if p.label.startswith("List all medicines")]
      == ["multiline text"])
check("a colon with nothing after it is found, and is the least sure of them",
      "Allergies" in labels
      and [p.confidence for p in proposals if p.label == "Allergies"] == [0.5], labels)
check("the underline of the heading is not proposed as somewhere to write",
      not any("RIVERSIDE" in lab for lab in labels), labels)
check("proposals come back in reading order",
      [round(p.rect[1]) for p in proposals]
      == sorted(round(p.rect[1]) for p in proposals))
check("every proposal has a field name and no two are the same",
      all(p.name for p in proposals) and len(set(p.name for p in proposals)) == len(proposals))
check("the surest source is a run of underscores",
      max(p.confidence for p in proposals) == 0.9)
check("one page can be asked for on its own",
      len(pdfforms.propose_fields(FLAT, page=1)) == 28
      and pdfforms.propose_fields(FLAT, page=2) == [])
check("a page with nothing on it proposes nothing", pdfforms.propose_fields(BLANK) == [])


# ------------------------------------------------------- putting them on

print("\nPutting fields on a form that has none")
ADDED = where("intake with fields.pdf")
ok, message, added = pdfforms.add_fields(FLAT, proposals, ADDED)
check("it says how many it added, and to check them",
      ok and added == 28 and "Added 28 fields" in message
      and "it can be wrong" in message, message)
with pikepdf.open(ADDED) as pdf:
    annots = list(pdf.pages[0].get("/Annots", []))
    added_tooltips = [str(a.get("/TU")) for a in annots if a.get("/TU") is not None]
    added_names = [str(a.get("/T")) for a in annots if a.get("/T") is not None]
    borders = [a.get("/BS", {}).get("/W") for a in annots]
    tabs = pdf.pages[0].get("/Tabs")
    has_acroform = "/AcroForm" in pdf.Root
check("pikepdf finds an AcroForm where there was none", has_acroform)
check("pikepdf finds every field", len(added_names) == 28, len(added_names))
check("every field carries a /TU, so NVDA has something to say",
      len(added_tooltips) == 28, len(added_tooltips))
check("the /TU strings are the labels read off the page",
      "Last name" in added_tooltips and "Street address" in added_tooltips
      and "Diabetes" in added_tooltips, added_tooltips[:4])
check("no two fields have the same name", len(set(added_names)) == 28, len(set(added_names)))
check("no field draws a border, so the page still looks exactly as it did",
      all(int(w or 0) == 0 for w in borders), borders)
check("the page carries a /Tabs so tabbing follows the page, as PDF/UA asks",
      str(tabs) == "/R", tabs)

added_doc = fitz.open(ADDED)
added_text = added_doc[0].get_text()
added_kinds = sorted(set(w.field_type_string for w in added_doc[0].widgets()))
added_doc.close()
original_doc = fitz.open(FLAT)
original_text = original_doc[0].get_text()
original_doc.close()
check("every word of the original page is still on it",
      all(line in added_text for line in original_text.split("\n") if line.strip()))
check("tick boxes were written as tick boxes and the rest as text",
      added_kinds == ["CheckBox", "Text"], added_kinds)

filled = pdfforms.open_form(ADDED)
check("the form we just made opens with all its fields",
      filled.has_fields and len(filled.fields) == 28, len(filled.fields))
check("its labels are the ones a screen reader will read",
      filled.fields[0].label == "Last name" and filled.fields[1].label == "First name")
ok, message = filled.set_value(filled.fields[0].id, "Smart")
check("the field we made takes a value", ok, message)
tick = [f for f in filled.fields if f.label == "Diabetes"][0]
ok, message = filled.set_value(tick.id, True)
check("the tick box we made can be ticked", ok, message)
FILLED_FLAT = where("intake filled.pdf")
ok, message = filled.save(FILLED_FLAT, flatten=True)
filled.close()
check("the form we made can be filled in and flattened", ok, message)
done = fitz.open(FILLED_FLAT)
done_text = done[0].get_text()
done.close()
check("what was typed into the field we made is printed on the page",
      "Smart" in done_text, done_text[:60])

again = pdfforms.propose_fields(ADDED)
check("a blank that is already a field is not proposed all over again",
      len(again) <= 2, [(p.label, p.source) for p in again])

class StandIn:
    """What the dialog builds when somebody renames a proposal, without
    the kind or the name. Adding must still work, and the kind must not
    quietly turn a tick box into a text box."""

    def __init__(self, proposal, label):
        for attribute in ("page", "rect", "confidence", "source", "kind"):
            setattr(self, attribute, getattr(proposal, attribute, None))
        self.label = label


tick = [p for p in proposals if p.kind == "checkbox"][0]
renamed = [StandIn(tick, "Do you have diabetes")]
ok, message, added = pdfforms.add_fields(FLAT, renamed, where("renamed.pdf"))
check("a renamed proposal from the dialog still becomes a field",
      ok and added == 1, (ok, message, added))
with pikepdf.open(where("renamed.pdf")) as pdf:
    annot = pdf.pages[0]["/Annots"][0]
    renamed_tu = str(annot.get("/TU"))
    renamed_ft = str(annot.get("/FT"))
check("the new label is the one a screen reader will read",
      renamed_tu == "Do you have diabetes", renamed_tu)
check("and it is still a tick box", renamed_ft == "/Btn", renamed_ft)
ok, message, added = pdfforms.add_fields(
    FLAT, [{"page": 1, "rect": [72, 100, 300, 118], "label": "From a dictionary"}],
    where("from dict.pdf"))
check("a plain dictionary works as a proposal too", ok and added == 1, message)
check("confidence_word turns a number into a word for the dialog",
      [pdfforms.confidence_word(v) for v in (0.9, 0.6, 0.35, None)]
      == ["high", "medium", "low", "low"])

ok, message, added = pdfforms.add_fields(FLAT, [], where("nothing.pdf"))
check("adding nothing is refused with a sentence",
      (not ok) and added == 0 and message == pdfforms.MSG_NO_PROPOSALS, message)


print("\nMore than one page")
TWO = where("two pages.pdf")
two_doc = fitz.open()
for number in range(2):
    page = two_doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Page %d" % (number + 1), fontsize=11)
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_name = "note_%d" % (number + 1)
    w.field_label = "Note on page %d" % (number + 1)
    w.field_value = ""
    w.rect = fitz.Rect(170, 88, 400, 106)
    page.add_widget(w)
two_doc.save(TWO)
two_doc.close()
two = pdfforms.open_form(TWO)
check("fields on later pages are found and numbered from one",
      [f.page for f in two.fields] == [1, 2], [f.page for f in two.fields])
ok, message = two.set_value("note_2", "written on the second page")
check("a field on the second page can be filled in", ok, message)
two.save()
two.close()
check("and it is in the file",
      str(value_of(TWO, "note_2", 1)) == "written on the second page")
check("describe_form counts the pages",
      "on 2 pages" in pdfforms.describe_form(pdfforms.open_form(TWO)),
      pdfforms.describe_form(pdfforms.open_form(TWO)))


# -------------------------------------------------------------- the AI path

print("\nThe path an AI can be wired into later")
boxes = [{"label": "Home telephone", "rect": [150, 200, 350, 218]},
         {"label": "Consent given", "rect": [72, 300, 86, 314], "kind": "checkbox",
          "confidence": 0.4},
         {"label": "no rectangle"},
         {"rect": [1, 2, 3]},
         {"rect": [10, 10, 11, 11], "label": "far too small"},
         "not a dict at all",
         {"label": "Notes", "rect": [72, 400, 540, 470], "kind": "multiline text"}]
ai = pdfforms.from_ai(1, boxes)
check("from_ai keeps the boxes it can use and drops the rest", len(ai) == 3, len(ai))
check("everything from an AI is marked as coming from an AI",
      all(p.source == "ai" for p in ai))
check("an AI's own confidence is kept when it gives one",
      [p.confidence for p in ai] == [0.7, 0.4, 0.7], [p.confidence for p in ai])
check("the kinds an AI asks for are honoured",
      [p.kind for p in ai] == ["text", "checkbox", "multiline text"], [p.kind for p in ai])
check("from_ai never raises, whatever it is handed",
      pdfforms.from_ai(1, None) == [] and pdfforms.from_ai("x", boxes) == []
      and pdfforms.from_ai(1, "rubbish") == [])
ai_added = pdfforms.add_fields(FLAT, ai, where("ai fields.pdf"))
check("an AI's proposals go on a page like any other", ai_added[0] and ai_added[2] == 3,
      ai_added)

image = pdfforms.render_page_png(FLAT, 1, dpi=72)
check("a page renders to a PNG for an AI to look at",
      image.png_bytes[:8] == b"\x89PNG\r\n\x1a\n" and image.problem == "",
      len(image.png_bytes))
check("the render says how big the page is in points, so boxes can come back in points",
      round(image.width_points) == 612 and round(image.height_points) == 792,
      (image.width_points, image.height_points))
check("a page that is not there is refused in a sentence",
      pdfforms.render_page_png(FLAT, 9).problem == pdfforms.MSG_NO_PAGE % 9)


def ask_nothing(png, width, height, page):
    return [{"label": "From a model", "rect": [72, 100, 300, 118]}]


got, said = pdfforms.ai_proposals(FLAT, 1, ask_nothing, dpi=72)
check("ai_proposals renders the page and hands what comes back through from_ai",
      len(got) == 1 and got[0].source == "ai" and got[0].name == "from_a_model" and said == "",
      (got, said))


def ask_badly(png, width, height, page):
    raise RuntimeError("the network fell over")


got, said = pdfforms.ai_proposals(FLAT, 1, ask_badly, dpi=72)
check("a provider that fails gives a sentence, not an exception",
      got == [] and "network fell over" in said, said)


# ------------------------------------------------------- when it goes wrong

print("\nWhen the file is wrong")
bad = pdfforms.open_form(DAMAGED)
check("a damaged file gives a sentence and does not raise",
      bad.problem != "" and bad.problem.endswith(".") and bad.has_fields is False,
      bad.problem)
bad.close()
missing = pdfforms.open_form(where("there is no such file.pdf"))
check("a missing file gives the missing file sentence",
      missing.problem == pdfforms.MSG_NO_FILE, missing.problem)
empty = pdfforms.open_form("")
check("no path at all gives the same sentence", empty.problem == pdfforms.MSG_NO_FILE)
not_pdf = pdfforms.open_form(NOT_PDF)
check("a file that is not a PDF gives a sentence", not_pdf.problem != "", not_pdf.problem)
check("describe_form on a broken file repeats the problem",
      pdfforms.describe_form(bad) == bad.problem)
check("a broken file proposes nothing rather than raising",
      pdfforms.propose_fields(DAMAGED) == [])
check("adding fields to a file that is not there is refused",
      pdfforms.add_fields(where("nope.pdf"), proposals)[1] == pdfforms.MSG_NO_FILE)
closed = pdfforms.open_form(MADE)
closed.close()
ok, message = closed.set_value("patient_name", "x")
check("a closed form says it is closed", (not ok) and message == pdfforms.MSG_CLOSED, message)
ok, message = closed.save()
check("a closed form cannot be saved", (not ok) and message == pdfforms.MSG_CLOSED, message)
closed.close()
check("closing twice is harmless and the form knows it is shut",
      closed.is_open is False)

with pdfforms.open_form(MADE) as held:
    check("a form can be used as a context manager", held.has_fields)
SENTENCES = [getattr(pdfforms, n) for n in dir(pdfforms)
             if n.split("_")[0] in ("MSG", "DESC", "LABEL")
             and isinstance(getattr(pdfforms, n), str)]
check("there are sentences to check", len(SENTENCES) > 25, len(SENTENCES))
check("no sentence anywhere has an em or an en dash",
      not any(ch in text for text in SENTENCES for ch in (chr(8212), chr(8211))))
check("every sentence ends like a sentence",
      all(text.rstrip().endswith((".", "?")) or "%" in text for text in SENTENCES),
      [t for t in SENTENCES if not (t.rstrip().endswith((".", "?")) or "%" in t)])


# --------------------------------------------------------------------------

print("\nThe proof that a check can fail")
if PROVE_FAIL:
    check("(deliberate) the intake form has no blanks at all", len(proposals) == 0)
else:
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--prove-fail"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("run with --prove-fail, this file exits 1 and prints FAIL",
          proc.returncode == 1 and "FAIL (deliberate)" in proc.stdout, proc.returncode)

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
