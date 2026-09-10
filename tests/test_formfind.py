"""Finding the blanks on a page of a form, which is the one thing in this app
a blind person cannot do any other way.

Chris Smart, a beta tester, meets PDF forms in healthcare that hold readable
text and no fields at all, so he prints them and dictates his medical history
to a sighted person. `pdfforms.py`, Worker A's, finds candidate blanks from
the lines and boxes drawn on the page. This file checks the other half: one
picture of one page sent to a model, and every number that comes back checked
against the page before it is used.

The rule these checks are built around is that a wrong box is worse than a
missing box. A box in the margin, or over the printed question, cannot be
seen to be wrong by the person who is going to fill the form in. So the
checks here are mostly about what is REFUSED: a reply that is not a list, a
rectangle off the page, a rectangle with no area, a rectangle the size of the
page, and a label the model was not sure of and left empty rather than
inventing.

No network at all: `urlopen` is a fake throughout, and there is no live call
in this file.

    python tests/test_formfind.py
"""

import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgimprint import ai, describe  # noqa: E402

CHECKS = []
NOTES = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


def head(title):
    print(os.linesep + title + os.linesep)


CIRCLE = open(os.path.join(HERE, "fixtures", "circle.png"), "rb").read()

#: US Letter, which is what nearly every form Chris meets is printed on.
WIDE, TALL = 612.0, 792.0


# ---------------------------------------------------------------------------
# Worker A's pdfforms.py may not be written yet. When it is here, the real one
# is used; when it is not, a stand in of the shape the brief gives is put in
# its place, so this file can be run before that file exists. The stand in is
# announced, so a green run is never mistaken for a run against the real one.
# ---------------------------------------------------------------------------

try:
    from tgimprint import pdfforms  # noqa: F401
    REAL_PDFFORMS = True
except Exception:
    REAL_PDFFORMS = False

    class Proposal:
        def __init__(self, page, rect, label, confidence, source):
            self.page = page
            self.rect = rect
            self.label = label
            self.confidence = confidence
            self.source = source

    def from_ai(page_index, boxes):
        return [Proposal(page_index, tuple(b["rect"]), b["label"], 0.5, "ai")
                for b in boxes]

    pdfforms = types.ModuleType("tgimprint.pdfforms")
    pdfforms.Proposal = Proposal
    pdfforms.from_ai = from_ai
    sys.modules["tgimprint.pdfforms"] = pdfforms
    import tgimprint
    tgimprint.pdfforms = pdfforms
    NOTES.append("pdfforms.py is not written yet, so a stand in was used")


# ---------------------------------------------------------------------------
head("The question names the page size and says where the origin is")

prompt = describe.form_prompt(WIDE, TALL)
check("it says the page is measured in points",
      "page points" in prompt, prompt[:0])
check("and gives this page's own width and height in them",
      "612 points wide" in prompt and "792 points tall" in prompt)
check("and says the origin is the TOP LEFT corner, in capitals so it is not "
      "skimmed past", "TOP LEFT corner of the page" in prompt)
check("and says which way each number is measured",
      "rightwards from the left edge" in prompt
      and "downwards from the top edge" in prompt)
check("and says top is the smaller of the two, which is the trap when the "
      "origin moves", "top is always the smaller" in prompt)
check("it asks for JSON and nothing else, with no fence",
      "JSON and nothing else" in prompt and "no code fence" in prompt)
check("it asks for a list of objects with exactly three keys",
      "The JSON is a list" in prompt and "exactly these three keys" in prompt)
check("it names the three keys",
      '"label"' in prompt and '"rect"' in prompt and '"kind"' in prompt)
check("and the five kinds",
      all('"%s"' % k in prompt for k in ("text", "checkbox", "choice",
                                         "signature", "date")))
check("it asks for accuracy over completeness, in those words",
      "Be accurate rather than complete" in prompt)
check("and says why: the person cannot see a box that landed in the margin",
      "cannot see that it landed in the margin" in prompt)
