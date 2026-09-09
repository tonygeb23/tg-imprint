"""Markdown to HTML, through markdown-it-py (DECISIONS.md decision 3).

    to_html(text) -> html

CommonMark plus pipe tables and strikethrough. Raw HTML inside the
Markdown is escaped, not parsed, so a Markdown file cannot smuggle markup
past the sanitiser; the result goes through htmlclean.normalise in
docfile.load anyway, which also embeds a local picture that exists.
"""

from markdown_it import MarkdownIt


def _parser():
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    return md


def to_html(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return _parser().render(text)
