"""The document check: what would stop this document being accessible, found
while it is still being written.

    check(body_html, meta) -> [Issue]
    Issue: key, severity ("fix" or "review"), message, kind, ordinal

pdfcheck reads a finished file. This reads the editor's HTML, so it can run
as often as the side panel wants and can say where each thing is: `kind` and
`ordinal` name the Nth heading, picture, link or table in the document, in
the terms the editor's own jump uses. A document-wide issue has an empty
kind.

"fix" is what stops the PDF/UA identifier; "review" is what a careful author
would want to look at and a program cannot decide.

Nothing here touches wx or prints.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# docs/STRINGS.md, 0.3.0.
MSG_NO_TITLE = "The document has no title. Set one in Document properties."
MSG_NO_LANG = "The document has no language. Set one in Document properties."
MSG_NO_HEADINGS = "The document has no headings, so nobody can move through it by heading."
MSG_FIRST_HEADING = "The first heading, \"%s\", is level %d. Make it level 1."
MSG_SKIP = "The heading \"%s\" is level %d after a level %d heading."
MSG_EMPTY_HEADING = "Heading %d has no text."
MSG_PICTURE = "Picture %d has no description."
MSG_AI_PICTURE = "Picture %d has a description written by AI that nobody has checked."
MSG_RECOVERED_PICTURE = "Picture %d has a description from the original PDF that nobody has checked."
MSG_LINK_TEXT = "The link \"%s\" does not say where it goes."
MSG_LINK_EMPTY = "Link %d has no text."
MSG_LINK_ADDRESS = "Link %d shows a web address rather than words."
MSG_TABLE_HEADER = "Table %d has no header row."
MSG_TABLE_CAPTION = "Table %d has no caption."
MSG_LONG_CAPS = "A paragraph is written in capitals, which some voices spell out: \"%s\"."

_VAGUE = frozenset(("click here", "here", "link", "read more", "more", "this", "this link",
                    "learn more", "details"))
_ADDRESS = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_VOID = frozenset(("br", "hr", "img"))


@dataclass
class Issue:
    key: str
    severity: str
    message: str
    kind: str = ""
    ordinal: int = 0


def _short(text, limit=40):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


class _Reader(HTMLParser):
    """Headings, pictures, links, tables and paragraph text, in order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []
        self.pictures = []
        self.links = []
        self.tables = []
        self.paragraphs = []
        self.collect = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in _HEADINGS:
            self._begin(("heading", _HEADINGS[tag]))
        elif tag == "p" and self.collect is None:
            self._begin(("paragraph", 0))
        elif tag == "a":
            self.link_at = len(self.buffer)
            self.link_collect = []
        elif tag == "img":
            self.pictures.append(attrs)
        elif tag == "table":
            self.tables.append({"th": 0, "caption": False})
        elif tag == "th" and self.tables:
            self.tables[-1]["th"] += 1
        elif tag == "caption" and self.tables:
            self.tables[-1]["caption"] = True

    def handle_endtag(self, tag):
        if tag == "a" and getattr(self, "link_collect", None) is not None:
            self.links.append("".join(self.link_collect))
            self.link_collect = None
        if self.collect and ((tag in _HEADINGS and self.collect[0] == "heading")
                             or (tag == "p" and self.collect[0] == "paragraph")):
            text = "".join(self.buffer)
            if self.collect[0] == "heading":
                self.headings.append((self.collect[1], text))
            else:
                self.paragraphs.append(text)
            self.collect = None
            self.buffer = []

    def handle_data(self, data):
        if self.collect is not None:
            self.buffer.append(data)
        if getattr(self, "link_collect", None) is not None:
            self.link_collect.append(data)

    def _begin(self, what):
        self.collect = what
        self.buffer = []


def check(body_html, meta=None):
    meta = meta or {}
    reader = _Reader()
    try:
        reader.feed(body_html or "")
        reader.close()
    except Exception:
        pass
    issues = []
    if not str(meta.get("title") or "").strip():
        issues.append(Issue("title", "fix", MSG_NO_TITLE))
    if not str(meta.get("lang") or "").strip():
        issues.append(Issue("lang", "fix", MSG_NO_LANG))
    words = sum(len(p.split()) for p in reader.paragraphs)
    if not reader.headings and words > 120:
        issues.append(Issue("no_headings", "review", MSG_NO_HEADINGS))
    previous = 0
    for number, (level, text) in enumerate(reader.headings, 1):
        if not text.strip():
            issues.append(Issue("empty_heading", "fix", MSG_EMPTY_HEADING % number, "heading", number))
            continue
        if level > previous + 1:
            if previous == 0:
                issues.append(Issue("first_heading", "fix", MSG_FIRST_HEADING % (_short(text), level),
                                    "heading", number))
            else:
                issues.append(Issue("heading_skip", "fix", MSG_SKIP % (_short(text), level, previous),
                                    "heading", number))
        previous = level
    for number, attrs in enumerate(reader.pictures, 1):
        needs = "data-needs-alt" in attrs
        alt = (attrs.get("alt") or "").strip()
        source = attrs.get("data-alt-source") or ""
        if not alt and (needs or "alt" not in attrs):
            issues.append(Issue("picture", "fix", MSG_PICTURE % number, "picture", number))
        elif source.startswith("ai"):
            issues.append(Issue("ai_picture", "review", MSG_AI_PICTURE % number, "picture", number))
        elif source == "pdf" and needs:
            issues.append(Issue("recovered_picture", "review", MSG_RECOVERED_PICTURE % number,
                                "picture", number))
    for number, text in enumerate(reader.links, 1):
        plain = re.sub(r"\s+", " ", text).strip()
        lowered = plain.lower().rstrip(".!")
        if not plain:
            issues.append(Issue("link_empty", "fix", MSG_LINK_EMPTY % number, "link", number))
        elif lowered in _VAGUE:
            issues.append(Issue("link_vague", "review", MSG_LINK_TEXT % plain, "link", number))
        elif _ADDRESS.match(plain):
            issues.append(Issue("link_address", "review", MSG_LINK_ADDRESS % number, "link", number))
    for number, table in enumerate(reader.tables, 1):
        if not table["th"]:
            issues.append(Issue("table_header", "fix", MSG_TABLE_HEADER % number, "table", number))
        if not table["caption"]:
            issues.append(Issue("table_caption", "review", MSG_TABLE_CAPTION % number, "table", number))
    for text in reader.paragraphs:
        letters = [c for c in text if c.isalpha()]
        if len(letters) > 40 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.9:
            issues.append(Issue("caps", "review", MSG_LONG_CAPS % _short(text)))
            break
    return issues
