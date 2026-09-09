"""The accessibility checker: what can be proven about a PDF from here.

    check(path) -> Report
    Report.results      list of CheckResult(name, passed, detail, warn_only, key)
    Report.passed       every check passed (warn-only checks count as passed)
    Report.score        (ok, total)
    Report.pdfua_gate   every check except the identifier check itself passed;
                        pdfexport writes pdfuaid:part only when this is True
    Report.format_report()  plain text, one check per line, PASS, FAIL or WARN

Every check is independent and every detail is a sentence that says what to
do. The checks are the ones a program can make by reading the file: the
catalogue entries, the structure tree, the fonts, the annotations, and the
content streams (every text operator inside marked content, counting BMC as
well as BDC, which CHALLENGE.md E6 learned the hard way). What no program
can see is whether a description is true, whether a heading is really a
heading, whether the reading order makes sense, or colour contrast. A full
PDF/UA verdict needs PAC or veraPDF, and the report says so.

Text is recovered per marked content id by parsing the content streams and
each font's ToUnicode map, so a skipped heading is named by its words and a
link gets its text as the annotation's Contents (pdfexport uses TextIndex
for that). Fonts without a ToUnicode map are decoded as Latin-1, which is
right for the standard fourteen and wrong for most others; the text is then
only used to name things, never to judge them.

Nothing here touches wx or prints.
"""

import os
import re
from dataclasses import dataclass, field

import pikepdf

_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")
HEADING_NAMES = {"/H1": 1, "/H2": 2, "/H3": 3, "/H4": 4, "/H5": 5, "/H6": 6}
MAX_FORM_DEPTH = 6
#: A kerning adjustment in a TJ array this large (thousandths of the font
#: size) is a word space; the text is only used to name things.
SPACE_ADJUSTMENT = -180

CLOSING = ("These are the checks Easy PDF can make from here. A full PDF/UA verdict "
           "needs PAC or veraPDF.")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    warn_only: bool = False
    key: str = ""

    @property
    def word(self):
        if self.passed:
            return "PASS"
        return "WARN" if self.warn_only else "FAIL"


@dataclass
class Report:
    path: str
    results: list = field(default_factory=list)
    pages: int = 0
    producer: str = ""

    @property
    def passed(self):
        return all(r.passed or r.warn_only for r in self.results)

    @property
    def score(self):
        return sum(1 for r in self.results if r.passed), len(self.results)

    @property
    def warnings(self):
        return sum(1 for r in self.results if r.warn_only and not r.passed)

    @property
    def pdfua_gate(self):
        return bool(self.results) and all(
            r.passed or r.warn_only for r in self.results if r.key != "identifier")

    def failed_names(self):
        """The failed checks other than the identifier check itself, which
        is a consequence of the others, not a cause."""
        return [r.name for r in self.results
                if not r.passed and not r.warn_only and r.key != "identifier"]

    def format_report(self):
        ok, total = self.score
        lines = ["Accessibility checks for %s" % os.path.basename(self.path)]
        summary = "%d of %d checks passed" % (ok, total)
        if self.warnings:
            summary += ", %s" % _n(self.warnings, "warning", "warnings")
        lines.append(summary + ".")
        for result in self.results:
            line = "%s: %s." % (result.word, result.name)
            if result.detail:
                line += " " + result.detail
            lines.append(line)
        lines.append(CLOSING)
        return "\n".join(lines)


def _n(count, one, many):
    return ("1 " + one) if count == 1 else ("%d " % count) + many


def _short(text, limit=40):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


# ------------------------------------------------------------ text index ---


def _bytes_of(obj):
    try:
        return bytes(obj)
    except Exception:
        return b""


