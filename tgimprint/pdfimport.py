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
the Nth img in body order. A page with no text at all is a scanned page;
there is no OCR in this release, and the result says so.

Nothing here touches wx or prints.
"""

import html
import re
from collections import Counter
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pikepdf

from . import docfile, pdfcheck

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
MSG_PASSWORD = "This PDF is protected by a password, so it cannot be opened."
MSG_NOT_PDF = "That file is not a PDF."
MSG_CANNOT_OPEN = "The PDF could not be opened. %s"
MSG_SCANNED = ("This PDF is pictures of text. Nothing could be read from it, and TG Imprint "
               "has no text recognition in this release. Run OCR in another program first.")
MSG_SOME_SCANNED = ("%s no text and may be pictures of text. TG Imprint has no text "
                    "recognition in this release.")
MSG_TAGGED = ("This PDF is tagged. Its headings and lists are re-created here from the "
              "text layout, not from its tags, so check them.")
MSG_ALT_RECOVERED = "%s recovered from the PDF's tags. Check each one in Pictures."
MSG_ALT_MISMATCH = ("The PDF's tags hold picture descriptions that could not be matched to "
                    "the pictures on page %s, so they were not used.")
MSG_PROGRESS = "Reading page %d of %d"


class PdfImportError(Exception):
    """The message is a sentence a user can act on."""


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


# ---------------------------------------------------------- the tree pass ---


def _tree_pass(path):
    """(tagged, figure alts per page index, lang, xmp title, image marks
    per page index). The marks are pdfcheck's [(object number, drawn
    inside tagged content)] per page, in drawing order."""
    alts = {}
    marks = {}
    tagged = False
    lang = ""
    title = ""
    try:
        pdf = pikepdf.open(path)
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


def import_pdf(path, progress=None):
    """See the module docstring."""
    try:
        doc = fitz.open(path)
    except Exception as exc:
        message = str(exc)
        if "password" in message.lower() or "encrypt" in message.lower():
            raise PdfImportError(MSG_PASSWORD)
        raise PdfImportError(MSG_CANNOT_OPEN % message)
    try:
        if doc.needs_pass:
            raise PdfImportError(MSG_PASSWORD)
        if not doc.is_pdf:
            raise PdfImportError(MSG_NOT_PDF)
        return _import_open(doc, path, progress)
    finally:
        doc.close()


def _import_open(doc, path, progress):
    warnings = []
    tagged, tree_alts, tree_lang, tree_title, tree_marks = _tree_pass(path)
    if tagged:
        warnings.append(MSG_TAGGED)
    page_count = doc.page_count

    # First pass: text blocks, pictures and sizes for every page.
    pages = []
    size_counts = Counter()
    for number in range(page_count):
        if progress is not None:
            try:
                progress(MSG_PROGRESS % (number + 1, page_count))
            except Exception:
                pass
        page = doc[number]
        try:
            text = page.get_text("dict")
        except Exception:
            text = {"blocks": []}
        blocks = [b for b in text.get("blocks", []) if b.get("type") == 0]
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
        pages.append({"blocks": blocks, "links": links,
                      "pictures": _page_pictures(doc, page, tree_marks.get(number, ())),
                      "shapes": _bullet_shapes(page)})

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
        if not blocks and pictures:
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
        for pic_index, picture in enumerate(pictures):
            items.append((picture[0], 1, "picture", (pic_index, picture)))
        # Text keeps its content order; a picture goes before the first
        # block that starts below it.
        ordered = []
        text_items = [i for i in items if i[2] == "block"]
        picture_items = sorted((i for i in items if i[2] == "picture"), key=lambda i: i[0])
        for item in text_items:
            while picture_items and picture_items[0][0] <= item[0]:
                ordered.append(picture_items.pop(0))
            ordered.append(item)
        ordered.extend(picture_items)

        for _y0, _order, kind, payload in ordered:
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

    body_html = builder.html()
    # Every page is pictures with no text at all: the body holds only the
    # figures, and there is nothing a screen reader could read.
    is_scanned = bool(page_count) and len(scanned_pages) == page_count
    if is_scanned:
        warnings.append(MSG_SCANNED)
    elif scanned_pages:
        warnings.append(MSG_SOME_SCANNED % (_n(len(scanned_pages), "page has", "pages have")))
    if recovered:
        warnings.append(MSG_ALT_RECOVERED % _n(recovered, "picture description was",
                                                "picture descriptions were"))
    if mismatched_pages:
        warnings.append(MSG_ALT_MISMATCH % ", ".join(mismatched_pages[:8]))

    info = doc.metadata or {}
    meta = {
        "title": (tree_title or info.get("title") or "").strip(),
        "author": (info.get("author") or "").strip(),
        "subject": (info.get("subject") or "").strip(),
        "lang": tree_lang,
        "source_kind": "pdf",
        "pages": page_count,
        "tagged": tagged,
    }
    return ImportResult(body_html=body_html, meta=meta, images=images,
                        warnings=warnings, is_scanned=is_scanned)


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
