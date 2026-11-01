"""A PDF somebody sent, turned into editor HTML so it can be made
accessible (DECISIONS.md decision 3 and edit A6).

    import_pdf(path, progress=None) -> ImportResult
    ImportResult: body_html, meta, images, warnings, is_scanned
    ImportedImage: id, png_bytes, width, height, page, alt, alt_source
    PdfImportError: the file cannot be opened; the message is a sentence

PyMuPDF reads the text blocks in content order. Headings come from
ranking the font sizes that appear: the largest distinct sizes above the
body size become h1, h2 and h3, and a short bold line at body size is h4.
Lines are joined into paragraphs, a hyphen at a line end is healed, a
paragraph continues across a page when the sentence does, bullets and
numbering are recognised into ul and ol (Chromium draws its bullet as a
small shape, not a character, so a small filled shape just left of an
indented line counts), pictures are extracted, downscaled through
docfile.embed_image and placed where they sat, links come from the page's
link annotations, and the title, author and language go into meta.

Before that, one pass with pikepdf over the structure tree when there is
one: if the PDF is tagged, a warning says its structure is re-created from
the layout here, and each page's Figure Alt strings are attached to that
page's pictures only when the counts match, marked data-alt-source="pdf"
and still data-needs-alt="1" so Pictures lists them as recovered and to
be checked. A picture drawn outside tagged content (an artifact, or a
decorative picture, which Chromium draws outside any marked content) is
left out of that count, so it never breaks the match for the described
picture beside it (Overseer round 2, defect 6). Full tree aware import is
out of 1.0.0 (docs/PDF-UA.md).

Every picture that arrives here needs a description: the img carries
alt="" and data-needs-alt="1", and ImportedImage.id is "picture-N" for
the Nth img in body order. A page with no text at all is a scanned page,
and a page whose text reads back as symbols is garbled: both are read by
text recognition (pdfocr), locally, with one warning that says how many
pages, because recognised text can be wrong. Without the language data the
old sentence about pictures of text stands.

0.3.0 adds what a real document needs (docs/RESEARCH-2026-11.md). A damaged
file is repaired through pdfrepair and the repair is said out loud. A good
tagged PDF is read from its tags, not re-guessed (_tree_html), and falls
back to the layout when the tree covers too little of the page text. A
ruled table comes back as a table with a header row. A line repeated at the
top or bottom of the pages is a running header or footer and is left out,
with a warning. Two columns are read down one and then the next. Headings
are renumbered so the first is level 1 and none is skipped.

Nothing here touches wx or prints.
"""

import html
import re
from collections import Counter
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pikepdf

from . import docfile, pdfcheck, pdfocr, pdfrepair
from .pdfrepair import PdfPasswordError  # noqa: F401  re-exported for callers

MIN_IMAGE_SIDE = 24
HEADING_RATIO = 1.15
SHORT_LINE = 80
#: Bullet, white bullet, black small square, black circle, white circle,
#: black square, triangular bullet, hyphen bullet, middle dot, asterisk,
#: en dash, em dash and hyphen, as escapes so no dash character and
#: nothing invisible sits in the source.
BULLET_CHARS = "\u2022\u25e6\u25aa\u25cf\u25cb\u25a0\u2023\u2043\u00b7*\u2013\u2014-"
_BULLET_RE = re.compile("^[%s]\\s+" % re.escape(BULLET_CHARS))
_NUMBER_RE = re.compile(r"^\(?(\d{1,3}|[a-zA-Z]|[ivxIVX]{1,6})[.)]\s+")
_END_RE = re.compile(r"[.!?:;\"”’)\]]\s*$")

# docs/STRINGS.md, Worker A.
MSG_PASSWORD = pdfrepair.MSG_PASSWORD
MSG_NOT_PDF = pdfrepair.MSG_NOT_PDF
MSG_SCANNED = ("This PDF is pictures of text, and nothing could be read from it. The text "
               "recognition data is missing from this copy of TG Imprint.")
MSG_SOME_SCANNED = ("%s no text and may be pictures of text. The text recognition data is "
                    "missing from this copy of TG Imprint.")
MSG_DECORATIVE = "%s marked as decoration in the PDF left out."
MSG_FIELDS = ("This PDF has %s. Bringing it in here removes them, so the PDF you export "
              "cannot be filled in. To keep them, use Fill in a PDF form instead.")
MSG_CONTROL = "%s that no font could show removed."
MSG_TAGGED = ("This PDF is tagged. Its headings and lists are re-created here from the "
              "text layout, not from its tags, so check them.")
MSG_ALT_RECOVERED = "%s recovered from the PDF's tags. Check each one in Pictures."
MSG_ALT_MISMATCH = ("The PDF's tags hold picture descriptions that could not be matched to "
                    "the pictures on page %s, so they were not used.")
MSG_PROGRESS = "Reading page %d of %d"
MSG_OCR_PROGRESS = "Recognising the text on page %d of %d"
MSG_OCR_DONE = ("%s read by text recognition. Check names, numbers and dates against "
                "somebody who can see the page, because recognition can get them wrong.")
MSG_GARBLED = ("%s text that reads back as symbols rather than letters, and no text "
               "recognition is available here, so it may read as nonsense.")
MSG_TREE = ("This PDF is tagged, and its headings, lists and tables were read from its "
            "tags. Check them.")
MSG_FURNITURE = "%s repeated on the pages left out as a running header or footer."
MSG_NOTHING = "This PDF has no text and no pictures on any page."
MSG_TABLES = ("%s rebuilt from the lines on the page, with the first row as the header row. "
              "Check that the first row really is one.")