class _FontDecoder:
    """Decodes the byte strings shown with one font into text."""

    def __init__(self, font):
        self.ranges = []          # (length, low, high) from the codespace
        self.single = {}          # code -> text
        self.spans = []           # (low, high, length, base text or list)
        self.two_byte_default = False
        self.fallback_latin = True
        try:
            subtype = str(font.get("/Subtype", ""))
        except Exception:
            subtype = ""
        if subtype == "/Type0":
            self.two_byte_default = True
            self.fallback_latin = False
        to_unicode = None
        try:
            to_unicode = font.get("/ToUnicode")
        except Exception:
            to_unicode = None
        if isinstance(to_unicode, pikepdf.Stream):
            try:
                self._parse_cmap(to_unicode)
            except Exception:
                pass
        self._prepare()

    def _parse_cmap(self, stream):
        # ToUnicode maps are small; pikepdf's parser is fine for them.
        for ops, operator in pikepdf.parse_content_stream(stream):
            name = str(operator)
            items = list(ops)
            if name == "endcodespacerange":
                for i in range(0, len(items) - 1, 2):
                    low, high = _bytes_of(items[i]), _bytes_of(items[i + 1])
                    if low and high and len(low) == len(high):
                        self.ranges.append((len(low), int.from_bytes(low, "big"),
                                            int.from_bytes(high, "big")))
            elif name == "endbfchar":
                for i in range(0, len(items) - 1, 2):
                    src, dst = _bytes_of(items[i]), items[i + 1]
                    if src:
                        self.single[(len(src), int.from_bytes(src, "big"))] = _dst_text(dst)
            elif name == "endbfrange":
                for i in range(0, len(items) - 2, 3):
                    low, high, dst = _bytes_of(items[i]), _bytes_of(items[i + 1]), items[i + 2]
                    if not low or len(low) != len(high):
                        continue
                    lo, hi = int.from_bytes(low, "big"), int.from_bytes(high, "big")
                    if isinstance(dst, pikepdf.Array):
                        self.spans.append((lo, hi, len(low), [_dst_text(d) for d in dst]))
                    else:
                        self.spans.append((lo, hi, len(low), _dst_text(dst)))
        if not self.ranges:
            lengths = {k[0] for k in self.single} | {s[2] for s in self.spans}
            for length in sorted(lengths):
                self.ranges.append((length, 0, (1 << (8 * length)) - 1))
        if self.ranges:
            self.fallback_latin = False

    def _prepare(self):
        """Chromium writes one text operator per glyph, so decode is called
        a million times on a long document: everything that can be
        computed once is, and every result is cached per byte string."""
        self.lengths = sorted({r[0] for r in self.ranges}) or ([2] if self.two_byte_default else [1])
        self.by_length = {length: [(lo, hi) for (ln, lo, hi) in self.ranges if ln == length]
                          for length in self.lengths}
        self.cache = {}

    def _lookup(self, length, code):
        text = self.single.get((length, code))
        if text is not None:
            return text
        for lo, hi, span_length, dst in self.spans:
            if span_length == length and lo <= code <= hi:
                if isinstance(dst, list):
                    index = code - lo
                    return dst[index] if index < len(dst) else ""
                if not dst:
                    return ""
                last = ord(dst[-1]) + (code - lo)
                try:
                    return dst[:-1] + chr(last)
                except ValueError:
                    return dst
        return None

    def decode(self, data):
        if not data:
            return ""
        cached = self.cache.get(data)
        if cached is not None:
            return cached
        text = self._decode(data)
        if len(self.cache) < 100000:
            self.cache[data] = text
        return text

    def _decode(self, data):
        if self.fallback_latin and not self.ranges:
            return data.decode("latin-1", "replace")
        out = []
        position = 0
        total = len(data)
        lengths = self.lengths
        by_length = self.by_length
        while position < total:
            chosen = None
            for length in lengths:
                if position + length > total:
                    continue
                code = int.from_bytes(data[position:position + length], "big")
                for lo, hi in by_length.get(length, ()):
                    if lo <= code <= hi:
                        chosen = (length, code)
                        break
                if chosen is not None:
                    break
            if chosen is None:
                length = min(lengths[0], total - position)
                code = int.from_bytes(data[position:position + length], "big")
                chosen = (max(1, length), code)
            length, code = chosen
            text = self._lookup(length, code)
            if text is None:
                if self.two_byte_default:
                    text = ""          # a glyph with no mapping: nothing to say
                else:
                    text = bytes([code & 0xFF]).decode("latin-1", "replace")
            out.append(text)
            position += length
        return "".join(out)


def _dst_text(obj):
    data = _bytes_of(obj)
    if not data:
        return ""
    if len(data) % 2 == 0:
        try:
            return data.decode("utf-16-be", "replace")
        except Exception:
            pass
    return data.decode("latin-1", "replace")


