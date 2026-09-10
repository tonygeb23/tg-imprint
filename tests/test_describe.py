"""The describer: what is asked, what leaves, and the dialogs it lives in.

Consent follows provenance, the outline lists the headings, the prompts
carry the context, the picture cap holds, and the three widgets can be
built and driven under a wx.App with no network at all. The one live
check at the end sends tests/fixtures/circle.png to Gemini on Tony's Drop
Deck key, if it is on this machine, and reports how long it took; without
the key it is skipped, and says so.

    python tests/test_describe.py
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgimprint import ai, describe, secrets  # noqa: E402

CHECKS = []
SKIPPED = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


def skip(label, why):
    SKIPPED.append(label)
    print("  skip " + label + "  " + why)


def head(title):
    print(os.linesep + title + os.linesep)


CIRCLE = open(os.path.join(HERE, "fixtures", "circle.png"), "rb").read()
BODY = open(os.path.join(HERE, "fixtures", "sample-body.html"),
            encoding="utf-8").read()

# ---------------------------------------------------------------------------
head("Consent follows provenance: document every time, own picture once")

describe.reset_consent()
check("a picture from the user's own disk asks the first time",
      describe.consent_needed("image", False, 1))
check("a whole document asks", describe.consent_needed("document", False, 0))
describe.record_consent("image")
check("after a yes, a picture from disk does not ask again",
      not describe.consent_needed("image", False, 1))
check("a picture that came in with an imported document still asks",
      describe.consent_needed("image", True, 1))
check("a batch of pictures still asks", describe.consent_needed("image", False, 2))
describe.record_consent("document")
check("a document asks every time, whatever was recorded",
      describe.consent_needed("document", False, 0)
      and describe.consent_needed("document", True, 3))
check("a kind this file does not know asks rather than assuming",
      describe.consent_needed("mystery", False, 1))
check("a count that is not a number asks", describe.consent_needed("image", False, "lots"))
describe.reset_consent()
check("a new session asks for a picture again",
      describe.consent_needed("image", False, 1))
check("nothing in the module keeps a document yes",
      "document" not in describe._consented)

# ---------------------------------------------------------------------------
head("The consent question names the provider, the count, the size and the policy")

question = describe.consent_question("document", "google", 3, 1240, 640, False,
                                     "Report.imprint")
check("a document names the provider", "Gemini, from Google" in question)
check("and the file", "Report.imprint" in question)
check("and the words and pictures", "1,240 words" in question and "3 pictures" in question)
check("and the size", "about 640 KB" in question)
check("and ends by asking", question.endswith("Send the document?"))
check("and points at the data policy, by file and by address",
      "DESCRIBER.md" in question and describe.POLICY_URLS["google"] in question)
question = describe.consent_question("document", "anthropic", 20, 50000, 5000, False)
check("over the picture cap it says only the first %d go" % describe.PICTURE_CAP,
      "first %d of its 20 pictures" % describe.PICTURE_CAP in question)
check("and a big size is said in megabytes", "about 4.9 MB" in question, question[:160])
question = describe.consent_question("document", "openai", 0, 12, 1, False)
check("no pictures is said plainly", "no pictures" in question)
question = describe.consent_question("image", "anthropic", 1, 0, 120, False)
check("a picture from disk says it will not ask again this session",
      "until TG Imprint is next opened" in question and "Claude, from Anthropic" in question)
check("and ends by asking", question.endswith("Send the picture?"))
question = describe.consent_question("image", "openai", 1, 0, 120, True)
check("an imported picture says why it asks every time",
      "imported" in question and "every time" in question)
question = describe.consent_question("image", "google", 5, 0, 2400, False)
check("a batch says it is a batch and how many",
      "5 pictures" in question and "batch" in question.lower()
      and question.endswith("Send the pictures?"))
for provider in ai.PROVIDERS:
    q = describe.consent_question("image", provider, 1, 0, 1, False)
    check("%s: the policy address is a real https address" % provider,
          describe.POLICY_URLS[provider].startswith("https://")
          and describe.POLICY_URLS[provider] in q)

# ---------------------------------------------------------------------------
head("payload_estimate counts words, pictures and kilobytes")

words, pictures, kilobytes = describe.payload_estimate(BODY, None)
check("the sample body has 60 words of text", words == 60, words)
check("and two embedded pictures, found without being handed them", pictures == 2)
check("and a size that is small and not zero", 0 < kilobytes < 10, "%.2f KB" % kilobytes)
check("a plain sentence counts its words", describe.payload_estimate(
    "<p>one two three</p>", [])[0] == 3)
check("markup words are not counted",
      describe.payload_estimate("<p style='color:red' class='x'>one</p>", [])[0] == 1)
check("script and style text are not counted",
      describe.payload_estimate("<style>p {color: red}</style><p>one</p>"
                                "<script>alert('x y z')</script>", [])[0] == 1)
many = [CIRCLE] * 15
words, pictures, kilobytes = describe.payload_estimate("<p>x</p>", many)
words12, pictures12, kilobytes12 = describe.payload_estimate("<p>x</p>", [CIRCLE] * 12)
check("fifteen pictures are counted as fifteen", pictures == 15)
check("but only the first %d are measured, so the size is a twelve picture "
      "size and not a fifteen picture one" % describe.PICTURE_CAP,
      abs(kilobytes - kilobytes12) < 1.0
      and kilobytes < kilobytes12 + (kilobytes12 - 12) / 12.0,
      "%.2f against %.2f" % (kilobytes, kilobytes12))
chosen, over_cap, over_budget, unreadable = describe._select(many)
check("the selection sends the first twelve and names the rest",
      [n for n, _p in chosen] == list(range(1, 13)) and over_cap == [13, 14, 15])
chosen, over_cap, over_budget, unreadable = describe._select([CIRCLE, b"junk", None, CIRCLE])
check("a picture that cannot be read is named and skipped, and the numbering holds",
      [n for n, _p in chosen] == [1, 4] and unreadable == [2, 3])
saved = describe.PAYLOAD_BUDGET_KB
describe.PAYLOAD_BUDGET_KB = 2.0
try:
    chosen, over_cap, over_budget, unreadable = describe._select([CIRCLE] * 4)
finally:
    describe.PAYLOAD_BUDGET_KB = saved
check("the byte budget stops the batch and names what stayed behind",
      [n for n, _p in chosen] == [1] and over_budget == [2, 3, 4], (over_budget,))
check("the picture cap is twelve, with the reasoning in the file",
      describe.PICTURE_CAP == 12)

# ---------------------------------------------------------------------------
head("The size and the count in the question are the size and the count "
     "that go")

# Defect 3 and defect 4 of the round 2 review. The question used to say the
# whole document's word count and the whole outline's size for a book, and
# "the first 12 of its N pictures" even when the byte budget or an unreadable
# picture meant fewer than twelve really went.

long_body = "<p>" + " ".join("w%d" % i for i in range(40000)) + "</p>"
at_cap = "<p>" + " ".join("w%d" % i for i in range(30000)) + "</p>"
words, pictures, attached, kilobytes = describe.payload_plan(long_body, [])
capped = describe.payload_plan(at_cap, [])[3]
uncut = len("\n".join(describe.analyse(long_body).lines).encode("utf-8")) / 1024.0
check("a book is counted at its real length", words == 40000)
check("but the size measured is the CUT document: a 40,000 word document "
      "measures the same as a 30,000 word one, not a quarter more",
      abs(kilobytes - capped) < 1.0 and kilobytes < uncut - 20,
      "%.0f KB, at the cap %.0f KB, uncut %.0f KB"
      % (kilobytes, capped, uncut))
question = describe.consent_question("document", "google", pictures, words,
                                     kilobytes, False, "Book.imprint")
check("and the question says which words go",
      "the first 30,000 of its 40,000 words" in question, question[:150])

saved = describe.PAYLOAD_BUDGET_KB
describe.PAYLOAD_BUDGET_KB = 2.0
try:
    words, pictures, attached, kilobytes = describe.payload_plan(
        "<p>x</p>", [CIRCLE] * 15)
finally:
    describe.PAYLOAD_BUDGET_KB = saved
check("with a byte budget that stops after one picture, the plan says one "
      "picture is attached, not twelve", pictures == 15 and attached == 1,
      (pictures, attached))
question = describe.consent_question("document", "google", pictures, words,
                                     kilobytes, False, attached=attached)
check("and the question says one of its fifteen pictures, not the cap",
      "one of its 15 pictures" in question
      and "first 12" not in question, question[:200])

words, pictures, attached, kilobytes = describe.payload_plan(
    "<p>x</p>", [CIRCLE, b"junk", None, CIRCLE, b"junk"])
check("pictures that cannot be read are counted in the document but not "
      "attached", pictures == 5 and attached == 2)
question = describe.consent_question("document", "google", pictures, words,
                                     kilobytes, False, attached=attached)
check("and the question says two of its five pictures",
      "the first 2 of its 5 pictures" in question, question[:200])
question = describe.consent_question("document", "google", 3, 10, 4, False,
                                     attached=0)
check("when not one picture could be read the question says so",
      "none of its 3 pictures, because none of them could be read" in question,
      question[:200])
check("and a document whose pictures all go still reads plainly",
      "and 3 pictures" in describe.consent_question(
          "document", "google", 3, 10, 4, False, attached=3))

# The number in the question is the number the progress line says, because
# both come from the same plan.
plan_said = []
real_ask_here = ai.ask
ai.ask = lambda pictures, prompt, provider, key, model="", timeout=None, \
    max_tokens=None: (True, "described")
real_key_here = describe.key_for
describe.key_for = lambda provider: "k"
try:
    _w, _p, _a, plan_kb = describe.payload_plan(BODY, None)
    describe.describe_document(BODY, None, "google", "",
                               progress=plan_said.append)
finally:
    ai.ask = real_ask_here
    describe.key_for = real_key_here
sending = [line for line in plan_said if line.startswith("Sending")]
check("the size the question would say is the size the progress line says",
      len(sending) == 1
      and describe._size_words(plan_kb) in sending[0], (sending, plan_kb))

# ---------------------------------------------------------------------------
head("The outline the model is given")

outline = describe.outline(BODY)
check("headings carry their level, in order",
      describe.headings(BODY) == [(1, "Sample document"), (2, "Lists"),
                                  (2, "A quotation"),
                                  (3, "A picture with a description"),
                                  (3, "A decorative picture"), (2, "A table")],
      describe.headings(BODY))
check("a picture with a description is given with it",
      "Picture 1, described as: A yellow circle on a blue background" in outline)
check("a decorative picture is said to be decorative",
      "Picture 2, marked decorative, no description." in outline)
check("a link carries its address", "(link to https://tgstudios.app/)" in outline)
check("a table's header row is named",
      "Header row: Name, Value" in outline and "Row: Alpha, 1" in outline
      and "Table ends, 3 rows and 2 columns." in outline)
check("list items are labelled", "List item: First bullet" in outline)
check("a quotation is labelled", "Quotation: Quoted text, set apart." in outline)
hostile = ('<p>Hello</p><img src="x" onerror="alert(1)"><script>evil()</script>'
           '<img alt="Old chart" data-alt-source="ai:google" src="data:image/png;base64,AAAA">'
           '<img alt="From the PDF" data-alt-source="pdf" src="y">')
outline = describe.outline(hostile)
check("a picture with no alt is said to have no description",
      "Picture 1, no description." in outline)
check("an AI written description is marked as unchecked",
      "Picture 2, described as: Old chart (this description was written by AI"
      in outline)
check("a recovered description is marked as unchecked",
      "Picture 3, described as: From the PDF (this description was recovered" in outline)
check("script text never reaches the outline",
      "evil" not in outline and "alert" not in outline)
check("a broken document still gives what it has",
      "Heading level 2: Open" in describe.outline("<h2>Open<p>and <b>unclosed"))

# ---------------------------------------------------------------------------
head("The prompts")

short = describe.alt_prompt("It sits under the heading Results. The paragraph "
                            "before it says: Sales rose in June.")
long = describe.alt_prompt("It sits under the heading Results.", long=True)
check("the alt prompt carries the context", "under the heading Results" in short)
check("and without context carries no context heading",
      "Where the picture sits" not in describe.alt_prompt(""))
check("short and long differ", short != long and "paragraph" in long)
check("it forbids 'image of'", '"image of"' in short)
check("it asks for numbers and words to be read out", "every number" in short)
check("it asks for a chart's meaning", "chart" in short and "trend" in short)
check("it says the reader is blind and cannot check",
      "blind" in short and "cannot check" in short)
check("it forbids markdown", "no markdown" in short)
document = describe.document_prompt(BODY)
check("the document prompt lists the headings, with levels",
      "Heading level 1: Sample document" in document
      and "Heading level 2: Lists" in document
      and "Heading level 3: A picture with a description" in document)
check("and says the pictures are attached", "pictures are attached" in document)
check("and asks for the accessibility flags",
      "skipped" in document and "click here" in document
      and "no description" in document and "header row" in document)
check("and says the answer is read aloud, no markdown",
      "read aloud" in document and "no markdown" in document)
partial = describe.document_prompt(BODY, pictures_total=20,
                                   sent=list(range(1, 13)), unreadable=[14])
check("over the cap, the prompt says which pictures are attached",
      "Only these are attached, in this order: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 "
      "and 12" in partial)
check("and which could not be read", "Picture 14 could not be read" in partial)
cut = describe.document_prompt("<p>" + " ".join("w%d" % i for i in range(100))
                               + "</p>", truncated_words=10)
check("a long document is cut at the word cap and the prompt says so",
      "first 10 words" in cut and "w9" in cut and "w10" not in cut)
for text in (short, long, document):
    check("no dashes in the prompt", chr(8212) not in text and chr(8211) not in text)

# ---------------------------------------------------------------------------
head("Every sentence the prompts build is in docs/STRINGS.md")

# Defect 9 of the round 2 review: the prompts were summarised in STRINGS.md,
# and ten sentences the app really sends appeared nowhere in it, so Tony
# could not approve what is asked in his name. These sentences are taken from
# the code, not typed out here, so changing the wording without changing
# STRINGS.md fails this check.

STRINGS = " ".join(open(os.path.join(os.path.dirname(HERE), "docs",
                                     "STRINGS.md"),
                        encoding="utf-8").read().split())


def digitless(sentence):
    """The parts of a sentence with no numbers in them, long enough to be
    worth matching. STRINGS.md writes a number as {n}, so the numbers
    themselves are what must NOT be compared."""
    import re as _re
    return [part.strip() for part in _re.split(r"[0-9][0-9,]*", sentence)
            if len(part.strip()) > 14]


def in_strings(label, sentence):
    missing = [part for part in digitless(sentence) if part not in STRINGS]
    check("STRINGS.md has %s" % label, not missing, missing[:1])


def attached_sentences(**kw):
    """The sentences document_prompt adds after the standing prompt, which
    are the ones that were missing."""
    whole = describe.document_prompt("<p>x</p>", **kw)
    middle = whole[len(describe._DOCUMENT):whole.index("The document:")]
    return [line.strip() for line in middle.splitlines() if line.strip()]


for label, kw in (
        ("no pictures", dict(pictures_total=0, sent=[])),
        ("one picture", dict(pictures_total=1, sent=[1])),
        ("all of them", dict(pictures_total=4, sent=[1, 2, 3, 4])),
        ("only some of them", dict(pictures_total=5, sent=[1, 2, 3])),
        ("one that could not be read",
         dict(pictures_total=2, sent=[1], unreadable=[2])),
        ("two that could not be read",
         dict(pictures_total=3, sent=[1], unreadable=[2, 3])),
        ("a document cut at the word cap",
         dict(pictures_total=0, sent=[], truncated_words=30000))):
    for sentence in attached_sentences(**kw):
        in_strings("the attachment sentence for %s" % label, sentence)

empty = describe.document_prompt("", pictures_total=0, sent=[])
in_strings("the line for a document with no text at all",
           "(The document has no text.)")
check("which is what a document with no text really sends",
      empty.rstrip().endswith("(The document has no text.)"))

outline_lines = describe.analyse(BODY).lines + describe.analyse(
    '<img alt="x" data-alt-source="ai:google">'
    '<img alt="y" data-alt-source="pdf"><img src="x">').lines
for line in outline_lines:
    label = line.split(":")[0] + ":" if ":" in line else line
    in_strings("the outline label in %r" % label[:30], label)
for mark in ("(this description was written by AI and has not been checked "
             "by a sighted person)",
             "(this description was recovered from a file and has not been "
             "checked)"):
    in_strings("the unchecked description mark", mark)

# The prompts are quoted in DESCRIBER.md, so every line starts "> " and the
# quote marks have to come off before the words can be compared.
DESCRIBER = " ".join(
    line[2:] if line.startswith("> ") else line[1:] if line == ">" else line
    for line in open(os.path.join(os.path.dirname(HERE), "docs",
                                  "DESCRIBER.md"),
                     encoding="utf-8").read().splitlines()).split()
DESCRIBER = " ".join(DESCRIBER)
for label, sentence in (
        ("the form question's origin line",
         "the origin is the TOP LEFT corner of the page"),
        ("the form question's accuracy rule",
         "Be accurate rather than complete."),
        ("the form question's rule against an invented label",
         "Never invent a label and never guess one from the shape of the "
         "form.")):
    check("DESCRIBER.md has %s" % label,
          " ".join(sentence.split()) in DESCRIBER, sentence[:40])

# ---------------------------------------------------------------------------
head("Tidying an answer into alternative text")

check("wrapping quotes go", describe.tidy_alt('"A circle."') == "A circle.")
check("an 'image of' opener goes and the rest is capitalised",
      describe.tidy_alt("An image of a yellow circle.") == "A yellow circle.")
check("a 'Alt text:' label goes", describe.tidy_alt("Alt text: A circle.") == "A circle.")
check("the short form has no line breaks",
      describe.tidy_alt("A circle.\n\nOn blue.") == "A circle. On blue.")
check("the long form keeps its paragraphs",
      describe.tidy_alt("A circle.\n\nOn blue.", long=True) == "A circle.\nOn blue.")
check("a plain answer is untouched", describe.tidy_alt("Two cats asleep.") == "Two cats asleep.")

# ---------------------------------------------------------------------------
head("describe_image and describe_document, with the network faked")

real_key_for = describe.key_for
real_ask = ai.ask

describe.key_for = lambda provider: ""
ok, said = describe.describe_image(CIRCLE, "google", "")
check("no key is a sentence naming the provider and Preferences",
      not ok and "Gemini, from Google" in said and "Preferences" in said)
ok, said = describe.describe_document(BODY, None, "anthropic", "")
check("the same for a document", not ok and "Claude" in said and "Preferences" in said)
describe.key_for = lambda provider: "k"
ok, said = describe.describe_image(b"", "google", "")
check("no picture is a sentence", not ok and "no picture" in said)
ok, said = describe.describe_image(b"junk", "google", "")
check("a picture that cannot be read is a sentence and nothing leaves",
      not ok and "nothing has left" in said)

asked = {}


def fake_ask(pictures, prompt, provider, key, model="", timeout=None,
             max_tokens=None):
    asked.update(pictures=pictures, prompt=prompt, provider=provider, key=key,
                 model=model, timeout=timeout, max_tokens=max_tokens)
    return True, '"An image of a yellow circle on a blue background."'


ai.ask = fake_ask
ok, text = describe.describe_image(CIRCLE, "google", "my-model",
                                   context="Under Results")
check("a picture is described and the answer tidied",
      ok and text == "A yellow circle on a blue background.", text)
check("one prepared PNG was sent", len(asked["pictures"]) == 1
      and asked["pictures"][0][0] == "image/png")
check("with the alt prompt carrying the context", "Under Results" in asked["prompt"])
check("to the provider and model asked for, on the picture timeout",
      asked["provider"] == "google" and asked["model"] == "my-model"
      and asked["timeout"] == ai.TIMEOUT and asked["max_tokens"] == ai.IMAGE_TOKENS)

progress = []
asked.clear()
ai.ask = lambda pictures, prompt, provider, key, model="", timeout=None, \
    max_tokens=None: (asked.update(pictures=pictures, prompt=prompt,
                                   timeout=timeout, max_tokens=max_tokens)
                      or (True, "A sample document with a circle."))
ok, text = describe.describe_document(BODY, None, "google", "",
                                      progress=progress.append)
check("a document is described", ok and text.startswith("A sample document"), text)
check("both embedded pictures went, prepared",
      len(asked["pictures"]) == 2 and all(m == "image/png" for m, _d in asked["pictures"]))
check("with the outline in the prompt", "Heading level 1: Sample document" in asked["prompt"])
check("on the document timeout and budget",
      asked["timeout"] == ai.DOCUMENT_TIMEOUT and asked["max_tokens"] == ai.DOCUMENT_TOKENS)
check("progress said what it was doing, in sentences",
      len(progress) >= 3 and progress[0] == "Reading the document."
      and any(s.startswith("Sending the document to Gemini, from Google:")
              for s in progress), progress)
check("and never leaked a key", all("k" != s for s in progress))
ok, text = describe.describe_document("<p>x</p>", [CIRCLE] * 15, "google", "")
check("over the cap, the answer says which pictures were not described",
      ok and text.endswith("Only 12 of the document's 15 pictures were sent, so "
                           "pictures 13, 14 and 15 are not described."), text[-90:])
check("and the prompt said so too", "Only these are attached" in asked["prompt"])
ok, text = describe.describe_document("<p>x</p>", [CIRCLE, b"junk"], "google", "")
check("an unreadable picture is named in the answer",
      ok and "Picture 2 could not be read and was not sent." in text, text[-60:])
ok, text = describe.describe_document("", None, "google", "")
check("an empty document is a sentence", not ok and "empty" in said.lower() or
      "nothing to describe" in text)
ok, text = describe.describe_document("<p>" + "word " * 40000 + "</p>", None,
                                      "google", "", progress=progress.append)
check("a very long document is cut at the word cap and the answer says so",
      ok and "only the first 30,000 were sent" in text, text[-80:])


def raising_progress(_text):
    raise RuntimeError("a progress callback that misbehaves")


ok, text = describe.describe_document(BODY, None, "google", "",
                                      progress=raising_progress)
check("a misbehaving progress callback cannot stop the description", ok)

ai.ask = real_ask
describe.key_for = real_key_for

# ---------------------------------------------------------------------------
head("The Drop Deck key helper, against probe entries it makes and removes")

SOURCE = "TG Imprint test source: "
TARGET = "TG Imprint test probe: "
if not secrets.available():
    skip("copying a key between prefixes", "no credential store on this machine")
else:
    secrets.forget("probe", SOURCE)
    secrets.forget("probe", TARGET)
    ok, said = describe.copy_drop_deck_key("probe", SOURCE, TARGET)
    check("with nothing under Drop Deck's name it says so",
          not ok and "no key" in said, said)
    secrets.store("probe", "probe-key-value-7890", SOURCE)
    ok, said = describe.copy_drop_deck_key("probe", SOURCE, TARGET)
    check("a key under the source prefix is copied under the target prefix",
          ok and secrets.fetch("probe", TARGET) == "probe-key-value-7890", said)
    check("the sentence gives the ending and never the key",
          "7890" in said and "probe-key-value-7890" not in said, said)
    check("the source entry is left where it was",
          secrets.fetch("probe", SOURCE) == "probe-key-value-7890")
    secrets.forget("probe", SOURCE)
    secrets.forget("probe", TARGET)
    check("the probe entries are gone again",
          not secrets.fetch("probe", SOURCE) and not secrets.fetch("probe", TARGET))
    check("and Tony's real Drop Deck entries were never touched by name",
          describe.DROP_DECK_PREFIX not in (SOURCE, TARGET))

# ---------------------------------------------------------------------------
head("The dialogs and the settings page, under wx, with no network")

import wx  # noqa: E402
from tgimprint.ui import ai_settings_page, describe_dialog  # noqa: E402

# Snapshot of the real entries, taken before any dialog or page runs, so the
# check at the end proves this test left them exactly as they were.
REAL_KEYS = {n: secrets.fetch(n, secrets.VISION_PREFIX) for n in ai.PROVIDERS}

app = wx.App(False)
frame = wx.Frame(None, title="test host")
spoken = []
helped = []


def flat(control):
    """A static's label with the line breaks Wrap() put in taken out again."""
    return " ".join(control.GetLabel().split())