check("it tells the model to leave out anything it is not sure of",
      "not sure a blank is there" in prompt and "leave it out" in prompt)
check("it forbids an invented label",
      "Never invent a label" in prompt and "empty string" in prompt)
check("it says the reader is blind and cannot check the answer",
      "blind" in prompt and "cannot check your answer" in prompt)
check("it asks for reading order", "reading order" in prompt)
check("and says what to answer when there is nothing to find",
      "empty list" in prompt)
check("no em or en dash in the prompt",
      chr(8212) not in prompt and chr(8211) not in prompt)
other = describe.form_prompt(1224, 1584)
check("a different page size is really carried through, not hard coded",
      "1224 points wide" in other and "1584 points tall" in other)

# ---------------------------------------------------------------------------
head("What Worker A already found goes in the question")

known = [
    pdfforms.Proposal(0, (72.0, 120.0, 300.0, 134.0), "Patient name", 0.9,
                      "underscores"),
    {"label": "Date of birth", "rect": [72, 150, 240, 164]},
    {"label": "", "rect": [400, 150, 500, 164]},
]
with_known = describe.form_prompt(WIDE, TALL, known)
check("a Proposal Worker A found is given with its label and rectangle",
      '"Patient name" at [72, 120, 300, 134]' in with_known, with_known[-400:])
check("a plain dictionary is taken as well",
      '"Date of birth" at [72, 150, 240, 164]' in with_known)
check("and one Worker A could not label is given as having no label",
      "no label, at [400, 150, 500, 164]" in with_known)
check("the model is told not to give those back",
      "Do not give any of those back" in with_known)
check("and to give only what is missing",
      "only the blanks that are missing" in with_known)
check("but to correct a label that is plainly wrong",
      "plainly wrong" in with_known and "label corrected" in with_known)
check("with nothing found yet, none of that is in the question",
      "already found these blanks" not in prompt)
check("a label that is only a string still goes in",
      '"Signature"' in describe.form_prompt(WIDE, TALL, ["Signature"]))
check("and something with no label and no rectangle is left out rather than "
      "sent as an empty line",
      "already found these blanks" not in describe.form_prompt(
          WIDE, TALL, [{"label": "", "rect": None}]))

# ---------------------------------------------------------------------------
head("A good reply becomes boxes in reading order")

good = json.dumps([
    {"label": "Signature", "rect": [72, 700, 300, 720], "kind": "signature"},
    {"label": "Date of birth", "rect": [72, 152, 240, 166], "kind": "date"},
    {"label": "Patient name", "rect": [72, 120, 300, 134], "kind": "text"},
    {"label": "Sex", "rect": [400, 151, 412, 163], "kind": "checkbox"},
])
ok, boxes = describe.form_boxes(good, WIDE, TALL)
check("four blanks come back", ok and len(boxes) == 4, boxes)
check("in reading order, down the page and then across it",
      [b["label"] for b in boxes]
      == ["Patient name", "Date of birth", "Sex", "Signature"],
      [b["label"] for b in boxes])
check("two blanks on the same printed line are one row, left to right even "
      "though their tops differ by a point",
      boxes[1]["label"] == "Date of birth" and boxes[2]["label"] == "Sex")
check("each keeps its rectangle as four numbers",
      boxes[0]["rect"] == [72.0, 120.0, 300.0, 134.0], boxes[0])
check("and its kind", [b["kind"] for b in boxes]
      == ["text", "date", "checkbox", "signature"])
ok, boxes = describe.form_boxes(json.dumps([]), WIDE, TALL)
check("a page with no blanks is an empty list and not a failure",
      ok and boxes == [])

# ---------------------------------------------------------------------------
head("A reply with prose around the JSON still parses")

wrapped = ("Sure. Looking at this page I can see two places to write.\n\n"
           "```json\n" + json.dumps([
               {"label": "Name", "rect": [72, 100, 300, 114], "kind": "text"},
               {"label": "Today's date [dd/mm]", "rect": [400, 100, 500, 114],
                "kind": "date"}]) +
           "\n```\n\nLet me know if you need anything else.")