class TextIndex:
    """Text per (page index, marked content id) for one PDF, built lazily
    one page at a time, plus per page counts of text shown outside any
    marked content, of all text, and of image XObjects drawn."""

    def __init__(self, pdf):
        self.pdf = pdf
        self.page_index = {}
        for index, page in enumerate(pdf.pages):
            self.page_index[page.obj.objgen] = index
        self._pages = {}
        self._decoders = {}

    def index_of_page(self, page_obj):
        try:
            return self.page_index.get(page_obj.objgen)
        except Exception:
            return None

    def page(self, index):
        if index not in self._pages:
            self._pages[index] = self._scan(index)
        return self._pages[index]

    def text(self, page_index, mcid):
        return self.page(page_index)["mcids"].get(mcid, "")

    def image_marks(self, page_index):
        """[(object number, drawn inside tagged content)] for every image
        XObject drawn on the page, in drawing order. Only a picture drawn
        inside marked content with an MCID can be the one a Figure in the
        tree describes; one drawn inside an Artifact, or outside any
        marked content at all (Chromium draws a decorative picture that
        way, measured), is not in the tree. An importer uses this so a
        decorative picture on the same page never breaks the match for
        the described one beside it (Overseer round 2, defect 6)."""
        return list(self.page(page_index)["image_marks"])

    def _decoder(self, font):
        try:
            key = font.objgen
        except Exception:
            key = id(font)
        if key == (0, 0):
            key = id(font)
        if key not in self._decoders:
            self._decoders[key] = _FontDecoder(font)
        return self._decoders[key]

    def _scan(self, index):
        page = self.pdf.pages[index]
        info = {"mcids": {}, "untagged": 0, "chars": 0, "images": 0, "image_marks": [],
                "error": ""}
        try:
            resources = page.obj.get("/Resources", pikepdf.Dictionary())
            data = _content_bytes(page.obj.get("/Contents"))
            self._walk(data, resources, info, [], 0, set())
        except Exception as exc:
            # A damaged content stream must not stop the other checks; the
            # reason is kept so a test or a report can see it.
            info["error"] = "%s: %s" % (type(exc).__name__, exc)
        info["mcids"] = {mcid: "".join(pieces) for mcid, pieces in info["mcids"].items()}
        return info

    def _walk(self, data, resources, info, stack, depth, visited):
        """One content stream, as raw decoded bytes, through a regex
        tokenizer. pikepdf's parse_content_stream is quick, but reading
        each instruction back into Python costs about forty microseconds
        (measured), and Chromium writes one instruction per glyph; the
        tokenizer does 163 pages in well under a second, and the glyph
        pair "<hex> Tj x 0 Td" is one token."""
        if not data:
            return
        data = _INLINE_IMAGE_RE.sub(_count_inline_image(info), data)
        if isinstance(resources, pikepdf.Dictionary):
            fonts = resources.get("/Font", pikepdf.Dictionary())
            xobjects = resources.get("/XObject", pikepdf.Dictionary())
        else:
            fonts = xobjects = pikepdf.Dictionary()
        decoder = None
        pending_space = False
        line_y = None
        mcids = info["mcids"]
        operands = []          # (kind, value) since the last operator
        array = None           # elements while inside [ ... ]
        op_start = 0

        def current_mcid():
            for item in reversed(stack):
                if item is not None and item != "artifact":
                    return item
            return None

        def decode(raw):
            if not raw:
                return ""
            if decoder is None:
                return raw.decode("latin-1", "replace")
            return decoder.decode(raw)

        def add_text(text):
            nonlocal pending_space
            if not text:
                return
            mcid = current_mcid()
            visible = len(text.strip())
            info["chars"] += visible
            if not stack:
                info["untagged"] += visible
            if mcid is not None:
                pieces = mcids.get(mcid)
                if pieces is None:
                    pieces = mcids[mcid] = []
                elif pending_space and not pieces[-1][-1:].isspace() and not text[0].isspace():
                    pieces.append(" ")
                pieces.append(text)
            pending_space = False

        def moved_line(new_y):
            # A vertical move is a new line. Chromium positions every glyph
            # with its own horizontal Td and writes real space glyphs
            # (measured), so a horizontal move is never a word break.
            nonlocal line_y, pending_space
            if line_y is not None and abs(new_y - line_y) > 0.01:
                pending_space = True
            line_y = new_y

        def last(kind):
            for item_kind, value in reversed(operands):
                if item_kind == kind:
                    return value
            return None

        def first(kind):
            for item_kind, value in operands:
                if item_kind == kind:
                    return value
            return None

        for match in _TOKEN_RE.finditer(data):
            kind = match.lastgroup
            if kind == "glyph":
                add_text(decode(_hex_bytes(match.group("glyphhex"))))
                operands = []
                op_start = match.end()
                continue
            if kind == "ws" or kind == "comment" or kind == "junk":
                continue
            if kind == "op":
                name = match.group().decode("latin-1")
                if name == "Tj":
                    add_text(decode(last("str") or b""))
                elif name == "Td" or name == "TD":
                    number = last("num")
                    if number is not None and number != 0.0:
                        pending_space = True
                        line_y = None
                elif name == "BDC":
                    # The tag is the first name operand and the property
                    # the last: "/Artifact /P1 BDC" names a property list
                    # in the resources, and reading the last name as the
                    # tag would count that artifact as content (Overseer
                    # round 2, defect 11). Chromium writes inline
                    # dictionaries, so the app's own files never hit it.
                    tag = first("name")
                    mcid = None
                    if tag != "/Artifact":
                        found = _MCID_RE.search(data, op_start, match.start())
                        if found is not None:
                            mcid = int(found.group(1))
                        else:
                            prop = last("name")
                            # A named property list in the resources.
                            mcid = _mcid_from_properties(resources, prop, tag)
                    stack.append("artifact" if tag == "/Artifact" else mcid)
                elif name == "BMC":
                    stack.append("artifact" if first("name") == "/Artifact" else None)
                elif name == "EMC":
                    if stack:
                        stack.pop()
                elif name == "Tf":
                    font_name = last("name")
                    decoder = None
                    if font_name is not None:
                        try:
                            font = fonts.get(font_name)
                        except Exception:
                            font = None
                        if font is not None:
                            decoder = self._decoder(font)
                elif name == "TJ":
                    items = last("arr") or []
                    for item_kind, value in items:
                        if item_kind == "str":
                            add_text(decode(value))
                        elif item_kind == "num" and value < SPACE_ADJUSTMENT:
                            pending_space = True
                elif name == "Tm":
                    number = last("num")
                    if number is not None:
                        moved_line(number)
                elif name == "T*":
                    pending_space = True
                    line_y = None
                elif name == "'" or name == '"':
                    pending_space = True
                    line_y = None
                    add_text(decode(last("str") or b""))
                elif name == "Do":
                    xname = last("name")
                    xobject = None
                    if xname is not None:
                        try:
                            xobject = xobjects.get(xname)
                        except Exception:
                            xobject = None
                    if isinstance(xobject, pikepdf.Stream):
                        subtype = str(xobject.get("/Subtype", ""))
                        if subtype == "/Image":
                            info["images"] += 1
                            try:
                                objnum = xobject.objgen[0]
                            except Exception:
                                objnum = 0
                            info["image_marks"].append((objnum, current_mcid() is not None))
                        elif subtype == "/Form" and depth < MAX_FORM_DEPTH:
                            key = xobject.objgen
                            if key not in visited:
                                visited.add(key)
                                inner = xobject.get("/Resources", resources)
                                try:
                                    inner_data = xobject.read_bytes()
                                except Exception:
                                    inner_data = b""
                                self._walk(inner_data, inner, info, stack, depth + 1, visited)
                                visited.discard(key)
                operands = []
                array = None
                op_start = match.end()
                continue
            # An operand.
            if kind == "arr":
                if match.group() == b"[":
                    array = []
                else:
                    if array is not None:
                        operands.append(("arr", array))
                    array = None
                continue
            if kind == "str":
                item = ("str", _literal_bytes(match.group()))
            elif kind == "hex":
                item = ("str", _hex_bytes(match.group()))
            elif kind == "name":
                item = ("name", _name_text(match.group()))
            elif kind == "num":
                try:
                    item = ("num", float(match.group()))
                except ValueError:
                    item = ("num", 0.0)
            else:
                item = ("other", match.group())
            if array is not None:
                array.append(item)
            else:
                operands.append(item)


