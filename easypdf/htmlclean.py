"""The one sanitiser. Load, paste, import, save and export all go through it.

    normalise(body_html, for_export=False, embed=None) -> (clean_html, warnings)

Why this exists, measured on 2026-09-09 (CHALLENGE.md E5, W9, W11 and the
Overseer's own probe): the editor's execCommand writes b, i, font, div and
style spans, and Chromium's PDF engine tags every one of those as nothing.
Only strong, em, code, a, headings, p, lists, blockquote, figure and tables
reach the structure tree. A received file ran its onerror handler inside
the editor. So this module does two jobs in one pass: it maps the editor's
markup onto the elements the engine tags, and it lets nothing through that
is not on the allow list below.

The allow list (docs/PDF-UA.md carries the same table):

  Kept:      h1 to h6, p, ul, ol, li, blockquote, strong, em, u, s, code,
             sup, sub, br, hr, a, img, figure, figcaption, table, caption,
             thead, tbody, tfoot, tr, th, td, and pre in the file (a
             code-block p for export).
  Mapped:    b to strong, i to em, strike and del to s, ins to u, tt, kbd,
             samp and var to code, div, section, article, center and the
             other containers to p (or unwrapped when they hold blocks),
             font and span unwrapped after their styles are folded into
             strong, em, u and s.
  Dropped with their content: script, style, template, iframe, object,
             embed, applet, frame, frameset, noscript, noembed, noframes,
             xmp, plaintext, svg, math, form, input, button, select,
             textarea, option, datalist, link, meta, base, head, title,
             video, audio, canvas, map, area.
  Attributes kept: href on a (http, https, mailto, tel), src on img
             (data: only, after embedding), alt, role="presentation" on an
             img with alt="", lang on block elements, scope on th, colspan
             and rowspan, class from the app's own set, and data-needs-alt
             and data-alt-source on img. Everything else is dropped:
             every on* attribute, id, style (after the text-align and span
             folding), title, contenteditable, spellcheck, dir, width and
             height.

Pictures: an img with no alt attribute gets alt="" and data-needs-alt="1"
in the file, with a warning, because a missing description must never
silently become "decorative". For export the same picture is written with
no alt at all, so the engine makes a Figure without Alt, the checker fails
it by name and the PDF/UA identifier is withheld (docs/PDF-UA.md). An img
with alt="" and no data-needs-alt is decorative on purpose and stays out
of the structure tree.

Nothing here touches wx, prints, or reads a file: a local picture is
embedded through the embed callback the caller passes.
"""

import html
import re
from html.parser import HTMLParser

from . import constants as C

# --------------------------------------------------------------- tables ---

KEPT = frozenset((
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "blockquote",
    "strong", "em", "u", "s", "code", "sup", "sub", "br", "hr", "a", "img",
    "figure", "figcaption", "table", "caption", "thead", "tbody", "tfoot",
    "tr", "th", "td", "pre",
))
MAPPED = {
    "b": "strong", "i": "em", "strike": "s", "del": "s", "ins": "u",
    "tt": "code", "kbd": "code", "samp": "code", "var": "code",
    "dt": "p", "dd": "p",
}
DROPPED = frozenset((
    "script", "style", "template", "iframe", "object", "embed", "applet",
    "frame", "frameset", "noscript", "noembed", "noframes", "xmp",
    "plaintext", "svg", "math", "form", "input", "button", "select",
    "textarea", "option", "datalist", "link", "meta", "base", "head",
    "title", "video", "audio", "canvas", "map", "area", "col", "colgroup",
    "source", "track", "param", "wbr",
))
#: Block containers that become a p when they hold only inline content and
#: are unwrapped when they hold blocks. "center" also centres.
CONTAINERS = frozenset((
    "div", "section", "article", "aside", "nav", "header", "footer", "main",
    "address", "details", "summary", "fieldset", "legend", "dl", "center",
    "body", "html", "hgroup", "menu", "dialog", "figure-wrapper",
))
BLOCKS = frozenset((
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "blockquote",
    "hr", "figure", "figcaption", "table", "caption", "thead", "tbody",
    "tfoot", "tr", "th", "td", "pre",
)) | CONTAINERS | frozenset(("dt", "dd"))
HEADINGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
#: Blocks that are dropped when they hold nothing a reader would notice.
EMPTIABLE = HEADINGS | frozenset(("p", "li", "blockquote", "figcaption", "caption"))
#: Elements that may carry a lang attribute in the file.
LANG_BLOCKS = frozenset((
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "th",
    "caption", "figcaption", "figure", "pre", "table",
))
VOID = frozenset(("img", "br", "hr", "wbr", "input", "meta", "link", "base",
                  "col", "area", "source", "track", "param", "embed"))
#: Opening one of these closes an open p, as a browser does.
P_CLOSERS = BLOCKS - frozenset(("figcaption", "caption", "thead", "tbody", "tfoot",
                                "tr", "th", "td", "li", "dt", "dd"))

ALIGN_CLASSES = {"left": "align-left", "start": "align-left",
                 "center": "align-center", "right": "align-right",
                 "end": "align-right", "justify": "align-justify"}