#: A picture this much of the page, on a page recognition has read, is the
#: page itself.
PAGE_PICTURE_SHARE = 0.75
#: The tags are used when they hold at least this much of the page text.
TREE_COVERAGE = 0.85
#: A line counts as running furniture when it sits in the top or bottom
#: tenth of at least this share of the pages, and of at least two.
FURNITURE_SHARE = 0.5
FURNITURE_MARGIN = 0.10
#: What XML, and so a Word file, cannot hold, and no font draws.
_CONTROL_RE = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\x9f]")


@dataclass
class ImportedImage:
    id: str
    png_bytes: bytes
    width: int
    height: int
    page: int
    alt: str = ""
    alt_source: str = ""


@dataclass
class ImportResult:
    body_html: str
    meta: dict
    images: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    is_scanned: bool = False


def _n(count, one, many):
    return ("1 " + one) if count == 1 else ("%d " % count) + many


#: Kept for callers. The message is a sentence a user can act on.
PdfImportError = pdfrepair.PdfOpenError


# ---------------------------------------------------------- the tree pass ---


def _tree_pass(path, password=""):
    """(tagged, figure alts per page index, lang, xmp title, image marks
    per page index). The marks are pdfcheck's [(object number, drawn
    inside tagged content)] per page, in drawing order."""
    alts = {}
    marks = {}
    tagged = False
    lang = ""
    title = ""
    try:
        pdf = pikepdf.open(path, password=password)
    except Exception:
        return tagged, alts, lang, title, marks
    try:
        try:
            lang = str(pdf.Root.get("/Lang", "") or "").strip()
        except Exception:
            lang = ""
        try:
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                title = str(meta.get("dc:title") or "").strip()
        except Exception:
            title = ""
        index = pdfcheck.TextIndex(pdf)
        elements = pdfcheck.walk_tree(pdf, index)
        tagged = bool(elements)
        if tagged:
            for number in range(len(pdf.pages)):
                try:
                    marks[number] = index.image_marks(number)
                except Exception:
                    marks[number] = []
        for elem in elements:
            if elem.kind != "/Figure":
                continue
            alt = ""
            try:
                alt = str(elem.obj.get("/Alt", "") or "").strip()
            except Exception:
                alt = ""
            page = elem.page if elem.page is not None else -1
            alts.setdefault(page, []).append(alt)
    finally:
        pdf.close()
    return tagged, alts, lang, title, marks


# ---------------------------------------------------------------- pictures ---


def _extract_image(doc, xref):
    """PNG or JPEG bytes for an image xref, with its soft mask applied."""
    try:
        info = doc.extract_image(xref)
    except Exception:
        info = None
    if info and info.get("ext") in ("png", "jpeg", "jpg") and not info.get("smask"):
        return info["image"]
    try:
        pix = fitz.Pixmap(doc, xref)
        if info and info.get("smask"):
            try:
                mask = fitz.Pixmap(doc, info["smask"])
                pix = fitz.Pixmap(pix, mask)
            except Exception:
                pass
        if pix.n - pix.alpha >= 4 or pix.colorspace is None:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return pix.tobytes("png")
    except Exception:
        return None


def _page_pictures(doc, page, marks=()):
    """[(y0, x0, width, height, bytes, untagged, content_index)] for the
    pictures worth keeping on a page, in drawing order. untagged is True
    when the content stream drew the picture outside tagged content (an
    artifact, or nothing marked at all); content_index counts the tagged
    pictures in order and is None for an untagged one, so the tree's Alt
    strings line up with the pictures the tree describes. With no marks
    (an untagged PDF) every picture counts as tagged, and the caller has
    no Alt strings to attach anyway."""
    out = []
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        infos = []
    # The same image object can be drawn more than once; each drawing
    # takes the next flag recorded for that object.
    flags = {}
    for objnum, in_tagged in marks:
        flags.setdefault(objnum, []).append(in_tagged)
    content_count = 0
    for info in infos:
        xref = info.get("xref", 0)
        untagged = not bool(flags[xref].pop(0)) if flags.get(xref) else False
        width, height = int(info.get("width", 0)), int(info.get("height", 0))
        if not xref or width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
            continue
        bbox = info.get("bbox") or (0, 0, 0, 0)
        if (bbox[2] - bbox[0]) < 6 or (bbox[3] - bbox[1]) < 6:
            continue
        data = _extract_image(doc, xref)
        if not data:
            continue
        content_index = None
        if not untagged:
            content_index = content_count
            content_count += 1
        out.append((float(bbox[1]), float(bbox[0]), width, height, data, untagged, content_index))
    return out


# -------------------------------------------------------------- the text ---


def _span_format(span):
    flags = span.get("flags", 0)
    return (bool(flags & 16), bool(flags & 2), bool(flags & 8), bool(flags & 1))


def _link_for(span, links):
    x0, y0, x1, y1 = span["bbox"]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for rect, uri in links:
        if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1:
            return uri
    return ""


def _line_html(line, links, heading):
    """Inline HTML for one line: spans merged by formatting and link."""
    pieces = []
    for span in line.get("spans", []):
        text = span.get("text", "")
        if not text:
            continue
        bold, italic, mono, superscript = _span_format(span)
        uri = _link_for(span, links)
        pieces.append([text, bold and not heading, italic, mono, superscript, uri])
    merged = []
    for piece in pieces:
        if merged and merged[-1][1:] == piece[1:]:
            merged[-1][0] += piece[0]
        else:
            merged.append(piece)
    out = []
    for text, bold, italic, mono, superscript, uri in merged:
        chunk = html.escape(text, quote=False)
        if superscript:
            chunk = "<sup>%s</sup>" % chunk
        if mono:
            chunk = "<code>%s</code>" % chunk
        if italic:
            chunk = "<em>%s</em>" % chunk
        if bold:
            chunk = "<strong>%s</strong>" % chunk
        if uri:
            chunk = '<a href="%s">%s</a>' % (html.escape(uri, quote=True), chunk)
        out.append(chunk)
    return "".join(out)


