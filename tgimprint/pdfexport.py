"""Export: the editor's HTML to a tagged PDF, checked, with an honest claim.

    export_html(body_html, out_path, meta, progress=None) -> ExportResult

    meta keys: title, author, lang, subject, page_size, margin_inches,
               font_family, font_points (defaults from constants for any
               missing)
    progress(step_text) is called from whatever thread runs this; the UI
               hops to its own thread itself.
    ExportResult: path, pages, warnings (sentences), engine ("<name>
               <version>"), pdfua_claimed (the identifier was written
               because the checker's gate passed), report (the checker's
               Report on the final file, so the UI need not run it again)

The steps, in order (DECISIONS.md decision 2 and edit A4):

1. htmlclean.normalise(body, for_export=True): the editor's markup mapped
   onto the elements the engine tags, everything else stripped, with
   warnings.
2. The body wrapped in a page: html lang from meta, title, author, the
   print stylesheet (page size and margins from meta, the base font, the
   heading scale, figures and captions, lists, tables, links, quotes,
   code).
3. pdfengine.render_pdf: Edge, the WebView2 runtime or Chrome, headless.
4. pikepdf: MarkInfo, Lang, DisplayDocTitle, the Info dictionary, the XMP
   (dc:title, dc:creator, dc:description, dc:language, xmp:CreatorTool,
   pdf:Producer with the engine's name and version so a bad batch can be
   traced), and every link annotation's Contents set to the link's text.
   Never a byte-level patch: the prototype's corrupted the cross reference
   table.
5. pdfcheck.check on the result. If the engine's own output has no
   MarkInfo or no structure tree, the export stops with EngineError and
   nothing is saved: never ship an untagged PDF (CLAUDE.md, decision 2).
   Otherwise the PDF/UA identifier (pdfuaid:part 1) is written only when
   Report.pdfua_gate is true; else the file is still exported, tagged,
   with a warning naming the check that failed.
6. One replace into place. All the work happens in a temp folder, so a
   Dropbox or antivirus lock on the destination cannot interrupt the
   patch and check in the middle, and the finished file is copied beside
   its destination and swapped in with os.replace, so a failed copy or a
   locked destination leaves the earlier PDF untouched.

Nothing here touches wx or prints. EngineError (from pdfengine) is the
one exception a caller should expect; its message is a sentence. A
pikepdf failure on the engine's output is wrapped the same way, so no
temp path and no library words reach the user.
"""

import datetime
import html
import os
import shutil
import tempfile
from dataclasses import dataclass, field

import pikepdf

from . import constants as C
from . import htmlclean, pdfcheck, pdfengine
from .pdfengine import EngineError  # noqa: F401  re-exported for callers

DEFAULT_LANG = "en-US"

# docs/STRINGS.md, Worker A.
STEP_CHECK_DOCUMENT = "Checking the document"
STEP_LAYOUT = "Laying out the pages"
STEP_INFO = "Writing the document information"
STEP_CHECK_PDF = "Checking the PDF"
STEP_IDENTIFIER = "Adding the PDF/UA identifier"
MSG_NO_TITLE = ("The document has no title. The PDF was written without one, and the "
                "PDF/UA claim needs one. Set a title in Document properties and "
                "export again.")
MSG_NO_CLAIM = ("The PDF/UA identifier was left out because %s did not pass: %s. The PDF "
                "is still tagged. Fix that and export again to add the claim.")
MSG_NOT_WRITTEN = ("The PDF could not be written to %s. Check that the folder allows "
                   "writing and that the file is not open in another program.")
MSG_WRITE_FAILED = ("The PDF could not be written to %s. The system reported: %s. The "
                    "earlier file at that path, if there was one, is untouched.")
MSG_UNTAGGED = ("The PDF engine wrote a PDF without tags, so nothing was saved. Save as "
                "web page keeps everything. Try the export again, and if it happens "
                "every time, update Microsoft Edge.")
MSG_DAMAGED = ("The PDF engine wrote a file that could not be read back as a PDF, so "
               "nothing was saved. Try the export again, and if it happens every time, "
               "update Microsoft Edge.")
MSG_WORK_FAILED = ("The PDF could not be finished because a temporary file could not be "
                   "written. The system reported: %s. Nothing was saved. Free some disk "
                   "space and export again.")
#: The print page loads nothing but its own inline stylesheet and data
#: pictures: no script, no fetch, no font or frame from anywhere, whatever
#: a received document carried into the meta (Overseer round 2, defect 1).
CONTENT_SECURITY_POLICY = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"