WIDTH_CLASSES = {25: "width-quarter", 50: "width-half", 75: "width-three-quarters",
                 100: "width-full"}
PLACE_CLASSES = {"left": "place-left", "center": "place-centre",
                 "centre": "place-centre", "right": "place-right"}
ALLOWED_CLASSES = frozenset(list(ALIGN_CLASSES.values()) + list(WIDTH_CLASSES.values())
                            + list(PLACE_CLASSES.values()) + ["code-block", "caption"])
ALLOWED_SCHEMES = ("http:", "https:", "mailto:", "tel:")
IMAGE_MIMES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
               "image/bmp")

_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")
#: A font family list is letters, digits, spaces, commas, quotes and
#: hyphens. Anything else (a brace, an angle bracket, a semicolon) could
#: break out of the print page's stylesheet, so it falls back to the
#: default (Overseer round 2, defect 1).
_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 ,'\"-]+$")
#: A source on another computer starts with two separators of either
#: kind (a UNC path, or the device form backslash backslash question mark).
_SHARE_RE = re.compile(r"^[\\/]{2}")
#: Hebrew, Arabic, Syriac, Arabic Supplement and Extended-A, and the two
#: presentation form blocks, written as escapes so nothing invisible sits
#: in the source.
_RTL_RE = re.compile("[\u0590-\u05ff\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff"
                     "\ufb1d-\ufdff\ufe70-\ufeff]")
#: Whitespace, no-break space, zero width space, joiner, non-joiner and the
#: byte order mark: what an "empty" paragraph from the editor really holds.
_EMPTY_RE = re.compile("^[\\s\u00a0\u200b\u200c\u200d\ufeff]*$")
_WS_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"^\d+$")

# ------------------------------------------------------------- strings ---
#: docs/STRINGS.md, Worker A: every sentence here is a draft for Tony.


def _n(count, one, many):
    return ("1 " + one) if count == 1 else ("%d " % count) + many


def _short(text, limit=60):
    text = _WS_RE.sub(" ", text).strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def _name_of(src):
    src = src.strip()
    for prefix in ("file:///", "file://", "file:"):
        if src.lower().startswith(prefix):
            src = src[len(prefix):]
            break
    src = src.replace("\\", "/").rstrip("/")
    tail = src.rsplit("/", 1)[-1]
    try:
        from urllib.parse import unquote
        tail = unquote(tail)
    except Exception:
        pass
    return tail or src


def msg_no_alt_file(count):
    return (_n(count, "picture has", "pictures have")
            + " no description yet. Pictures lists every picture that still needs one.")


def msg_no_alt_export(count):
    return (_n(count, "picture still needs", "pictures still need")
            + " a description. The PDF holds "
            + ("it" if count == 1 else "them")
            + " as a picture without one, which the description check reports.")


def msg_link_dropped(address):
    return ("A link to " + _short(address) + " was removed. Only web, email and "
            "phone addresses can be kept. Its text stays.")


def msg_lang_dropped(words):
    return ("The language mark on \"" + _short(words, 40) + "\" was removed. A mark "
            "on a few words does not reach the PDF. Put the language on the "
            "whole paragraph instead.")


def msg_remote_image(address):
    return ("A picture at " + _short(address) + " was left out. Pictures are never "
            "fetched from the web. Save it to disk and insert it.")


def msg_image_embedded(name):
    return "The picture " + _short(name) + " was copied into the document."


def msg_image_missing(name):
    return ("The picture " + _short(name)
            + " was left out because the file could not be found or read.")


def msg_image_share(name):
    return ("The picture " + _short(name) + " is on a network share and was left "
            "out. Pictures are never fetched from another computer. Copy it to "
            "this computer and insert it.")


def msg_image_type(kind):
    return ("A picture of type " + _short(kind, 30) + " was left out because it cannot go "
            "into the PDF. Save it as PNG or JPEG and insert it.")


def msg_ai_count(count):
    return (_n(count, "picture description was", "picture descriptions were")
            + " written by AI and " + ("has" if count == 1 else "have")
            + " not been checked by somebody who can see the picture.")


def msg_recovered_count(count):
    return (_n(count, "picture description was", "picture descriptions were")
            + " recovered from the original PDF and " + ("has" if count == 1 else "have")
            + " not been checked.")


MSG_RTL = ("The document holds Arabic or Hebrew text. This release has not been "
           "checked with a right to left screen reader, and the PDF may read in "
           "the wrong order.")
MSG_SCRIPT = "Script in the file was removed. It cannot run inside Easy PDF."


# ---------------------------------------------------------------- tree ---


class Element:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []


