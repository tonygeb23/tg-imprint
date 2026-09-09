"""The export: a tagged PDF read back with pikepdf, and an honest claim.

The structure tree, the fonts, the XMP and the Info dictionary of the
app's own export of tests/fixtures/sample-body.html are read back from the
file; nothing here is inferred from the code that wrote it. Then the
three ways the PDF/UA claim is withheld: a picture without a description,
a skipped heading level, no title. Then the Overseer's round 2 defects: a
received font family cannot break out of the print page (1), an engine
that stops tagging makes the export refuse and save nothing (2), junk
after the PDF header is a sentence rather than a temp path (4), and the
file goes into place atomically with one sentence for a locked or
read-only destination (5 and 12).

    python tests/test_pdfexport.py
"""

import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # noqa: E402
import pikepdf  # noqa: E402

from easypdf import constants as C  # noqa: E402
from easypdf import pdfcheck, pdfengine, pdfexport  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


BODY = open(os.path.join(HERE, "tests", "fixtures", "sample-body.html"), encoding="utf-8").read()
META = {"title": "Sample document", "author": "Tony Gebhard", "lang": "en-US",
        "subject": "The export fixture"}
WORK = tempfile.mkdtemp(prefix="easypdf export é ")


def elements(path):
    with pikepdf.open(path) as pdf:
        index = pdfcheck.TextIndex(pdf)
        out = []
        for elem in pdfcheck.walk_tree(pdf, index):
            alt = str(elem.obj.get("/Alt", "")) if "/Alt" in elem.obj else None
            out.append((elem.kind, pdfcheck.element_text(elem, index), alt,
                        [c.kind for c in elem.children]))
        return out


