"""Getting a damaged PDF open, and repairing one without rebuilding it.

    open_readable(path, password="") -> Opened     a context manager
    Opened: doc (PyMuPDF), path (a file both libraries can read), notes
    repair_copy(source, target, password="", title="", lang="") -> RepairResult
    RepairResult: path, changes (sentences), report (pdfcheck.Report)

    PdfOpenError        the file cannot be opened; the message is a sentence
    PdfPasswordError    a PdfOpenError; the file needs a password, or the
                        one given was wrong (.wrong says which)

MuPDF and qpdf recover different files (measured 2026-11-01): a PDF cut off
half way opens in pikepdf and not in PyMuPDF, and a copy saved by pikepdf
then opens in both. So PyMuPDF goes first, and when it refuses, or finds no
pages, pikepdf rebuilds a working copy in a temp folder. What was done is
said in notes, never done quietly: a page lost to damage is the reader's
business.

repair_copy keeps every page exactly as it looks. It sets what can be set
without guessing at structure: the title, the language, the title shown in
the window, link descriptions, the tab order, and a name on each form
field. A PDF with no tags stays a PDF with no tags, and nothing here claims
PDF/UA.

Nothing here touches wx or prints.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pikepdf

from . import pdfcheck, pdfocr

# docs/STRINGS.md, 0.3.0.
MSG_MISSING = "That file could not be found. It may have been moved or renamed."
MSG_EMPTY = "That file is empty. It has nothing in it to open."
MSG_NOT_PDF = "That file is not a PDF."
MSG_WEB_PAGE = ("That file is a web page saved with a PDF name, probably an error from a "
                "failed download. Try downloading it again.")
MSG_DAMAGED = ("This PDF is too damaged to open. Nothing in it could be recovered. Ask the "
               "sender for a new copy.")
MSG_PASSWORD = "This PDF is protected by a password."
MSG_WRONG_PASSWORD = "That password did not open the PDF."
MSG_NO_PAGES = "This PDF has no pages in it."
NOTE_REPAIRED = "This PDF was damaged. TG Imprint repaired its file structure to open it."
NOTE_JUNK = "This PDF had extra data in front of it, which was ignored."
NOTE_LOST = ("This PDF is damaged and only %d of its %d pages could be recovered. Ask the "
             "sender for a new copy.")
CHANGE_TITLE = "Set the title to \"%s\", the largest text on the first page."
CHANGE_TITLE_GIVEN = "Set the title to \"%s\"."
CHANGE_TITLE_FILE = ("Set the title to the file name, \"%s\", because nothing readable in the "
                     "PDF gives one.")
CHANGE_LANG = "Set the document language to %s."
CHANGE_LANG_GUESS = "Set the document language to %s, a guess from the words on the pages."
CHANGE_LANG_DEFAULT = ("Set the document language to %s, because the pages gave no way to tell. "
                       "A wrong language makes a voice very hard to follow.")
CHANGE_DISPLAY = "Viewers now show the title rather than the file name."
CHANGE_LINKS = "Added a description to %s."
CHANGE_TABS = "Set the tab order on %s."
CHANGE_FIELDS = "Named %s."
CHANGE_REBUILT = "Rebuilt the file's internal structure."
CHANGE_NONE = "Nothing needed changing."

HEADER_WINDOW = 1024


class PdfOpenError(Exception):
    """The message is a sentence a user can act on."""


class PdfPasswordError(PdfOpenError):
    def __init__(self, wrong=False):
        super().__init__(MSG_WRONG_PASSWORD if wrong else MSG_PASSWORD)
        self.wrong = wrong


@dataclass
class RepairResult:
    path: str
    changes: list = field(default_factory=list)
    report: object = None


def _n(count, one, many):
    return ("1 " + one) if count == 1 else ("%d " % count) + many


def _expected_pages(path):
    """The largest /Count the raw file mentions: the page total of the
    undamaged document, near enough to say pages were lost."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return 0
    counts = [int(c) for c in re.findall(rb"/Count\s+(\d{1,6})", data)]
    return max(counts) if counts else 0


