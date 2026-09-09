"""Describing one picture, or a whole document, on the user's own key.

The job, in Tony's words from the analysis: describe the selected picture
so its alternative text can be written, and describe a whole document so a
blind reader knows what they have been sent. The three providers are
reached through ai.py; this file holds what is ASKED, what LEAVES the
machine and when, and the sentences the dialogs show.

Three things this file promises.

Nothing here raises. Every public function returns `(ok, text)` or a plain
value, and every failure is a sentence somebody can act on.

Nothing here touches the window. Everything that goes near the network is
called from a thread the dialog starts, so this file never imports wx.

Nothing leaves the machine without consent, and consent follows provenance
(docs/DECISIONS.md, decision 8). A whole document asks every time. A
picture the user put in from their own disk asks once per session. A
picture that arrived inside an imported document, and any batch of
pictures, is somebody else's document leaving the machine, so it asks
every time. The person answering cannot look at the picture to check what
is in it, which is the whole reason the rule is strict.

The answer is never written into the document by this file or by the
dialogs. It lands in a field the user reads and edits, and the editor only
gets what they accept.
"""
from __future__ import annotations

import base64
import re
from html.parser import HTMLParser

from . import ai, secrets

#: Where TG Drop Deck keeps the same kind of key. The settings page offers
#: to copy it, after a yes in a dialog that names the provider.
DROP_DECK_PREFIX = "TG Drop Deck vision key: "

#: How many pictures travel with a document description, and a second cap
#: on their bytes. Twelve, because at the 1,600 pixel width a prepared
#: picture measured 235 to 384 KB for a photograph as JPEG and 314 to 324 KB
#: for a screenshot as PNG (9 September 2026, the table is in
#: docs/DESCRIBER.md); twelve of those is under five megabytes, and even at
#: a megabyte each, which a dense screenshot can reach, twelve is sixteen
#: megabytes once base64 adds its third on the wire, under the twenty
#: megabyte ceiling Gemini and OpenAI publish for pictures sent inline, with
#: room for a long document's text. The byte budget catches the dense case.
#: Over either cap, the first pictures go and the answer says so.
PICTURE_CAP = 12
PAYLOAD_BUDGET_KB = 12 * 1024

#: A very long document is sent in part. Thirty thousand words is about
#: forty thousand tokens, inside every provider's window with room for the
#: pictures; a book is described from its first thirty thousand words and
#: the answer says so.
WORD_CAP = 30000

#: Where each provider says what it does with what is sent. Read on
#: 9 September 2026; policies change, and docs/DESCRIBER.md says what each
#: one said that day.
POLICY_URLS = {
    "anthropic": "https://www.anthropic.com/legal/commercial-terms",
    "openai": "https://developers.openai.com/api/docs/guides/your-data",
    "google": "https://ai.google.dev/gemini-api/terms",
}

#: The short name each provider is known by in a sentence about its policy.
_SHORT_NAMES = {"anthropic": "Anthropic", "openai": "OpenAI",
                "google": "Google"}

#: What has been agreed to this session. Only "image" is ever remembered;
#: a document asks every time, so it is never added.
_consented = set()


def key_for(provider):
    """The stored key for a provider, or an empty string. One place, so a
    test can stand in a key without storing anything."""
    try:
        return secrets.fetch(provider, secrets.VISION_PREFIX) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Consent, which is a decision and not a formality
# ---------------------------------------------------------------------------

def consent_needed(kind, imported, pictures):
    """Whether to ask before this leaves.

    "document": every time. "image" from the user's own disk: once per
    session. An image that arrived inside an imported document
    (`imported` True), and any batch (`pictures` above one): every time.
    Anything this file does not recognise asks, because asking too often
    is a nuisance and not asking is a breach.
    """
    kind = (kind or "").strip().lower()
    if kind != "image":
        return True
    if imported:
        return True
    try:
        if int(pictures or 0) > 1:
            return True
    except (TypeError, ValueError):
        return True
    return "image" not in _consented


def record_consent(kind):
    """Remember a yes, for the one case that is remembered."""
    if (kind or "").strip().lower() == "image":
        _consented.add("image")


def reset_consent():
    """Forget every yes. A new session starts here; tests use it too."""
    _consented.clear()


def _size_words(kilobytes):
    try:
        kilobytes = float(kilobytes)
    except (TypeError, ValueError):
        kilobytes = 0.0
    if kilobytes >= 1024:
        return "about %.1f MB" % (kilobytes / 1024.0)
    return "about %d KB" % int(round(kilobytes))