class _Parser(HTMLParser):
    """A tolerant tree builder. Browsers' tree construction is far bigger
    than this, but every output of this module is re-serialised from the
    tree with everything escaped, so what matters is that nothing survives
    that is not on the allow list, not that every odd input is parsed the
    way a browser would."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#root")
        self.stack = [self.root]

    # -- helpers
    def _open(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                return i
        return -1

    def _close_to(self, index):
        del self.stack[index:]

    def _implied_closes(self, tag):
        if tag in P_CLOSERS or tag in HEADINGS:
            i = self._open("p")
            if i > 0 and all(e.tag not in BLOCKS for e in self.stack[i + 1:]):
                self._close_to(i)
        if tag == "li":
            i = self._open("li")
            if i > 0 and all(e.tag not in ("ul", "ol") for e in self.stack[i + 1:]):
                self._close_to(i)
        if tag in ("td", "th"):
            for cell in ("td", "th"):
                i = self._open(cell)
                if i > 0 and all(e.tag != "table" for e in self.stack[i + 1:]):
                    self._close_to(i)
        if tag == "tr":
            i = self._open("tr")
            if i > 0 and all(e.tag != "table" for e in self.stack[i + 1:]):
                self._close_to(i)
        if tag in ("thead", "tbody", "tfoot"):
            for sec in ("thead", "tbody", "tfoot"):
                i = self._open(sec)
                if i > 0 and all(e.tag != "table" for e in self.stack[i + 1:]):
                    self._close_to(i)
        if tag in ("dt", "dd"):
            for d in ("dt", "dd"):
                i = self._open(d)
                if i > 0 and all(e.tag != "dl" for e in self.stack[i + 1:]):
                    self._close_to(i)

    # -- HTMLParser callbacks
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {}
        for key, value in attrs:
            key = key.lower()
            if key not in attrs_dict:
                attrs_dict[key] = value if value is not None else ""
        self._implied_closes(tag)
        element = Element(tag, attrs_dict)
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "br":
            self.handle_starttag("br", [])
            return
        i = self._open(tag)
        if i > 0:
            self._close_to(i)

    def handle_data(self, data):
        if not data:
            return
        children = self.stack[-1].children
        if children and isinstance(children[-1], str):
            children[-1] += data
        else:
            children.append(data)

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def handle_pi(self, data):
        pass

    def unknown_decl(self, data):
        pass


def parse(text):
    parser = _Parser()
    parser.feed(text or "")
    parser.close()
    return parser.root


# ------------------------------------------------------------- cleaning ---


class _State:
    def __init__(self, for_export, embed):
        self.for_export = for_export
        self.embed = embed
        self.warnings = []
        self.no_alt = 0
        self.ai_alt = 0
        self.pdf_alt = 0
        self.script_seen = False
        self.rtl_seen = False

    def warn(self, sentence):
        if sentence not in self.warnings:
            self.warnings.append(sentence)


def _text_of(node):
    if isinstance(node, str):
        return node
    return "".join(_text_of(child) for child in node.children)


def _is_empty(node):
    """True when a block holds nothing a reader would notice: no text but
    whitespace, no picture, no rule, no nested block."""
    for child in node.children:
        if isinstance(child, str):
            if not _EMPTY_RE.match(child):
                return False
        elif child.tag in ("img", "hr", "table", "ul", "ol", "figure", "pre"):
            return False
        elif child.tag == "br":
            continue
        elif not _is_empty(child):
            return False
    return True


def _style_map(style):
    out = {}
    for part in (style or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip().lower()] = value.strip().lower()
    return out


def _class_list(value):
    return [c for c in (value or "").split() if c in ALLOWED_CLASSES]


def _add_class(attrs, name):
    """Add one of the app's classes. The align, width and place families
    hold one member each, so the newcomer replaces its relative."""
    family = name.split("-", 1)[0] + "-"
    classes = [c for c in _class_list(attrs.get("class"))
               if not (family in ("align-", "width-", "place-") and c.startswith(family))]
    if name not in classes:
        classes.append(name)
    attrs["class"] = " ".join(classes)


def _fold_span_styles(style):
    """Which semantic elements a style span stands for, inner first."""
    styles = _style_map(style)
    wrappers = []
    weight = styles.get("font-weight", "")
    if weight in ("bold", "bolder") or (_NUMBER_RE.match(weight) and int(weight) >= 600):
        wrappers.append("strong")
    if styles.get("font-style", "") in ("italic", "oblique"):
        wrappers.append("em")
    decoration = styles.get("text-decoration", "") + " " + styles.get("text-decoration-line", "")
    if "underline" in decoration:
        wrappers.append("u")
    if "line-through" in decoration:
        wrappers.append("s")
    return wrappers


def _valid_href(value):
    """The address with control characters removed and the ends trimmed,
    if its scheme is one of the four allowed; else None. A space inside
    the address (a mailto subject, say) is kept as %20 rather than
    deleted, so "hello world" does not become "helloworld" (Overseer
    round 2, defect 10). A newline between "java" and "script:" is a control
    character, so it still vanishes and the scheme is still refused."""
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if ord(ch) >= 32 and ord(ch) != 127).strip()
    cleaned = re.sub(r" +", "%20", cleaned)
    lowered = cleaned.lower()
    for scheme in ALLOWED_SCHEMES:
        if lowered.startswith(scheme) and len(cleaned) > len(scheme):
            return cleaned
    return None


def is_network_source(src):
    """True for a picture source on another computer: a UNC path with
    either separator (two backslashes, two slashes, or one of each), a
    device path (backslash backslash question mark), or a file address
    whose host is not empty, not localhost and not a drive letter. Shared
    by the sanitiser and docfile so the rule lives once."""
    src = (src or "").strip()
    if src.lower().startswith("file:"):
        rest = src[5:]
        if not _SHARE_RE.match(rest):
            return False  # file:C:/x or file:/home/x, no host part at all
        host, path = re.match(r"^([^\\/]*)(.*)$", rest[2:], re.DOTALL).groups()
        if host.lower() in ("", "localhost") or re.match(r"^[A-Za-z]:$", host):
            # file:///C:/x and file://localhost/x are this machine; the
            # four slash form file:////server/share is a UNC path again.
            return bool(_SHARE_RE.match(path))
        return True
    return bool(_SHARE_RE.match(src))


def clean_font_family(value):
    """The font family list if it is letters, digits, spaces, commas,
    quotes and hyphens, else the default. Applied on the way into the
    document (docfile) and on the way into the print page (pdfexport)."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text and _FONT_FAMILY_RE.match(text):
        return text
    return C.DEFAULT_FONT_FAMILY


