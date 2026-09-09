"""The native document, the readers, autosave snapshots, and pictures.

    save(path, body_html, meta) -> warnings   atomic: temp file, then replace
    load(path) -> (body_html, meta)           dispatches on kind_of(path)
    kind_of(path) -> "native" | "html" | "text" | "markdown" | "docx" | "pdf"
    snapshot(body_html, meta, source_path) -> snapshot_path
    recoverable() -> [(snapshot_path, source_path, saved_at, title), ...]
    discard_snapshot(snapshot_path) -> None
    embed_image(source) -> EmbeddedImage

The native document is .epdf (constants.DOC_EXTENSION): self-contained
UTF-8 HTML with the title, author, subject and language in the head, a
generator meta, a small stylesheet so it reads right in a browser, every
picture a data URI, and the body as the one sanitiser left it. "Save as
web page" is the same bytes written to a .html path; save dispatches on
nothing. Rename an .epdf to .html and any browser opens it, so nobody's
writing is ever trapped here (DECISIONS.md decision 3).

Load takes the body of a native or web page, plain text, Markdown
(markdown_in), Word (docx_in) or a PDF (pdfimport), and every one of them
goes through htmlclean.normalise before it reaches the editor. meta always
carries source_kind so the window can say where a document came from, and
meta["warnings"] carries the sentences the readers produced.

Pictures are downscaled on the way in, through embed_image: longest edge
constants.IMAGE_MAX_EDGE, JPEG at constants.IMAGE_JPEG_QUALITY for JPEG
sources, PNG kept for PNG sources (CHALLENGE.md E8: five phone photos made
a 7 MB document at full size; 2,000 pixels across a letter page is still
300 dots per inch).

Nothing here touches wx or prints.
"""

import base64
import datetime
import hashlib
import html
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote

from PIL import Image, ImageOps, UnidentifiedImageError

from . import constants as C
from . import htmlclean, paths

KINDS = {
    ".epdf": "native", ".html": "html", ".htm": "html", ".txt": "text",
    ".md": "markdown", ".markdown": "markdown", ".docx": "docx", ".pdf": "pdf",
}
#: Meta keys that travel in the file head. lang goes on the html element.
HEAD_META = ("author", "subject")
PAGE_META = ("page_size", "margin_inches", "font_family", "font_points")

# docs/STRINGS.md, Worker A.
MSG_NOT_A_PICTURE = ("That file is not a picture Easy PDF can read. PNG, JPEG, GIF, BMP "
                     "and WebP pictures work.")
MSG_TOO_LARGE = ("That picture is too large to open. Pictures over about 178 million "
                 "pixels are refused. Reduce it in another program and insert it again.")
MSG_RTF = ("Easy PDF cannot open RTF. Open it in WordPad, save it as a Word document "
           "or plain text, and open that.")


def msg_reduced(ow, oh, w, h):
    return "Reduced from {:,} by {:,} to {:,} by {:,} pixels.".format(ow, oh, w, h)


# ---------------------------------------------------------------- images ---


@dataclass
class EmbeddedImage:
    data_uri: str
    mime: str
    width: int
    height: int
    original_width: int
    original_height: int
    kilobytes: float
    original_kilobytes: float
    note: str
    data: bytes

    def png_bytes(self):
        """The same picture as PNG, for a describer that wants one."""
        if self.mime == "image/png":
            return self.data
        with Image.open(io.BytesIO(self.data)) as image:
            out = io.BytesIO()
            image.save(out, format="PNG", optimize=True)
            return out.getvalue()


def _read_source(source):
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    with open(source, "rb") as handle:
        return handle.read()


def embed_image(source):
    """Downscale and encode a picture for the document. source is a path or
    the picture's bytes. Raises ValueError with a sentence when it is not a
    picture."""
    raw = _read_source(source)
    original_kb = round(len(raw) / 1024.0, 1)
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Image.DecompressionBombError:
        # Pillow refuses a picture over about 178 million pixels with an
        # exception that is not an OSError, so a hostile picture in a
        # docx or a PDF must not crash the load (Overseer round 2,
        # defect 8).
        raise ValueError(MSG_TOO_LARGE)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError(MSG_NOT_A_PICTURE)
    except Exception:
        raise ValueError(MSG_NOT_A_PICTURE)
    source_format = (image.format or "").upper()
    try:
        transposed = ImageOps.exif_transpose(image)
    except Exception:
        transposed = image
    if transposed is None:
        transposed = image
    changed = transposed is not image and transposed.size != image.size
    image = transposed
    original_width, original_height = image.size
    scaled = False
    if max(image.size) > C.IMAGE_MAX_EDGE:
        image.thumbnail((C.IMAGE_MAX_EDGE, C.IMAGE_MAX_EDGE), Image.LANCZOS)
        scaled = True
    width, height = image.size
    if source_format == "JPEG":
        mime = "image/jpeg"
        if scaled or changed:
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=C.IMAGE_JPEG_QUALITY, optimize=True)
            data = out.getvalue()
        else:
            data = raw
    elif source_format == "PNG" and not scaled and not changed:
        mime = "image/png"
        data = raw
    else:
        mime = "image/png"
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P", "1"):
            image = image.convert("RGBA" if "A" in image.mode else "RGB")
        if image.mode == "P" and "transparency" in image.info:
            image = image.convert("RGBA")
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        data = out.getvalue()
    note = msg_reduced(original_width, original_height, width, height) if scaled else ""
    data_uri = "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
    return EmbeddedImage(data_uri=data_uri, mime=mime, width=width, height=height,
                         original_width=original_width, original_height=original_height,
                         kilobytes=round(len(data) / 1024.0, 1),
                         original_kilobytes=original_kb, note=note, data=data)