def _policy_sentence(provider):
    who = _SHORT_NAMES.get(provider, provider)
    return ("Before sending anything private, check what %s says it does "
            "with what it receives; the address of its data policy is in "
            "Easy PDF's guide, DESCRIBER.md, and it is %s"
            % (who, POLICY_URLS.get(provider, "on the provider's own site")))


def consent_question(kind, provider, pictures, words, kilobytes, imported,
                     document_name=""):
    """What to put in front of somebody before anything leaves.

    Names the provider, the count and the size, and ends with the one
    sentence about the provider's data policy. Every wording here is in
    docs/STRINGS.md for Tony to approve.
    """
    kind = (kind or "").strip().lower()
    who = ai.PROVIDER_NAMES.get(provider, provider)
    size = _size_words(kilobytes)
    try:
        pictures = int(pictures or 0)
    except (TypeError, ValueError):
        pictures = 0
    try:
        words = int(words or 0)
    except (TypeError, ValueError):
        words = 0
    if kind == "document":
        what = ("the whole of %s" % document_name) if document_name \
            else "your whole document"
        # The size said is the size that goes: only the first WORD_CAP words
        # are sent, and `pictures` is the number that will really go.
        wtext = ("about {:,} words".format(words) if words <= WORD_CAP
                 else "the first {:,} of its {:,} words".format(WORD_CAP, words))
        if pictures == 0:
            count = wtext + " and no pictures"
        elif pictures == 1:
            count = wtext + " and one picture"
        elif pictures > PICTURE_CAP:
            count = wtext + " and the first {} of its {} pictures".format(PICTURE_CAP, pictures)
        else:
            count = wtext + " and {} pictures".format(pictures)
        return ("This sends %s to %s, over the internet, so it can be "
                "described to you: %s, %s. The description comes back as "
                "text for you to read; nothing is written into your "
                "document. %s. Send the document?"
                % (what, who, count, size, _policy_sentence(provider)))
    if pictures > 1:
        return ("This sends %d pictures to %s, over the internet, %s, so "
                "they can be described for you. A batch of pictures asks "
                "every time. Each description comes back for you to read "
                "and change before anything goes into your document. %s. "
                "Send the pictures?"
                % (pictures, who, size, _policy_sentence(provider)))
    if imported:
        return ("This sends one picture to %s, over the internet, %s, so "
                "it can be described for you. The picture came in with a "
                "document that was imported, so Easy PDF asks every time "
                "before any of it leaves this machine. The description "
                "comes back for you to read and change before anything "
                "goes into your document. %s. Send the picture?"
                % (who, size, _policy_sentence(provider)))
    return ("This sends one picture to %s, over the internet, %s, so it "
            "can be described for you. The description comes back for you "
            "to read and change before anything goes into your document. "
            "You will not be asked again for pictures from your own files "
            "until Easy PDF is next opened. %s. Send the picture?"
            % (who, size, _policy_sentence(provider)))


# ---------------------------------------------------------------------------
# Reading the document: an outline the model can follow, and the counts
# ---------------------------------------------------------------------------

_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_LABELS = {"p": "Paragraph", "li": "List item", "blockquote": "Quotation",
           "figcaption": "Caption", "pre": "Preformatted text",
           "dt": "Term", "dd": "Definition"}
_LINK_MARK = re.compile(r"\(link to [^)]*\)")


