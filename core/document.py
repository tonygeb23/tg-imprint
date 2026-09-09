"""
Document model — a simple, serialisable content tree that sits between
the wxPython RichTextCtrl and the ReportLab PDF exporter.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union


@dataclass
class Run:
    """A span of text with uniform character formatting."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    code: bool = False          # monospace / inline-code
    link: str = ""              # non-empty = hyperlink URL (display text is Run.text)


@dataclass
class HeadingNode:
    level: int                  # 1–6
    text: str


@dataclass
class ParagraphNode:
    runs: list[Run] = field(default_factory=list)
    alignment: str = "left"   # "left" | "center" | "right" | "justify"

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class ImageNode:
    path: str
    alt_text: str               # empty string = decorative (Artifact in PDF)
    width_pts: float  = 0.0    # 0 = auto-fit to page width
    height_pts: float = 0.0    # 0 = auto (maintain aspect ratio)


@dataclass
class ListItemNode:
    runs: list[Run] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class ListNode:
    items: list[ListItemNode] = field(default_factory=list)
    ordered: bool = False       # False = bullet, True = numbered


@dataclass
class BlockQuoteNode:
    runs: list[Run] = field(default_factory=list)
    alignment: str = "left"   # "left" | "center" | "right" | "justify"

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs)


ContentNode = Union[
    HeadingNode, ParagraphNode, ImageNode,
    ListNode, BlockQuoteNode,
]


@dataclass
class Document:
    nodes: list[ContentNode] = field(default_factory=list)
    title: str = "Untitled"
    lang: str = "en-US"
    author: str = ""