def _local_path(src, base_folder):
    """A file system path on this computer for an img src that is not a
    data URI, or None.

    A source on another computer is refused before anything probes it:
    os.path.isfile on a UNC path (two backslashes, two slashes, or the
    device form with a question mark) opens a connection to the named
    host with the user's credentials the moment a received file is
    opened, and a file address with a host does the same (Overseer round
    2, defect 3). The one exception is a document that itself lives on a
    share: a picture inside that document's own folder is on a host the
    user already reached, so it is allowed. The rule is checked again
    after percent decoding, so an encoded UNC path cannot slip through.
    """
    src = (src or "").strip()
    lowered = src.lower()
    if lowered.startswith(("http:", "https:", "data:", "//", "ftp:", "javascript:", "blob:")):
        return None
    if htmlclean.is_network_source(src):
        return None
    if lowered.startswith("file:"):
        # file:///C:/pictures/x.png and file://localhost/C:/pictures/x.png
        # become C:/pictures/x.png; a Unix style file:///home/x.png keeps
        # its leading slash.
        src = re.sub(r"^//localhost(?=/)", "", src[5:], flags=re.IGNORECASE).lstrip("/")
        if not re.match(r"^[A-Za-z]:", src):
            src = "/" + src
    src = unquote(src)
    if htmlclean.is_network_source(src):
        return None
    if not os.path.isabs(src) and base_folder:
        src = os.path.join(base_folder, src)
    resolved = os.path.normpath(src)
    if htmlclean.is_network_source(resolved):
        if not base_folder or not htmlclean.is_network_source(base_folder):
            return None
        base = os.path.normcase(os.path.normpath(base_folder)).rstrip(os.sep) + os.sep
        if not os.path.normcase(resolved).startswith(base):
            return None
    return resolved


def embedder_for(base_folder):
    """The embed callback normalise wants: a local picture becomes a data
    URI, anything else returns None."""
    def embed(src):
        path = _local_path(src, base_folder)
        if not path or not os.path.isfile(path):
            return None
        try:
            return embed_image(path).data_uri
        except ValueError:
            return None
    return embed


# ---------------------------------------------------------- the document ---

DOCUMENT_STYLE = """
body { font-family: Arial, Helvetica, sans-serif; font-size: 12pt; line-height: 1.5; max-width: 42em; margin: 2em auto; padding: 0 1em; color: #000; background: #fff; }
h1 { font-size: 2em; } h2 { font-size: 1.55em; } h3 { font-size: 1.25em; }
p.code-block, pre { font-family: Consolas, "Courier New", monospace; background: #f3f3f3; border: 1px solid #ccc; padding: 0.5em 0.7em; white-space: pre-wrap; }
code { font-family: Consolas, "Courier New", monospace; }
a { color: #0000b4; }
blockquote { margin: 0.6em 0 0.6em 1.5em; padding-left: 0.8em; border-left: 3px solid #888; }
figure { margin: 0.8em 0; text-align: center; }
figure img { max-width: 100%; height: auto; }
figcaption { font-size: 0.9em; color: #333; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #666; padding: 0.3em 0.5em; text-align: left; vertical-align: top; }
th { background: #e8e8e8; }
.align-left { text-align: left; } .align-center { text-align: center; } .align-right { text-align: right; } .align-justify { text-align: justify; }
figure.width-quarter img, img.width-quarter { width: 25%; } figure.width-half img, img.width-half { width: 50%; }
figure.width-three-quarters img, img.width-three-quarters { width: 75%; } figure.width-full img, img.width-full { width: 100%; }
figure.place-left { text-align: left; } figure.place-centre { text-align: center; } figure.place-right { text-align: right; }
"""