# ------------------------------------------------------ the tokenizer ---

_TOKEN_RE = re.compile(rb"""
 (?P<glyph><(?P<glyphhex>[0-9A-Fa-f]+)>\s*Tj\s+[-+.\d]+\s+0\s+Td(?=\s|$))
|(?P<ws>[\x00\t\n\x0c\r ]+)
|(?P<comment>%[^\r\n]*)
|(?P<str>\((?:\\.|[^\\()])*\))
|(?P<hex><[0-9A-Fa-f\s]*>)
|(?P<dict><<(?:[^<>]|<[^<>]*>)*>>)
|(?P<arr>[\[\]])
|(?P<name>/[^\x00\t\n\x0c\r /\[\]<>(){}%]*)
|(?P<num>[+-]?(?:\d+\.?\d*|\.\d+))
|(?P<op>[^\x00\t\n\x0c\r /\[\]<>(){}%]+)
|(?P<junk>[(){}<>])
""", re.VERBOSE)
_MCID_RE = re.compile(rb"/MCID\s+(\d+)")
_INLINE_IMAGE_RE = re.compile(rb"(?:^|(?<=\s))BI(?=\s).*?(?<=\s)ID\s.*?(?<=\s)EI(?=\s|$)", re.DOTALL)
_ESCAPE_RE = re.compile(rb"\\(\d{1,3}|\r\n|\r|\n|.)", re.DOTALL)
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
            b"(": b"(", b")": b")", b"\\": b"\\", b"\r\n": b"", b"\r": b"", b"\n": b""}


def _count_inline_image(info):
    def replace(match):
        info["images"] += 1
        return b" "
    return replace


def _content_bytes(contents):
    if isinstance(contents, pikepdf.Array):
        parts = []
        for stream in contents:
            if isinstance(stream, pikepdf.Stream):
                parts.append(stream.read_bytes())
        return b"\n".join(parts)
    if isinstance(contents, pikepdf.Stream):
        return contents.read_bytes()
    return b""


def _hex_bytes(token):
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", token)
    if len(digits) % 2:
        digits += b"0"
    try:
        return bytes.fromhex(digits.decode("ascii"))
    except ValueError:
        return b""


def _literal_bytes(token):
    body = token[1:-1]

    def unescape(match):
        code = match.group(1)
        if code.isdigit():
            try:
                return bytes([int(code, 8) & 0xFF])
            except ValueError:
                return b""
        return _ESCAPES.get(code, code)
    return _ESCAPE_RE.sub(unescape, body)


def _name_text(token):
    text = token.decode("latin-1")
    if "#" in text:
        text = re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), text)
    return text


def _mcid_from_properties(resources, prop, tag):
    if not isinstance(resources, pikepdf.Dictionary) or prop is None:
        return None
    try:
        properties = resources.get("/Properties")
        entry = properties.get(prop) if isinstance(properties, pikepdf.Dictionary) else None
        if isinstance(entry, pikepdf.Dictionary) and "/MCID" in entry:
            return int(entry.MCID)
    except Exception:
        return None
    return None