def _clean_lang(value):
    value = (value or "").strip()
    return value if _LANG_RE.match(value) else ""


def _int_attr(value, default=1):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return number if 1 <= number <= 1000 else default


def _has_handler(attrs):
    return any(key.startswith("on") for key in attrs)


def _image_src(attrs, state):
    """The src an img may keep, or None when the picture is dropped."""
    src = (attrs.get("src") or "").strip()
    if not src:
        return None
    lowered = src.lower()
    if lowered.startswith("data:"):
        head = lowered[5:].split(",", 1)[0]
        mime = head.split(";", 1)[0]
        if mime in IMAGE_MIMES and ";base64" in head:
            return src
        state.warn(msg_image_type(mime or "unknown"))
        return None
    if lowered.startswith(("http:", "https:", "//", "ftp:")):
        state.warn(msg_remote_image(src))
        return None
    if lowered.startswith(("javascript:", "vbscript:", "blob:", "about:")):
        state.script_seen = True
        return None
    if is_network_source(src):
        # Never probed: os.path.isfile on a UNC path opens a connection to
        # the named host with the user's credentials the moment the file
        # is opened (Overseer round 2, defect 3).
        state.warn(msg_image_share(_name_of(src)))
        return None
    if state.embed is not None:
        data_uri = None
        try:
            data_uri = state.embed(src)
        except Exception:
            data_uri = None
        if data_uri:
            state.warn(msg_image_embedded(_name_of(src)))
            return data_uri
    state.warn(msg_image_missing(_name_of(src)))
    return None


def _clean_img(node, state, parent_tag):
    attrs = node.attrs
    if _has_handler(attrs):
        state.script_seen = True
    src = _image_src(attrs, state)
    if src is None:
        return []
    out = {"src": src}
    has_alt = "alt" in attrs
    alt = (attrs.get("alt") or "").strip() if has_alt else ""
    needs = attrs.get("data-needs-alt", "") == "1" or not has_alt
    if alt:
        needs = False
    source = (attrs.get("data-alt-source") or "").strip()
    if not alt:
        source = ""
    if alt:
        out["alt"] = alt
    elif state.for_export:
        if needs:
            state.no_alt += 1
            # No alt attribute at all: the engine writes a Figure without
            # Alt and the checker names it (measured, CHALLENGE.md E5).
        else:
            out["alt"] = ""
            if attrs.get("role", "").strip().lower() == "presentation":
                out["role"] = "presentation"
    else:
        out["alt"] = ""
        if needs:
            out["data-needs-alt"] = "1"
            state.no_alt += 1
        elif attrs.get("role", "").strip().lower() == "presentation":
            out["role"] = "presentation"
    if source:
        if source.startswith("ai:"):
            state.ai_alt += 1
        elif source == "pdf":
            state.pdf_alt += 1
        if not state.for_export:
            out["data-alt-source"] = source
            if attrs.get("data-needs-alt", "") == "1":
                out["data-needs-alt"] = "1"
    styles = _style_map(attrs.get("style"))
    element = Element("img", out)
    classes = _class_list(attrs.get("class"))
    for name in classes:
        _add_class(element.attrs, name)
    width = styles.get("width", "")
    if width.endswith("%"):
        _width_class(element.attrs, width)
    return [element]


def _width_class(attrs, width):
    try:
        percent = float(width.rstrip("%"))
    except ValueError:
        return
    nearest = min(WIDTH_CLASSES, key=lambda w: abs(w - percent))
    classes = [c for c in _class_list(attrs.get("class")) if not c.startswith("width-")]
    classes.append(WIDTH_CLASSES[nearest])
    attrs["class"] = " ".join(classes)


def _wrap_inline_runs(children, state, align_class=None):
    """Bare text and inline elements between blocks get a p each."""
    out = []
    run = []

    def flush():
        if run:
            p = Element("p")
            p.children = list(run)
            if align_class:
                _add_class(p.attrs, align_class)
            if not _is_empty(p):
                _strip_edges(p)
                out.append(p)
            del run[:]

    for child in children:
        if isinstance(child, str) or child.tag not in BLOCKS:
            run.append(child)
        else:
            flush()
            out.append(child)
    flush()
    return out