class _Outline(HTMLParser):
    """The document as numbered, labelled lines: each heading with its
    level, each paragraph, each list item, each picture with the
    description it already has, each link with its address, each table
    row. Written so that somebody reading the model's answer can tie every
    remark back to a place in the document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.headings = []
        self.words = 0
        self.pictures = 0
        self._label = None
        self._buffer = []
        self._skip = 0
        self._link = None
        self._row = None
        self._row_header = False
        self._table_rows = 0
        self._table_cols = 0

    # -- helpers ----------------------------------------------------------
    def _text(self):
        return " ".join("".join(self._buffer).split())

    def _flush(self):
        text = self._text()
        if text:
            self.words += len(_LINK_MARK.sub("", text).split())
            label = self._label or "Text"
            self.lines.append("%s: %s" % (label, text))
            if label.startswith("Heading level "):
                self.headings.append((int(label[-1]), text))
        self._buffer = []
        self._label = None

    # -- tags -------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self._skip += 1
            return
        if self._skip:
            return
        a = dict(attrs)
        if tag in _HEADINGS:
            self._flush()
            self._label = "Heading level %d" % _HEADINGS[tag]
        elif tag in _LABELS:
            if (tag == "p" and self._label in ("List item", "Quotation",
                                                "Caption", "Definition")
                    and not self._text()):
                return
            self._flush()
            self._label = _LABELS[tag]
        elif tag == "img":
            self._flush()
            self.pictures += 1
            self.lines.append(self._picture_line(a))
        elif tag == "a":
            self._link = (a.get("href") or "").strip()
        elif tag == "br":
            self._buffer.append(" ")
        elif tag == "table":
            self._flush()
            self._table_rows = 0
            self._table_cols = 0
            self.lines.append("Table starts.")
        elif tag == "tr":
            self._flush()
            self._row = []
            self._row_header = False
        elif tag in ("th", "td"):
            self._flush()
            if self._row is None:
                self._row = []
            if tag == "th":
                self._row_header = True
        elif tag in ("div", "section", "article", "ul", "ol", "figure",
                     "hr"):
            self._flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "a":
            if self._link and not self._link.lower().startswith("data:"):
                self._buffer.append(" (link to %s)" % self._link[:120])
            self._link = None
        elif tag in ("th", "td"):
            if self._row is not None:
                self._row.append(self._text())
                self._buffer = []
                self._label = None
        elif tag == "tr":
            if self._row is not None:
                self._flush()
                cells = [c for c in self._row]
                self._table_rows += 1
                self._table_cols = max(self._table_cols, len(cells))
                self.lines.append(("Header row: " if self._row_header
                                   else "Row: ") + ", ".join(cells))
                self._row = None
        elif tag == "table":
            self._flush()
            self.lines.append("Table ends, %d rows and %d columns."
                              % (self._table_rows, self._table_cols))
        elif tag in _HEADINGS or tag in _LABELS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        self._buffer.append(data)

    def _picture_line(self, a):
        number = self.pictures
        alt = a.get("alt")
        role = (a.get("role") or "").lower()
        hidden = (a.get("aria-hidden") or "").lower() == "true"
        source = (a.get("data-alt-source") or "").lower()
        if alt is not None and not alt.strip() and (
                role == "presentation" or role == "none" or hidden):
            return "Picture %d, marked decorative, no description." % number
        if alt is None or not alt.strip():
            return "Picture %d, no description." % number
        line = "Picture %d, described as: %s" % (number, " ".join(alt.split()))
        if source.startswith("ai:"):
            line += (" (this description was written by AI and has not "
                     "been checked by a sighted person)")
        elif source:
            line += " (this description was recovered from a file and " \
                    "has not been checked)"
        return line

    def close(self):
        super().close()
        self._flush()


def analyse(body_html):
    """The outline, the headings, the word count and the picture count."""
    parser = _Outline()
    try:
        parser.feed(body_html or "")
        parser.close()
    except Exception:
        # A malformed file is still a document. Whatever was read is used.
        try:
            parser._flush()
        except Exception:
            pass
    return parser


def outline(body_html):
    """The document as labelled lines, one per block."""
    return "\n".join(analyse(body_html).lines)


def headings(body_html):
    """`[(level, text), ...]` in document order."""
    return list(analyse(body_html).headings)


def word_count(body_html):
    return analyse(body_html).words


_DATA_IMG = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*([\"'])\s*data:(image/[A-Za-z0-9.+-]+)"
    r"(?:;[^,\"']*)?;base64,([^\"']*)\1", re.IGNORECASE | re.DOTALL)
_ANY_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)


def pictures_in(body_html):
    """The bytes of every picture in the document, in order, with None
    where a picture's source is not embedded and so cannot be sent."""
    out = []
    for tag in _ANY_IMG.findall(body_html or ""):
        found = _DATA_IMG.search(tag)
        if not found:
            out.append(None)
            continue
        try:
            out.append(base64.b64decode(re.sub(r"\s+", "", found.group(3))))
        except Exception:
            out.append(None)
    return out