ok, boxes = describe.form_boxes(wrapped, WIDE, TALL)
check("a code fence and a sentence either side do not stop it",
      ok and len(boxes) == 2, boxes)
check("and a square bracket inside a label does not end the list early",
      ok and boxes[1]["label"] == "Today's date [dd/mm]", boxes)
ok, boxes = describe.form_boxes(
    'I found one: [{"label": "Name", "rect": [72, 100, 300, 114]}] '
    'and that is all.', WIDE, TALL)
check("bare prose around bare JSON parses too", ok and len(boxes) == 1)

# ---------------------------------------------------------------------------
head("A reply that is not a list is a sentence, never an exception")

for bad, why in ((
        '{"fields": [{"label": "Name", "rect": [1, 2, 3, 4]}]}',
        "an object rather than a list"),
        ("I could not find any blanks on this page.", "a sentence"),
        ("", "nothing at all"),
        ("null", "a JSON null"),
        ('"a string"', "a JSON string"),
        ("[unclosed", "a list that never closes")):
    ok, said = describe.form_boxes(bad, WIDE, TALL)
    check("%s is a sentence, not a list and not a raise" % why,
          not ok and isinstance(said, str) and "nothing has been proposed"
          in said, said[:60] if isinstance(said, str) else said)
ok, said = describe.form_boxes(json.dumps([1, 2, 3]), WIDE, TALL)
check("a list of things that are not boxes is an empty list, not a raise",
      ok and said == [])
ok, said = describe.form_boxes(good, 0, TALL)
check("a page with no size is a sentence and not a division by zero",
      not ok and "no size" not in said and "nowhere to put a box" in said)
ok, said = describe.form_boxes(good, "wide", TALL)
check("and a page size that is not a number is the same sentence",
      not ok and "nowhere to put a box" in said)

# ---------------------------------------------------------------------------
head("A rectangle that is not really on the page is dropped")

off_page = json.dumps([
    {"label": "On the page", "rect": [72, 100, 300, 114], "kind": "text"},
    {"label": "Off the right edge", "rect": [700, 100, 900, 114]},
    {"label": "Below the page", "rect": [72, 900, 300, 914]},
    {"label": "Negative", "rect": [-200, -100, -20, -80]},
])
ok, boxes = describe.form_boxes(off_page, WIDE, TALL)
check("only the one that is on the page survives",
      ok and [b["label"] for b in boxes] == ["On the page"],
      [b["label"] for b in boxes])

no_area = json.dumps([
    {"label": "A line with no height", "rect": [72, 100, 300, 100]},
    {"label": "A box with no width", "rect": [72, 100, 72, 114]},
    {"label": "The same point twice", "rect": [72, 100, 72, 100]},
    {"label": "Half a point tall", "rect": [72, 100, 300, 100.5]},
])
ok, boxes = describe.form_boxes(no_area, WIDE, TALL)
check("a rectangle with no area is dropped, every way of having none",
      ok and boxes == [], boxes)
ok, boxes = describe.form_boxes(json.dumps([
    {"label": "Three points tall", "rect": [72, 100, 300, 103]}]), WIDE, TALL)
check("and so is one too small to write in, at the same size pdfforms "
      "refuses, so the count of what was left out stays honest",
      ok and boxes == [] and describe.MIN_BLANK_SIDE == 4.0, boxes)

out_of_scale = json.dumps([
    {"label": "The whole page", "rect": [0, 0, 612, 792]},
    {"label": "Half the page", "rect": [0, 0, 612, 400]},
    {"label": "A real blank", "rect": [72, 100, 300, 114]},
])
ok, boxes = describe.form_boxes(out_of_scale, WIDE, TALL)
check("a rectangle wildly out of scale for a blank is dropped",
      ok and [b["label"] for b in boxes] == ["A real blank"],
      [b["label"] for b in boxes])