def _strip_edges(block):
    """Trailing br elements and whitespace only text at either edge of a
    block. The editor leaves a br at the end of most blocks."""
    children = block.children
    while children:
        last = children[-1]
        if isinstance(last, str):
            if last.strip(" \t\r\n") == "":
                children.pop()
                continue
            children[-1] = last.rstrip(" \t\r\n")
            break
        if last.tag == "br":
            children.pop()
            continue
        break
    while children and isinstance(children[0], str) and children[0].strip(" \t\r\n") == "":
        children.pop(0)
    if children and isinstance(children[0], str):
        children[0] = children[0].lstrip(" \t\r\n")


def _has_block_child(children):
    return any(not isinstance(c, str) and c.tag in BLOCKS for c in children)


def _clean_children(node, state, parent_tag):
    out = []
    for child in node.children:
        if isinstance(child, str):
            if state.for_export and not state.rtl_seen and _RTL_RE.search(child):
                state.rtl_seen = True
            out.append(child)
        else:
            out.extend(_clean_element(child, state, parent_tag))
    # Merge adjacent text nodes so later checks see whole strings.
    merged = []
    for item in out:
        if isinstance(item, str) and merged and isinstance(merged[-1], str):
            merged[-1] += item
        else:
            merged.append(item)
    return merged


def _clean_element(node, state, parent_tag):
    """Returns a list of nodes that replace this one."""
    tag = node.tag
    attrs = node.attrs
    if _has_handler(attrs):
        state.script_seen = True
    if tag in DROPPED:
        if tag in ("script", "iframe", "object", "embed", "applet"):
            state.script_seen = True
        return []
    if tag == "img":
        return _clean_img(node, state, parent_tag)
    if tag == "br":
        return [Element("br")]
    if tag == "hr":
        return [Element("hr")]
    if tag in MAPPED:
        # dt and dd fall through to the p branch below, which reads the
        # original node's children and attributes.
        tag = MAPPED[tag]
    # ---- containers become p or vanish
    if tag in CONTAINERS:
        align = None
        if tag == "center":
            align = "align-center"
        styles = _style_map(attrs.get("style"))
        if styles.get("text-align") in ALIGN_CLASSES:
            align = ALIGN_CLASSES[styles["text-align"]]
        children = _clean_children(node, state, tag)
        if _has_block_child(children):
            return _wrap_inline_runs(children, state, align)
        p = Element("p")
        p.children = children
        lang = _clean_lang(attrs.get("lang"))
        if lang:
            p.attrs["lang"] = lang
        if align:
            _add_class(p.attrs, align)
        _strip_edges(p)
        return [] if _is_empty(p) else [p]
    if tag in ("span", "font"):
        return _clean_span(node, state, parent_tag)
    if tag == "a":
        return _clean_anchor(node, state, parent_tag)
    if tag == "pre":
        return _clean_pre(node, state)
    if tag in ("ul", "ol"):
        return _clean_list(node, state, tag)
    if tag == "li":
        return _clean_li(node, state)
    if tag == "table":
        return _clean_table(node, state)
    if tag in ("thead", "tbody", "tfoot", "tr", "th", "td", "caption"):
        # Only meaningful inside a table; _clean_table handles them there.
        # Anywhere else the text survives as a paragraph.
        children = _clean_children(node, state, tag)
        return _wrap_inline_runs(children, state)
    if tag == "figure":
        return _clean_figure(node, state)
    if tag == "figcaption":
        if parent_tag == "figure":
            element = Element("figcaption")
            element.children = _clean_children(node, state, "figcaption")
            _copy_lang(attrs, element)
            return [] if _is_empty(element) else [element]
        p = Element("p")
        p.children = _clean_children(node, state, "p")
        return [] if _is_empty(p) else [p]
    if tag in HEADINGS or tag == "p":
        element = Element(tag)
        element.children = _clean_children(node, state, tag)
        if _has_block_child(element.children):
            # A heading holding blocks is not a thing; keep the text.
            return _wrap_inline_runs(element.children, state)
        _copy_lang(attrs, element)
        _copy_align(attrs, element)
        _strip_edges(element)
        return [] if _is_empty(element) else [element]
    if tag == "blockquote":
        element = Element("blockquote")
        children = _clean_children(node, state, "blockquote")
        element.children = _wrap_inline_runs(children, state)
        _copy_lang(attrs, element)
        return [] if _is_empty(element) else [element]
    if tag in ("strong", "em", "u", "s", "code", "sup", "sub"):
        element = Element(tag)
        element.children = _clean_children(node, state, tag)
        if _has_block_child(element.children):
            return _wrap_inline_runs(element.children, state)
        if not element.children:
            return []
        return [element]
    # Anything else: unwrap, text kept.
    return _clean_children(node, state, parent_tag)


def _copy_lang(attrs, element):
    lang = _clean_lang(attrs.get("lang"))
    if lang and element.tag in LANG_BLOCKS:
        element.attrs["lang"] = lang


