# PDF forms in TG Imprint

Two beta testers asked for this, and they asked for two different things.

HarmonicaPlayer wanted the ordinary one: open a PDF that already has
editable fields, fill them in, save it.

Chris Smart wanted the hard one. "What I keep running into are PDF forms
that contain readable text, but do not contain edit fields or other
controls which would allow me to fill in the form myself. Could an app
take a form like that, add the relevant controls, let me fill things in,
and save the result, keeping the visual formatting the same? I keep
running into this in healthcare, where I still have to print things out,
find a sighted person to dictate my medical history to."

`tgimprint/pdfforms.py` does both. This file says what it can do, what it
is guessing at, and what to check before a filled form goes anywhere.

## The one rule the whole feature is built on

**Forms work edits the original PDF. It never goes through Open.**

Opening a PDF in TG Imprint rebuilds it as an editable document, which
throws the page layout away and re-creates it. That is right for making a
document accessible and completely wrong here: Chris asked for the visual
formatting to be kept, and a medical form has to still look like that
clinic's form when it comes back.

So a form is opened as a form. The pages, the text, the drawings, the
other annotations and the fonts are left exactly where they were, and only
the form fields are touched. Saving over the original file is done
incrementally: the changes are appended and every byte that was already
there stays there, byte for byte. The tests check that.

## Filling in a form that already has fields

Every kind of field a PDF can hold is read:

| What you meet | What it is called here |
|---|---|
| A box to type in | text |
| A box for several lines | multiline text |
| A tick box | checkbox |
| A group of buttons where only one can be on | radio |
| A list or a drop down | choice |
| A place to sign | signature |
| A button that does something | button |

For each one TG Imprint knows its label (the /TU tooltip, which is the
string a screen reader reads out), its value, whether it is required,
whether it is locked, which page it is on and where on that page. Fields
come back in reading order, top of the page first and left to right along
a row, not in whatever order they happen to sit in the file.

A radio group is one field, not one field per button, which is how it
sounds to a screen reader and how you think about it. Its options are the
names its buttons export.

**A locked field says so.** Some forms lock a reference number or a date
the clinic filled in already. Trying to change one gets you a sentence
saying it cannot be changed and who locked it, never silence. This matters
more than it sounds: PyMuPDF will happily write to a read only field
without complaining, so the rule is enforced by TG Imprint itself.

