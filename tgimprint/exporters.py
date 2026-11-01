"""The other ways out: Word, Markdown and plain text.

    export_docx(body_html, path, meta)
    export_markdown(body_html, path, meta)
    export_text(body_html, path, meta)
    KINDS   {"docx": export_docx, "md": export_markdown, "txt": export_text}

A PDF somebody sent often ends up wanted as words to read or to pass on, so
each of these takes the same clean HTML the PDF export does. The Word file
is an accessible Word file: real heading styles, real list styles, real
hyperlinks, the description on every picture, a repeating header row on
every table, the title and language in the properties.

Each one writes through docfile.write_atomic or a temp file, so a failure
leaves the earlier file alone. Nothing here touches wx or prints.
"""

import base64
import io
import os
import re
import tempfile
from html.parser import HTMLParser

from . import docfile, htmlclean

#: What XML cannot hold, so what a Word file refuses outright.
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag="", attrs=None, text=""):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.text = text


class _Tree(HTMLParser):
    VOID = ("br", "hr", "img")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("body")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                break

    def handle_data(self, data):
        data = _CONTROL.sub("", data)
        if data:
            self.stack[-1].children.append(Node(text=data))


def parse(body_html):
    tree = _Tree()
    tree.feed(body_html)
    tree.close()
    return tree.root


def _clean(body_html):
    clean, _warnings = htmlclean.normalise(body_html)
    return clean


def plain(node):
    if node.text:
        return node.text
    if node.tag == "br":
        return "\n"
    return "".join(plain(child) for child in node.children)


def _squash(text):
    return re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*", "\n", re.sub(r"[ \t\r\f\v]+", " ", text)).strip()


# --------------------------------------------------------------- markdown ---


def _picture_words(node):
    """Neither format can hold the picture, so its description stands in,
    and a picture with none is still said to be there."""
    alt = node.attrs.get("alt", "").strip()
    if alt:
        return "Picture: " + alt
    if node.attrs.get("role") == "presentation":
        return ""
    return "Picture with no description."


def _title_line(root, meta, mark=""):
    """The title, when the body has no level 1 heading to carry it."""
    title = str((meta or {}).get("title") or "").strip()
    if not title or any(node.tag == "h1" for node in root.children):
        return []
    return [mark + title, ""]


def _md_escape(text):
    return re.sub(r"([\\`*_\[\]])", r"\\\1", text)


def _md_inline(node):
    out = []
    for child in node.children:
        if child.text:
            out.append(_md_escape(re.sub(r"\s+", " ", child.text)))
        elif child.tag == "br":
            out.append("  \n")
        elif child.tag in ("strong", "b"):
            out.append("**%s**" % _md_inline(child))
        elif child.tag in ("em", "i"):
            out.append("*%s*" % _md_inline(child))
        elif child.tag == "code":
            out.append("`%s`" % plain(child))
        elif child.tag == "a":
            out.append("[%s](%s)" % (_md_inline(child), child.attrs.get("href", "")))
        elif child.tag == "img":
            out.append(_picture_words(child))
        else:
            out.append(_md_inline(child))
    return "".join(out)


def _md_list(node, depth, out):
    number = 0
    for item in node.children:
        if item.tag != "li":
            continue
        number += 1
        lead = "%d. " % number if node.tag == "ol" else "- "
        nested = [c for c in item.children if c.tag in ("ul", "ol")]
        own = Node("li")
        own.children = [c for c in item.children if c.tag not in ("ul", "ol")]
        out.append("%s%s%s" % ("    " * depth, lead, _md_inline(own).strip()))
        for sub in nested:
            _md_list(sub, depth + 1, out)


def _md_table(node, out):
    rows = []

    def walk(current):
        for child in current.children:
            if child.tag == "tr":
                rows.append([_md_inline(c).replace("|", "\\|").strip()
                             for c in child.children if c.tag in ("th", "td")])
            elif child.tag in ("thead", "tbody", "tfoot"):
                walk(child)
            elif child.tag == "caption":
                out.append(_md_inline(child))
                out.append("")

    walk(node)
    if not rows:
        return
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out.append("| %s |" % " | ".join(rows[0]))
    out.append("| %s |" % " | ".join(["---"] * width))
    for row in rows[1:]:
        out.append("| %s |" % " | ".join(row))