@dataclass
class ExportResult:
    path: str
    pages: int
    warnings: list = field(default_factory=list)
    engine: str = ""
    pdfua_claimed: bool = False
    report: object = None


# ------------------------------------------------------------- the page ---

STYLESHEET = """
@page { size: %(page_size)s; margin: %(margin)sin; }
html { font-family: %(font_family)s; font-size: %(font_points)spt; line-height: 1.4; color: #000000; }
body { margin: 0; }
h1 { font-size: 2em; margin: 0.9em 0 0.4em; break-after: avoid; }
h2 { font-size: 1.55em; margin: 0.9em 0 0.35em; break-after: avoid; }
h3 { font-size: 1.25em; margin: 0.8em 0 0.3em; break-after: avoid; }
h4 { font-size: 1.1em; margin: 0.8em 0 0.3em; break-after: avoid; }
h5 { font-size: 1em; font-style: italic; margin: 0.8em 0 0.3em; break-after: avoid; }
h6 { font-size: 1em; font-weight: normal; font-style: italic; margin: 0.8em 0 0.3em; break-after: avoid; }
p { margin: 0 0 0.6em; }
p.code-block { font-family: Consolas, "Courier New", monospace; font-size: 0.9em; white-space: pre-wrap; background: #f3f3f3; border: 1px solid #cccccc; padding: 0.5em 0.7em; }
code { font-family: Consolas, "Courier New", monospace; font-size: 0.95em; }
a { color: #0000b4; text-decoration: underline; overflow-wrap: anywhere; }
blockquote { margin: 0.6em 0 0.6em 1.5em; padding-left: 0.8em; border-left: 3px solid #888888; }
blockquote p:last-child { margin-bottom: 0; }
ul, ol { margin: 0.2em 0 0.6em; padding-left: 2em; }
li { margin-bottom: 0.2em; }
li p:last-child { margin-bottom: 0; }
figure { margin: 0.8em 0; text-align: center; break-inside: avoid; }
figure img { max-width: 100%%; height: auto; }
figcaption { font-size: 0.9em; color: #333333; margin-top: 0.3em; }
table { border-collapse: collapse; margin: 0.6em 0; width: 100%%; }
th, td { border: 1px solid #666666; padding: 0.3em 0.5em; text-align: left; vertical-align: top; }
th { background: #e8e8e8; font-weight: bold; }
caption { font-weight: bold; text-align: left; margin-bottom: 0.3em; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
hr { border: 0; border-top: 1px solid #888888; margin: 1em 0; }
sup, sub { font-size: 0.75em; line-height: 0; }
.align-left { text-align: left; }
.align-center { text-align: center; }
.align-right { text-align: right; }
.align-justify { text-align: justify; }
figure.width-quarter img, img.width-quarter { width: 25%%; }
figure.width-half img, img.width-half { width: 50%%; }
figure.width-three-quarters img, img.width-three-quarters { width: 75%%; }
figure.width-full img, img.width-full { width: 100%%; }
figure.place-left { text-align: left; }
figure.place-centre { text-align: center; }
figure.place-right { text-align: right; }
"""


def _meta_value(meta, key, default):
    value = meta.get(key) if meta else None
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return value


def settings_from(meta):
    """The export settings with every missing key filled from constants."""
    meta = meta or {}
    page_size = str(_meta_value(meta, "page_size", C.DEFAULT_PAGE_SIZE)).strip()
    if page_size not in C.PAGE_SIZES:
        page_size = C.DEFAULT_PAGE_SIZE
    try:
        margin = float(_meta_value(meta, "margin_inches", C.DEFAULT_MARGIN_INCHES))
    except (TypeError, ValueError):
        margin = C.DEFAULT_MARGIN_INCHES
    margin = min(max(margin, 0.25), 3.0)
    try:
        points = float(_meta_value(meta, "font_points", C.DEFAULT_FONT_POINTS))
    except (TypeError, ValueError):
        points = C.DEFAULT_FONT_POINTS
    points = min(max(points, 6.0), 36.0)
    lang = str(_meta_value(meta, "lang", DEFAULT_LANG)).strip()
    if not htmlclean._LANG_RE.match(lang):
        lang = DEFAULT_LANG
    return {
        "title": str(_meta_value(meta, "title", "")).strip(),
        "author": str(_meta_value(meta, "author", "")).strip(),
        "subject": str(_meta_value(meta, "subject", "")).strip(),
        "lang": lang,
        "page_size": page_size,
        "margin": ("%.3f" % margin).rstrip("0").rstrip("."),
        # Letters, digits, spaces, commas, quotes and hyphens only; anything
        # else could close the style element, so it falls back to the default.
        "font_family": htmlclean.clean_font_family(
            _meta_value(meta, "font_family", C.DEFAULT_FONT_FAMILY)),
        "font_points": ("%.1f" % points).rstrip("0").rstrip("."),
    }