# ------------------------------------------------------- structure tree ---


class Elem:
    __slots__ = ("obj", "kind", "parent", "page", "children", "depth")

    def __init__(self, obj, kind, parent, page, depth):
        self.obj = obj
        self.kind = kind
        self.parent = parent
        self.page = page
        self.children = []
        self.depth = depth


def _role_map(root):
    mapping = {}
    try:
        role_map = root.StructTreeRoot.get("/RoleMap")
        if isinstance(role_map, pikepdf.Dictionary):
            for key, value in role_map.items():
                mapping[str(key)] = str(value)
    except Exception:
        pass
    return mapping


def _resolve_kind(name, role_map):
    seen = set()
    while name in role_map and name not in seen:
        seen.add(name)
        name = role_map[name]
    return name


def walk_tree(pdf, index=None):
    """Every structure element in document order, as Elem objects with
    kind (after the role map), page index (own or inherited), depth,
    parent and children. Cycles are guarded."""
    out = []
    try:
        root = pdf.Root.StructTreeRoot
    except Exception:
        return out
    role_map = _role_map(pdf.Root)
    visited = set()

    def page_of(obj, inherited):
        page = obj.get("/Pg") if isinstance(obj, pikepdf.Dictionary) else None
        if page is not None and index is not None:
            found = index.index_of_page(page)
            if found is not None:
                return found
        return inherited

    def visit(obj, parent, inherited_page, depth):
        if isinstance(obj, pikepdf.Array):
            for item in obj:
                visit(item, parent, inherited_page, depth)
            return
        if not isinstance(obj, pikepdf.Dictionary):
            return
        try:
            key = obj.objgen
        except Exception:
            key = None
        if key and key != (0, 0):
            if key in visited:
                return
            visited.add(key)
        kind_type = str(obj.get("/Type", ""))
        if kind_type in ("/MCR", "/OBJR"):
            return
        kind = _resolve_kind(str(obj.get("/S", "")), role_map)
        page = page_of(obj, inherited_page)
        elem = Elem(obj, kind, parent, page, depth)
        if parent is not None:
            parent.children.append(elem)
        out.append(elem)
        kids = obj.get("/K")
        if kids is None:
            return
        visit(kids, elem, page, depth + 1)

    visit(root.get("/K"), None, None, 0)
    # An element with no Pg of its own (Chromium puts Pg on the leaf
    # NonStruct elements) takes the page of its first descendant that has
    # one, so callers can group elements by page.
    for elem in reversed(out):
        if elem.page is None:
            for child in elem.children:
                if child.page is not None:
                    elem.page = child.page
                    break
    return out


def element_mcids(elem, index):
    """(page index, mcid) pairs for the element's own marked content, in
    order, through its descendants."""
    found = []

    def visit(obj, page):
        if isinstance(obj, pikepdf.Array):
            for item in obj:
                visit(item, page)
            return
        if isinstance(obj, pikepdf.Dictionary):
            kind_type = str(obj.get("/Type", ""))
            own_page = page
            pg = obj.get("/Pg")
            if pg is not None and index is not None:
                got = index.index_of_page(pg)
                if got is not None:
                    own_page = got
            if kind_type == "/MCR":
                try:
                    found.append((own_page, int(obj.MCID)))
                except Exception:
                    pass
                return
            if kind_type == "/OBJR":
                return
            kids = obj.get("/K")
            if kids is not None:
                visit(kids, own_page)
            return
        try:
            found.append((page, int(obj)))
        except Exception:
            pass

    visit(elem.obj.get("/K"), elem.page)
    return found


def element_text(elem, index):
    parts = []
    for page, mcid in element_mcids(elem, index):
        if page is None:
            continue
        parts.append(index.text(page, mcid))
    text = "".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def _annotations_of(elem):
    """Annotation dictionaries referenced by OBJR children."""
    found = []

    def visit(obj):
        if isinstance(obj, pikepdf.Array):
            for item in obj:
                visit(item)
        elif isinstance(obj, pikepdf.Dictionary):
            if str(obj.get("/Type", "")) == "/OBJR":
                target = obj.get("/Obj")
                if isinstance(target, pikepdf.Dictionary):
                    found.append(target)

    visit(elem.obj.get("/K"))
    return found


# ------------------------------------------------------------- the checks ---


def _xmp(pdf):
    # update_docinfo must be False: with the default, leaving the context
    # on a file that has no XMP wipes the Info title in memory (measured
    # 2026-09-09). The checker reads; it never writes.
    try:
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
            return {"dc:title": str(meta.get("dc:title") or "").strip(),
                    "pdfuaid:part": str(meta.get("pdfuaid:part") or "").strip()}
    except Exception:
        return {"dc:title": "", "pdfuaid:part": ""}