def _line_text(line):
    return "".join(span.get("text", "") for span in line.get("spans", []))


def _join_lines(parts):
    """Lines of one paragraph joined, hyphenation at a line end healed."""
    text = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not text:
            text = part
            continue
        plain_end = re.sub(r"<[^>]+>", "", text)
        plain_start = re.sub(r"<[^>]+>", "", part)
        if plain_end.endswith("-") and plain_start[:1].islower():
            text = text[:-1] + part if text.endswith("-") else re.sub(r"-(<[^>]+>)*$", r"\1", text) + part
        else:
            text += " " + part
    return text


def _bullet_shapes(page):
    """Small filled shapes, as (x0, y0, x1, y1), which is how Chromium
    draws a list bullet (measured: the bullet is not in the text)."""
    shapes = []
    try:
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None or drawing.get("fill") is None:
                continue
            if rect.width <= 8 and rect.height <= 8 and rect.width > 0.5 and rect.height > 0.5:
                shapes.append((rect.x0, rect.y0, rect.x1, rect.y1))
    except Exception:
        pass
    return shapes


def _shape_before(line, shapes):
    """A small filled shape just left of the line, overlapping it
    vertically: a drawn bullet."""
    x0, y0, x1, y1 = line["bbox"]
    for sx0, sy0, sx1, sy1 in shapes:
        if x0 - 30 <= sx1 <= x0 + 1 and sy1 >= y0 and sy0 <= y1:
            return True
    return False


class _Builder:
    """Collects blocks in order and writes the body."""

    def __init__(self):
        self.blocks = []       # (kind, payload)
        self.pending = None    # a body paragraph that may continue

    def flush(self):
        if self.pending is not None:
            self.blocks.append(("p", self.pending))
            self.pending = None

    def paragraph(self, inline):
        plain = re.sub(r"<[^>]+>", "", inline).strip()
        if not plain:
            return
        if self.pending is not None:
            previous = re.sub(r"<[^>]+>", "", self.pending)
            if not _END_RE.search(previous) and plain[:1].islower():
                self.pending = self.pending + " " + inline
                return
            self.flush()
        self.pending = inline

    def block(self, kind, payload):
        self.flush()
        self.blocks.append((kind, payload))

    def list_item(self, tag, inline):
        self.flush()
        if self.blocks and self.blocks[-1][0] == "list" and self.blocks[-1][1][0] == tag:
            self.blocks[-1][1][1].append(inline)
        else:
            self.blocks.append(("list", (tag, [inline])))

    def html(self):
        self.flush()
        out = []
        for kind, payload in self.blocks:
            if kind == "p":
                out.append("<p>%s</p>" % payload)
            elif kind == "h":
                level, inline = payload
                out.append("<h%d>%s</h%d>" % (level, inline, level))
            elif kind == "list":
                tag, items = payload
                out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % i for i in items), tag))
            elif kind == "figure":
                out.append(payload)
        return "\n".join(out)


# ---------------------------------------------------------------- import ---


def _size_key(size):
    return round(float(size) * 2) / 2.0


def _has_page_image(page):
    try:
        return bool(page.get_images())
    except Exception:
        return False


def _picture_area(page, picture):
    """The drawn area of a picture from _page_pictures, from its image size
    scaled to the page: the bbox is not kept in the tuple."""
    try:
        for info in page.get_image_info():
            bbox = info.get("bbox")
            if bbox and abs(float(bbox[1]) - picture[0]) < 0.5 and abs(float(bbox[0]) - picture[1]) < 0.5:
                return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    except Exception:
        pass
    return 0.0


def _level_sizes(blocks, target=None):
    """Recognised text reports a size per line that wanders by a point or
    two, which would rank every line as its own heading level, and a scale
    of its own, which would rank a scanned page above the typed page beside
    it. Lines near the page's commonest size all become that size, or
    target when the document has typed pages to match; a line well above
    it keeps its proportion."""
    sizes = Counter()
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                sizes[round(span.get("size", 0))] += len(span.get("text", ""))
    if not sizes:
        return
    body = sizes.most_common(1)[0][0]
    target = float(target or body)
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("size", 0) < body * 1.3:
                    span["size"] = target
                else:
                    span["size"] = span.get("size", 0) * target / body


def import_pdf(path, progress=None, password="", ocr=True):
    """See the module docstring. ocr=False keeps every page as it is read,
    for a caller that wants to know what is really in the file."""
    with pdfrepair.open_readable(path, password) as opened:
        result = _import_open(opened.doc, opened.path, progress, password, ocr)
        result.body_html, removed = _CONTROL_RE.subn("", result.body_html)
        if removed:
            result.warnings.append(MSG_CONTROL % _n(removed, "character", "characters"))
        fields = _field_count(opened.doc)
        result.meta["form_fields"] = fields
        if fields:
            result.warnings.insert(0, MSG_FIELDS % _n(fields, "form field", "form fields"))
        result.warnings[:0] = opened.notes
        return result


def _field_count(doc):
    count = 0
    for number in range(doc.page_count):
        try:
            count += sum(1 for _widget in doc[number].widgets())
        except Exception:
            pass
    return count


def _reading_order(blocks, width):
    """Text blocks in reading order. Content order is kept unless the page
    has a clear gutter, because a producer's own order is usually right and
    this is a guess. With a gutter, each run between full width blocks is
    read down the left column and then the right."""
    narrow = [b for b in blocks if (b["bbox"][2] - b["bbox"][0]) < width * 0.55]
    if len(narrow) < 2:
        return blocks
    middle = width / 2.0
    left = [b for b in narrow if b["bbox"][2] <= middle + 12]
    right = [b for b in narrow if b["bbox"][0] >= middle - 12]
    if not left or not right or len(left) + len(right) != len(narrow):
        return blocks
    bands = []
    current = []
    for block in sorted(blocks, key=lambda b: b["bbox"][1]):
        if (block["bbox"][2] - block["bbox"][0]) >= width * 0.55:
            if current:
                bands.append(current)
                current = []
            bands.append([block])
        else:
            current.append(block)
    if current:
        bands.append(current)
    out = []
    for band in bands:
        out.extend(sorted((b for b in band if b["bbox"][0] < middle - 12),
                          key=lambda b: b["bbox"][1]))
        out.extend(sorted((b for b in band if b["bbox"][0] >= middle - 12),
                          key=lambda b: b["bbox"][1]))
    return out


