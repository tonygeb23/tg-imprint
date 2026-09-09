"""
Parse a wx.TextCtrl (TE_RICH2) buffer into the Document model.

Strategy
--------
Walk every line of the TextCtrl:
  1. Read the line text and the wx.TextAttr at the line start.
  2. Classify the line (heading, list item, block quote, image, normal).
  3. For paragraphs/list items, walk character-by-character to extract
     character-level formatting runs (bold, italic, underline).
  4. Read paragraph alignment from wx.TextAttr and store it on the node.

Paragraph type is inferred from:
  - Visible list prefix  ("• " or "N. ")  → list item
  - Image marker prefix  ("📷 ")           → image
  - Font size + bold at line start        → heading level
  - Italic + left indent                  → block quote
  - Anything else                         → normal paragraph
"""
from __future__ import annotations

import re
import wx

from core.document import (
    Document, HeadingNode, ParagraphNode,
    ListNode, ListItemNode, BlockQuoteNode, ImageNode, Run,
)
from ui.editor import IMAGE_MARKER_PREFIX, _align_wx_to_str, _LINK_COLOR_RGB

_BULLET_RE    = re.compile(r"^•\s")
_NUMBERED_RE  = re.compile(r"^\d+\.\s")
_IMAGE_PREFIX = IMAGE_MARKER_PREFIX             # "📷 "


def parse_document(editor, title: str = "Untitled", lang: str = "en-US", author: str = "") -> Document:
    ctrl        = editor.ctrl
    img_lookup  = {d["marker"]: d for d in editor.get_images()}
    # Build lookup: display_text → url (last entry wins for duplicates)
    link_lookup = {d["display_text"]: d["url"] for d in editor.get_links()}

    nodes: list = []
    pending_list: ListNode | None = None
    pending_ordered: bool | None  = None

    def flush_list() -> None:
        nonlocal pending_list, pending_ordered
        if pending_list is not None:
            nodes.append(pending_list)
            pending_list      = None
            pending_ordered   = None

    n_lines = ctrl.GetNumberOfLines()

    for ln in range(n_lines):
        line_start = ctrl.XYToPosition(0, ln)
        text       = ctrl.GetLineText(ln)

        if not text.strip():
            flush_list()
            continue

        # ---- Image placeholder ----
        if text.startswith(_IMAGE_PREFIX):
            flush_list()
            meta = img_lookup.get(text)
            if meta:
                nodes.append(ImageNode(path=meta["path"], alt_text=meta["alt_text"]))
            else:
                alt = text[len(_IMAGE_PREFIX):]
                nodes.append(ImageNode(path="", alt_text=alt))
            continue

        # ---- List items ----
        if _BULLET_RE.match(text):
            if pending_list is None or pending_ordered:
                flush_list()
                pending_list    = ListNode(ordered=False)
                pending_ordered = False
            content_start = line_start + 2
            content_end   = line_start + len(text)
            runs = _extract_runs(ctrl, content_start, content_end, link_lookup)
            pending_list.items.append(ListItemNode(runs=runs))
            continue

        m_num = _NUMBERED_RE.match(text)
        if m_num:
            if pending_list is None or not pending_ordered:
                flush_list()
                pending_list    = ListNode(ordered=True)
                pending_ordered = True
            prefix_len    = m_num.end()
            content_start = line_start + prefix_len
            content_end   = line_start + len(text)
            runs = _extract_runs(ctrl, content_start, content_end, link_lookup)
            pending_list.items.append(ListItemNode(runs=runs))
            continue

        flush_list()

        # ---- Read attributes at line start ----
        attr = wx.TextAttr()
        ctrl.GetStyle(line_start, attr)
        pt        = attr.GetFontPointSize() or 11
        bold      = attr.GetFontWeight() == wx.FONTWEIGHT_BOLD
        italic    = attr.GetFontStyle() == wx.FONTSTYLE_ITALIC
        indent    = attr.GetLeftIndent() or 0
        alignment = _align_wx_to_str(attr.GetAlignment())

        # ---- Headings ----
        if bold:
            level = None
            if pt >= 26: level = 1
            elif pt >= 20: level = 2
            elif pt >= 17: level = 3
            elif pt >= 15: level = 4
            elif pt >= 13: level = 5
            elif pt >= 12: level = 6
            if level is not None:
                nodes.append(HeadingNode(level=level, text=text))
                continue

        # ---- Block quote ----
        if italic and indent >= 150:
            runs = _extract_runs(ctrl, line_start, line_start + len(text), link_lookup)
            nodes.append(BlockQuoteNode(runs=runs, alignment=alignment))
            continue

        # ---- Normal paragraph ----
        runs = _extract_runs(ctrl, line_start, line_start + len(text), link_lookup)
        nodes.append(ParagraphNode(runs=runs, alignment=alignment))

    flush_list()
    return Document(nodes=nodes, title=title, lang=lang, author=author)


# ---------------------------------------------------------------------------
# Character-run extraction
# ---------------------------------------------------------------------------

def _extract_runs(
    ctrl: wx.TextCtrl,
    start: int,
    end: int,
    link_lookup: dict[str, str] | None = None,
) -> list[Run]:
    """
    Walk [start, end) and split into runs wherever bold/italic/underline/
    link-colour changes.  Returns at least one Run.

    link_lookup: {display_text: url} — built from editor.get_links().
    A run whose text colour matches _LINK_COLOR_RGB is treated as a
    hyperlink; the URL is looked up from link_lookup.
    """
    if start >= end:
        return [Run(text="")]

    lr, lg, lb = _LINK_COLOR_RGB
    runs: list[Run] = []
    pos = start

    while pos < end:
        a         = wx.TextAttr()
        ctrl.GetStyle(pos, a)
        bold          = a.GetFontWeight() == wx.FONTWEIGHT_BOLD
        italic        = a.GetFontStyle()  == wx.FONTSTYLE_ITALIC
        underline     = a.GetFontUnderlined()
        try:
            strike    = a.GetFontStrikethrough()
        except AttributeError:
            strike    = False
        col           = a.GetTextColour()
        is_link       = (col.IsOk()
                         and col.Red()   == lr
                         and col.Green() == lg
                         and col.Blue()  == lb)

        run_end = pos + 1
        while run_end < end:
            b = wx.TextAttr()
            ctrl.GetStyle(run_end, b)
            if (b.GetFontWeight()    == wx.FONTWEIGHT_BOLD)  != bold:      break
            if (b.GetFontStyle()     == wx.FONTSTYLE_ITALIC) != italic:    break
            if b.GetFontUnderlined() != underline:                          break
            try:
                b_strike = b.GetFontStrikethrough()
            except AttributeError:
                b_strike = False
            if b_strike != strike:
                break
            bc  = b.GetTextColour()
            bis = (bc.IsOk()
                   and bc.Red()   == lr
                   and bc.Green() == lg
                   and bc.Blue()  == lb)
            if bis != is_link:
                break
            run_end += 1

        chunk = ctrl.GetRange(pos, run_end)
        if chunk:
            link_url = ""
            if is_link and link_lookup:
                link_url = link_lookup.get(chunk, "")
                if not link_url:
                    for dt, url in link_lookup.items():
                        if chunk in dt or dt in chunk:
                            link_url = url
                            break
            runs.append(Run(
                text=chunk, bold=bold, italic=italic,
                underline=underline, strikethrough=strike, link=link_url,
            ))
        pos = run_end

    return runs or [Run(text=ctrl.GetRange(start, end))]