def _copy_align(attrs, element):
    """The block's own classes first, then an inline text-align, which
    wins over a class because it is the later edit."""
    for name in _class_list(attrs.get("class")):
        if name.startswith("align-") or name == "code-block":
            _add_class(element.attrs, name)
    styles = _style_map(attrs.get("style"))
    align = styles.get("text-align")
    if align in ALIGN_CLASSES:
        _add_class(element.attrs, ALIGN_CLASSES[align])


def _clean_span(node, state, parent_tag):
    attrs = node.attrs
    children = _clean_children(node, state, parent_tag)
    if not children:
        return []
    wrappers = _fold_span_styles(attrs.get("style"))
    lang = _clean_lang(attrs.get("lang"))
    if lang:
        # Kept on the span for now; the block pass decides whether it
        # covers the whole block (hoist) or a few words (drop and warn).
        holder = Element("#lang", {"lang": lang})
        holder.children = children
        children = [holder]
    for wrapper in wrappers:
        element = Element(wrapper)
        element.children = children
        children = [element]
    return children


def _clean_anchor(node, state, parent_tag):
    attrs = node.attrs
    children = _clean_children(node, state, parent_tag)
    raw = attrs.get("href")
    href = _valid_href(raw)
    if href is None:
        if raw is not None and raw.strip():
            lowered = "".join(ch for ch in raw if not ch.isspace()).lower()
            if lowered.startswith(("javascript:", "vbscript:", "data:")):
                state.script_seen = True
            state.warn(msg_link_dropped(raw))
        return children
    if not children or _is_empty_inline(children):
        return children
    element = Element("a", {"href": href})
    element.children = children
    return [element]


def _is_empty_inline(children):
    holder = Element("#tmp")
    holder.children = children
    return _is_empty(holder)


def _clean_pre(node, state):
    text_children = _clean_children(node, state, "pre")
    text = "".join(_text_of(c) for c in text_children)
    if text.startswith("\n"):
        text = text[1:]
    text = text.rstrip("\n")
    if not text.strip():
        return []
    if state.for_export:
        p = Element("p", {"class": "code-block"})
        code = Element("code")
        lines = text.split("\n")
        for index, line in enumerate(lines):
            if index:
                code.children.append(Element("br"))
            code.children.append(line)
        p.children = [code]
        return [p]
    pre = Element("pre")
    pre.children = [text]
    return [pre]


def _clean_list(node, state, tag):
    element = Element(tag)
    items = []
    stray = []

    def flush_stray():
        if stray:
            li = Element("li")
            li.children = _wrap_inline_runs(stray, state) if _has_block_child(stray) else list(stray)
            if not _is_empty(li):
                items.append(li)
            del stray[:]

    for child in _clean_children(node, state, tag):
        if isinstance(child, str):
            if not _EMPTY_RE.match(child):
                stray.append(child)
            continue
        if child.tag == "li":
            flush_stray()
            items.append(child)
        elif child.tag in ("ul", "ol"):
            # execCommand indent writes a list straight inside a list
            # (measured: L inside L in the PDF). It belongs to the item
            # before it.
            flush_stray()
            if items:
                items[-1].children.append(child)
            else:
                li = Element("li")
                li.children = [child]
                items.append(li)
        else:
            stray.append(child)
    flush_stray()
    element.children = items
    _copy_lang(node.attrs, element)
    return [element] if items else []


def _clean_li(node, state):
    element = Element("li")
    children = _clean_children(node, state, "li")
    # An item's own text stays bare when its only blocks are nested lists,
    # which is the shape the editor writes; other blocks make it mixed
    # content and the text runs get paragraphs.
    if any(not isinstance(c, str) and c.tag in BLOCKS and c.tag not in ("ul", "ol")
           for c in children):
        children = _wrap_inline_runs(children, state)
    element.children = children
    _copy_lang(node.attrs, element)
    _copy_align(node.attrs, element)
    _strip_edges(element)
    return [] if _is_empty(element) else [element]


def _clean_table(node, state):
    table = Element("table")
    caption = None
    sections = []
    rows_loose = []
    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag == "caption" and caption is None:
            caption = Element("caption")
            caption.children = _clean_children(child, state, "caption")
            _copy_lang(child.attrs, caption)
            if _is_empty(caption):
                caption = None
        elif child.tag in ("thead", "tbody", "tfoot"):
            section = Element(child.tag)
            section.children = _clean_rows(child, state)
            if section.children:
                sections.append(section)
        elif child.tag == "tr":
            rows_loose.extend(_clean_rows(Element("#rows", {}), state, [child]))
        elif child.tag in ("colgroup", "col"):
            continue
        else:
            # Text or blocks inside a table but outside a row: keep them
            # after the table rather than lose them.
            rows_loose.append(("#after", _clean_element(child, state, "table")))
    after = []
    rows = []
    for item in rows_loose:
        if isinstance(item, tuple):
            after.extend(item[1])
        else:
            rows.append(item)
    if rows:
        body = Element("tbody")
        body.children = rows
        sections.append(body)
    all_rows = [row for section in sections for row in section.children]
    if not all_rows:
        return after
    _scope_headers(all_rows, sections)
    table.children = ([caption] if caption is not None else []) + sections
    _copy_lang(node.attrs, table)
    return [table] + after


