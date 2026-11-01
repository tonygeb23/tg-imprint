"""Analyse a PDF: what is wrong with it, in words, and what to do next.

    analyse(path, password="") -> Analysis
    Analysis: path, name, pages, kinds (Counter of page kinds), notes
              (repairs), report (pdfcheck.Report), level, verdict (one
              sentence), steps (what to do, in order), format_report()

The checker answers "which checks pass". This answers the question a person
has when a PDF arrives: can a screen reader read it, and if not, what then.
Every page is classified as text, scanned, garbled or blank by looking at
it, and the file lands on one of seven levels:

    unreadable      it will not open
    empty           every page is blank
    pictures        no readable text on any page
    partly          some pages have readable text and some do not
    flat            readable text, no structure
    faults          tagged, with faults the checks can name
    good            nothing the checks can find

Nothing is written. Nothing leaves the machine. Nothing here touches wx or
prints.
"""

import os
from collections import Counter
from dataclasses import dataclass, field

from . import pdfcheck, pdfrepair

LEVEL_UNREADABLE = "unreadable"
LEVEL_EMPTY = "empty"
LEVEL_PICTURES = "pictures"
LEVEL_PARTLY = "partly"
LEVEL_FLAT = "flat"
LEVEL_FAULTS = "faults"
LEVEL_GOOD = "good"

# docs/STRINGS.md, 0.3.0.
VERDICTS = {
    LEVEL_UNREADABLE: "This PDF cannot be opened.",
    LEVEL_EMPTY: "This PDF has no content: every page is blank.",
    LEVEL_PICTURES: "A screen reader cannot read this PDF: its pages are pictures, with no "
                    "readable text.",
    LEVEL_PARTLY: "A screen reader can read only part of this PDF.",
    LEVEL_FLAT: "A screen reader can read the words, but there are no headings, lists or "
                "other structure to move through.",
    LEVEL_FAULTS: "A screen reader can read this PDF and move through its structure, but "
                  "it has faults.",
    LEVEL_GOOD: "This PDF passes every check TG Imprint can make.",
}
STEP_OPEN = ("Open it in TG Imprint. It reads the pages by text recognition, and from there "
             "you can check the text and export a tagged PDF.")
STEP_REBUILD = ("Open it in TG Imprint and export it. That rebuilds it as a tagged PDF, with "
                "headings, lists and tables, though the page layout will change.")
STEP_REPAIR = ("Or use Repair a PDF to set the title, language, link descriptions and field "
               "names and keep every page looking as it does now. It will not add headings "
               "or other structure.")
STEP_FORM = "Use Fill in a PDF form to fill it in from a list."
STEP_XFA = "This form type cannot be filled in here. Ask the sender for an ordinary PDF."
STEP_PICTURES = "Describe the pictures in Pictures once the document is open."
STEP_FULL = "A full PDF/UA verdict needs PAC or veraPDF, and neither can judge what the words mean."
STEP_RESEND = "Ask the sender for a new copy."
PAGE_WORDS = {"text": ("page of text", "pages of text"),
              "scanned": ("scanned page", "scanned pages"),
              "garbled": ("page that reads as symbols", "pages that read as symbols"),
              "blank": ("blank page", "blank pages")}
SAME_FIX = "Open it in TG Imprint and export it again."
REPAIRABLE = ("title", "lang", "display_title", "link_contents", "fields", "tabs")