def _furniture_key(text):
    """A running line with its page number taken out."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text)).strip().lower()


def _find_furniture(pages):
    """The keys of lines repeated in the margins of the pages."""
    count = len(pages)
    if count < 2:
        return set()
    seen = Counter()
    for page in pages:
        keys = set()
        height = page["height"]
        for block in page["blocks"]:
            y0, y1 = block["bbox"][1], block["bbox"][3]
            if y1 <= height * FURNITURE_MARGIN or y0 >= height * (1 - FURNITURE_MARGIN):
                for line in block.get("lines", []):
                    key = _furniture_key(_line_text(line))
                    if key and len(key) < 90:
                        keys.add(key)
        seen.update(keys)
    needed = max(2, int(count * FURNITURE_SHARE + 0.5))
    return {key for key, number in seen.items() if number >= needed}


def _drop_furniture(page, furniture, words):
    """Take the repeated lines out of the page's blocks, adding the first
    few to words so a reader can tell nothing real went. Returns how many."""
    dropped = 0
    height = page["height"]
    kept = []
    for block in page["blocks"]:
        y0, y1 = block["bbox"][1], block["bbox"][3]
        if y1 <= height * FURNITURE_MARGIN or y0 >= height * (1 - FURNITURE_MARGIN):
            lines = []
            for line in block.get("lines", []):
                if _furniture_key(_line_text(line)) in furniture:
                    text = re.sub(r"\s+", " ", _line_text(line)).strip()
                    if len(words) < 3 and _furniture_key(text) not in map(_furniture_key, words):
                        words.append(text)
                else:
                    lines.append(line)
            dropped += len(block.get("lines", [])) - len(lines)
            if not lines:
                continue
            block = dict(block, lines=lines)
        kept.append(block)
    page["blocks"] = kept
    return dropped


def _page_tables(page):
    """[(bbox, rows)] for tables drawn with ruled lines. Only ruled ones: a
    text-only guess turns ordinary paragraphs into tables."""
    try:
        # Finding tables costs a tenth of a second a page even on a page of
        # plain text, and a table needs at least four ruled edges.
        if len(page.get_cdrawings()) < 4:
            return []
        finder = page.find_tables(strategy="lines")
    except Exception:
        return []
    out = []
    for table in getattr(finder, "tables", []):
        try:
            rows = table.extract()
        except Exception:
            continue
        rows = [[re.sub(r"\s+", " ", c or "").strip() for c in row] for row in rows]
        if len(rows) >= 2 and rows[0] and len(rows[0]) >= 2:
            out.append((tuple(table.bbox), rows))
    return out


def _table_html(rows):
    head = "".join('<th scope="col">%s</th>' % html.escape(c, quote=False) for c in rows[0])
    body = []
    for row in rows[1:]:
        body.append("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(c, quote=False) for c in row))
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, "".join(body))


def _block_inside(block, tables):
    x0, y0, x1, y1 = block["bbox"]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b, _rows in tables)


def _renumber_headings(body):
    """The first heading level 1 and none skipped: the levels here came
    from ranking font sizes, so a gap means nothing about the document."""
    levels = sorted({int(m) for m in re.findall(r"<h([1-6])>", body)})
    if not levels:
        return body
    mapping = {level: index + 1 for index, level in enumerate(levels)}
    return re.sub(r"(</?h)([1-6])>", lambda m: "%s%d>" % (m.group(1), mapping[int(m.group(2))]), body)


# ---------------------------------------------------------- from the tags ---


class _TreeReader:
    """Body HTML from a structure tree, in tree order. A wrapper element is
    walked through; anything with a meaning becomes that element."""

    GROUPS = ("/Document", "/Part", "/Art", "/Sect", "/Div", "/NonStruct", "/Private",
              "/THead", "/TBody", "/TFoot", "/TOC", "/Index")
    INLINE = ("/Span", "/Strong", "/Em", "/Code", "/Link", "/Quote", "/Reference", "/Note",
              "/Lbl", "/NonStruct", "/Private", "/Annot", "/BibEntry")

    def __init__(self, pdf, doc, index, role_map):
        self.pdf = pdf
        self.doc = doc
        self.index = index
        self.role_map = role_map
        self.pictures = 0
        self.images = []
        self.tables = 0
        self.seen = set()
        self.chars = 0

    def kind(self, obj):
        return pdfcheck._resolve_kind(str(obj.get("/S", "")), self.role_map)

    def raw_kind(self, obj):
        return str(obj.get("/S", ""))

    def page_of(self, obj, page):
        pg = obj.get("/Pg")
        if pg is not None:
            found = self.index.index_of_page(pg)
            if found is not None:
                return found
        return page

    def kids(self, obj, page):
        """(kind, value, page) children in tree order: "mc" with an mcid,
        "el" with a structure element, "ob" with an annotation."""
        page = self.page_of(obj, page)
        kids = obj.get("/K")
        if kids is None:
            return []
        items = list(kids) if isinstance(kids, pikepdf.Array) else [kids]
        out = []
        for item in items:
            if isinstance(item, pikepdf.Dictionary):
                kind = str(item.get("/Type", ""))
                if kind == "/MCR":
                    try:
                        out.append(("mc", int(item.MCID), self.page_of(item, page)))
                    except Exception:
                        pass
                elif kind == "/OBJR":
                    out.append(("ob", item.get("/Obj"), self.page_of(item, page)))
                else:
                    key = item.objgen
                    if key in self.seen:
                        continue
                    if key != (0, 0):
                        self.seen.add(key)
                    out.append(("el", item, page))
            else:
                try:
                    out.append(("mc", int(item), page))
                except Exception:
                    pass
        return out

    def link_of(self, obj, page):
        for kind, value, _page in self.kids_peek(obj, page):
            if kind == "ob" and isinstance(value, pikepdf.Dictionary):
                try:
                    action = value.get("/A")
                    if isinstance(action, pikepdf.Dictionary) and "/URI" in action:
                        return str(action.URI)
                except Exception:
                    pass
        return ""

    def kids_peek(self, obj, page):
        kids = obj.get("/K")
        items = list(kids) if isinstance(kids, pikepdf.Array) else ([kids] if kids is not None else [])
        out = []
        for item in items:
            if isinstance(item, pikepdf.Dictionary) and str(item.get("/Type", "")) == "/OBJR":
                out.append(("ob", item.get("/Obj"), page))
        return out

    def inline(self, obj, page):
        """Inline HTML for an element's own content and inline children."""
        pieces = []
        for kind, value, kid_page in self.kids(obj, page):
            if kind == "mc":
                if kid_page is None:
                    continue
                text = self.index.text(kid_page, value)
                self.chars += len(text.strip())
                pieces.append(html.escape(text, quote=False))
            elif kind == "el":
                role = self.kind(value)
                raw = self.raw_kind(value)
                inner = self.inline(value, kid_page)
                if not inner.strip():
                    continue
                if raw == "/Strong":
                    inner = "<strong>%s</strong>" % inner
                elif raw == "/Em":
                    inner = "<em>%s</em>" % inner
                elif role == "/Code":
                    inner = "<code>%s</code>" % inner
                elif role == "/Link":
                    uri = self.link_of(value, kid_page)
                    if uri:
                        inner = '<a href="%s">%s</a>' % (html.escape(uri, quote=True), inner)
                pieces.append(inner)
        return re.sub(r"\s+", " ", "".join(pieces))

    def blocks(self, obj, page, out):
        """Walk block level content into out."""
        for kind, value, kid_page in self.kids(obj, page):
            if kind == "mc":
                if kid_page is None:
                    continue
                text = self.index.text(kid_page, value).strip()
                if text:
                    self.chars += len(text)
                    out.append("<p>%s</p>" % html.escape(text, quote=False))
                continue
            if kind != "el":
                continue
            self.element(value, kid_page, out)

    def element(self, obj, page, out):
        role = self.kind(obj)
        if role in pdfcheck.HEADING_NAMES:
            text = self.inline(obj, page).strip()
            if text:
                level = pdfcheck.HEADING_NAMES[role]
                out.append("<h%d>%s</h%d>" % (level, text, level))
        elif role == "/H":
            text = self.inline(obj, page).strip()
            if text:
                out.append("<h2>%s</h2>" % text)
        elif role in ("/P", "/Caption", "/TOCI", "/BibEntry", "/Note", "/Code", "/Span",
                      "/Strong", "/Em", "/Link", "/Reference", "/Quote", "/Formula"):
            if role == "/P" and self._has_blocks(obj, page):
                self.blocks(obj, page, out)
                return
            text = self.inline(obj, page).strip()
            if text:
                out.append("<p>%s</p>" % text)
        elif role == "/L":
            out.append(self.list_html(obj, page))
        elif role == "/Table":
            out.append(self.table_html(obj, page))
        elif role == "/BlockQuote":
            inner = []
            self.blocks(obj, page, inner)
            out.append("<blockquote>%s</blockquote>" % "".join(inner))
        elif role == "/Figure":
            out.append(self.figure_html(obj, page))
        elif role == "/Form":
            pass
        else:
            self.blocks(obj, page, out)

    def _has_blocks(self, obj, page):
        kids = obj.get("/K")
        items = list(kids) if isinstance(kids, pikepdf.Array) else ([kids] if kids is not None else [])
        for item in items:
            if isinstance(item, pikepdf.Dictionary) and self.kind(item) in ("/L", "/Table", "/Figure"):
                return True
        return False

    def list_html(self, obj, page):
        items = []
        ordered = False
        for kind, value, kid_page in self.kids(obj, page):
            if kind != "el" or self.kind(value) != "/LI":
                if kind == "el" and self.kind(value) == "/L":
                    items.append("<li>%s</li>" % self.list_html(value, kid_page))
                continue
            pieces = []
            nested = []
            for sub_kind, sub, sub_page in self.kids(value, kid_page):
                if sub_kind != "el":
                    if sub_kind == "mc" and sub_page is not None:
                        pieces.append(html.escape(self.index.text(sub_page, sub), quote=False))
                    continue
                role = self.kind(sub)
                if role == "/Lbl":
                    label = re.sub(r"<[^>]+>", "", self.inline(sub, sub_page)).strip()
                    if re.match(r"^\(?(\d+|[a-zA-Z]|[ivxIVX]+)[.)]", label):
                        ordered = True
                elif role == "/LBody":
                    self._body_of_item(sub, sub_page, pieces, nested)
                elif role == "/L":
                    nested.append(self.list_html(sub, sub_page))
                else:
                    pieces.append(self.inline(sub, sub_page))
            items.append("<li>%s%s</li>" % (re.sub(r"\s+", " ", "".join(pieces)).strip(), "".join(nested)))
        tag = "ol" if ordered else "ul"
        return "<%s>%s</%s>" % (tag, "".join(items), tag)

    def _body_of_item(self, body, page, pieces, nested):
        for kind, value, kid_page in self.kids(body, page):
            if kind == "mc":
                if kid_page is not None:
                    text = self.index.text(kid_page, value)
                    self.chars += len(text.strip())
                    pieces.append(html.escape(text, quote=False))
            elif kind == "el":
                role = self.kind(value)
                if role == "/L":
                    nested.append(self.list_html(value, kid_page))
                elif role == "/P":
                    pieces.append(self.inline(value, kid_page))
                else:
                    wrapped = self.inline(value, kid_page)
                    if self.raw_kind(value) == "/Strong":
                        wrapped = "<strong>%s</strong>" % wrapped
                    elif self.raw_kind(value) == "/Em":
                        wrapped = "<em>%s</em>" % wrapped
                    elif role == "/Link":
                        uri = self.link_of(value, kid_page)
                        if uri:
                            wrapped = '<a href="%s">%s</a>' % (html.escape(uri, quote=True), wrapped)
                    pieces.append(wrapped)

    def table_html(self, obj, page):
        rows = []
        caption = ""

        def collect(node, node_page):
            nonlocal caption
            for kind, value, kid_page in self.kids(node, node_page):
                if kind != "el":
                    continue
                role = self.kind(value)
                if role == "/TR":
                    rows.append(self.row(value, kid_page))
                elif role == "/Caption":
                    caption = self.inline(value, kid_page).strip()
                elif role in ("/THead", "/TBody", "/TFoot", "/Div", "/Sect", "/NonStruct"):
                    collect(value, kid_page)

        collect(obj, page)
        self.tables += 1
        head = "<caption>%s</caption>" % caption if caption else ""
        return "<table>%s%s</table>" % (head, "".join(rows))

    def row(self, obj, page):
        cells = []
        for kind, value, kid_page in self.kids(obj, page):
            if kind != "el":
                continue
            role = self.kind(value)
            if role not in ("/TH", "/TD"):
                continue
            tag = "th" if role == "/TH" else "td"
            spans = ""
            attributes = value.get("/A")
            if isinstance(attributes, pikepdf.Dictionary):
                for key, name in (("/ColSpan", "colspan"), ("/RowSpan", "rowspan")):
                    try:
                        number = int(attributes.get(key, 1))
                    except Exception:
                        number = 1
                    if number > 1:
                        spans += ' %s="%d"' % (name, number)
            inner = []
            self.blocks_inline(value, kid_page, inner)
            cells.append("<%s%s>%s</%s>" % (tag, spans, " ".join(inner), tag))
        return "<tr>%s</tr>" % "".join(cells)

    def blocks_inline(self, obj, page, out):
        text = self.inline(obj, page).strip()
        if text:
            out.append(text)

    def figure_html(self, obj, page):
        alt = ""
        try:
            alt = str(obj.get("/Alt", "") or "").strip() or str(obj.get("/ActualText", "") or "").strip()
        except Exception:
            alt = ""
        objnum = None
        for kind, value, kid_page in self.kids(obj, page):
            if kind == "mc" and kid_page is not None:
                objnum = self.index.page(kid_page)["image_mcids"].get(value, objnum)
                if objnum is not None:
                    page = kid_page
                    break
        if objnum is None:
            if alt:
                return "<p>%s</p>" % html.escape(alt, quote=False)
            return ""
        data = _extract_image(self.doc, objnum)
        if not data:
            return ""
        try:
            embedded = docfile.embed_image(data)
        except ValueError:
            return ""
        self.pictures += 1
        try:
            as_png = embedded.png_bytes()
        except Exception:
            as_png = b""
        self.images.append(ImportedImage(
            id="picture-%d" % self.pictures, png_bytes=as_png, width=embedded.width,
            height=embedded.height, page=(page or 0) + 1, alt=alt, alt_source="pdf" if alt else ""))
        if alt:
            return ('<figure><img src="%s" alt="%s" data-alt-source="pdf" data-needs-alt="1"></figure>'
                    % (embedded.data_uri, html.escape(alt, quote=True)))
        return '<figure><img src="%s" alt="" data-needs-alt="1"></figure>' % embedded.data_uri