class Opened:
    """A PDF both libraries can read. Use with `with`: the working copy, if
    one was made, goes when the block ends."""

    def __init__(self, path, password=""):
        self.source = path
        self.path = path
        self.password = password
        self.notes = []
        self.doc = None
        self._work = None

    def __enter__(self):
        try:
            self._open()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
            self.doc = None
        if self._work:
            shutil.rmtree(self._work, ignore_errors=True)
            self._work = None

    def _sniff(self):
        try:
            size = os.path.getsize(self.source)
            with open(self.source, "rb") as handle:
                head = handle.read(HEADER_WINDOW)
        except FileNotFoundError:
            raise PdfOpenError(MSG_MISSING)
        except OSError as exc:
            raise PdfOpenError(MSG_DAMAGED) from exc
        if size == 0:
            raise PdfOpenError(MSG_EMPTY)
        at = head.find(b"%PDF-")
        if at < 0:
            if head.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
                raise PdfOpenError(MSG_WEB_PAGE)
            raise PdfOpenError(MSG_NOT_PDF)
        if at > 0:
            self.notes.append(NOTE_JUNK)

    def _fitz(self, path):
        """The open document, or None when PyMuPDF cannot read it."""
        try:
            doc = fitz.open(path)
        except Exception:
            return None
        if doc.needs_pass:
            if not self.password:
                doc.close()
                raise PdfPasswordError()
            if not doc.authenticate(self.password):
                doc.close()
                raise PdfPasswordError(wrong=True)
        return doc

    def _rebuild(self):
        """A working copy saved by pikepdf, or None."""
        self._work = tempfile.mkdtemp(prefix="tgimprint-repair-")
        target = os.path.join(self._work, "repaired.pdf")
        try:
            with pikepdf.open(self.source, password=self.password) as pdf:
                pdf.save(target, encryption=False)
        except pikepdf.PasswordError:
            raise PdfPasswordError(wrong=bool(self.password))
        except Exception:
            return None
        return target

    def _open(self):
        self._sniff()
        doc = self._fitz(self.source)
        if doc is not None and doc.page_count > 0:
            self.doc = doc
            if doc.is_repaired:
                self.notes.append(NOTE_REPAIRED)
                self._note_lost(doc.page_count)
            return
        if doc is not None:
            doc.close()
        rebuilt = self._rebuild()
        doc = self._fitz(rebuilt) if rebuilt else None
        if doc is None:
            raise PdfOpenError(MSG_DAMAGED)
        if doc.page_count == 0:
            doc.close()
            raise PdfOpenError(MSG_NO_PAGES)
        self.doc = doc
        self.path = rebuilt
        self.notes.append(NOTE_REPAIRED)
        self._note_lost(doc.page_count)

    def _note_lost(self, found):
        expected = _expected_pages(self.source)
        if expected > found:
            self.notes.append(NOTE_LOST % (found, expected))


def open_readable(path, password=""):
    return Opened(path, password)


# ------------------------------------------------------------ repair copy ---


def _first_big_line(doc):
    """The largest text on the first page with any: a title that can be
    defended, for a file that has none."""
    for number in range(min(doc.page_count, 3)):
        best = ""
        best_size = 0.0
        try:
            blocks = doc[number].get_text("dict").get("blocks", [])
        except Exception:
            continue
        for block in blocks:
            for line in block.get("lines", []):
                text = " ".join(s.get("text", "") for s in line.get("spans", [])).strip()
                size = max((s.get("size", 0) for s in line.get("spans", [])), default=0)
                if 3 <= len(text) <= 90 and size > best_size and _reads(text) \
                        and not text.endswith("."):
                    best, best_size = text, size
        if best:
            return re.sub(r"\s+", " ", best)
    return ""


def _reads(text):
    """Text somebody could read: letters, and not symbols."""
    return (pdfcheck.text_quality(text) < pdfcheck.GARBLED_RATIO
            and sum(1 for c in text if c.isalpha()) >= 3)


def _guess_lang(doc):
    text = []
    for number in range(min(doc.page_count, 6)):
        try:
            text.append(doc[number].get_text())
        except Exception:
            pass
    return {"es": "es", "en": "en-US"}.get(pdfocr.guess_language(" ".join(text)), "")


def _label_near(page, rect):
    """The words nearest the left of a field, else above it."""
    words = page.get_text("words")
    left = [w for w in words if w[2] <= rect.x0 + 2 and w[3] >= rect.y0 and w[1] <= rect.y1
            and rect.x0 - w[2] < 220]
    if left:
        left.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in left)
    else:
        above = [w for w in words if w[3] <= rect.y0 + 2 and rect.y0 - w[3] < 28
                 and w[2] >= rect.x0 and w[0] <= rect.x1]
        above.sort(key=lambda w: (w[1], w[0]))
        text = " ".join(w[4] for w in above)
    return re.sub(r"[_.:\s]+$", "", re.sub(r"\s+", " ", text)).strip()[:120]


def _name_fields(pdf, doc):
    named = 0
    for number, page in enumerate(pdf.pages):
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        fitz_page = doc[number] if number < doc.page_count else None
        unnamed_on_page = 0
        for annot in annots:
            if not isinstance(annot, pikepdf.Dictionary):
                continue
            if str(annot.get("/Subtype", "")) != "/Widget":
                continue
            node = annot
            has_name = False
            for _depth in range(8):
                if not isinstance(node, pikepdf.Dictionary):
                    break
                if str(node.get("/TU", "") or "").strip():
                    has_name = True
                    break
                node = node.get("/Parent")
            if has_name:
                continue
            unnamed_on_page += 1
            label = ""
            if fitz_page is not None and "/Rect" in annot:
                try:
                    box = [float(v) for v in annot.Rect]
                    height = fitz_page.rect.height
                    label = _label_near(fitz_page, fitz.Rect(
                        min(box[0], box[2]), height - max(box[1], box[3]),
                        max(box[0], box[2]), height - min(box[1], box[3])))
                except Exception:
                    label = ""
            annot.TU = pikepdf.String(label or "Blank %d on page %d" % (unnamed_on_page, number + 1))
            named += 1
    return named