def _clean_rows(node, state, rows_in=None):
    rows = []
    source = rows_in if rows_in is not None else [c for c in node.children if not isinstance(c, str)]
    for child in source:
        if isinstance(child, str) or child.tag != "tr":
            continue
        tr = Element("tr")
        for cell in child.children:
            if isinstance(cell, str) or cell.tag not in ("td", "th"):
                continue
            element = Element(cell.tag)
            children = _clean_children(cell, state, cell.tag)
            if _has_block_child(children):
                children = _wrap_inline_runs(children, state)
            element.children = children
            _strip_edges(element)
            _copy_lang(cell.attrs, element)
            _copy_align(cell.attrs, element)
            colspan = _int_attr(cell.attrs.get("colspan"))
            rowspan = _int_attr(cell.attrs.get("rowspan"))
            if colspan > 1:
                element.attrs["colspan"] = str(colspan)
            if rowspan > 1:
                element.attrs["rowspan"] = str(rowspan)
            scope = (cell.attrs.get("scope") or "").strip().lower()
            if cell.tag == "th" and scope in ("col", "row", "colgroup", "rowgroup"):
                element.attrs["scope"] = scope
            tr.children.append(element)
        if tr.children:
            rows.append(tr)
    return rows


def _scope_headers(rows, sections):
    """th in the first row (or in thead) get scope col; th in the first
    column of later rows get scope row. Explicit scopes stay."""
    first_row = rows[0]
    header_rows = set()
    for section in sections:
        if section.tag == "thead":
            header_rows.update(id(r) for r in section.children)
    header_rows.add(id(first_row))
    first_row_all_th = all(c.tag == "th" for c in first_row.children)
    for row in rows:
        for index, cell in enumerate(row.children):
            if cell.tag != "th" or "scope" in cell.attrs:
                continue
            if id(row) in header_rows and (first_row_all_th or id(row) != id(first_row)):
                cell.attrs["scope"] = "col"
            elif index == 0:
                cell.attrs["scope"] = "row"
            else:
                cell.attrs["scope"] = "col"


def _clean_figure(node, state):
    attrs = node.attrs
    figure = Element("figure")
    children = _clean_children(node, state, "figure")
    images = [c for c in children if not isinstance(c, str) and c.tag == "img"]
    captions = [c for c in children if not isinstance(c, str) and c.tag == "figcaption"]
    if not images:
        # A caption with no picture is just text now.
        out = []
        for caption in captions:
            p = Element("p")
            p.children = caption.children
            out.append(p)
        others = [c for c in children if isinstance(c, str) or c.tag not in ("img", "figcaption")]
        out.extend(_wrap_inline_runs(others, state))
        return out
    caption = captions[0] if captions else None
    stray = [c for c in children if isinstance(c, str) or c.tag not in ("img", "figcaption")]
    if any(isinstance(c, str) and not _EMPTY_RE.match(c) or not isinstance(c, str) for c in stray):
        # Text inside a figure but outside its caption is caption text;
        # nothing a person wrote is dropped.
        if caption is None:
            caption = Element("figcaption")
        caption.children.extend(_wrap_inline_runs(stray, state) if _has_block_child(stray) else stray)
        if _is_empty(caption):
            caption = None
    figure.children = images + ([caption] if caption is not None else [])
    styles = _style_map(attrs.get("style"))
    for name in _class_list(attrs.get("class")):
        _add_class(figure.attrs, name)
    if styles.get("width", "").endswith("%"):
        _width_class(figure.attrs, styles["width"])
    align = styles.get("text-align")
    if align in PLACE_CLASSES and not any(c.startswith("place-") for c in _class_list(figure.attrs.get("class"))):
        _add_class(figure.attrs, PLACE_CLASSES[align])
    if styles.get("float") in ("left", "right") and not any(c.startswith("place-") for c in _class_list(figure.attrs.get("class"))):
        _add_class(figure.attrs, PLACE_CLASSES[styles["float"]])
    _copy_lang(attrs, figure)
    if state.for_export:
        # Measured 2026-09-09: a plain figure becomes a Figure with no Alt
        # wrapped round the picture's own Figure, which fails the
        # description check in PAC and here. With role presentation the
        # picture and its Caption sit side by side, each properly tagged.
        figure.attrs["role"] = "presentation"
    return [figure]


# ------------------------------------------------------- the lang pass ---


def _resolve_lang_holders(node, state):
    """A #lang holder that is the whole text of its block moves its lang
    onto the block; any other is unwrapped with a warning naming the words
    (Chromium writes no Span element, measured)."""
    for child in list(node.children):
        if isinstance(child, str):
            continue
        _resolve_lang_holders(child, state)
    if node.tag in LANG_BLOCKS:
        holders = _direct_holders(node)
        if len(holders) == 1 and _covers_block(node, holders[0]):
            holder = holders[0]
            if "lang" not in node.attrs:
                node.attrs["lang"] = holder.attrs["lang"]
                _replace(node, holder, holder.children)
                return
    for child in list(node.children):
        if not isinstance(child, str) and child.tag == "#lang":
            words = _text_of(child)
            if words.strip():
                state.warn(msg_lang_dropped(words))
            _replace(node, child, child.children)