def _tree_html(path, doc, password):
    """(body, images, tables) from the tags, or None when the tree holds
    too little of the page text to be trusted."""
    try:
        pdf = pikepdf.open(path, password=password)
    except Exception:
        return None
    try:
        page_chars = 0
        for number in range(doc.page_count):
            page_chars += len("".join(doc[number].get_text().split()))
        if not page_chars:
            return None
        index = pdfcheck.TextIndex(pdf)
        reader = _TreeReader(pdf, doc, index, pdfcheck._role_map(pdf.Root))
        out = []
        reader.blocks(pdf.Root.StructTreeRoot, None, out)
        body = "\n".join(piece for piece in out if piece)
        tree_chars = len("".join(re.sub(r"<[^>]+>", "", body).split()))
        if tree_chars < page_chars * TREE_COVERAGE or tree_chars > page_chars * 1.3:
            return None
        return body, reader.images, reader.tables
    except Exception:
        return None
    finally:
        pdf.close()


def _say(progress, text):
    if progress is not None:
        try:
            progress(text)
        except Exception:
            pass


def _meta_for(doc, tree_title, tree_lang, tagged, body):
    info = doc.metadata or {}
    title = (tree_title or info.get("title") or "").strip()
    if not title:
        found = re.search(r"<h1>(.*?)</h1>", body, re.DOTALL)
        if found:
            title = re.sub(r"<[^>]+>", "", found.group(1)).strip()
    lang = tree_lang
    if not lang:
        guessed = pdfocr.guess_language(re.sub(r"<[^>]+>", " ", body))
        lang = {"es": "es", "en": "en-US"}.get(guessed, "")
    return {
        "title": title,
        "author": (info.get("author") or "").strip(),
        "subject": (info.get("subject") or "").strip(),
        "lang": lang,
        "source_kind": "pdf",
        "pages": doc.page_count,
        "tagged": tagged,
    }