def _fonts_of(pdf):
    """(name, embedded) for every font in page resources and form XObjects."""
    fonts = {}
    visited = set()

    def visit_resources(resources, depth):
        if not isinstance(resources, pikepdf.Dictionary) or depth > MAX_FORM_DEPTH:
            return
        font_dict = resources.get("/Font")
        if isinstance(font_dict, pikepdf.Dictionary):
            for _key, font in font_dict.items():
                if not isinstance(font, pikepdf.Dictionary):
                    continue
                try:
                    ident = font.objgen if font.objgen != (0, 0) else id(font)
                except Exception:
                    ident = id(font)
                if ident in fonts:
                    continue
                fonts[ident] = _font_embedded(font)
        xobjects = resources.get("/XObject")
        if isinstance(xobjects, pikepdf.Dictionary):
            for _key, xobject in xobjects.items():
                if not isinstance(xobject, pikepdf.Stream):
                    continue
                if str(xobject.get("/Subtype", "")) != "/Form":
                    continue
                try:
                    ident = xobject.objgen
                except Exception:
                    ident = id(xobject)
                if ident in visited:
                    continue
                visited.add(ident)
                visit_resources(xobject.get("/Resources"), depth + 1)

    for page in pdf.pages:
        visit_resources(page.obj.get("/Resources"), 0)
    return list(fonts.values())


def _font_embedded(font):
    subtype = str(font.get("/Subtype", ""))
    name = str(font.get("/BaseFont", "unnamed")).lstrip("/")
    if "+" in name and len(name.split("+", 1)[0]) == 6:
        name = name.split("+", 1)[1]
    if subtype == "/Type3":
        return name or "Type 3", True
    descriptor = font.get("/FontDescriptor")
    if subtype == "/Type0":
        try:
            descendant = font.DescendantFonts[0]
            descriptor = descendant.get("/FontDescriptor")
        except Exception:
            descriptor = None
    embedded = False
    if isinstance(descriptor, pikepdf.Dictionary):
        embedded = any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
    return name, embedded


def identifier_check(part):
    return CheckResult("PDF/UA identifier", part == "1",
                       "The file identifies itself as PDF/UA-1." if part == "1" else
                       "No PDF/UA identifier. Easy PDF writes one only when every other "
                       "check passes.",
                       key="identifier")


def identifier_result(path):
    """The identifier check alone, read from the file. The export uses it
    after writing the identifier, so a long document is not parsed twice
    for the one entry that changed."""
    try:
        pdf = pikepdf.open(path)
    except Exception:
        return identifier_check("")
    try:
        return identifier_check(_xmp(pdf)["pdfuaid:part"])
    finally:
        pdf.close()


def check(path):
    """Run every check on the PDF at path. Never raises for a bad file: the
    report then holds one failed result that says why."""
    report = Report(path=path)
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError:
        report.results.append(CheckResult(
            "File readable", False,
            "The PDF is protected by a password, so nothing in it can be checked.",
            key="readable"))
        return report
    except Exception as exc:
        report.results.append(CheckResult(
            "File readable", False,
            "The file could not be opened as a PDF. %s" % _short(str(exc), 120),
            key="readable"))
        return report
    try:
        _run_checks(pdf, report)
    finally:
        pdf.close()
    return report