def build_page(clean_body, settings):
    """The whole HTML document the engine prints."""
    style = STYLESHEET % {
        "page_size": settings["page_size"],
        "margin": settings["margin"],
        "font_family": settings["font_family"].replace("\n", " "),
        "font_points": settings["font_points"],
    }
    head = [
        "<!DOCTYPE html>",
        '<html lang="%s">' % html.escape(settings["lang"], quote=True),
        "<head>",
        '<meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="%s">' % CONTENT_SECURITY_POLICY,
        "<title>%s</title>" % html.escape(settings["title"]),
    ]
    if settings["author"]:
        head.append('<meta name="author" content="%s">' % html.escape(settings["author"], quote=True))
    head.append("<style>%s</style>" % style)
    head.append("</head>")
    head.append("<body>")
    return "\n".join(head) + "\n" + clean_body + "\n</body>\n</html>\n"


# ------------------------------------------------------------ the patch ---


def _now():
    return datetime.datetime.now().astimezone().replace(microsecond=0)


def _pdf_date(when):
    text = when.strftime("D:%Y%m%d%H%M%S")
    offset = when.strftime("%z")
    if offset:
        text += "%s'%s'" % (offset[:3], offset[3:5])
    return text


def patch_pdf(source, target, settings, engine):
    """The catalogue entries, the Info dictionary, the XMP and the link
    descriptions, written from source to target. No identifier yet."""
    producer = "%s %s (%s %s)" % (C.APP_NAME, C.APP_VERSION, engine.name, engine.version)
    creator = "%s %s" % (C.APP_NAME, C.APP_VERSION)
    when = _now()
    try:
        _patch_pdf(source, target, settings, producer, creator, when)
    except EngineError:
        raise
    except OSError as exc:
        raise EngineError(MSG_WORK_FAILED % (exc.strerror or str(exc)))
    except Exception:
        # pikepdf's message for a damaged file is the temp path and library
        # words; the user gets a sentence (Overseer round 2, defect 4).
        raise EngineError(MSG_DAMAGED)


def _patch_pdf(source, target, settings, producer, creator, when):
    pdf = pikepdf.open(source)
    try:
        root = pdf.Root
        mark_info = root.get("/MarkInfo")
        if not isinstance(mark_info, pikepdf.Dictionary):
            mark_info = pikepdf.Dictionary()
            root.MarkInfo = mark_info
        mark_info.Marked = True
        root.Lang = pikepdf.String(settings["lang"])
        prefs = root.get("/ViewerPreferences")
        if not isinstance(prefs, pikepdf.Dictionary):
            prefs = pikepdf.Dictionary()
            root.ViewerPreferences = prefs
        prefs.DisplayDocTitle = True

        info = pdf.docinfo
        info["/Title"] = pikepdf.String(settings["title"])
        if settings["author"]:
            info["/Author"] = pikepdf.String(settings["author"])
        elif "/Author" in info:
            del info["/Author"]
        if settings["subject"]:
            info["/Subject"] = pikepdf.String(settings["subject"])
        elif "/Subject" in info:
            del info["/Subject"]
        info["/Creator"] = pikepdf.String(creator)
        info["/Producer"] = pikepdf.String(producer)
        info["/CreationDate"] = pikepdf.String(_pdf_date(when))
        info["/ModDate"] = pikepdf.String(_pdf_date(when))

        # Every link annotation carries its text, so a screen reader that
        # reads the annotation rather than the tagged text says the words.
        for annot, text, uri in pdfcheck.link_descriptions(pdf):
            annot.Contents = pikepdf.String(text or uri)

        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
            meta["dc:title"] = settings["title"]
            if settings["author"]:
                meta["dc:creator"] = [settings["author"]]
            if settings["subject"]:
                meta["dc:description"] = settings["subject"]
            meta["dc:language"] = [settings["lang"]]
            meta["xmp:CreatorTool"] = creator
            meta["pdf:Producer"] = producer
            stamp = when.isoformat()
            meta["xmp:CreateDate"] = stamp
            meta["xmp:ModifyDate"] = stamp
            meta["xmp:MetadataDate"] = stamp
        pdf.save(target)
    finally:
        pdf.close()


