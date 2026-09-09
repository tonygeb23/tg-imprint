"""
Document model → semantic HTML5 for WeasyPrint.

WeasyPrint maps HTML semantics directly to PDF/UA-1 structure tags:
  <h1>…<h6>  →  /H1…/H6  structure elements
  <p>         →  /P
  <ul> / <ol> →  /L  with  <li> → /LI
  <img alt="">→  /Figure  with  /Alt  attribute  (or Artifact if alt="")
  <a href=""> →  /Link  with  /URI  action
  <strong>    →  /Strong  (announces "bold" semantics to AT)
  <em>        →  /Em     (announces "italic" semantics to AT)

CSS @page sets letter-size margins.  Inline alignment styles on <p>
propagate to the PDF paragraph layout.

WebAIM / WCAG notes embedded as comments below.
"""
from __future__ import annotations

import os
from html import escape as _esc
from pathlib import Path

from core.document import (
    Document, HeadingNode, ParagraphNode, ImageNode,
    ListNode, BlockQuoteNode, Run,
)

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_CSS = """\
@page {
  size: letter;
  margin: 1in;
}
body {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #000000;
}
h1 { font-size: 26pt; font-weight: bold;  margin: 18pt 0 6pt; }
h2 { font-size: 20pt; font-weight: bold;  margin: 14pt 0 4pt; }
h3 { font-size: 16pt; font-weight: bold;  margin: 12pt 0 4pt; }
h4 { font-size: 14pt; font-weight: bold;  margin: 10pt 0 4pt; }
h5 { font-size: 13pt; font-weight: bold;  font-style: italic; margin: 8pt 0 2pt; }
h6 { font-size: 12pt; font-weight: normal; font-style: italic; margin: 8pt 0 2pt; }
p  { margin: 0 0 8pt; }
blockquote {
  margin: 8pt 0 8pt 2em;
  padding: 0 0 0 1em;
  border-left: 3px solid #cccccc;
  font-style: italic;
  color: #444444;
}
ul, ol { margin: 4pt 0 8pt; padding-left: 2em; }
li     { margin-bottom: 4pt; }
/* WCAG 1.4.1 — colour alone must not convey info; underline also present */
a      { color: #0000b4; text-decoration: underline; }
figure { margin: 8pt 0; text-align: center; }
figure img  { max-width: 100%; height: auto; }
figcaption  { font-size: 9pt; color: #555555; margin-top: 4pt; }
code        { font-family: Courier New, Courier, monospace; }
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def document_to_html(doc: Document) -> str:
    """
    Convert a Document model to a complete HTML5 string suitable for
    WeasyPrint.  The output uses semantic elements so WeasyPrint can build
    a proper PDF/UA-1 structure tree automatically.
    """
    title_safe  = _esc(doc.title or "Untitled")
    author_safe = _esc(doc.author or "")
    lang_safe   = _esc(doc.lang or "en-US", quote=True)

    head = (
        f'<!DOCTYPE html>\n'
        f'<html lang="{lang_safe}">\n'
        f'<head>\n'
        f'<meta charset="UTF-8">\n'
        f'<title>{title_safe}</title>\n'
        f'<meta name="author" content="{author_safe}">\n'
        f'<style>\n{_CSS}</style>\n'
        f'</head>\n'
        f'<body>\n'
    )
    body_parts = [_node_to_html(n) for n in doc.nodes]
    return head + "\n".join(body_parts) + "\n</body>\n</html>\n"


# ---------------------------------------------------------------------------
# Node conversion
# ---------------------------------------------------------------------------

def _node_to_html(node) -> str:
    if isinstance(node, HeadingNode):
        return _heading(node)
    if isinstance(node, ParagraphNode):
        return _paragraph(node)
    if isinstance(node, BlockQuoteNode):
        return _blockquote(node)
    if isinstance(node, ImageNode):
        return _image(node)
    if isinstance(node, ListNode):
        return _list(node)
    return ""


def _heading(node: HeadingNode) -> str:
    lvl  = max(1, min(6, node.level))
    text = _esc(node.text)
    return f"<h{lvl}>{text}</h{lvl}>"


def _paragraph(node: ParagraphNode) -> str:
    inner = _runs_to_html(node.runs)
    if not inner.strip():
        return ""
    style = _align_style(node.alignment)
    attrs = f' style="{style}"' if style else ""
    return f"<p{attrs}>{inner}</p>"


def _blockquote(node: BlockQuoteNode) -> str:
    inner = _runs_to_html(node.runs)
    if not inner.strip():
        return ""
    style = _align_style(node.alignment)
    attrs = f' style="{style}"' if style else ""
    return f"<blockquote><p{attrs}>{inner}</p></blockquote>"


def _image(node: ImageNode) -> str:
    if node.path and os.path.isfile(node.path):
        src = _path_to_url(node.path)
        if node.alt_text:
            # Informative image — alt text required (WCAG 1.1.1)
            alt  = _esc(node.alt_text, quote=True)
            cap  = _esc(node.alt_text)
            return (
                f'<figure>'
                f'<img src="{src}" alt="{alt}">'
                f'<figcaption>{cap}</figcaption>'
                f'</figure>'
            )
        else:
            # Decorative image — alt="" tells AT to skip it (WCAG 1.1.1)
            return f'<figure><img src="{src}" alt="" role="presentation"></figure>'
    else:
        # File missing — emit alt text as italic paragraph so content is not lost
        if node.alt_text:
            return f"<p><em>[Image: {_esc(node.alt_text)}]</em></p>"
        return ""


def _list(node: ListNode) -> str:
    if not node.items:
        return ""
    tag   = "ol" if node.ordered else "ul"
    items = "".join(
        f"<li>{_runs_to_html(li.runs)}</li>"
        for li in node.items
        if any(r.text.strip() for r in li.runs)
    )
    return f"<{tag}>{items}</{tag}>" if items else ""


# ---------------------------------------------------------------------------
# Run (inline) conversion
# ---------------------------------------------------------------------------

def _runs_to_html(runs: list[Run]) -> str:
    """
    Convert character-level runs to HTML inline markup.

    Uses <strong>/<em> (semantic) rather than <b>/<i> so screen readers
    can announce bold/italic semantics, and so WeasyPrint maps them to
    PDF /Strong and /Em structure roles.
    """
    parts = []
    for r in runs:
        t = _esc(r.text)
        if not t:
            continue

        # Character formatting (innermost → outermost)
        if r.code:
            t = f"<code>{t}</code>"
        if r.bold and r.italic:
            t = f"<strong><em>{t}</em></strong>"
        elif r.bold:
            t = f"<strong>{t}</strong>"
        elif r.italic:
            t = f"<em>{t}</em>"
        if r.strikethrough:
            t = f"<s>{t}</s>"
        if r.underline:
            t = f'<span style="text-decoration:underline">{t}</span>'

        # Hyperlinks — wrap last so the link contains all formatting
        # WCAG 2.4.4: link text must describe purpose — enforced at insert time
        if r.link:
            href = _esc(r.link, quote=True)
            t = f'<a href="{href}">{t}</a>'

        parts.append(t)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _align_style(alignment: str) -> str:
    """Return a CSS text-align inline style fragment, or empty string for left."""
    if alignment in ("center", "right", "justify"):
        return f"text-align:{alignment}"
    return ""


def _path_to_url(path: str) -> str:
    """Convert an OS absolute path to a file:/// URL WeasyPrint can load."""
    return Path(os.path.abspath(path)).as_uri()