def _select(images):
    """Which pictures go, as `[(number, (mime, data)), ...]`, and the
    numbers of the ones that stay behind, split by reason.

    The first `PICTURE_CAP` that can be prepared, within
    `PAYLOAD_BUDGET_KB`. Every picture is prepared before it is counted, so
    the size said in the consent question is the size that really goes.
    """
    chosen = []
    over_cap = []
    over_budget = []
    unreadable = []
    total_kb = 0.0
    for number, raw in enumerate(images or [], 1):
        if len(chosen) >= PICTURE_CAP:
            over_cap.append(number)
            continue
        prepared = ai.prepare_picture(raw) if raw else None
        if prepared is None:
            unreadable.append(number)
            continue
        kilobytes = len(prepared[1]) / 1024.0
        if chosen and total_kb + kilobytes > PAYLOAD_BUDGET_KB:
            over_budget.append(number)
            continue
        total_kb += kilobytes
        chosen.append((number, prepared))
    return chosen, over_cap, over_budget, unreadable


def _images_or_embedded(body_html, images):
    """What the caller passed, or the document's own embedded pictures when
    the caller passed nothing."""
    if images:
        return list(images)
    return pictures_in(body_html)


def payload_estimate(body_html, images):
    """`(words, pictures, kilobytes)`: what a document description would
    send. `pictures` is the document's count; `kilobytes` is the size of
    the ones that would actually go, prepared, plus the text."""
    read = analyse(body_html)
    images = _images_or_embedded(body_html, images)
    chosen, _cap, _budget, _bad = _select(images)
    text = "\n".join(read.lines)
    kilobytes = ai.sent_kilobytes([p for _n, p in chosen], text)
    return read.words, len(images), kilobytes


# ---------------------------------------------------------------------------
# What is asked, which is most of whether the answer is any use
# ---------------------------------------------------------------------------

_ALT_COMMON = """You are writing the alternative text for one picture in a \
document. The person who will use your words is blind and cannot see the \
picture, so they cannot check what you write against it. Be accurate, be \
plain, and if something is unclear say that it is unclear rather than \
guessing.

Start with the subject itself: never with "image of", "picture of", "photo \
of", "this shows" or "the picture". Read out every number and every word \
that appears in the picture, exactly as written. If it is a chart, a graph \
or a diagram, say what it means: what is compared, the biggest and the \
smallest values, and the direction of any trend. Give the colours of a \
simple graphic, a logo, a flag or anything where colour is the point; \
otherwise do not spend words on colour, style or decoration. Plain \
sentences, no markdown, no headings, no bullet characters, no quotation \
marks around the whole answer, and nothing before or after the \
description itself."""

_ALT_SHORT = _ALT_COMMON + """

Write one or two sentences saying what the picture shows and what it is \
for in the document."""

_ALT_LONG = _ALT_COMMON + """

Write one paragraph of up to about a hundred and fifty words. First one \
sentence saying what the picture is and what it is for in the document, \
then the detail a reader would otherwise miss: every number, label and \
word in it, exactly as written; the layout, from top to bottom and from \
left to right; and for a chart, a graph, a diagram or a table, what it \
means, including what the arrows or lines connect."""

_ALT_CONTEXT = """

Where the picture sits in the document, so the description fits it:
"""

_DOCUMENT = """You are describing a whole document to its reader, who is \
blind and cannot see it. They will hear your answer read aloud, so write \
plain spoken sentences: no markdown, no headings, no bullet characters, no \
tables, no numbered lists. Nothing you write is checked against the \
document by a sighted person, so be accurate, and say when you are unsure.

The document's text follows at the end of this message, with its structure \
marked: each heading is given with its level, each picture is marked where \
it appears with its number and any description it already has, each link \
is given with its address, and each table row is given in order. The \
pictures themselves are attached to this message in the same order, \
numbered to match.

Answer in this order, as short paragraphs.

First, what the document is, in one or two sentences: its kind, its \
subject, and who it seems to be for.

Second, its structure: the headings in order, each with its level, said as \
sentences. If there are no headings, say so.

Third, each picture by number: what it shows, and where the document \
already gives a description, whether that description is accurate and \
complete.

Fourth, anything an accessibility check would flag, saying where each one \
is: a heading level that is skipped, a first heading that is not level \
one, a link whose text says only click here or here or read more or shows \
a bare address, a picture with no description, a picture whose description \
is wrong or empty, a table with no header row, and text that seems to be \
in a different language from the rest. If nothing needs flagging, say so \
in one sentence.

Do not pad, do not compliment the document, and do not say "appears to be" \
where you can say what is there."""


def alt_prompt(context="", long=False):
    """The question for one picture. `context` is the heading the picture
    sits under and the paragraph before it, from the editor."""
    prompt = _ALT_LONG if long else _ALT_SHORT
    context = (context or "").strip()
    if context:
        prompt += _ALT_CONTEXT + context
    return prompt