def _import_open(doc, path, progress, password="", ocr=True):
    warnings = []
    tagged, tree_alts, tree_lang, tree_title, tree_marks = _tree_pass(path, password)
    page_count = doc.page_count
    if tagged:
        for number in range(page_count):
            _say(progress, MSG_PROGRESS % (number + 1, page_count))
        from_tree = _tree_html(path, doc, password)
        if from_tree is not None:
            body, tree_images, table_count = from_tree
            warnings.append(MSG_TREE)
            decorative = sum(1 for marks in tree_marks.values() for _o, inside in marks if not inside)
            if decorative:
                warnings.append(MSG_DECORATIVE % _n(decorative, "picture", "pictures"))
            needing = sum(1 for image in tree_images if image.alt)
            if needing:
                warnings.append(MSG_ALT_RECOVERED % _n(needing, "picture description was",
                                                        "picture descriptions were"))
            return ImportResult(body_html=_renumber_headings(body),
                                meta=_meta_for(doc, tree_title, tree_lang, tagged, body),
                                images=tree_images, warnings=warnings, is_scanned=False)
        warnings.append(MSG_TAGGED)

    # First pass: text blocks, pictures and sizes for every page.
    pages = []
    size_counts = Counter()
    ocr_ok = ocr and pdfocr.available()
    language = pdfocr.language_for(tree_lang)
    recognised = []
    garbled = []
    table_total = 0
    for number in range(page_count):
        _say(progress, MSG_PROGRESS % (number + 1, page_count))
        page = doc[number]
        try:
            text = page.get_text("dict")
        except Exception:
            text = {"blocks": []}
        blocks = [b for b in text.get("blocks", []) if b.get("type") == 0]
        plain = "".join(s.get("text", "") for b in blocks for l in b.get("lines", [])
                        for s in l.get("spans", []))
        is_garbled = bool(plain.strip()) and pdfcheck.text_quality(plain) >= pdfcheck.GARBLED_RATIO
        needs_ocr = is_garbled or (not plain.strip() and _has_page_image(page))
        if needs_ocr and ocr_ok:
            _say(progress, MSG_OCR_PROGRESS % (number + 1, page_count))
            try:
                read = pdfocr.page_dict(page, language)
                blocks = [b for b in read.get("blocks", []) if b.get("type") == 0]
                recognised.append(number + 1)
            except Exception:
                needs_ocr = False
        elif is_garbled:
            garbled.append(number + 1)
        tables = _page_tables(page) if number not in recognised else []
        if tables:
            blocks = [b for b in blocks if not _block_inside(b, tables)]
            table_total += len(tables)
        blocks = _reading_order(blocks, page.rect.width)
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size_counts[_size_key(span.get("size", 0))] += len(span.get("text", "").strip())
        links = []
        try:
            for link in page.get_links():
                if link.get("kind") == fitz.LINK_URI and link.get("uri"):
                    links.append((fitz.Rect(link["from"]), link["uri"]))
        except Exception:
            links = []
        pictures = _page_pictures(doc, page, tree_marks.get(number, ()))
        if (number + 1) in recognised:
            area = max(1.0, page.rect.width * page.rect.height)
            pictures = [p for p in pictures if _picture_area(page, p) / area < PAGE_PICTURE_SHARE]
        pages.append({"blocks": blocks, "links": links, "pictures": pictures,
                      "shapes": _bullet_shapes(page), "height": page.rect.height,
                      "tables": tables})

    if recognised:
        native = Counter()
        for number, page_data in enumerate(pages):
            if (number + 1) not in recognised:
                for block in page_data["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            native[_size_key(span.get("size", 0))] += len(span.get("text", "").strip())
        target = native.most_common(1)[0][0] if native else None
        for number in recognised:
            _level_sizes(pages[number - 1]["blocks"], target)
    furniture = _find_furniture(pages)
    dropped = 0
    furniture_words = []
    if furniture:
        for page_data in pages:
            dropped += _drop_furniture(page_data, furniture, furniture_words)
    size_counts = Counter()
    for page_data in pages:
        for block in page_data["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size_counts[_size_key(span.get("size", 0))] += len(span.get("text", "").strip())

    body_size = size_counts.most_common(1)[0][0] if size_counts else 0.0
    heading_sizes = sorted((s for s in size_counts if body_size and s >= body_size * HEADING_RATIO),
                           reverse=True)
    heading_level = {}
    for index, size in enumerate(heading_sizes):
        heading_level[size] = min(index + 1, 3)

    builder = _Builder()
    images = []
    scanned_pages = []
    recovered = 0
    mismatched_pages = []
    picture_number = 0

    for number, page_data in enumerate(pages):
        blocks = page_data["blocks"]
        pictures = page_data["pictures"]
        if not blocks and pictures and not page_data["tables"] and (number + 1) not in recognised:
            scanned_pages.append(number + 1)
        page_alts = tree_alts.get(number, []) if tagged else []
        described = [p for p in pictures if p[6] is not None]
        alts_match = bool(page_alts) and len(page_alts) == len(described)
        if page_alts and not alts_match:
            mismatched_pages.append(str(number + 1))
        items = []
        for block in blocks:
            y0 = float(block.get("bbox", (0, 0, 0, 0))[1])
            items.append((y0, 0, "block", block))
        for bbox, rows in page_data["tables"]:
            items.append((float(bbox[1]), 1, "table", rows))
        for pic_index, picture in enumerate(pictures):
            items.append((picture[0], 1, "picture", (pic_index, picture)))
        # Text keeps its content order; a picture goes before the first
        # block that starts below it.
        ordered = []
        text_items = [i for i in items if i[2] == "block"]
        picture_items = sorted((i for i in items if i[2] != "block"), key=lambda i: i[0])
        for item in text_items:
            while picture_items and picture_items[0][0] <= item[0]:
                ordered.append(picture_items.pop(0))
            ordered.append(item)
        ordered.extend(picture_items)

        for _y0, _order, kind, payload in ordered:
            if kind == "table":
                builder.block("figure", _table_html(payload))
                continue
            if kind == "picture":
                _pic_index, (py0, px0, width, height, data, _untagged, content_index) = payload
                try:
                    embedded = docfile.embed_image(data)
                except ValueError:
                    continue
                picture_number += 1
                alt = ""
                source = ""
                if alts_match and content_index is not None and page_alts[content_index]:
                    alt = page_alts[content_index]
                    source = "pdf"
                    recovered += 1
                if alt:
                    figure = ('<figure><img src="%s" alt="%s" data-alt-source="pdf" '
                              'data-needs-alt="1"></figure>'
                              % (embedded.data_uri, html.escape(alt, quote=True)))
                else:
                    figure = ('<figure><img src="%s" alt="" data-needs-alt="1"></figure>'
                              % embedded.data_uri)
                builder.block("figure", figure)
                # Guarded, because embed_image above is and this was not.
                # The picture is already in the page as a data URI by this
                # point; this copy exists only so a describer has a PNG to
                # look at. Losing it costs the alt text for one image and
                # nothing else, where raising costs the whole document.
                try:
                    as_png = embedded.png_bytes()
                except Exception:
                    as_png = b""
                images.append(ImportedImage(
                    id="picture-%d" % picture_number, png_bytes=as_png,
                    width=embedded.width, height=embedded.height, page=number + 1,
                    alt=alt, alt_source=source))
                continue
            block = payload
            _emit_block(block, page_data, builder, body_size, heading_level)

    body_html = _renumber_headings(builder.html())
    if recognised:
        warnings.append(MSG_OCR_DONE % _n(len(recognised), "page was", "pages were"))
    if garbled:
        warnings.append(MSG_GARBLED % _n(len(garbled), "page has", "pages have"))
    if dropped:
        warnings.append(MSG_FURNITURE % _n(len(furniture), "line", "lines")
                        + " For example: " + "; ".join(furniture_words) + ".")
    if table_total:
        warnings.append(MSG_TABLES % _n(table_total, "table was", "tables were"))
    # Every page is pictures with no text at all: the body holds only the
    # figures, and there is nothing a screen reader could read.
    is_scanned = bool(page_count) and len(scanned_pages) == page_count
    if is_scanned:
        warnings.append(MSG_SCANNED)
    elif scanned_pages:
        warnings.append(MSG_SOME_SCANNED % (_n(len(scanned_pages), "page has", "pages have")))
    if not re.sub(r"<[^>]+>", "", body_html).strip() and not images:
        warnings.append(MSG_NOTHING)
    if recovered:
        warnings.append(MSG_ALT_RECOVERED % _n(recovered, "picture description was",
                                                "picture descriptions were"))
    if mismatched_pages:
        warnings.append(MSG_ALT_MISMATCH % ", ".join(mismatched_pages[:8]))

    return ImportResult(body_html=body_html,
                        meta=_meta_for(doc, tree_title, tree_lang, tagged, body_html),
                        images=images, warnings=warnings, is_scanned=is_scanned)


def _emit_block(block, page_data, builder, body_size, heading_level):
    lines = block.get("lines", [])
    if not lines:
        return
    links = page_data["links"]
    shapes = page_data["shapes"]
    # The block's dominant size and whether every span is bold.
    sizes = Counter()
    all_bold = True
    for line in lines:
        for span in line.get("spans", []):
            text = span.get("text", "").strip()
            if not text:
                continue
            sizes[_size_key(span.get("size", 0))] += len(text)
            if not (span.get("flags", 0) & 16):
                all_bold = False
    if not sizes:
        return
    size = sizes.most_common(1)[0][0]
    plain = " ".join(_line_text(l).strip() for l in lines).strip()
    level = heading_level.get(size)
    if level is None and all_bold and len(lines) == 1 and len(plain) < SHORT_LINE \
            and not _END_RE.search(plain) and body_size and size >= body_size * 0.95:
        level = 4
    if level is not None and plain:
        builder.block("h", (level, _join_lines(_line_html(l, links, True) for l in lines)))
        return
    # Lists: each marked line starts an item; other lines continue it.
    current_tag = None
    current_lines = []
    paragraph_lines = []

    def close_item():
        nonlocal current_tag, current_lines
        if current_tag and current_lines:
            builder.list_item(current_tag, _join_lines(current_lines))
        current_tag = None
        current_lines = []

    def close_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            builder.paragraph(_join_lines(paragraph_lines))
        paragraph_lines = []

    for line in lines:
        text = _line_text(line)
        stripped = text.lstrip()
        marker = None
        if _BULLET_RE.match(stripped):
            marker = "ul"
            cut = _BULLET_RE.match(stripped).end()
        elif _NUMBER_RE.match(stripped):
            marker = "ol"
            cut = _NUMBER_RE.match(stripped).end()
        elif _shape_before(line, shapes):
            marker = "ul"
            cut = 0
        if marker:
            close_paragraph()
            close_item()
            current_tag = marker
            inline = _line_html(line, links, False)
            if cut:
                inline = _cut_prefix(inline, stripped[:cut])
            current_lines = [inline]
        elif current_tag:
            current_lines.append(_line_html(line, links, False))
        else:
            paragraph_lines.append(_line_html(line, links, False))
    close_item()
    close_paragraph()


def _cut_prefix(inline, prefix):
    """Remove a list marker from the start of an inline string that may
    begin with a tag."""
    escaped = html.escape(prefix.rstrip(), quote=False)
    match = re.match(r"^((?:<[^>]+>)*)\s*" + re.escape(escaped) + r"\s*", inline)
    if match:
        return match.group(1) + inline[match.end():]
    return inline