A value that does not fit is refused with the numbers ("Initials holds at
most 3 characters and that is 11"). A choice that is not on the list is
refused with the list. A line break typed into a single line field becomes
a space, and it tells you it did.

### Saving

- **Save** writes over the original, incrementally.
- **Save a copy** writes a new file and leaves the original alone.
- **Save flattened** prints the answers onto the page and takes the fields
  away. Use it when you are sending a form somewhere and do not want it
  changed on the way. It cannot be undone: the message says so, in those
  words, because nobody can correct a mistake in a flattened form either.

## Finding the blanks on a form that has none

This is the half that is guessing, and it says so everywhere it can.

TG Imprint looks at the page and works out where somebody would write.
Five things give a blank away, and they are not equally reliable, so every
proposal carries a confidence between 0 and 1:

| What it saw | Called | How sure |
|---|---|---|
| Three or more underscores in a row | underscores | 0.90 |
| A ruled line with a label ending in a colon to its left | line | 0.80 |
| A pair of brackets beside a word, like `[ ] Diabetic` | box | 0.80 |
| A small drawn square beside a word | box | 0.75 |
| A cell of a ruled table with nothing in it | box | 0.60 |
| A ruled line with a label above it | line | 0.62 |
| A drawn rectangle with nothing in it | box | 0.58 |
| A label and a colon with nothing after it to the end of the line | colon | 0.50 |
| A ruled line with no label at all | line | 0.35 |

A blank with no label anywhere near it is still offered, named "Blank 3 on
page 2", so you can give it a name yourself rather than never being told
it was there.

The label comes from the nearest text: before the blank on the same line,
then to its left, then after it on the same line (some forms label from
the right: `________ Printed name`), then above it. A tick box takes the
word to its right, because that is the convention everywhere.

**Nothing is written to the file while it is looking.** Proposing and
adding are two separate steps on purpose, so you can read the list, change
the labels, throw out the ones that are wrong, and only then commit.

### What is added

Each field you accept becomes a real AcroForm field with:

- its label as the /TU tooltip, which is what NVDA speaks when you tab
  into it,
- a field name made from the label, made unique,
- **no border and no background**, so the page looks exactly as it did.
  The line or the underscores or the box are already drawn on the page;
  drawing another one over them would change the form's appearance, which
  is the one thing Chris asked us not to do,
- text that sizes itself to the box, so a long answer still fits,
- the fields added in reading order, and the page marked so that tabbing
  through them follows the page rather than the file.

## Measured, on a form built to look like a real one

`tests/test_forms.py` builds a one page new patient intake form for the
Riverside Family Clinic: a heading with a rule under it, underscore blanks
two to a line, a date split into three, bracket tick boxes for sex, ruled
lines with colon labels for the address and the telephone numbers, six
drawn tick boxes for conditions, a large empty box for a list of
medicines, two labels with a colon and nothing after them, three more
underscore blanks for the emergency contact, and a signature and date on
ruled lines.

**A person filling that in by hand would use 28 blanks. TG Imprint finds
28, and proposes nothing that is not one.** It takes about 25
milliseconds, and adding all 28 fields takes about 20 more.

The two things it got wrong in the first pass and now gets right, both
worth knowing because they say what it is doing:

- "Last name: \_\_\_\_ First name: \_\_\_\_" gave the second blank the
  whole line as its label. It now cuts at the last run of underscores, so
  the second blank is "First name".
- The rule under the clinic's name was offered as somewhere to write. A
  rule whose only label is above it, and which runs most of the way across
  the page, is now taken to be the underline of a heading.

A date split into three boxes gets the label "Date of birth" three times.
That is deliberate: it is honest, and it is more use than "Blank 2".

## Where it fails

Measured on a page built to break it:

- **Dotted leaders are missed.** "Name . . . . . . . . ." is a blank to a
  sighted reader and nothing at all to this code. Only underscores are
  recognised as a written line.
- **A round tick box is missed.** A circle is drawn as curves, and only
  straight sided rectangles are recognised. A form using circles for its
  tick boxes gives you nothing there.
- **A scanned form gives nothing**, and nothing can be done about that
  here. If the page is a photograph of a form there is no text to read a
  label from and no drawing to find a line in. There is no text
  recognition in this release.
- **A shaded box with no border is found, but so is a decorative shaded
  band.** Anything that looks like an empty rectangle is offered.
- **A ruled table gives one field per empty cell**, labelled from the
  column heading. A table that is a table of printed information, rather
  than one to fill in, has text in its cells and is left alone, but a
  half filled one will be offered in part.
- **Sideways text is skipped entirely**, labels and blanks both.
- **Nothing understands the form.** It does not know that a telephone
  number is a telephone number, that two blanks are the same question
  asked twice, or that a section does not apply to you.

That last one is why the AI path exists.

## Asking an AI where the blanks are

There is a second, optional way in: render the page as a picture and ask
Claude, ChatGPT or Gemini to point at the blanks. It is a separate path on
purpose. The page rendering and the checking of what comes back live in
`pdfforms`; the provider, the key, the consent question and the prompt
belong to the describer, and nothing here ever calls out on its own.

An AI's answer is a list of boxes, each with a label and a rectangle in
page points measured from the top left of the page, and optionally a kind
and a confidence. Anything malformed is dropped rather than trusted.
Everything that survives is marked as having come from an AI, so the list
you read can say so.

Nothing leaves the machine unless you say it can, and the consent question
names the provider. That rule is the same here as it is everywhere else in
TG Imprint.

## Signatures: what this is, and what it is not

A signature here is **a typed name in a script face, or a picture of your
signature**, drawn onto the page where the form asks you to sign.

That is what most forms actually want and what most organisations
actually accept: a mark that says you read it and you agree.

**It is not a digital signature.** There is no certificate, no key, no
timestamp, and nothing in the file that proves the document has not been
changed since you signed it. A verifier will not show a green tick, and it
should not. Every message TG Imprint gives you when you sign says this in
plain words, so nobody is ever left thinking they have something they do
not have.

If the form has an empty signature field, TG Imprint draws your name or
your picture in it and then **removes the empty field**, so that nothing
left in the file claims a digital signature that is not there.

If you need a real digital signature, that is a different job and a
different tool: your certificate provider, or Acrobat, or your
government's own signing service.

## Before you send a filled form anywhere

1. **Read it back.** Open the saved file again and go through the fields.
   What you typed is what is in the file, and reading it back is the only
   way to know.
2. **Check the labels on any field TG Imprint added.** It worked them out
   by looking at the page. "Name" might be the patient's name or the
   emergency contact's name, and only you can tell which.
3. **Check the fields it did not add.** A dotted line, a circle, a
   shaded panel or a scanned page will have been missed. Look at the
   count: 28 blanks proposed on a page you know has 30 means two are
   somewhere you have not been told about.
4. **Flatten it if it must not change**, and keep the unflattened copy for
   yourself, because a flattened form cannot be corrected.
5. **Remember what is in it.** A filled medical form holds your medical
   history. Where it goes and how it gets there is worth a moment's
   thought before you attach it to an email.

## Tagging, and PDF/UA

A form field ought to be tagged as a Form element in the structure tree
and carry a /TU. TG Imprint writes the /TU on every field it adds, which
is the half that a screen reader actually uses, and does not add structure
tree entries, because a flat form has no structure tree to add them to.
`docs/PDF-UA.md` says what that means for a claim of conformance.

## For the record: the interface

```python
open_form(path) -> FormDocument            # never raises; carries .problem
FormDocument: fields, has_fields, page_count, path, problem, dirty,
              flattened, is_open,
              set_value(field_id, value) -> (ok, message)
              save(out_path=None, flatten=False) -> (ok, message)
              close()                      # also a context manager
Field: id, name, label, kind, value, choices, required, read_only,
       page, rect, tooltip, is_filled
propose_fields(source, page=None) -> list[Proposal]
Proposal: page, rect, label, confidence, source, kind, name
add_fields(path, proposals, out_path=None) -> (ok, message, added)
sign_with_text(path, field_or_rect, name, out_path=None) -> (ok, message)
sign_with_image(path, field_or_rect, image_bytes, out_path=None) -> (ok, message)
describe_form(doc) -> str
render_page_png(path, page_index, dpi=150) -> PageImage
ai_proposals(source, page_index, ask, dpi=150) -> (list[Proposal], str)
from_ai(page_index, boxes) -> list[Proposal]
confidence_word(value) -> "high" | "medium" | "low"
```

`add_fields` takes anything that carries a page, a rectangle and a label:
a Proposal, a plain dictionary, or the stand in object the dialog builds
when somebody renames one. A rename must never be the thing that makes a
field disappear.

`set_value` and `sign_with_text` both take a Field id or a field name, so
the dialog can hand over `field.id` and a script can hand over the name
the form's author chose.

Page numbers are 1 based throughout, as they are in `pdfimport` and as a
person says them. Rectangles are `(x0, y0, x1, y1)` in page points with
the origin at the top left of the page, which is what PyMuPDF reports and
not what a raw PDF /Rect holds.

Nothing here touches wx, nothing prints, and no public function raises:
everything that can go wrong comes back as a sentence, a `.problem`, or an
empty list. All of it is safe on a worker thread, one thread per open
form.

`python tests/test_forms.py` is the proof, 140 checks, every fixture built
inside the test and every result read back with pikepdf as well as with
the library that wrote it.