def document_html(body_html, meta):
    """The native file's text: a self-contained page around the body."""
    meta = meta or {}
    lang = str(meta.get("lang") or "en-US").strip() or "en-US"
    if not htmlclean._LANG_RE.match(lang):
        lang = "en-US"
    title = str(meta.get("title") or "").strip()
    lines = [
        "<!DOCTYPE html>",
        '<html lang="%s">' % html.escape(lang, quote=True),
        "<head>",
        '<meta charset="utf-8">',
        "<title>%s</title>" % html.escape(title),
    ]
    author = str(meta.get("author") or "").strip()
    if author:
        lines.append('<meta name="author" content="%s">' % html.escape(author, quote=True))
    subject = str(meta.get("subject") or "").strip()
    if subject:
        lines.append('<meta name="description" content="%s">' % html.escape(subject, quote=True))
    lines.append('<meta name="generator" content="%s">' % html.escape(htmlclean.generator_string(), quote=True))
    for key in PAGE_META:
        value = meta.get(key)
        if value is None or str(value).strip() == "":
            continue
        lines.append('<meta name="easypdf-%s" content="%s">'
                     % (key.replace("_", "-"), html.escape(str(value), quote=True)))
    lines.append("<style>%s</style>" % DOCUMENT_STYLE.strip("\n"))
    lines.append("</head>")
    lines.append("<body>")
    lines.append(body_html)
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def write_atomic(path, text):
    """Write text to path through a temp file in the same folder and one
    replace, so an interrupted save leaves the previous file intact."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=folder,
                                         prefix=".easypdf-", suffix=".part", delete=False)
    temp = handle.name
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


def save(path, body_html, meta):
    """Save the document as native HTML at path, whatever its extension.
    Returns the sanitiser's warnings. Raises OSError when the write fails;
    the previous file is then untouched."""
    base = os.path.dirname(os.path.abspath(path))
    clean, warnings = htmlclean.normalise(body_html, for_export=False, embed=embedder_for(base))
    write_atomic(path, document_html(clean, meta))
    return warnings


RTF_HEAD = b"{" + bytes([92]) + b"rtf"


def is_rtf(path):
    """An .rtf file, or any file that starts with the RTF signature."""
    if os.path.splitext(str(path))[1].lower() == ".rtf":
        return True
    try:
        with open(path, "rb") as handle:
            return handle.read(5).lstrip() == RTF_HEAD
    except OSError:
        return False


def kind_of(path):
    ext = os.path.splitext(str(path))[1].lower()
    if ext in KINDS:
        return KINDS[ext]
    try:
        with open(path, "rb") as handle:
            head = handle.read(512)
    except OSError:
        return "text"
    text = head.decode("utf-8", "replace").lstrip("﻿ \t\r\n").lower()
    if text.startswith(("<!doctype html", "<html")):
        return "html"
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "docx"
    return "text"


# -------------------------------------------------------------- reading ---


class _HeadReader(HTMLParser):
    """Title, meta and the html lang from the head of a page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.lang = ""
        self.meta = {}
        self._in_title = False
        self.done = False

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        attrs = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = attrs.get("lang", "").strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs.get("name", "").strip().lower()
            if name:
                self.meta[name] = attrs.get("content", "")
        elif tag == "body":
            self.done = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.done:
            self.title += data


_BODY_RE = re.compile(r"<body\b[^>]*>(.*?)(?:</body\s*>|$)", re.IGNORECASE | re.DOTALL)