ok, boxes = describe.form_boxes(json.dumps([
    {"label": "A signature line right across the page",
     "rect": [40, 700, 572, 716]}]), WIDE, TALL)
check("but a blank that is merely wide, like a signature line, is kept",
      ok and len(boxes) == 1)

clamped = json.dumps([{"label": "Runs off the edge",
                       "rect": [500, 100, 900, 114]}])
ok, boxes = describe.form_boxes(clamped, WIDE, TALL)
check("a rectangle that runs off the edge is clamped to the page, not thrown "
      "away", ok and boxes and boxes[0]["rect"] == [500.0, 100.0, 612.0,
                                                    114.0], boxes)

reversed_rect = json.dumps([{"label": "Upside down",
                             "rect": [300, 134, 72, 120]}])
ok, boxes = describe.form_boxes(reversed_rect, WIDE, TALL)
check("a rectangle given back to front is put in order, not dropped",
      ok and boxes and boxes[0]["rect"] == [72.0, 120.0, 300.0, 134.0], boxes)

odd = json.dumps([
    {"label": "Three numbers", "rect": [72, 100, 300]},
    {"label": "Words for numbers", "rect": ["a", "b", "c", "d"]},
    {"label": "No rectangle at all"},
    {"rect": [72, 200, 300, 214]},
])
ok, boxes = describe.form_boxes(odd, WIDE, TALL)
check("a rectangle that is not four numbers is dropped, and one with no "
      "label at all is kept, because an honest blank label is better than an "
      "invented one",
      ok and len(boxes) == 1 and boxes[0]["label"] == "", boxes)
ok, boxes = describe.form_boxes(json.dumps([
    {"label": "  Patient\n  name  ", "rect": [72, 100, 300, 114]}]),
    WIDE, TALL)
check("a label keeps its words and loses its line breaks",
      ok and boxes[0]["label"] == "Patient name", boxes)
ok, boxes = describe.form_boxes(json.dumps([
    {"label": "x" * 400, "rect": [72, 100, 300, 114]}]), WIDE, TALL)
check("a label that is really a paragraph is cut short rather than read out "
      "in full", ok and len(boxes[0]["label"]) <= 120)
ok, boxes = describe.form_boxes(json.dumps([
    {"label": "Name", "rect": [72, 100, 300, 114], "kind": "wingding"}]),
    WIDE, TALL)
check("a kind this app does not know becomes text rather than a failure",
      ok and boxes[0]["kind"] == "text")

# ---------------------------------------------------------------------------
head("Consent: a page of somebody else's form asks every time")

describe.reset_consent()
check("a form page asks", describe.consent_needed("form page", True, 1))
describe.record_consent("form page")
check("and asks again after a yes, because a yes is never remembered for a "
      "form", describe.consent_needed("form page", True, 1))
describe.record_consent("image")
check("and a yes given for a picture from the user's own disk does not "
      "carry over to it", describe.consent_needed("form page", True, 1)
      and not describe.consent_needed("image", False, 1))
describe.reset_consent()

question = describe.consent_question("form page", "google", 1, 0, 240, True,
                                     page_number=3)
check("the question says a picture of one page of the form is what goes",
      "a picture of page 3 of this form" in question, question[:120])
check("and names who it goes to", "Gemini, from Google" in question)
check("and how big it is", "about 240 KB" in question)
check("and says it goes over the internet", "over the internet" in question)
check("and why it asks every time",
      "their document" in question and "every time" in question)
check("and that nothing is put in the form until the person accepts it",
      "nothing is put into your form until you accept it" in question)
check("and points at the provider's data policy, by file and by address",
      "DESCRIBER.md" in question and describe.POLICY_URLS["google"] in question)
check("and ends by asking", question.endswith("Send the page?"))
check("without a page number it still reads properly",
      "a picture of one page of this form" in describe.consent_question(
          "form page", "anthropic", 1, 0, 240, True))