def _direct_holders(node):
    """#lang holders reachable through inline elements only."""
    found = []

    def visit(element):
        for child in element.children:
            if isinstance(child, str):
                continue
            if child.tag == "#lang":
                found.append(child)
            elif child.tag not in BLOCKS:
                visit(child)
    visit(node)
    return found


def _covers_block(block, holder):
    inside = _text_of(holder)
    whole = _text_of(block)
    return _WS_RE.sub("", inside) == _WS_RE.sub("", whole) and inside.strip() != ""


def _replace(parent, child, replacement):
    index = parent.children.index(child)
    parent.children[index:index + 1] = list(replacement)


def _unwrap_all_holders(node):
    for child in list(node.children):
        if isinstance(child, str):
            continue
        _unwrap_all_holders(child)
        if child.tag == "#lang":
            _replace(node, child, child.children)


# --------------------------------------------------------- serialising ---

ATTR_ORDER = ("src", "href", "alt", "class", "lang", "scope", "colspan", "rowspan",
              "role", "data-needs-alt", "data-alt-source")


def _serialise(node, out, in_pre=False):
    """Every text and attribute value escaped; attributes in one fixed
    order so two saves of the same document are byte identical."""
    for child in node.children:
        if isinstance(child, str):
            out.append(html.escape(child, quote=False))
            continue
        tag = child.tag
        parts = ["<", tag]
        for key in ATTR_ORDER:
            if key not in child.attrs:
                continue
            value = str(child.attrs[key])
            if value == "" and key != "alt":
                continue
            parts.append(' %s="%s"' % (key, html.escape(value, quote=True)))
        parts.append(">")
        out.append("".join(parts))
        if tag in VOID:
            if tag == "hr" and not in_pre:
                out.append("\n")
            continue
        _serialise(child, out, in_pre or tag == "pre")
        out.append("</%s>" % tag)
        if tag in BLOCKS and not in_pre:
            out.append("\n")


def to_html(root):
    out = []
    _serialise(root, out)
    return "".join(out).strip("\n")


# ----------------------------------------------------------- the entry ---


def normalise(body_html, for_export=False, embed=None):
    """The one sanitiser.

    body_html: the editor's body, a pasted fragment, an imported document
      or a whole page (html and body are unwrapped; head is dropped).
    for_export: also strip every data-* attribute (after counting the AI
      and recovered descriptions into warnings), write undescribed pictures
      with no alt so the engine and the checker see them, turn pre into a
      code-block p, mark figures presentational, and warn on right to left
      script.
    embed: callable(src) -> data URI or None, used for a local picture
      whose src is a file path; None means local pictures are dropped with
      a warning. Remote pictures are never fetched.

    Returns (clean_html, warnings). Warnings are sentences; the caller
    shows them. Nothing prints.
    """
    state = _State(for_export, embed)
    root = parse(body_html)
    cleaned = Element("#root")
    cleaned.children = _clean_children(root, state, "#root")
    cleaned.children = _wrap_inline_runs(cleaned.children, state)
    _resolve_lang_holders(cleaned, state)
    _unwrap_all_holders(cleaned)
    _drop_empty_blocks(cleaned)
    warnings = []
    if state.no_alt:
        warnings.append(msg_no_alt_export(state.no_alt) if for_export
                        else msg_no_alt_file(state.no_alt))
    if for_export and state.ai_alt:
        warnings.append(msg_ai_count(state.ai_alt))
    if for_export and state.pdf_alt:
        warnings.append(msg_recovered_count(state.pdf_alt))
    if for_export and state.rtl_seen:
        warnings.append(MSG_RTL)
    if state.script_seen:
        warnings.append(MSG_SCRIPT)
    warnings.extend(state.warnings)
    return to_html(cleaned), warnings


def _drop_empty_blocks(node):
    for child in list(node.children):
        if isinstance(child, str):
            continue
        _drop_empty_blocks(child)
        if child.tag in EMPTIABLE:
            if _is_empty(child):
                node.children.remove(child)
        elif child.tag in ("ul", "ol", "thead", "tbody", "tfoot", "tr"):
            if not any(not isinstance(c, str) for c in child.children):
                node.children.remove(child)
        elif child.tag == "table":
            if not any(not isinstance(c, str) and c.tag in ("thead", "tbody", "tfoot") for c in child.children):
                node.children.remove(child)


def plain_text(body_html):
    """The words of a body, for word counts and warnings. Blocks are
    separated by newlines."""
    root = parse(body_html)
    out = []

    def visit(node):
        for child in node.children:
            if isinstance(child, str):
                out.append(child)
            else:
                if child.tag in DROPPED:
                    continue
                visit(child)
                if child.tag in BLOCKS or child.tag == "br":
                    out.append("\n")
    visit(root)
    text = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def generator_string():
    return "%s %s" % (C.APP_NAME, C.APP_VERSION)