def split_page(text):
    """(head meta, body html) for a whole page or a bare body."""
    reader = _HeadReader()
    try:
        reader.feed(text)
        reader.close()
    except Exception:
        pass
    match = _BODY_RE.search(text)
    body = match.group(1) if match else text
    if not match:
        # No body element: drop anything that is plainly head furniture.
        body = re.sub(r"<!doctype[^>]*>", "", body, flags=re.IGNORECASE)
        body = re.sub(r"<head\b.*?</head\s*>", "", body, flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(r"</?html\b[^>]*>", "", body, flags=re.IGNORECASE)
    meta = {
        "title": re.sub(r"\s+", " ", reader.title).strip(),
        "author": reader.meta.get("author", "").strip(),
        "subject": reader.meta.get("description", "").strip(),
        "lang": reader.lang if htmlclean._LANG_RE.match(reader.lang or "") else "",
    }
    for key in PAGE_META:
        value = reader.meta.get("easypdf-" + key.replace("_", "-"))
        if value:
            value = _page_setting(key, value)
        if value:
            meta[key] = value
    return meta, body


def _page_setting(key, value):
    """A page setting from a file head, or "" when it is not one Easy
    PDF would write: the export puts these into the print page's
    stylesheet, so a received file must not carry anything there but a
    page size name, a number, or a font family list (Overseer round 2,
    defect 1)."""
    value = str(value).strip()
    if key == "font_family":
        return value if htmlclean.clean_font_family(value) == value else ""
    if key == "page_size":
        return value if value in C.PAGE_SIZES else ""
    try:
        float(value)
    except ValueError:
        return ""
    return value


def _read_text(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", "replace")


def text_to_html(text):
    """Plain text: blank lines separate paragraphs, single newlines join."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for chunk in re.split(r"\n\s*\n", text):
        words = " ".join(line.strip() for line in chunk.split("\n") if line.strip())
        if words:
            out.append("<p>%s</p>" % html.escape(words, quote=False))
    return "\n".join(out)


def _first_heading(body_html):
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", body_html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", "", match.group(1))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def load(path):
    """(body_html, meta). meta holds title, author, lang, subject,
    source_kind and warnings, plus the page settings a native file
    carried. Raises OSError for a file that cannot be read and ValueError
    (with a sentence) for a Word file or PDF that cannot be opened, and
    for RTF, which is out of 1.0.0 (DECISIONS.md decision 3): opened as
    text it would be paragraphs of control words with no explanation
    (Overseer round 2, defect 9)."""
    if is_rtf(path):
        raise ValueError(MSG_RTF)
    kind = kind_of(path)
    folder = os.path.dirname(os.path.abspath(path))
    meta = {"title": "", "author": "", "lang": "", "subject": "", "source_kind": kind}
    warnings = []
    if kind in ("native", "html"):
        head, body = split_page(_read_text(path))
        meta.update(head)
        clean, warnings = htmlclean.normalise(body, embed=embedder_for(folder))
    elif kind == "text":
        clean, warnings = htmlclean.normalise(text_to_html(_read_text(path)))
    elif kind == "markdown":
        from . import markdown_in
        clean, warnings = htmlclean.normalise(markdown_in.to_html(_read_text(path)),
                                              embed=embedder_for(folder))
        meta["title"] = _first_heading(clean)
    elif kind == "docx":
        from . import docx_in
        body, docx_meta, docx_warnings = docx_in.read(path)
        meta.update({k: v for k, v in docx_meta.items() if v})
        clean, warnings = htmlclean.normalise(body)
        warnings = docx_warnings + warnings
        if not meta["title"]:
            meta["title"] = _first_heading(clean)
    elif kind == "pdf":
        from . import pdfimport
        result = pdfimport.import_pdf(path)
        meta.update({k: v for k, v in result.meta.items() if v})
        clean, warnings = htmlclean.normalise(result.body_html)
        warnings = result.warnings + warnings
        meta["is_scanned"] = result.is_scanned
        meta["images"] = result.images
    else:
        clean, warnings = htmlclean.normalise(text_to_html(_read_text(path)))
    meta["source_kind"] = kind
    meta["warnings"] = warnings
    return clean, meta


# ------------------------------------------------------------- snapshots ---


def _snapshot_stem(source_path):
    key = os.path.abspath(source_path) if source_path else "untitled-%d" % os.getpid()
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:12]
    name = os.path.splitext(os.path.basename(source_path))[0] if source_path else "untitled"
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "document"
    return "%s-%s" % (name[:40], digest)


def snapshot_path_for(source_path):
    """Where a snapshot of this document goes, so the window can discard it
    on a clean close."""
    return os.path.join(paths.autosave_dir(), _snapshot_stem(source_path) + C.DOC_EXTENSION)


def snapshot(body_html, meta, source_path):
    """Write an autosave snapshot and return its path. The body is written
    as it is, without the sanitiser, so this is quick; recovery goes
    through load, which sanitises."""
    path = snapshot_path_for(source_path)
    write_atomic(path, document_html(body_html, meta))
    sidecar = {
        "source_path": os.path.abspath(source_path) if source_path else "",
        "saved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "title": str((meta or {}).get("title") or "").strip(),
    }
    write_atomic(path + ".json", json.dumps(sidecar, ensure_ascii=False, indent=1))
    return path


def recoverable():
    """Every snapshot on disk, newest first, as
    (snapshot_path, source_path, saved_at, title). saved_at is a datetime."""
    folder = paths.autosave_dir()
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        if not name.endswith(C.DOC_EXTENSION + ".json"):
            continue
        sidecar_path = os.path.join(folder, name)
        snapshot_file = sidecar_path[:-5]
        if not os.path.isfile(snapshot_file):
            continue
        try:
            with open(sidecar_path, encoding="utf-8") as handle:
                data = json.load(handle)
            saved_at = datetime.datetime.fromisoformat(data.get("saved_at", ""))
        except (OSError, ValueError, TypeError):
            saved_at = datetime.datetime.fromtimestamp(os.path.getmtime(snapshot_file))
            data = {}
        found.append((snapshot_file, data.get("source_path", ""), saved_at, data.get("title", "")))
    found.sort(key=lambda item: item[2], reverse=True)
    return found


def discard_snapshot(snapshot_path):
    for target in (snapshot_path, snapshot_path + ".json"):
        try:
            os.remove(target)
        except OSError:
            pass