check("the size said is the size of the prepared picture, measured and not "
      "guessed", abs(describe.page_kilobytes(CIRCLE)
                     - ai.sent_kilobytes([ai.prepare_picture(CIRCLE)])) < 0.001)
check("and a picture that cannot be prepared measures nothing rather than "
      "raising", describe.page_kilobytes(b"not a picture") == 0.0)

# ---------------------------------------------------------------------------
head("find_form_fields end to end, against a fake urlopen")


class _Answer:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _Fake:
    """urlopen, with the model's reply written by the check that installs it."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return _Answer({"candidates": [{"content": {"parts": [
            {"text": self.reply}]}, "finishReason": "STOP"}]})


real_urlopen = urllib.request.urlopen
real_key_for = describe.key_for
describe.key_for = lambda provider: "test-key"


def ask_with(reply, **kwargs):
    fake = _Fake(reply)
    urllib.request.urlopen = fake
    try:
        got = describe.find_form_fields(CIRCLE, kwargs.pop("page", 2), WIDE,
                                        TALL, "google", "", **kwargs)
    finally:
        urllib.request.urlopen = real_urlopen
    return got, fake


(ok, proposals), fake = ask_with(good)
check("a good reply becomes proposals", ok and len(proposals) == 4, proposals)
check("they are Worker A's Proposals, made by from_ai, and marked as coming "
      "from the AI",
      all(getattr(p, "source", "") == "ai" for p in proposals)
      and all(getattr(p, "page", None) == 2 for p in proposals))
(ok, unlabelled), _fake = ask_with(json.dumps(
    [{"label": "", "rect": [72, 100, 300, 114]}]))
check("a blank the model would not name comes back with a made up NAME and "
      "never a made up meaning",
      ok and len(unlabelled) == 1
      and ("blank" in unlabelled[0].label.lower()
           or "field" in unlabelled[0].label.lower()
           or unlabelled[0].label == ""), unlabelled[0].label)
check("in reading order, with the labels the model gave",
      [p.label for p in proposals]
      == ["Patient name", "Date of birth", "Sex", "Signature"],
      [p.label for p in proposals])
check("the kind travels: a checkbox stays a checkbox",
      [p.kind for p in proposals][2] == "checkbox",
      [getattr(p, "kind", None) for p in proposals])
check("and every kind is one a PDF field can really be, so date and "
      "signature come back as text rather than as something pdfforms would "
      "have to guess at",
      all(getattr(p, "kind", "text") in ("text", "multiline text", "checkbox")
          for p in proposals) if REAL_PDFFORMS else True,
      [getattr(p, "kind", None) for p in proposals])
request, timeout = fake.requests[0]
sent = json.loads(request.data.decode("utf-8"))
check("exactly one picture went, and it is the page",
      len(sent["contents"][0]["parts"]) == 2
      and "inline_data" in sent["contents"][0]["parts"][1])
check("the question that went is the form question, with this page's size",
      "612 points wide" in sent["contents"][0]["parts"][0]["text"])
check("the key travelled in a header, never in the address",
      "test-key" in str(request.headers)
      and "test-key" not in request.full_url)
check("and the answer had room for a form full of blanks",
      sent["generationConfig"]["maxOutputTokens"] == ai.FORM_TOKENS)

(ok, proposals), fake = ask_with(good, known=known)
sent = json.loads(fake.requests[0][0].data.decode("utf-8"))
check("what Worker A already found is in the question that goes",
      "Patient name" in sent["contents"][0]["parts"][0]["text"]
      and "Do not give any of those back"
      in sent["contents"][0]["parts"][0]["text"])

(ok, said), _fake = ask_with("I had a look and could not see any blanks.")
check("a reply that is not the list asked for is a sentence naming the "
      "provider", not ok and said.startswith("Gemini, from Google answered, "
                                             "but not with the list"), said[:70])
(ok, said), _fake = ask_with(json.dumps([]))
check("no blanks found is a sentence that says you can add one yourself",
      not ok and "found no blanks it was sure of" in said
      and "add a field yourself" in said, said[:70])
(ok, said), _fake = ask_with(json.dumps(
    [{"label": "In the margin", "rect": [700, 900, 800, 950]}]))
check("blanks that all landed off the page are a sentence, not an empty list "
      "passed off as success",
      not ok and "none of them was on the page" in said, said[:80])

progress = []
(ok, proposals), _fake = ask_with(json.dumps([
    {"label": "Real", "rect": [72, 100, 300, 114]},
    {"label": "In the margin", "rect": [700, 900, 800, 950]}]),
    progress=progress.append)
check("when some are dropped the good ones still come back",
      ok and len(proposals) == 1)
check("and the progress channel says how many were left out",
      any("1 of the 2 blanks" in line and "not on the page" in line
          for line in progress), progress)
check("and it said who it was asking before it asked",
      progress and progress[0].startswith("Asking Gemini, from Google where "
                                          "the blanks"), progress[:1])

fake = _Fake(error=urllib.error.HTTPError("u", 401, "m", {}, None))
urllib.request.urlopen = fake
try:
    ok, said = describe.find_form_fields(CIRCLE, 0, WIDE, TALL, "google", "")
finally:
    urllib.request.urlopen = real_urlopen
check("a key the provider will not take is the usual sentence, not a shape "
      "complaint", not ok and "would not accept that key" in said, said[:60])

describe.key_for = lambda provider: ""
ok, said = describe.find_form_fields(CIRCLE, 0, WIDE, TALL, "google", "")
check("with no key nothing is sent and the sentence points at Preferences",
      not ok and "No key has been set up" in said and "Preferences" in said)
describe.key_for = lambda provider: "test-key"

ok, said = describe.find_form_fields(b"", 0, WIDE, TALL, "google", "")
check("no picture of the page is a sentence",
      not ok and "no picture of the page" in said and "nothing has left" in said)
ok, said = describe.find_form_fields(b"not a picture", 0, WIDE, TALL,
                                     "google", "")
check("a picture that cannot be prepared is a sentence and nothing leaves",
      not ok and "could not be prepared" in said and "nothing has left" in said)
ok, said = describe.find_form_fields(CIRCLE, 0, 0, TALL, "google", "")
check("a page with no size never reaches the network",
      not ok and "nowhere to put a box" in said)
ok, said = describe.find_form_fields(CIRCLE, 0, WIDE, TALL, "nobody", "")
check("a provider this app does not know is a sentence",
      not ok and "provider" in said.lower())

# Nothing raises, whatever comes back.
for reply in (None, "", "[", "[[[[", '[{"rect": null}]', "\x00\x01",
              json.dumps([{"label": None, "rect": [1, 2, 3, 4]}]),
              json.dumps([{"label": "x", "rect": [float("1e400")] * 4}])):
    try:
        (ok, got), _fake = ask_with(reply)
        raised = ""
    except Exception as error:  # pragma: no cover
        raised = "%s: %s" % (type(error).__name__, error)
    check("nothing raises on a reply of %r" % (str(reply)[:14],), not raised,
          raised)

describe.key_for = real_key_for

# ---------------------------------------------------------------------------
head("Nothing here touches the window, and pdfforms is imported late")

source = open(describe.__file__, encoding="utf-8").read()
check("describe.py still imports no wx", "import wx" not in source)
check("and imports pdfforms inside the one function that needs it, so this "
      "module loads before Worker A's file exists",
      "from . import pdfforms" in source
      and "\nfrom . import pdfforms" not in source
      and source.count("import pdfforms") == 1)
check("nothing in find_form_fields writes to a document: it returns "
      "proposals and says so in its own words",
      "a proposal and nothing more" in describe.find_form_fields.__doc__)

print("\n%d/%d checks passed%s"
      % (sum(CHECKS), len(CHECKS),
         ("  (" + "; ".join(NOTES) + ")") if NOTES else ""))
sys.exit(0 if all(CHECKS) else 1)