def pump(until, seconds=6.0):
    """Turn the event loop by hand until `until()` holds or time is up."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.Yield()
        if until():
            return True
        time.sleep(0.02)
    app.Yield()
    return until()


describe.reset_consent()

# Defect 8 of the round 2 review: the preview used to be decoded inside
# __init__, so a photograph held the dialog shut for a sixth of a second
# before a single key could reach it. The decode now runs on a thread and the
# bitmap arrives through wx.CallAfter, which is what this proves: the
# decoding function is not called on the window thread.
real_preview_data = describe_dialog.preview_data
decoded_on = {}
decode_started = threading.Event()
decode_may_finish = threading.Event()


def watched_preview_data(image_bytes, box=describe_dialog.PREVIEW_BOX):
    decoded_on["thread"] = threading.current_thread().ident
    decode_started.set()
    # Two seconds of decoding, held here on purpose. Done on the window
    # thread, as it was before, those two seconds are two seconds in which
    # the dialog does not exist and a keystroke goes nowhere.
    decode_may_finish.wait(2.0)
    return real_preview_data(image_bytes, box)


describe_dialog.preview_data = watched_preview_data
built_at = time.monotonic()
dialog = describe_dialog.DescribeImageDialog(
    frame, CIRCLE, current_alt="old text", context="ctx", provider="google",
    announce=spoken.append)
building_took = time.monotonic() - built_at
check("a slow decode does not hold the dialog shut: it was built in under a "
      "second while the decode was still running",
      building_took < 1.0 and decode_started.wait(5.0),
      "built in %.2f seconds" % building_took)
check("and the description field can be typed in before the picture has "
      "been decoded", dialog.answer.IsEditable()
      and not dialog.preview.GetBitmap().IsOk())
decode_may_finish.set()
arrived = pump(lambda: "thread" in decoded_on)
check("the picture is decoded, and NOT on the window thread",
      arrived and decoded_on.get("thread") not in
      (None, threading.main_thread().ident), decoded_on)
check("and the decoded picture reaches the preview",
      pump(lambda: dialog.preview.GetBitmap().IsOk()))
describe_dialog.preview_data = real_preview_data
check("the picture preview refuses focus",
      dialog.preview is not None and not dialog.preview.AcceptsFocus()
      and not dialog.preview.AcceptsFocusFromKeyboard())
check("every control is named",
      dialog.provider.GetName() == "Who to ask"
      and dialog.answer.GetName() == "Description"
      and dialog.status.GetName() == "Status")
check("the buttons say what they do",
      dialog.describe_button.GetLabel() == "&Describe"
      and dialog.detail_button.GetLabel() == "Describe in d&etail"
      and dialog.use_button.GetLabel() == "&Use this description")
check("the current description is offered for editing",
      dialog.answer.GetValue() == "old text")
check("the description field is editable", dialog.answer.IsEditable())
check("nothing accepted yet", dialog.result is None and dialog.provider_used == "")
check("the provider defaults to the settings' choice", dialog.chosen_provider() == "google")
dialog.answer.SetValue("typed by hand")
dialog._on_ok()
check("text typed by hand is accepted with no provider marked",
      dialog.result == "typed by hand" and dialog.provider_used == "")
dialog.Destroy()

broken = describe_dialog.DescribeImageDialog(frame, b"not a picture at all",
                                            provider="google",
                                            announce=spoken.append)
pump(lambda: broken.preview_note.IsShown())
check("a picture that cannot be decoded says so where the preview would be, "
      "and does not speak it",
      broken.preview_note.GetLabel() == "The picture could not be shown here."
      and not broken.preview.IsShown()
      and spoken[-1:] != ["The picture could not be shown here."])
broken.Destroy()

# The asking flow, with the describer faked and consent answered by code.
real_describe_image = describe.describe_image
real_key_for = describe.key_for
describe.key_for = lambda provider: "k"
asked_consent = []


def slow_describe(image_bytes, provider, model, context="", long=False):
    time.sleep(0.15)
    return True, "A yellow circle on a blue background%s." % (
        ", in detail" if long else "")


describe.describe_image = slow_describe
describe.reset_consent()
dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, provider="google",
                                             announce=spoken.append)
dialog.ask_consent = lambda question: asked_consent.append(question) or True
dialog._on_describe(False)
check("the dialog is busy while the picture is measured and sent",
      dialog._busy and not dialog.describe_button.IsEnabled())
arrived = pump(lambda: dialog.answer.GetValue() != "")
check("the answer arrives in the description field", arrived
      and dialog.answer.GetValue() == "A yellow circle on a blue background.",
      dialog.answer.GetValue())
check("consent was asked once, naming the provider and the size",
      len(asked_consent) == 1 and "Gemini, from Google" in asked_consent[0]
      and "KB" in asked_consent[0], asked_consent[:1])
check("focus landed in the description field",
      dialog.FindFocus() is dialog.answer)
check("announce said it arrived, with the text",
      any(s.startswith("Described by Gemini, from Google: A yellow circle")
          for s in spoken), spoken[-1:])
check("the status says who described it and to read it",
      flat(dialog.status).startswith("Described by Gemini, from Google in")
      and "Use this description" in flat(dialog.status), flat(dialog.status))
check("the buttons are back", dialog.describe_button.IsEnabled()
      and dialog.use_button.IsEnabled() and not dialog._busy)
dialog._on_describe(True)
pump(lambda: "in detail" in dialog.answer.GetValue())
check("Describe in detail asks the long form",
      dialog.answer.GetValue().endswith(", in detail."))
check("a second picture from disk did not ask again", len(asked_consent) == 1)
dialog.answer.SetValue(dialog.answer.GetValue() + " Edited.")
dialog._on_ok()
check("the accepted text is the edited one and the provider is marked",
      dialog.result.endswith("Edited.") and dialog.provider_used == "google")
dialog.Destroy()

dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, imported=True,
                                             provider="google",
                                             announce=spoken.append)
dialog.ask_consent = lambda question: asked_consent.append(question) or True
dialog._on_describe(False)
pump(lambda: dialog.answer.GetValue() != "")
check("an imported picture asks even though a yes was already given",
      len(asked_consent) == 2 and "imported" in asked_consent[1])
dialog._on_describe(False)
pump(lambda: len(asked_consent) == 3)
check("and asks again the next time", len(asked_consent) == 3)
dialog.Destroy()

describe.reset_consent()
dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, provider="google",
                                             announce=spoken.append)
dialog._help = spoken.append   # a confirmation is a hint, on announce_help
dialog.ask_consent = lambda question: False
dialog._on_describe(False)
pump(lambda: flat(dialog.status) == "Nothing was sent.")
check("saying no sends nothing and says so",
      flat(dialog.status) == "Nothing was sent." and spoken[-1] == "Nothing was sent."
      and not dialog._busy, flat(dialog.status))
check("and a no is not remembered as a yes", describe.consent_needed("image", False, 1))
dialog.Destroy()
describe.record_consent("image")

# Cancel while the answer is in the air.
gate = threading.Event()


def blocked_describe(image_bytes, provider, model, context="", long=False):
    gate.wait(5.0)
    return True, "Too late."


describe.describe_image = blocked_describe
dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, provider="google",
                                             announce=spoken.append)
dialog.ask_consent = lambda question: True
dialog._on_describe(False)
pump(lambda: dialog._busy and dialog.status.GetLabel().startswith("Asking"))
check("the request is running", dialog._busy)
dialog._on_cancel()
check("Cancel works at once, with nothing accepted",
      dialog.result is None and not dialog.IsShown())
gate.set()
time.sleep(0.3)
app.Yield()
check("the late answer is dropped, not shown",
      dialog.answer.GetValue() == "" and dialog.result is None)
dialog.Destroy()

# A failure is shown and spoken, and the dialog stays open.
describe.describe_image = lambda *a, **k: (False, "Gemini, from Google would not "
                                                  "accept that key. Check it.")
dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, provider="google",
                                             announce=spoken.append)
dialog.ask_consent = lambda question: True
dialog._on_describe(False)
pump(lambda: not dialog._busy)
check("a failure is put in the status line and spoken",
      dialog.status.GetLabel().startswith("Gemini, from Google would not accept")
      and spoken[-1] == dialog.status.GetLabel())
check("and the dialog stays open with the buttons back",
      dialog.describe_button.IsEnabled() and dialog.result is None)
dialog.Destroy()

# No key: no thread, a sentence.
describe.key_for = lambda provider: ""
dialog = describe_dialog.DescribeImageDialog(frame, CIRCLE, provider="google",
                                             announce=spoken.append)
dialog._on_describe(False)
check("no key is a sentence pointing at Preferences, without asking consent",
      "Preferences" in dialog.status.GetLabel() and not dialog._busy)
dialog.Destroy()
describe.key_for = lambda provider: "k"

# The consent dialog itself.
consent = describe_dialog.ConsentDialog(frame, "Send the picture?", "The question.")
check("the consent dialog holds the question in a read-only field with focus",
      not consent.question.IsEditable() and consent.question.GetValue() == "The question."
      and consent.question.GetName() == "Question")
check("its default button sends nothing", consent.keep.GetLabel() == "&Don't send")
consent._on_keep(None)
check("and closing it is a no", consent.result is False)
consent.Destroy()

# The document dialog.
real_describe_document = describe.describe_document


def slow_document(body_html, images, provider, model, progress=None):
    if progress:
        progress("Reading the document.")
        progress("Sending the document to Gemini, from Google: about 60 words, "
                 "2 pictures, about 4 KB. This can take a minute.")
    time.sleep(0.15)
    return True, "A sample document with a circle in it."


describe.describe_document = slow_document
dialog = describe_dialog.DescribeDocumentDialog(
    frame, BODY, None, provider="google", announce=spoken.append,
    announce_help=helped.append, document_name="sample.imprint")
check("the message field is read-only, named, and has focus",
      not dialog.message.IsEditable() and dialog.message.GetName() == "Message"
      and dialog.FindFocus() is dialog.message)
check("Send waits until the size is known", not dialog.send_button.IsEnabled())
pump(lambda: dialog._stage == "asking")
question = dialog.message.GetValue()
check("the consent question arrives in the field, naming the file, the "
      "provider, the words and the pictures",
      "sample.imprint" in question and "Gemini, from Google" in question
      and "60 words" in question and "2 pictures" in question
      and question.endswith("Send the document?"), question[:120])
check("and then Send is offered", dialog.send_button.IsEnabled()
      and not dialog.copy_button.IsEnabled())
dialog.provider.SetSelection(ai.PROVIDERS.index("anthropic"))
dialog._on_provider()
check("changing the provider rewrites the question",
      "Claude, from Anthropic" in dialog.message.GetValue())
dialog.provider.SetSelection(ai.PROVIDERS.index("google"))
dialog._on_provider()
dialog._on_send()
check("while sending, Send and the provider are locked",
      not dialog.send_button.IsEnabled() and not dialog.provider.IsEnabled())
pump(lambda: dialog._stage == "answered")
check("the answer lands in the field, with focus, and is the result",
      dialog.message.GetValue() == "A sample document with a circle in it."
      and dialog.result == dialog.message.GetValue()
      and dialog.FindFocus() is dialog.message and dialog.provider_used == "google")
check("progress went through the help channel",
      any(s.startswith("Sending the document") for s in helped), helped[-1:])
check("arrival was announced", any("The description is in the Message field" in s
                                   for s in spoken), spoken[-1:])
check("Copy is offered", dialog.copy_button.IsEnabled())
dialog._on_copy()
check("Copy reports what it did", "clipboard" in dialog.status.GetLabel().lower())
dialog._on_close()
check("Close keeps the answer as the result",
      dialog.result == "A sample document with a circle in it.")
dialog.Destroy()

gate = threading.Event()


def blocked_document(body_html, images, provider, model, progress=None):
    gate.wait(5.0)
    return True, "Too late."


describe.describe_document = blocked_document
dialog = describe_dialog.DescribeDocumentDialog(frame, BODY, None, provider="google",
                                                announce=spoken.append)
pump(lambda: dialog._stage == "asking")
dialog._on_send()
dialog._on_close()
gate.set()
time.sleep(0.3)
app.Yield()
check("closing during a request drops the late answer",
      dialog.result is None and dialog.message.GetValue() != "Too late.")
dialog.Destroy()

describe.describe_document = lambda *a, **k: (False, "Could not reach Gemini, from "
                                                     "Google. Check this machine is online.")
dialog = describe_dialog.DescribeDocumentDialog(frame, BODY, None, provider="google",
                                                announce=spoken.append)
pump(lambda: dialog._stage == "asking")
dialog._on_send()
pump(lambda: dialog._stage == "asking" and dialog.send_button.IsEnabled())
check("a failure is spoken, the question is back in the field, and Send is offered again",
      dialog.message.GetValue().startswith("This sends")
      and spoken[-1].startswith("Could not reach") and dialog.send_button.IsEnabled())
dialog.Destroy()

describe.describe_image = real_describe_image
describe.describe_document = real_describe_document
describe.key_for = real_key_for

# The settings page, writing only under a probe prefix.
PROBE = "TG Imprint test probe: "
if not secrets.available():
    skip("the settings page against the credential store", "no credential store")
else:
    for name in ai.PROVIDERS:
        secrets.forget(name, PROBE)
    settings = {"ai_provider": "google", "ai_model": ""}
    page = ai_settings_page.AISettingsPage(frame, settings, prefix=PROBE,
                                           announce=spoken.append)
    check("every control on the page is named",
          page.provider.GetName() == "Who to ask" and page.key.GetName() == "Their key"
          and page.show.GetName() == "Show the key" and page.model.GetName() == "Model"
          and page.status.GetName() == "Status")
    check("the buttons say what they do",
          page.forget_button.GetLabel() == "&Forget this key"
          and page.drop_deck_button.GetLabel() == "Use the key I gave TG &Drop Deck"
          and page.list_button.GetLabel() == "&Get the list"
          and page.test_button.GetLabel() == "&Test the key and model")
    check("the provider follows settings", page.chosen_provider() == "google")
    check("with no key kept the page says so and Forget is off",
          page.key_state.GetLabel().startswith("No key for Gemini, from Google")
          and not page.forget_button.IsEnabled())
    check("the model note names the accurate default and says what Test sends",
          ai.DEFAULT_MODELS["google"] in flat(page.model_note)
          and "nothing of yours" in flat(page.model_note))
    page.key.ChangeValue("probe-google-key-1111")
    page.show.SetValue(True)
    page._on_show()
    page.show.SetValue(False)
    page._on_show()
    check("Show can be toggled and the key survives it",
          page.key.GetValue() == "probe-google-key-1111")
    page.provider.SetSelection(ai.PROVIDERS.index("anthropic"))
    page._on_provider()
    check("switching provider shows that provider's (empty) box",
          page.key.GetValue() == "" and page.chosen_provider() == "anthropic")
    page.key.ChangeValue("probe-claude-key-2222")
    page.model.SetValue("claude-test-model")
    page.apply()
    check("apply writes the provider and model into settings, never the key",
          settings["ai_provider"] == "anthropic"
          and settings["ai_model"] == "claude-test-model"
          and "2222" not in str(settings) and "1111" not in str(settings))
    check("apply keeps a key for every provider whose box was filled",
          secrets.fetch("anthropic", PROBE) == "probe-claude-key-2222"
          and secrets.fetch("google", PROBE) == "probe-google-key-1111")
    page.Destroy()

    page = ai_settings_page.AISettingsPage(frame, dict(settings), prefix=PROBE,
                                           announce=spoken.append)
    check("reopened, the box holds the kept key and the state says so",
          page.key.GetValue() == "probe-claude-key-2222"
          and "ending 2222" in flat(page.key_state)
          and page.forget_button.IsEnabled(), flat(page.key_state))
    page.key.ChangeValue("")
    page.apply()
    check("a blank box at apply forgets the kept key",
          secrets.fetch("anthropic", PROBE) == "")
    check("and leaves a provider that was not visited alone",
          secrets.fetch("google", PROBE) == "probe-google-key-1111")
    page.provider.SetSelection(ai.PROVIDERS.index("google"))
    page._on_provider()
    page._on_forget()
    check("Forget removes the key at once and says so",
          secrets.fetch("google", PROBE) == "" and page.key.GetValue() == ""
          and "forgotten" in page.status.GetLabel() and "forgotten" in spoken[-1])

    real_list = ai.list_models
    ai.list_models = lambda provider, key, timeout=30.0: (True, ["m-one", "m-two"])
    page.key.ChangeValue("typed-key")
    page.model.SetValue("keep-me")
    page._on_list()
    pump(lambda: page.model.GetCount() == 2)
    check("Get the list fills the model box and keeps what was typed",
          [page.model.GetString(i) for i in range(page.model.GetCount())]
          == ["m-one", "m-two"] and page.model.GetValue() == "keep-me")
    check("and reports the count", page.status.GetLabel().startswith("2 models"))
    ai.list_models = lambda provider, key, timeout=30.0: (False, "Gemini, from Google "
                                                                 "would not accept that key.")
    page._on_list()
    pump(lambda: flat(page.status).startswith("Gemini"))
    check("a failed list is the sentence, spoken",
          flat(page.status).startswith("Gemini, from Google would not")
          and spoken[-1] == "Gemini, from Google would not accept that key.",
          flat(page.status))
    ai.list_models = real_list

    real_ask = ai.ask
    seen = {}
    ai.ask = lambda pictures, prompt, provider, key, model="", timeout=None, \
        max_tokens=None: (seen.update(pictures=pictures, prompt=prompt, key=key)
                          or (True, "A red circle on white."))
    page._on_test()
    pump(lambda: "answered" in page.status.GetLabel())
    check("Test reports the answer and the time, never the key",
          flat(page.status).startswith("Gemini, from Google answered in")
          and flat(page.status).endswith("A red circle on white.")
          and "typed-key" not in flat(page.status), flat(page.status))
    check("Test sent the app's own tiny picture and the typed key",
          len(seen["pictures"]) == 1 and seen["pictures"][0][0] == "image/png"
          and len(seen["pictures"][0][1]) < 4096 and seen["key"] == "typed-key")
    ai.ask = real_ask

    page.key.ChangeValue("")
    page.ask_yes = lambda question, title, yes, no: "TG Drop Deck" in question
    secrets.store("google", "probe-dd-key-3333", "TG Imprint test source: ")
    real_prefix = describe.DROP_DECK_PREFIX
    describe.DROP_DECK_PREFIX = "TG Imprint test source: "
    real_copy = describe.copy_drop_deck_key
    describe.copy_drop_deck_key = lambda provider, source_prefix="TG Imprint test source: ", \
        target_prefix=None: real_copy(provider, "TG Imprint test source: ", target_prefix)
    page._on_drop_deck()
    describe.copy_drop_deck_key = real_copy
    describe.DROP_DECK_PREFIX = real_prefix
    check("the Drop Deck button copies the key under the probe prefix and "
          "loads it into the box",
          secrets.fetch("google", PROBE) == "probe-dd-key-3333"
          and page.key.GetValue() == "probe-dd-key-3333"
          and "ending 3333" in page.status.GetLabel())
    page.ask_yes = lambda question, title, yes, no: False
    page._on_drop_deck()
    check("saying no copies nothing", page.status.GetLabel() == "Nothing was copied.")
    page.Destroy()
    for name in ai.PROVIDERS:
        secrets.forget(name, PROBE)
    secrets.forget("google", "TG Imprint test source: ")
    check("every probe entry is gone",
          not any(secrets.fetch(n, PROBE) for n in ai.PROVIDERS)
          and not secrets.fetch("google", "TG Imprint test source: "))
    check("the real Credential Manager entries are exactly as they were",
          {n: secrets.fetch(n, secrets.VISION_PREFIX) for n in ai.PROVIDERS} == REAL_KEYS)

frame.Destroy()
app.Yield()

# ---------------------------------------------------------------------------
head("The live Gemini check, on Tony's Drop Deck key, if it is here")

live_key = secrets.fetch("google", describe.DROP_DECK_PREFIX)
if not live_key:
    skip("Gemini describes tests/fixtures/circle.png",
         "no Drop Deck Gemini key in Credential Manager")
else:
    describe.key_for = lambda provider: live_key
    try:
        started = time.monotonic()
        ok, text = describe.describe_image(
            CIRCLE, "google", "",
            context="It sits under the heading \"A picture with a description\". "
                    "The paragraph before it says: \"A sample document used to "
                    "test TG Imprint.\"")
        took = time.monotonic() - started
    finally:
        describe.key_for = real_key_for
    check("Gemini answered with a non-empty description of the circle fixture",
          ok and len(text) > 10, text if ok else text[:120])
    check("and it reads like a sentence, not markdown",
          ok and "." in text and "*" not in text and "#" not in text)
    print("       took %.1f seconds with %s; the answer was: %s"
          % (took, ai.DEFAULT_MODELS["google"], text))

print("\n%d/%d checks passed%s" % (sum(CHECKS), len(CHECKS),
                                   (", %d skipped" % len(SKIPPED)) if SKIPPED else ""))
sys.exit(0 if all(CHECKS) else 1)