def document_prompt(body_html, pictures_total=None, sent=None,
                    unreadable=None, truncated_words=0):
    """The question for a whole document, outline included.

    `sent` is the list of picture numbers attached; `pictures_total` the
    document's count. When they differ, the prompt says which pictures are
    missing, so the model neither invents them nor misnumbers the rest.
    """
    read = analyse(body_html)
    lines = list(read.lines)
    if truncated_words:
        lines = _first_words(lines, truncated_words)
    total = read.pictures if pictures_total is None else pictures_total
    sent = list(sent) if sent is not None else list(range(1, total + 1))
    parts = [_DOCUMENT]
    if total == 0:
        parts.append("\nThe document has no pictures.")
    elif len(sent) == total:
        parts.append("\nAll %d of the document's pictures are attached, in "
                     "order." % total if total > 1
                     else "\nThe document's one picture is attached.")
    else:
        parts.append("\nThe document has %d pictures. Only these are "
                     "attached, in this order: %s. The others were not "
                     "sent; say that they were not described rather than "
                     "guessing at them." % (total, _numbers(sent)))
    if unreadable:
        parts.append("\nPicture%s %s could not be read by the program that "
                     "sent this, so %s not attached."
                     % ("" if len(unreadable) == 1 else "s",
                        _numbers(unreadable),
                        "it is" if len(unreadable) == 1 else "they are"))
    if truncated_words:
        parts.append("\nThe document is long, so only its first {:,} words "
                     "are given.".format(truncated_words))
    parts.append("\nThe document:\n")
    parts.append("\n".join(lines) if lines else "(The document has no text.)")
    return "\n".join(parts)


def _numbers(numbers):
    numbers = [str(n) for n in numbers]
    if len(numbers) <= 1:
        return "".join(numbers)
    return ", ".join(numbers[:-1]) + " and " + numbers[-1]


def _first_words(lines, limit):
    """The outline cut after `limit` words of text. The labels in front of
    each line ("Paragraph:", "Heading level 2:") are not counted, so the
    cap means words the author wrote."""
    kept = []
    count = 0
    for line in lines:
        label, sep, text = line.partition(": ")
        if not sep:
            label, text = "", line
        words = text.split()
        if count + len(words) > limit:
            room = max(0, limit - count)
            if room:
                kept.append((label + sep if sep else "") + " ".join(words[:room]))
            break
        kept.append(line)
        count += len(words)
    return kept


# ---------------------------------------------------------------------------
# Doing it
# ---------------------------------------------------------------------------

_LEADING = re.compile(
    r"^(?:(?:an?|the|this)\s+)?(?:image|picture|photo|photograph|"
    r"illustration|graphic|screenshot)\s+(?:of|showing|shows|depicting)\s+",
    re.IGNORECASE)
_LABEL = re.compile(r"^(?:alt(?:ernative)? text|description)\s*:\s*",
                    re.IGNORECASE)


def tidy_alt(text, long=False):
    """The model's answer made fit for an alt attribute: no wrapping
    quotes, no "Alt text:" label, no "image of" opener, and for the short
    form no line breaks at all."""
    text = (text or "").strip()
    text = _LABEL.sub("", text)
    if len(text) > 1 and text[0] in "\"'“‘" and text[-1] in "\"'”’":
        text = text[1:-1].strip()
    if text.startswith("*") and text.endswith("*"):
        text = text.strip("*").strip()
    stripped = _LEADING.sub("", text, count=1)
    if stripped and stripped != text:
        text = stripped[0].upper() + stripped[1:]
    if long:
        return "\n".join(" ".join(line.split()) for line in text.splitlines()
                         if line.strip())
    return " ".join(text.split())


def describe_image(image_bytes, provider, model, context="", long=False):
    """One picture, one description. Returns `(ok, text)`, never raises.

    The key is read from Windows Credential Manager here, so a dialog never
    handles it. The picture is scaled before it goes, as `ai.prepare_picture`
    says. Consent is the dialog's job and has already been given when this
    is called.
    """
    if not image_bytes:
        return False, "There is no picture to describe."
    provider = (provider or "").strip().lower()
    key = key_for(provider)
    if not key:
        return False, ("No key has been set up for %s yet. Put one in on "
                       "the AI page of Preferences, then try again."
                       % ai.PROVIDER_NAMES.get(provider, provider))
    prepared = ai.prepare_picture(image_bytes)
    if prepared is None:
        return False, ("The picture could not be prepared for sending, so "
                       "nothing has left this machine. It may be a kind of "
                       "picture file Easy PDF cannot read.")
    ok, text = ai.ask([prepared], alt_prompt(context, long), provider, key,
                      model, timeout=ai.TIMEOUT, max_tokens=ai.IMAGE_TOKENS)
    if not ok:
        return False, text
    text = tidy_alt(text, long)
    if not text:
        return False, ("%s answered, but with nothing that could be used "
                       "as a description." % ai.PROVIDER_NAMES.get(provider,
                                                                   provider))
    return True, text