def fonts_embedded(path):
    names = {}
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            for _key, font in page.obj.Resources.get("/Font", pikepdf.Dictionary()).items():
                descriptor = font.get("/FontDescriptor")
                if str(font.get("/Subtype")) == "/Type0":
                    descriptor = font.DescendantFonts[0].get("/FontDescriptor")
                names[str(font.BaseFont)] = descriptor is not None and any(
                    key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
    return names


print("\nThe clean fixture")
out = os.path.join(WORK, "sample ü.pdf")
steps = []
started = time.perf_counter()
result = pdfexport.export_html(BODY, out, META, progress=steps.append)
elapsed = time.perf_counter() - started
print("  export took %.2f seconds with %s" % (elapsed, result.engine))
check("the PDF exists and the result names it", os.path.isfile(out) and result.path == out)
check("two pages", result.pages == 2, result.pages)
check("the engine string is a name and a version",
      re.match(r"^.+ \d+(\.\d+){2,3}$", result.engine), result.engine)
check("no warnings on the clean fixture", result.warnings == [], result.warnings)
check("pdfua_claimed is True", result.pdfua_claimed is True)
check("the report came back with the result and its gate passed",
      result.report is not None and result.report.pdfua_gate and result.report.passed)
check("progress reported every step in order", steps == [
    pdfexport.STEP_CHECK_DOCUMENT, pdfexport.STEP_LAYOUT, pdfexport.STEP_INFO,
    pdfexport.STEP_CHECK_PDF, pdfexport.STEP_IDENTIFIER], steps)

print("\nThe structure tree, read back with pikepdf")
tree = elements(out)
kinds = [kind for kind, _text, _alt, _children in tree]
for wanted in ("/Document", "/H1", "/H2", "/H3", "/P", "/Strong", "/Em", "/Code", "/Link",
               "/L", "/LI", "/Lbl", "/BlockQuote", "/Figure", "/Caption", "/Table", "/TR",
               "/TH", "/TD"):
    check("the tree holds %s" % wanted, wanted in kinds)
texts = {kind: text for kind, text, _alt, _children in tree}
check("the H1 is the fixture's title", any(k == "/H1" and t == "Sample document" for k, t, _a, _c in tree))
headings = [(k, t) for k, t, _a, _c in tree if k in pdfcheck.HEADING_NAMES]
check("headings come in document order", headings == [
    ("/H1", "Sample document"), ("/H2", "Lists"), ("/H2", "A quotation"),
    ("/H3", "A picture with a description"), ("/H3", "A decorative picture"), ("/H2", "A table")],
    headings)
figures = [(t, a) for k, t, a, _c in tree if k == "/Figure"]
check("exactly one Figure: the decorative picture is absent from the tree", len(figures) == 1, figures)
check("the Figure carries the exact Alt",
      figures and figures[0][1] == "A yellow circle on a blue background", figures)
check("no Figure without Alt (the figure element is presentational, its caption beside it)",
      all(a for _t, a in figures))
captions = [t for k, t, _a, _c in tree if k == "/Caption"]
check("the caption is a Caption element with its text",
      captions == ["Figure 1. A yellow circle on a blue background."], captions)
check("the Link holds its text and its annotation",
      any(k == "/Link" and t == "a link to TG Studios" for k, t, _a, _c in tree))
with pikepdf.open(out) as pdf:
    link_annots = [a for page in pdf.pages for a in page.obj.get("/Annots", [])
                   if str(a.get("/Subtype")) == "/Link"]
    check("the link annotation has a StructParent (OBJR from the Link)",
          link_annots and all("/StructParent" in a for a in link_annots))
    check("the link annotation carries the link text as Contents",
          link_annots and str(link_annots[0].Contents) == "a link to TG Studios",
          [str(a.get("/Contents")) for a in link_annots])
    check("every page has Tabs S", all(str(p.obj.get("/Tabs")) == "/S" for p in pdf.pages))
    check("MarkInfo Marked, Lang and DisplayDocTitle are set",
          bool(pdf.Root.MarkInfo.Marked) and str(pdf.Root.Lang) == "en-US"
          and bool(pdf.Root.ViewerPreferences.DisplayDocTitle))
    info = {str(k): str(v) for k, v in pdf.docinfo.items()}
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        xmp = {key: meta.get(key) for key in ("dc:title", "dc:creator", "dc:description",
                                              "dc:language", "xmp:CreatorTool", "pdf:Producer",
                                              "pdfuaid:part")}
li_children = [c for k, _t, _a, c in tree if k == "/LI"]
check("list items hold a label (LBody is the engine's known gap)",
      li_children and all("/Lbl" in c for c in li_children))
th = [k for k, _t, _a, _c in tree if k == "/TH"]
check("the table has two header cells", len(th) == 2)

print("\nFonts")
fonts = fonts_embedded(out)
check("every font is embedded", fonts and all(fonts.values()), fonts)
check("the body font is Arial and code is Consolas",
      any("Arial" in n for n in fonts) and any("Consolas" in n for n in fonts), list(fonts))

print("\nInfo and XMP after the final save")
producer = "%s %s (%s)" % (C.APP_NAME, C.APP_VERSION, result.engine)
check("Info Creator is the app", info.get("/Creator") == "%s %s" % (C.APP_NAME, C.APP_VERSION), info.get("/Creator"))
check("Info Producer names the app and the engine with its version",
      info.get("/Producer") == producer, info.get("/Producer"))
check("pikepdf did not stamp itself anywhere",
      "pikepdf" not in (info.get("/Producer", "") + str(xmp["pdf:Producer"])))
check("Info Title, Author and Subject", info.get("/Title") == META["title"]
      and info.get("/Author") == META["author"] and info.get("/Subject") == META["subject"])
check("XMP dc:title", xmp["dc:title"] == META["title"], xmp["dc:title"])
check("XMP dc:creator", list(xmp["dc:creator"] or []) == [META["author"]], xmp["dc:creator"])
check("XMP dc:description and dc:language",
      xmp["dc:description"] == META["subject"] and list(xmp["dc:language"] or []) == ["en-US"])
check("XMP CreatorTool and Producer", xmp["xmp:CreatorTool"] == "%s %s" % (C.APP_NAME, C.APP_VERSION)
      and xmp["pdf:Producer"] == producer)
check("XMP pdfuaid:part is 1", str(xmp["pdfuaid:part"]) == "1", xmp["pdfuaid:part"])
with pikepdf.open(out) as pdf:
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        raw = str(meta)
check("the identifier is in the PDF/UA namespace",
      'xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/"' in raw or "aiim.org/pdfua/ns/id" in raw)

print("\nThe header and footer flag")
with fitz.open(out) as doc:
    text = "\n".join(page.get_text() for page in doc)
lines = [line.strip() for line in text.splitlines()]
check("no file path, no date, no page number in the page text",
      "file:" not in text and ".html" not in text
      and not any(re.match(r"^\d+/\d+$", line) for line in lines)
      and not any(re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", line) for line in lines))

print("\nA picture without a description withholds the claim")
bad = BODY.replace('alt="A yellow circle on a blue background"', "")
result2 = pdfexport.export_html(bad, os.path.join(WORK, "no-alt.pdf"), META)
check("the PDF is still tagged", result2.report.results[0].passed and result2.pages == 2)
check("pdfua_claimed is False", result2.pdfua_claimed is False)
check("the identifier was not written",
      any(r.key == "identifier" and not r.passed for r in result2.report.results))
check("a warning names the check that failed",
      any("Pictures described" in w for w in result2.warnings), result2.warnings)
check("the normaliser warned that a picture still needs a description",
      any("still needs a description" in w for w in result2.warnings))
check("the undescribed picture is in the tree as a Figure without Alt",
      any(k == "/Figure" and not a for k, _t, a, _c in elements(os.path.join(WORK, "no-alt.pdf"))))

print("\nA skipped heading level withholds the claim")
skipped = BODY.replace("<h2>Lists</h2>", "<h4>Lists</h4>")
result3 = pdfexport.export_html(skipped, os.path.join(WORK, "skip.pdf"), META)
check("pdfua_claimed is False", result3.pdfua_claimed is False)
check("the warning names Heading levels", any("Heading levels" in w for w in result3.warnings), result3.warnings)
detail = [r.detail for r in result3.report.results if r.key == "headings"][0]
check("the checker names the heading text and the levels",
      '"Lists"' in detail and "level 4" in detail and "level 1" in detail, detail)

print("\nNo title withholds the claim")
result4 = pdfexport.export_html(BODY, os.path.join(WORK, "no-title.pdf"), {"author": "x"})
check("pdfua_claimed is False", result4.pdfua_claimed is False)
check("the no title warning is first and the Title check is named",
      result4.warnings and result4.warnings[0] == pdfexport.MSG_NO_TITLE
      and any("Title" in w for w in result4.warnings[1:]), result4.warnings)

print("\nOther warnings and defaults")
arabic = BODY + "<p>مرحبا بالعالم</p>"
result5 = pdfexport.export_html(arabic, os.path.join(WORK, "rtl.pdf"), META)
check("Arabic text produces the right to left warning",
      any("right to left" in w for w in result5.warnings), result5.warnings)
ai = BODY.replace('alt="A yellow circle on a blue background"',
                  'alt="A yellow circle on a blue background" data-alt-source="ai:anthropic"')
result6 = pdfexport.export_html(ai, os.path.join(WORK, "ai.pdf"), META)
check("an AI written description is counted into one warning",
      any("written by AI" in w for w in result6.warnings), result6.warnings)
check("and the claim still stands (the description is present)", result6.pdfua_claimed is True)
with pikepdf.open(os.path.join(WORK, "ai.pdf")) as pdf:
    raw = pdf.pages[0].obj.get("/StructParents") is not None
check("data attributes never reach the PDF", "data-alt-source" not in open(os.path.join(WORK, "ai.pdf"), "rb").read().decode("latin-1"))
settings = pdfexport.settings_from({"title": "T"})
check("missing meta keys take the constants' defaults",
      settings["page_size"] == C.DEFAULT_PAGE_SIZE and settings["margin"] == "1"
      and settings["font_points"] == str(C.DEFAULT_FONT_POINTS) and settings["lang"] == "en-US"
      and settings["font_family"] == C.DEFAULT_FONT_FAMILY, settings)
a4 = pdfexport.settings_from({"page_size": "A4", "margin_inches": 0.5, "font_points": 12, "lang": "de"})
check("page size, margin, font size and language are honoured",
      a4["page_size"] == "A4" and a4["margin"] == "0.5" and a4["font_points"] == "12" and a4["lang"] == "de")
result7 = pdfexport.export_html(BODY, os.path.join(WORK, "a4.pdf"), dict(META, page_size="A4"))
with fitz.open(os.path.join(WORK, "a4.pdf")) as doc:
    width = doc[0].rect.width
check("an A4 export has an A4 page (595 points wide)", 590 < width < 600, width)

print("\nA received font family cannot break out of the print page")
INJECTION = "Arial}</style><p>INJECTED</p><style>"
settings = pdfexport.settings_from(dict(META, font_family=INJECTION))
check("a font family holding a brace and a tag falls back to the default",
      settings["font_family"] == C.DEFAULT_FONT_FAMILY, settings["font_family"])
page = pdfexport.build_page("<p>x</p>", settings)
check("the injection string is not in the print page", "INJECTED" not in page and "</style><p>" not in page)
check("the print page carries the Content Security Policy",
      '<meta http-equiv="Content-Security-Policy" content="%s">' % pdfexport.CONTENT_SECURITY_POLICY in page
      and "default-src 'none'" in page and "img-src data:" in page and "style-src 'unsafe-inline'" in page)
good = pdfexport.settings_from(dict(META, font_family='Georgia, "Times New Roman", serif'))
check("a font family of letters, commas and quotes is kept", good["font_family"] == 'Georgia, "Times New Roman", serif')
odd_families = ("Arial; color: red", "Arial</style>", "url(x)", "Arial" + chr(92) + "x", "<b>", "Arial{", "")
check("semicolons, angle brackets, parentheses, backslashes, braces and an empty value all fall back",
      all(pdfexport.settings_from({"font_family": odd})["font_family"] == C.DEFAULT_FONT_FAMILY for odd in odd_families))
inject_pdf = os.path.join(WORK, "inject.pdf")
pdfexport.export_html("<h1>Title</h1><p>Body text.</p>", inject_pdf, dict(META, font_family=INJECTION))
with fitz.open(inject_pdf) as doc:
    inject_text = "\n".join(page.get_text() for page in doc)
check("rendered through the engine, the page holds no injected text",
      "INJECTED" not in inject_text and "Body text." in inject_text, inject_text)

print("\nAn engine that stops tagging")
FAKE = pdfengine.Engine("Fake engine", "fake.exe", "0.0.0")


def untagged_engine(html_text, out_path, timeout=90, engine=None):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 100), "Text with no tags", fontname="helv", fontsize=12)
        doc.save(out_path)
    return FAKE


def junk_engine(html_text, out_path, timeout=90, engine=None):
    with open(out_path, "wb") as handle:
        handle.write(b"%PDF-1.7 and then nothing a PDF reader can use")
    return FAKE


earlier = open(out, "rb").read()
real_render = pdfengine.render_pdf
pdfengine.render_pdf = untagged_engine
try:
    try:
        pdfexport.export_html(BODY, out, META)
        check("an untagged engine output raises EngineError", False)
    except pdfengine.EngineError as exc:
        check("an untagged engine output raises EngineError with the untagged sentence",
              str(exc) == pdfexport.MSG_UNTAGGED, exc)
    check("the earlier PDF at that path is untouched", open(out, "rb").read() == earlier)
    fresh = os.path.join(WORK, "untagged.pdf")
    try:
        pdfexport.export_html(BODY, fresh, META)
    except pdfengine.EngineError:
        pass
    check("nothing is written at a new path either", not os.path.exists(fresh))
    check("no part file is left in the folder", not [n for n in os.listdir(WORK) if n.endswith(".part")])
finally:
    pdfengine.render_pdf = real_render

print("\nGarbage from the engine")
pdfengine.render_pdf = junk_engine
junk = os.path.join(WORK, "junk.pdf")
try:
    try:
        pdfexport.export_html(BODY, junk, META)
        check("junk after the PDF header raises EngineError", False)
    except pdfengine.EngineError as exc:
        check("junk after the PDF header raises EngineError with a sentence", str(exc) == pdfexport.MSG_DAMAGED, exc)
        check("and no temp path or library words in it",
              "easypdf-export" not in str(exc) and "trailer" not in str(exc)
              and tempfile.gettempdir().lower() not in str(exc).lower())
    except Exception as exc:
        check("junk after the PDF header raises EngineError, not %s" % type(exc).__name__, False, exc)
finally:
    pdfengine.render_pdf = real_render
check("no file was left at the destination", not os.path.exists(junk))

print("\nThe file goes into place atomically")
earlier = open(out, "rb").read()
real_replace = os.replace


def no_space(source, target):
    if os.path.abspath(str(target)) == os.path.abspath(out):
        raise OSError(28, "No space left on device")
    return real_replace(source, target)


os.replace = no_space
try:
    pdfexport.export_html(BODY, out, META)
    check("a failed replace raises EngineError", False)
except pdfengine.EngineError as exc:
    check("a failed replace raises EngineError naming the path and the reason",
          str(exc).startswith("The PDF could not be written to " + out) and "No space left" in str(exc), exc)
finally:
    os.replace = real_replace
check("the earlier PDF is untouched after the failed replace", open(out, "rb").read() == earlier)
check("no part file is left beside it", not [n for n in os.listdir(WORK) if n.endswith(".part")])
with open(out, "rb"):
    # Held open, as another program would hold it: os.replace over it
    # fails with PermissionError on Windows.
    try:
        pdfexport.export_html(BODY, out, META)
        check("a destination open in another program raises EngineError", False)
    except pdfengine.EngineError as exc:
        check("a destination open in another program raises EngineError with the one sentence "
              "for locks and read-only folders", str(exc) == pdfexport.MSG_NOT_WRITTEN % out, exc)
check("the earlier PDF is untouched after the lock", open(out, "rb").read() == earlier)
check("no part file is left after the lock", not [n for n in os.listdir(WORK) if n.endswith(".part")])

print("\nWithout an engine")
real = pdfengine.engines
pdfengine.engines = lambda: []
try:
    pdfexport.export_html(BODY, os.path.join(WORK, "none.pdf"), META)
    check("export raises EngineError when there is no engine", False)
except pdfengine.EngineError as exc:
    check("export raises EngineError when there is no engine, naming the three engines",
          "Microsoft Edge" in str(exc) and "Google Chrome" in str(exc))
finally:
    pdfengine.engines = real
check("nothing was written", not os.path.exists(os.path.join(WORK, "none.pdf")))
leftovers = [n for n in os.listdir(tempfile.gettempdir()) if n.startswith("easypdf-export-")]
check("no export folder is left behind", not leftovers, leftovers)

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