def to_markdown(body_html, meta=None):
    root = parse(_clean(body_html))
    out = _title_line(root, meta, "# ")
    for node in root.children:
        if node.text:
            continue
        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            out.append("%s %s" % ("#" * int(node.tag[1]), _md_inline(node).strip()))
        elif node.tag in ("ul", "ol"):
            _md_list(node, 0, out)
        elif node.tag == "blockquote":
            for line in _md_inline(node).strip().splitlines() or [""]:
                out.append("> " + line.strip())
        elif node.tag == "table":
            _md_table(node, out)
        elif node.tag == "pre":
            out.append("```\n%s\n```" % plain(node).strip("\n"))
        elif node.tag == "hr":
            out.append("---")
        elif node.tag == "figure":
            for child in node.children:
                if child.tag == "img":
                    out.append(_picture_words(child))
                elif child.tag == "figcaption":
                    out.append("")
                    out.append(_md_inline(child).strip())
        else:
            text = _md_inline(node).strip()
            if text:
                out.append(text)
        out.append("")
    return "\n".join(out).strip() + "\n"


# ------------------------------------------------------------------ text ---


def _text_table(node, out):
    def walk(current):
        for child in current.children:
            if child.tag == "tr":
                out.append("    ".join(_squash(plain(c)) for c in child.children
                                       if c.tag in ("th", "td")))
            elif child.tag in ("thead", "tbody", "tfoot"):
                walk(child)
            elif child.tag == "caption":
                out.append(_squash(plain(child)))

    walk(node)


def _text_list(node, depth, out):
    number = 0
    for item in node.children:
        if item.tag != "li":
            continue
        number += 1
        lead = "%d. " % number if node.tag == "ol" else "* "
        own = Node("li")
        own.children = [c for c in item.children if c.tag not in ("ul", "ol")]
        out.append("%s%s%s" % ("  " * depth, lead, _squash(plain(own))))
        for sub in item.children:
            if sub.tag in ("ul", "ol"):
                _text_list(sub, depth + 1, out)


def to_text(body_html, meta=None):
    root = parse(_clean(body_html))
    out = _title_line(root, meta)
    for node in root.children:
        if node.text:
            continue
        if node.tag in ("ul", "ol"):
            _text_list(node, 0, out)
        elif node.tag == "table":
            _text_table(node, out)
        elif node.tag == "figure":
            for child in node.children:
                if child.tag == "img":
                    words = _picture_words(child)
                    if words:
                        out.append(words)
                elif child.tag == "figcaption":
                    out.append(_squash(plain(child)))
        elif node.tag == "hr":
            continue
        else:
            text = _squash(plain(node))
            if text:
                out.append(text)
        out.append("")
    return "\n".join(out).strip() + "\n"


# ------------------------------------------------------------------- word ---


def _add_hyperlink(paragraph, url, text, bold=False, italic=False):
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    part = paragraph.part
    rel = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "0000B4")
    props.append(colour)
    line = OxmlElement("w:u")
    line.set(qn("w:val"), "single")
    props.append(line)
    if bold:
        props.append(OxmlElement("w:b"))
    if italic:
        props.append(OxmlElement("w:i"))
    run.append(props)
    body = OxmlElement("w:t")
    body.text = text
    body.set(qn("xml:space"), "preserve")
    run.append(body)
    link.append(run)
    paragraph._p.append(link)


def _runs(paragraph, node, bold=False, italic=False, code=False, underline=False, strike=False):
    for child in node.children:
        if child.text:
            text = re.sub(r"\s+", " ", child.text)
            if not text:
                continue
            run = paragraph.add_run(text)
            run.bold = bold or None
            run.italic = italic or None
            run.underline = underline or None
            run.font.strike = strike or None
            if code:
                run.font.name = "Consolas"
        elif child.tag == "br":
            paragraph.add_run().add_break()
        elif child.tag == "a":
            _add_hyperlink(paragraph, child.attrs.get("href", ""), plain(child), bold, italic)
        elif child.tag == "img":
            _picture(paragraph.part.document, child, paragraph)
        else:
            _runs(paragraph, child,
                  bold or child.tag in ("strong", "b"), italic or child.tag in ("em", "i"),
                  code or child.tag == "code", underline or child.tag == "u",
                  strike or child.tag == "s")