def write_identifier(path):
    """pdfuaid:part 1 in the file's XMP, in place."""
    try:
        pdf = pikepdf.open(path, allow_overwriting_input=True)
        try:
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                meta["pdfuaid:part"] = "1"
            pdf.save(path)
        finally:
            pdf.close()
    except OSError as exc:
        raise EngineError(MSG_WORK_FAILED % (exc.strerror or str(exc)))
    except Exception:
        raise EngineError(MSG_DAMAGED)


def _quiet_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def put_in_place(source, out_path):
    """Copy the finished file to a temporary name beside its destination,
    then replace in one step, so a failed copy (disk full, antivirus) or a
    locked destination leaves the earlier PDF at out_path untouched
    (Overseer round 2, defects 5 and 12). Raises EngineError with a
    sentence that names the path."""
    folder = os.path.dirname(out_path) or "."
    part = None
    try:
        handle = tempfile.NamedTemporaryFile("wb", dir=folder, prefix=".tgimprint-",
                                             suffix=".pdf.part", delete=False)
        part = handle.name
        with handle, open(source, "rb") as reader:
            shutil.copyfileobj(reader, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(part, out_path)
    except PermissionError:
        if part:
            _quiet_remove(part)
        raise EngineError(MSG_NOT_WRITTEN % out_path)
    except OSError as exc:
        if part:
            _quiet_remove(part)
        raise EngineError(MSG_WRITE_FAILED % (out_path, exc.strerror or str(exc)))


def _refuse_untagged(report):
    """EngineError when the engine's own output is not a tagged PDF. The
    file is in the work folder, which the caller removes, so nothing is
    saved (Overseer round 2, defect 2)."""
    by_key = {r.key: r for r in report.results}
    readable = by_key.get("readable")
    if readable is not None and not readable.passed:
        raise EngineError(MSG_DAMAGED)
    for key in ("tagged", "tree"):
        item = by_key.get(key)
        if item is None or not item.passed:
            raise EngineError(MSG_UNTAGGED)


# ------------------------------------------------------------- the entry ---


def export_html(body_html, out_path, meta, progress=None):
    """See the module docstring. Raises EngineError when there is no engine
    or it fails; the message is a sentence."""

    def step(text):
        if progress is not None:
            try:
                progress(text)
            except Exception:
                pass

    settings = settings_from(meta)
    warnings = []
    step(STEP_CHECK_DOCUMENT)
    if not settings["title"]:
        warnings.append(MSG_NO_TITLE)
    clean_body, clean_warnings = htmlclean.normalise(body_html, for_export=True)
    warnings.extend(clean_warnings)
    page = build_page(clean_body, settings)

    out_path = os.path.abspath(out_path)
    out_folder = os.path.dirname(out_path)
    if not os.path.isdir(out_folder):
        raise EngineError(pdfengine.MSG_BAD_FOLDER % out_folder)

    work = tempfile.mkdtemp(prefix="tgimprint-export-")
    try:
        rendered = os.path.join(work, "rendered.pdf")
        patched = os.path.join(work, "patched.pdf")
        step(STEP_LAYOUT)
        engine = pdfengine.render_pdf(page, rendered)
        step(STEP_INFO)
        patch_pdf(rendered, patched, settings, engine)
        step(STEP_CHECK_PDF)
        report = pdfcheck.check(patched)
        _refuse_untagged(report)
        claimed = False
        if report.pdfua_gate:
            step(STEP_IDENTIFIER)
            write_identifier(patched)
            # Read the one entry that changed back from the file rather
            # than parse every page again.
            fresh = pdfcheck.identifier_result(patched)
            report.results = [fresh if r.key == "identifier" else r for r in report.results]
            claimed = fresh.passed and report.pdfua_gate
        if not claimed:
            names = report.failed_names() or ["a check"]
            warnings.append(MSG_NO_CLAIM % (
                "this check" if len(names) == 1 else "these checks", ", ".join(names)))
        put_in_place(patched, out_path)
        report.path = out_path
        return ExportResult(path=out_path, pages=report.pages, warnings=warnings,
                            engine="%s %s" % (engine.name, engine.version),
                            pdfua_claimed=claimed, report=report)
    finally:
        shutil.rmtree(work, ignore_errors=True)