def _run_checks(pdf, report):
    root = pdf.Root
    report.pages = len(pdf.pages)
    try:
        report.producer = str(pdf.docinfo.get("/Producer", ""))
    except Exception:
        report.producer = ""
    index = TextIndex(pdf)
    add = report.results.append

    # 1. Tagged
    marked = False
    try:
        mark_info = root.get("/MarkInfo")
        marked = bool(mark_info is not None and mark_info.get("/Marked", False))
    except Exception:
        marked = False
    add(CheckResult("Tagged PDF", marked,
                    "The file says it is tagged." if marked else
                    "The file does not say it is tagged (no MarkInfo). A screen reader "
                    "gets no structure from it. Export it again from Easy PDF.",
                    key="tagged"))

    # 2. Structure tree
    elements = walk_tree(pdf, index)
    has_tree = bool(elements)
    add(CheckResult("Structure tree", has_tree,
                    ("The tree holds %s." % _n(len(elements), "element", "elements")) if has_tree else
                    "There is no structure tree, so headings, lists, links and pictures "
                    "have no roles. Export it again from Easy PDF.",
                    key="tree"))

    # 3. Language
    lang = ""
    try:
        lang = str(root.get("/Lang", "")).strip()
    except Exception:
        lang = ""
    lang_ok = bool(lang) and bool(_LANG_RE.match(lang))
    if lang_ok:
        detail = "The document language is %s." % lang
    elif lang:
        detail = ("The document language \"%s\" is not a language code. Set the language "
                  "in Document properties, for example en-US." % _short(lang, 20))
    else:
        detail = ("No document language is set, so a screen reader cannot pick the right "
                  "voice. Set it in Document properties.")
    add(CheckResult("Language", lang_ok, detail, key="lang"))

    # 4. DisplayDocTitle
    display = False
    try:
        prefs = root.get("/ViewerPreferences")
        display = bool(prefs is not None and prefs.get("/DisplayDocTitle", False))
    except Exception:
        display = False
    add(CheckResult("Title shown in the window", display,
                    "Viewers show the document title rather than the file name." if display else
                    "Viewers will show the file name instead of the title (DisplayDocTitle "
                    "is off). Export it again from Easy PDF.",
                    key="display_title"))

    # 5. Title. Info is read before the XMP is opened, on purpose.
    info_title = ""
    try:
        info_title = str(pdf.docinfo.get("/Title", "")).strip()
    except Exception:
        info_title = ""
    xmp = _xmp(pdf)
    if xmp["dc:title"]:
        add(CheckResult("Title", True, "The title is \"%s\"." % _short(xmp["dc:title"], 60), key="title"))
    elif info_title:
        add(CheckResult("Title", False,
                        "The title \"%s\" is in the file's information but not in its "
                        "XMP metadata, which PDF/UA requires. Export it again from Easy PDF."
                        % _short(info_title, 60), key="title"))
    else:
        add(CheckResult("Title", False,
                        "The document has no title. Give it one in Document properties.",
                        key="title"))

    # 6. Identifier
    add(identifier_check(xmp["pdfuaid:part"]))

    # 7. Pictures
    figures = [e for e in elements if e.kind == "/Figure"]
    missing = 0
    for figure in figures:
        alt = ""
        try:
            alt = str(figure.obj.get("/Alt", "") or "").strip()
            if not alt:
                alt = str(figure.obj.get("/ActualText", "") or "").strip()
        except Exception:
            alt = ""
        if not alt:
            missing += 1
    if not figures:
        detail = "There are no pictures."
    elif missing and len(figures) == 1:
        detail = ("The picture has no description. Give it one in Pictures, or mark it "
                  "decorative.")
    elif missing:
        detail = ("%d of the %d pictures %s no description. Give every picture a "
                  "description in Pictures, or mark it decorative."
                  % (missing, len(figures), "has" if missing == 1 else "have"))
    elif len(figures) == 1:
        detail = "The picture has a description."
    else:
        detail = "All %d pictures have a description." % len(figures)
    add(CheckResult("Pictures described", missing == 0, detail, key="figures"))

    # 8. Headings
    headings = [e for e in elements if e.kind in HEADING_NAMES]
    generic = [e for e in elements if e.kind == "/H"]
    skip_detail = ""
    previous = 0
    previous_text = ""
    for heading in headings:
        level = HEADING_NAMES[heading.kind]
        if level > previous + 1:
            text = element_text(heading, index)
            where = "\"%s\"" % _short(text) if text else "a heading"
            if previous == 0:
                skip_detail = ("The first heading, %s, is level %d. Make the first heading "
                               "level 1." % (where, level))
            else:
                skip_detail = ("%s is level %d after the level %d heading \"%s\". Make it "
                               "level %d, or add the level in between."
                               % (where[0].upper() + where[1:], level, previous,
                                  _short(previous_text), previous + 1))
            break
        previous = level
        previous_text = element_text(heading, index)
    if generic and not headings:
        add(CheckResult("Heading levels", True,
                        "The headings are unnumbered (H), so levels cannot be checked here.",
                        key="headings"))
    elif not headings:
        add(CheckResult("Heading levels", True, "There are no headings.", key="headings"))
    elif skip_detail:
        add(CheckResult("Heading levels", False, skip_detail, key="headings"))
    else:
        add(CheckResult("Heading levels", True,
                        "%s, and no level is skipped." % _n(len(headings), "heading", "headings"),
                        key="headings"))

    # 9. Fonts
    fonts = _fonts_of(pdf)
    not_embedded = sorted({name for name, embedded in fonts if not embedded})
    if not fonts:
        add(CheckResult("Fonts embedded", True, "No fonts are used.", key="fonts"))
    elif not_embedded:
        add(CheckResult("Fonts embedded", False,
                        "%s not embedded: %s. Every reader needs the fonts inside the file. "
                        "Export it again from Easy PDF."
                        % (_n(len(not_embedded), "font is", "fonts are"), ", ".join(not_embedded[:6])),
                        key="fonts"))
    else:
        add(CheckResult("Fonts embedded", True,
                        "%s embedded." % ("The 1 font is" if len(fonts) == 1 else "All %d fonts are" % len(fonts)),
                        key="fonts"))

    # 10. Tab order and 11. Links
    pages_with_annots = 0
    pages_without_tabs = 0
    links = 0
    links_without_parent = 0
    links_without_contents = 0
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array) or len(annots) == 0:
            continue
        pages_with_annots += 1
        if str(page.obj.get("/Tabs", "")) != "/S":
            pages_without_tabs += 1
        for annot in annots:
            if not isinstance(annot, pikepdf.Dictionary):
                continue
            if str(annot.get("/Subtype", "")) != "/Link":
                continue
            links += 1
            if "/StructParent" not in annot:
                links_without_parent += 1
            contents = ""
            try:
                contents = str(annot.get("/Contents", "") or "").strip()
            except Exception:
                contents = ""
            if not contents:
                links_without_contents += 1
    if not pages_with_annots:
        add(CheckResult("Tab order", True, "No page has links or fields.", key="tabs"))
    elif pages_without_tabs:
        add(CheckResult("Tab order", False,
                        "%s with links or fields %s no tab order set. Export it again from "
                        "Easy PDF." % (_n(pages_without_tabs, "page", "pages"),
                                       "has" if pages_without_tabs == 1 else "have"),
                        key="tabs"))
    else:
        add(CheckResult("Tab order", True,
                        "Tab order follows the structure on every page with links.", key="tabs"))
    if not links:
        add(CheckResult("Links tagged", True, "There are no links.", key="links"))
    elif links_without_parent:
        add(CheckResult("Links tagged", False,
                        "%s of %d %s not in the structure tree, so a screen reader cannot "
                        "reach %s. Export it again from Easy PDF."
                        % (links_without_parent, links,
                           "link is" if links_without_parent == 1 else "links are",
                           "it" if links_without_parent == 1 else "them"),
                        key="links"))
    else:
        add(CheckResult("Links tagged", True,
                        "%s in the structure tree." % ("The 1 link is" if links == 1 else "All %d links are" % links),
                        key="links"))
    if links:
        if links_without_contents:
            add(CheckResult("Links described", False,
                            "%s of %d %s no description, so some screen readers read only "
                            "the address. Easy PDF writes the link text as the description "
                            "when it exports."
                            % (links_without_contents, links,
                               "link has" if links_without_contents == 1 else "links have"),
                            key="link_contents"))
        else:
            add(CheckResult("Links described", True,
                            "Every link carries its text as a description.", key="link_contents"))

    # 12. Bookmarks (warn only)
    has_outline = False
    try:
        outlines = root.get("/Outlines")
        has_outline = bool(outlines is not None and outlines.get("/First") is not None)
    except Exception:
        has_outline = False
    add(CheckResult("Bookmarks", has_outline,
                    "The headings are bookmarks." if has_outline else
                    "There are no bookmarks. Readers of a long document jump by them; "
                    "Easy PDF makes one per heading.",
                    warn_only=True, key="outline"))

    # 13. Text layer and 14. untagged text
    total_chars = 0
    untagged = 0
    images = 0
    for page_number in range(len(pdf.pages)):
        info = index.page(page_number)
        total_chars += info["chars"]
        untagged += info["untagged"]
        images += info["images"]
    if total_chars:
        add(CheckResult("Text layer", True,
                        "The pages hold text a screen reader can read.", key="text"))
    elif images:
        add(CheckResult("Text layer", False,
                        "This PDF is pictures of text. There is no text for a screen reader "
                        "to read, and Easy PDF has no text recognition in this release. "
                        "Run OCR in another program first.", key="text"))
    else:
        add(CheckResult("Text layer", False,
                        "The PDF has no text at all.", key="text"))
    if total_chars:
        add(CheckResult("All text tagged", untagged == 0,
                        "Every piece of text is inside tagged content." if untagged == 0 else
                        "%s of text %s outside any tag, where a screen reader may skip "
                        "%s. Export it again from Easy PDF."
                        % (_n(untagged, "character", "characters"),
                           "is" if untagged == 1 else "are", "it" if untagged == 1 else "them"),
                        key="untagged"))

    # 15. List items and LBody (warn only)
    items = [e for e in elements if e.kind == "/LI"]
    without_body = sum(1 for item in items if not any(c.kind == "/LBody" for c in item.children))
    if not items:
        add(CheckResult("List items", True, "There are no lists.", warn_only=True, key="lbody"))
    elif without_body:
        add(CheckResult("List items", False,
                        "%s of %d list %s no LBody element. The PDF engine does not write "
                        "one; PAC may warn about it and screen readers read the items anyway."
                        % (without_body, len(items), "item has" if without_body == 1 else "items have"),
                        warn_only=True, key="lbody"))
    else:
        add(CheckResult("List items", True,
                        "%s carries a label and a body." % ("The 1 list item" if len(items) == 1
                                                             else "Each of the %d list items" % len(items)),
                        warn_only=True, key="lbody"))


# ---------------------------------------------------------- for the export ---


def link_descriptions(pdf):
    """(annotation, text, uri) for every Link structure element that holds a
    link annotation, with the element's text from the content streams. The
    export writes the text as the annotation's Contents."""
    index = TextIndex(pdf)
    found = []
    for elem in walk_tree(pdf, index):
        if elem.kind != "/Link":
            continue
        annots = _annotations_of(elem)
        if not annots:
            continue
        text = element_text(elem, index)
        for annot in annots:
            uri = ""
            try:
                action = annot.get("/A")
                if isinstance(action, pikepdf.Dictionary) and "/URI" in action:
                    uri = str(action.URI)
            except Exception:
                uri = ""
            found.append((annot, text, uri))
    return found