@dataclass
class Analysis:
    path: str
    name: str = ""
    pages: int = 0
    kinds: Counter = field(default_factory=Counter)
    notes: list = field(default_factory=list)
    report: object = None
    level: str = LEVEL_UNREADABLE
    verdict: str = ""
    steps: list = field(default_factory=list)
    needs_password: bool = False

    def page_summary(self):
        parts = []
        for kind in ("text", "scanned", "garbled", "blank"):
            count = self.kinds.get(kind, 0)
            if count:
                one, many = PAGE_WORDS[kind]
                parts.append("%d %s" % (count, one if count == 1 else many))
        return ", ".join(parts)

    def format_report(self):
        """Plain text for a read-only field: the answer first, because a
        screen reader lands on line one, and the check by check detail after
        it for anybody who wants it. The file name is in the dialog's title."""
        lines = [self.verdict]
        summary = self.page_summary()
        if summary:
            lines.append("%s: %s." % (_pages(self.pages), summary) if len(
                [k for k in self.kinds if self.kinds[k]]) > 1 else "%s, all %s." % (
                    _pages(self.pages), {"text": "text", "scanned": "scanned", "blank": "blank",
                                         "garbled": "reading as symbols"}[
                                             next(k for k in self.kinds if self.kinds[k])]))
        lines.extend(self.notes)
        if self.steps:
            lines.append("")
            lines.append("What to do:")
            lines.extend(self.steps)
        if self.report is not None and self.report.results:
            lines.append("")
            # The steps above already say how to fix it; once is enough.
            lines.append(self.report.format_report().replace(" %s" % SAME_FIX, ""))
        return "\n".join(lines)


def _pages(count):
    return "1 page" if count == 1 else "%d pages" % count


def classify_page(page):
    """"text", "scanned", "garbled" or "blank", from one PyMuPDF page."""
    try:
        text = page.get_text()
    except Exception:
        text = ""
    if text.strip():
        return "garbled" if pdfcheck.text_quality(text) >= pdfcheck.GARBLED_RATIO else "text"
    try:
        return "scanned" if page.get_images() else "blank"
    except Exception:
        return "blank"


def _failed(report, key):
    return any(r.key == key and not r.passed for r in report.results)


def _judge(analysis):
    report = analysis.report
    kinds = analysis.kinds
    readable = kinds.get("text", 0)
    unreadable = kinds.get("scanned", 0) + kinds.get("garbled", 0)
    steps = []
    has_fields = any(r.key == "fields" for r in report.results)
    if not readable and not unreadable:
        analysis.level = LEVEL_EMPTY
        steps.append(STEP_RESEND)
    elif not readable:
        analysis.level = LEVEL_PICTURES
        steps.append(STEP_OPEN)
    elif readable and unreadable:
        analysis.level = LEVEL_PARTLY
        steps.append(STEP_OPEN)
    elif _failed(report, "tree") or _failed(report, "tagged"):
        analysis.level = LEVEL_FLAT
        steps.append(STEP_REBUILD)
    elif not report.pdfua_gate:
        analysis.level = LEVEL_FAULTS
    else:
        analysis.level = LEVEL_GOOD
    if any(_failed(report, key) for key in REPAIRABLE):
        steps.append(STEP_REPAIR)
    if _failed(report, "figures"):
        steps.append(STEP_PICTURES)
    if _failed(report, "xfa"):
        steps.append(STEP_XFA)
    elif has_fields:
        steps.append(STEP_FORM)
    if analysis.level == LEVEL_FAULTS and STEP_REBUILD not in steps:
        steps.append(STEP_REBUILD)
    steps.append(STEP_FULL)
    analysis.steps = steps
    analysis.verdict = VERDICTS[analysis.level]


def analyse(path, password=""):
    """See the module docstring. Never raises for a bad file."""
    analysis = Analysis(path=path, name=os.path.basename(path))
    try:
        with pdfrepair.open_readable(path, password) as opened:
            analysis.pages = opened.doc.page_count
            analysis.notes = list(opened.notes)
            for number in range(opened.doc.page_count):
                analysis.kinds[classify_page(opened.doc[number])] += 1
            analysis.report = pdfcheck.check(opened.path, password)
    except pdfrepair.PdfPasswordError as exc:
        analysis.needs_password = True
        analysis.verdict = str(exc)
        analysis.steps = []
        return analysis
    except pdfrepair.PdfOpenError as exc:
        analysis.verdict = "%s %s" % (VERDICTS[LEVEL_UNREADABLE], exc)
        analysis.steps = [STEP_RESEND]
        return analysis
    analysis.report.path = path
    _judge(analysis)
    return analysis