def _say(progress, text):
    if progress is None:
        return
    try:
        progress(text)
    except Exception:
        pass


def describe_document(body_html, images, provider, model, progress=None):
    """A whole document described. Returns `(ok, text)`, never raises.

    `images` is one entry of bytes per `img` in `body_html`, in document
    order, or nothing, in which case the document's own embedded pictures
    are used. `progress` is called with a sentence at each step, from
    whatever thread this runs on; the dialog hops to the window itself.
    """
    provider = (provider or "").strip().lower()
    who = ai.PROVIDER_NAMES.get(provider, provider)
    key = key_for(provider)
    if not key:
        return False, ("No key has been set up for %s yet. Put one in on "
                       "the AI page of Preferences, then try again." % who)
    _say(progress, "Reading the document.")
    read = analyse(body_html)
    if not read.lines:
        return False, "The document is empty, so there is nothing to describe."
    images = _images_or_embedded(body_html, images)
    if images:
        _say(progress, "Preparing %d picture%s." % (len(images),
                                                     "" if len(images) == 1
                                                     else "s"))
    chosen, over_cap, over_budget, unreadable = _select(images)
    truncated = read.words if read.words > WORD_CAP else 0
    prompt = document_prompt(body_html, pictures_total=len(images),
                             sent=[n for n, _p in chosen],
                             unreadable=unreadable,
                             truncated_words=WORD_CAP if truncated else 0)
    pictures = [p for _n, p in chosen]
    kilobytes = ai.sent_kilobytes(pictures, prompt)
    _say(progress, "Sending the document to %s: about %s words, %d "
         "picture%s, %s. This can take a minute."
         % (who, "{:,}".format(min(read.words, WORD_CAP)), len(pictures),
            "" if len(pictures) == 1 else "s", _size_words(kilobytes)))
    ok, text = ai.ask(pictures, prompt, provider, key, model,
                      timeout=ai.DOCUMENT_TIMEOUT,
                      max_tokens=ai.DOCUMENT_TOKENS)
    if not ok:
        return False, text
    notes = []
    left = sorted(over_cap + over_budget)
    if left:
        notes.append("Only %d of the document's %d pictures were sent, so "
                     "pictures %s are not described."
                     % (len(pictures), len(images), _numbers(left)))
    if unreadable:
        notes.append("Picture%s %s could not be read and %s not sent."
                     % ("" if len(unreadable) == 1 else "s",
                        _numbers(unreadable),
                        "was" if len(unreadable) == 1 else "were"))
    if truncated:
        notes.append("The document has about {:,} words and only the first "
                     "{:,} were sent.".format(read.words, WORD_CAP))
    if notes:
        text = text.rstrip() + "\n\n" + " ".join(notes)
    return True, text


# ---------------------------------------------------------------------------
# The key TG Drop Deck already has
# ---------------------------------------------------------------------------

def copy_drop_deck_key(provider, source_prefix=DROP_DECK_PREFIX,
                       target_prefix=None):
    """Read the key TG Drop Deck keeps for this provider and keep a copy
    under Easy PDF's own name. Nothing is sent anywhere. Returns
    `(ok, sentence)`; the sentence never contains the key."""
    provider = (provider or "").strip().lower()
    who = ai.PROVIDER_NAMES.get(provider, provider)
    if target_prefix is None:
        target_prefix = secrets.VISION_PREFIX
    try:
        found = secrets.fetch(provider, source_prefix)
    except Exception:
        found = ""
    if not found:
        return False, ("TG Drop Deck has no key for %s on this machine, so "
                       "there is nothing to copy." % who)
    try:
        kept = secrets.store(provider, found, target_prefix)
    except Exception:
        kept = False
    if not kept:
        return False, ("The %s key was found, but Windows Credential "
                       "Manager would not keep a copy for Easy PDF. Paste "
                       "the key into the box instead." % who)
    return True, ("The %s key from TG Drop Deck is now kept for Easy PDF as "
                  "well, %s." % (who, secrets.redact(found)))