def _picture(document, node, paragraph=None):
    from docx.shared import Inches
    source = node.attrs.get("src", "")
    match = re.match(r"data:[^;,]+;base64,(.*)$", source, re.DOTALL)
    if not match:
        return
    data = base64.b64decode(match.group(1))
    try:
        image = docfile.png_safe_bytes(data)
    except Exception:
        return
    run = (paragraph or document.add_paragraph()).add_run()
    shape = run.add_picture(io.BytesIO(image), width=Inches(5))
    props = shape._inline.docPr
    alt = node.attrs.get("alt", "").strip()
    props.set("descr", alt)
    if not alt:
        props.set("title", "")


def _docx_list(document, node, depth):
    style = "List Number" if node.tag == "ol" else "List Bullet"
    if depth:
        style += " %d" % min(depth + 1, 3)
    for item in node.children:
        if item.tag != "li":
            continue
        own = Node("li")
        own.children = [c for c in item.children if c.tag not in ("ul", "ol")]
        _runs(document.add_paragraph(style=style), own)
        for sub in item.children:
            if sub.tag in ("ul", "ol"):
                _docx_list(document, sub, depth + 1)


def _docx_table(document, node):
    from docx.oxml import OxmlElement
    rows = []
    caption = None

    def walk(current):
        nonlocal caption
        for child in current.children:
            if child.tag == "tr":
                rows.append([c for c in child.children if c.tag in ("th", "td")])
            elif child.tag in ("thead", "tbody", "tfoot"):
                walk(child)
            elif child.tag == "caption":
                caption = child

    walk(node)
    if not rows:
        return
    if caption is not None:
        _runs(document.add_paragraph(style="Caption"), caption)
    width = max(len(r) for r in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    for row_index, row in enumerate(rows):
        for cell_index, cell in enumerate(row):
            target = table.cell(row_index, cell_index).paragraphs[0]
            _runs(target, cell, bold=cell.tag == "th")
    if any(c.tag == "th" for c in rows[0]):
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))


def build_docx(body_html, meta=None):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    meta = meta or {}
    document = Document()
    props = document.core_properties
    props.title = str(meta.get("title") or "")
    props.author = str(meta.get("author") or "")
    props.subject = str(meta.get("subject") or "")
    lang = str(meta.get("lang") or "")
    if lang:
        props.language = lang
        styles = document.styles.element
        defaults = styles.find(qn("w:docDefaults"))
        run_props = None if defaults is None else defaults.find(qn("w:rPrDefault") + "/" + qn("w:rPr"))
        if run_props is not None:
            element = run_props.find(qn("w:lang"))
            if element is None:
                element = OxmlElement("w:lang")
                run_props.append(element)
            element.set(qn("w:val"), lang)
    for node in parse(_clean(body_html)).children:
        if node.text:
            continue
        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            paragraph = document.add_heading("", level=int(node.tag[1]))
            _runs(paragraph, node)
        elif node.tag in ("ul", "ol"):
            _docx_list(document, node, 0)
        elif node.tag == "blockquote":
            paragraph = document.add_paragraph(style="Quote")
            _runs(paragraph, node)
        elif node.tag == "table":
            _docx_table(document, node)
        elif node.tag == "figure":
            for child in node.children:
                if child.tag == "img":
                    _picture(document, child)
                elif child.tag == "figcaption":
                    _runs(document.add_paragraph(style="Caption"), child)
        elif node.tag == "hr":
            continue
        elif node.tag == "pre":
            paragraph = document.add_paragraph()
            run = paragraph.add_run(plain(node))
            run.font.name = "Consolas"
        else:
            paragraph = document.add_paragraph()
            _runs(paragraph, node)
    return document


def _replace_with(path, writer):
    folder = os.path.dirname(os.path.abspath(path)) or "."
    handle, temp = tempfile.mkstemp(dir=folder, prefix=".tgimprint-", suffix=".part")
    os.close(handle)
    try:
        writer(temp)
        os.replace(temp, path)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


def export_docx(body_html, path, meta=None):
    document = build_docx(body_html, meta)
    _replace_with(path, document.save)


def export_markdown(body_html, path, meta=None):
    docfile.write_atomic(path, to_markdown(body_html, meta))


def export_text(body_html, path, meta=None):
    docfile.write_atomic(path, to_text(body_html, meta))


KINDS = {"docx": export_docx, "md": export_markdown, "txt": export_text}