def _describe_links(pdf, doc):
    described = 0
    for number, page in enumerate(pdf.pages):
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        fitz_page = doc[number] if number < doc.page_count else None
        for annot in annots:
            if not isinstance(annot, pikepdf.Dictionary) or str(annot.get("/Subtype", "")) != "/Link":
                continue
            if str(annot.get("/Contents", "") or "").strip():
                continue
            text = ""
            if fitz_page is not None and "/Rect" in annot:
                try:
                    box = [float(v) for v in annot.Rect]
                    height = fitz_page.rect.height
                    rect = fitz.Rect(min(box[0], box[2]), height - max(box[1], box[3]),
                                     max(box[0], box[2]), height - min(box[1], box[3]))
                    text = re.sub(r"\s+", " ", fitz_page.get_textbox(rect)).strip()
                except Exception:
                    text = ""
            if not text:
                try:
                    text = str(annot.A.URI)
                except Exception:
                    text = ""
            if text:
                annot.Contents = pikepdf.String(text)
                described += 1
    return described


def repair_copy(source, target, password="", title="", lang=""):
    """See the module docstring. Raises PdfOpenError with a sentence."""
    from .pdfexport import put_in_place

    with open_readable(source, password) as opened:
        changes = []
        if opened.path != source or opened.doc.is_repaired:
            changes.append(CHANGE_REBUILT)
        try:
            pdf = pikepdf.open(opened.path, password=password)
        except Exception as exc:
            raise PdfOpenError(MSG_DAMAGED) from exc
        work = tempfile.mkdtemp(prefix="tgimprint-fix-")
        try:
            with pdf:
                root = pdf.Root
                has_tree = bool(pdfcheck.walk_tree(pdf))
                with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                    existing = str(meta.get("dc:title") or "").strip()
                    info_title = str(pdf.docinfo.get("/Title", "") or "").strip()
                    if existing and not _reads(existing):
                        existing = ""
                    if info_title and not _reads(info_title):
                        info_title = ""
                    big_line = _first_big_line(opened.doc)
                    chosen = title.strip() or existing or info_title or big_line
                    sentence = CHANGE_TITLE_GIVEN if (title.strip() or info_title) else CHANGE_TITLE
                    if not chosen:
                        chosen = os.path.splitext(os.path.basename(source))[0]
                        sentence = CHANGE_TITLE_FILE
                    if chosen != existing:
                        meta["dc:title"] = chosen
                        pdf.docinfo["/Title"] = pikepdf.String(chosen)
                        changes.append(sentence % chosen)
                    current_lang = str(root.get("/Lang", "") or "").strip()
                    guessed = "" if (lang.strip() or current_lang) else _guess_lang(opened.doc)
                    wanted = lang.strip() or current_lang or guessed or "en-US"
                    if wanted != current_lang:
                        root.Lang = pikepdf.String(wanted)
                        meta["dc:language"] = [wanted]
                        if lang.strip():
                            changes.append(CHANGE_LANG % wanted)
                        else:
                            changes.append((CHANGE_LANG_GUESS if guessed else CHANGE_LANG_DEFAULT) % wanted)
                prefs = root.get("/ViewerPreferences")
                if not isinstance(prefs, pikepdf.Dictionary):
                    prefs = pikepdf.Dictionary()
                    root.ViewerPreferences = prefs
                if not bool(prefs.get("/DisplayDocTitle", False)):
                    prefs.DisplayDocTitle = True
                    changes.append(CHANGE_DISPLAY)
                described = _describe_links(pdf, opened.doc)
                if described:
                    changes.append(CHANGE_LINKS % _n(described, "link", "links"))
                named = _name_fields(pdf, opened.doc)
                if named:
                    changes.append(CHANGE_FIELDS % _n(named, "form field", "form fields"))
                wanted_tabs = "/S" if has_tree else "/R"
                tabbed = 0
                for page in pdf.pages:
                    annots = page.obj.get("/Annots")
                    if isinstance(annots, pikepdf.Array) and len(annots) \
                            and str(page.obj.get("/Tabs", "")) != wanted_tabs:
                        page.obj.Tabs = pikepdf.Name(wanted_tabs)
                        tabbed += 1
                if tabbed:
                    changes.append(CHANGE_TABS % _n(tabbed, "page", "pages"))
                finished = os.path.join(work, "repaired.pdf")
                pdf.save(finished)
            report = pdfcheck.check(finished)
            put_in_place(finished, os.path.abspath(target))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        report.path = target
        return RepairResult(path=target, changes=changes or [CHANGE_NONE], report=report)
