"""The checker: passes the app's own export, fails a file broken on purpose.

Each break is made with pikepdf on a copy of the clean export, then the
checker must fail exactly that check by name. A PDF made by PyMuPDF with
no structure tree, an unembedded font and text outside any tag covers the
checks the export never trips.

    python tests/test_pdfcheck.py
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

from tgimprint import pdfcheck, pdfexport  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


BODY = open(os.path.join(HERE, "tests", "fixtures", "sample-body.html"), encoding="utf-8").read()
META = {"title": "Sample document", "author": "Tony Gebhard", "lang": "en-US"}
WORK = tempfile.mkdtemp(prefix="tgimprint check é ")
CLEAN = os.path.join(WORK, "clean.pdf")
pdfexport.export_html(BODY, CLEAN, META)


def result(report, key):
    for item in report.results:
        if item.key == key:
            return item
    return None


def broken(name, breaker):
    """A copy of the clean export with one thing broken."""
    path = os.path.join(WORK, name)
    with pikepdf.open(CLEAN) as pdf:
        breaker(pdf)
        pdf.save(path)
    return path


print("\nThe clean export")
started = time.perf_counter()
report = pdfcheck.check(CLEAN)
elapsed = time.perf_counter() - started
print("  the check took %.2f seconds" % elapsed)
check("every check passes", report.passed, report.failed_names())
check("the gate is open", report.pdfua_gate)
check("sixteen checks", len(report.results) == 16, len(report.results))
check("the score counts what passed", report.score == (15, 16), report.score)
check("the one warning is the engine's LBody gap", report.warnings == 1
      and result(report, "lbody").warn_only and not result(report, "lbody").passed)
check("every check has a key, a name and a detail sentence",
      all(r.key and r.name and r.detail.endswith(".") for r in report.results))
text = report.format_report()
lines = text.splitlines()
check("format_report is one line per check, plus header and footer",
      len(lines) == 2 + 16 + 1, len(lines))
check("every check line starts with PASS, FAIL or WARN",
      all(re.match(r"^(PASS|FAIL|WARN): ", line) for line in lines[2:-1]))
check("no markdown in the report", not any(ch in text for ch in "#*|`"))
check("the report says a full verdict needs PAC or veraPDF", lines[-1] == pdfcheck.CLOSING)
check("no dashes", chr(8212) not in text and chr(8211) not in text)
print("  " + lines[1])

print("\nBroken on purpose")


def strip_markinfo(pdf):
    del pdf.Root["/MarkInfo"]


path = broken("no-markinfo.pdf", strip_markinfo)
report = pdfcheck.check(path)
check("stripping MarkInfo fails Tagged PDF", not result(report, "tagged").passed and not report.pdfua_gate)
check("and the other checks still run", result(report, "figures").passed and len(report.results) == 16)


def remove_alt(pdf):
    for elem in pdfcheck.walk_tree(pdf):
        if elem.kind == "/Figure" and "/Alt" in elem.obj:
            del elem.obj["/Alt"]


path = broken("no-alt.pdf", remove_alt)
report = pdfcheck.check(path)
item = result(report, "figures")
check("removing the Alt fails Pictures described", not item.passed and not report.pdfua_gate)
check("with a sentence that says what to do", "Give it one in Pictures" in item.detail, item.detail)


def remove_lang(pdf):
    del pdf.Root["/Lang"]


report = pdfcheck.check(broken("no-lang.pdf", remove_lang))
check("removing Lang fails Language", not result(report, "lang").passed
      and "Document properties" in result(report, "lang").detail)


def bad_lang(pdf):
    pdf.Root.Lang = pikepdf.String("not a language")


report = pdfcheck.check(broken("bad-lang.pdf", bad_lang))
check("a Lang that is not a language code fails", not result(report, "lang").passed)


def skip_heading(pdf):
    for elem in pdfcheck.walk_tree(pdf):
        if elem.kind == "/H2":
            elem.obj.S = pikepdf.Name("/H4")
            break


report = pdfcheck.check(broken("skip.pdf", skip_heading))
item = result(report, "headings")
check("a skipped level fails Heading levels", not item.passed and not report.pdfua_gate)
check("and names the heading by its text from the content stream",
      '"Lists"' in item.detail and '"Sample document"' in item.detail, item.detail)


def remove_identifier(pdf):
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        del meta["pdfuaid:part"]


report = pdfcheck.check(broken("no-id.pdf", remove_identifier))
check("removing the identifier fails only the identifier check",
      not result(report, "identifier").passed and report.failed_names() == [])
check("and the gate stays open, because the gate excludes the identifier itself",
      report.pdfua_gate and not report.passed)
check("its detail says when TG Imprint writes one",
      "only when every other check passes" in result(report, "identifier").detail)


def remove_display(pdf):
    del pdf.Root["/ViewerPreferences"]


report = pdfcheck.check(broken("no-display.pdf", remove_display))
check("removing ViewerPreferences fails Title shown in the window", not result(report, "display_title").passed)


def remove_title(pdf):
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        del meta["dc:title"]


report = pdfcheck.check(broken("no-xmp-title.pdf", remove_title))
item = result(report, "title")
check("a title in Info but not in XMP fails Title and says so",
      not item.passed and "XMP" in item.detail, item.detail)


def remove_contents(pdf):
    for page in pdf.pages:
        for annot in page.obj.get("/Annots", []):
            if "/Contents" in annot:
                del annot["/Contents"]


report = pdfcheck.check(broken("no-contents.pdf", remove_contents))
check("a link without Contents fails Links described", not result(report, "link_contents").passed)


def remove_struct_parent(pdf):
    for page in pdf.pages:
        for annot in page.obj.get("/Annots", []):
            if "/StructParent" in annot:
                del annot["/StructParent"]


report = pdfcheck.check(broken("no-structparent.pdf", remove_struct_parent))
check("a link outside the tree fails Links tagged", not result(report, "links").passed)


def remove_tabs(pdf):
    for page in pdf.pages:
        if "/Tabs" in page.obj:
            del page.obj["/Tabs"]


report = pdfcheck.check(broken("no-tabs.pdf", remove_tabs))
check("a page with links and no Tabs S fails Tab order", not result(report, "tabs").passed)


def remove_outline(pdf):
    del pdf.Root["/Outlines"]


report = pdfcheck.check(broken("no-outline.pdf", remove_outline))
item = result(report, "outline")
check("no bookmarks is a warning, not a failure",
      not item.passed and item.warn_only and report.pdfua_gate and item.word == "WARN")


def strip_tree(pdf):
    del pdf.Root["/StructTreeRoot"]


report = pdfcheck.check(broken("no-tree.pdf", strip_tree))
check("no structure tree fails Structure tree", not result(report, "tree").passed)

print("\nA PDF made without any tagging")
untagged = os.path.join(WORK, "untagged.pdf")
with fitz.open() as doc:
    page = doc.new_page()
    page.insert_text((72, 100), "Hello from an untagged file", fontname="helv", fontsize=12)
    doc.save(untagged)
report = pdfcheck.check(untagged)
check("Tagged PDF and Structure tree fail",
      not result(report, "tagged").passed and not result(report, "tree").passed)
check("an unembedded font fails Fonts embedded and is named",
      not result(report, "fonts").passed and "Helvetica" in result(report, "fonts").detail,
      result(report, "fonts").detail)
check("text outside any tag fails All text tagged", not result(report, "untagged").passed)
check("the text layer is still found", result(report, "text").passed)

print("\nA scanned PDF")
scanned = os.path.join(WORK, "scanned.pdf")
with fitz.open() as doc:
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 400, 300),
                      filename=os.path.join(HERE, "tests", "fixtures", "circle.png"))
    doc.save(scanned)
report = pdfcheck.check(scanned)
item = result(report, "text")
check("a PDF of pictures fails Text layer with the pictures of text sentence",
      not item.passed and item.detail.startswith("This PDF is pictures of text"), item.detail)
check("All text tagged is not reported when there is no text",
      result(report, "untagged") is None)

print("\nFiles that are not readable PDFs")
report = pdfcheck.check(os.path.join(HERE, "tests", "fixtures", "sample.txt"))
check("a text file gives one failed File readable result",
      len(report.results) == 1 and report.results[0].key == "readable" and not report.passed)
check("and no gate", not report.pdfua_gate)
locked = os.path.join(WORK, "locked.pdf")
with pikepdf.open(CLEAN) as pdf:
    pdf.save(locked, encryption=pikepdf.Encryption(owner="owner", user="user"))
report = pdfcheck.check(locked)
check("a password protected PDF says so",
      len(report.results) == 1 and "password" in report.results[0].detail)
report = pdfcheck.check(os.path.join(WORK, "does-not-exist.pdf"))
check("a missing file is reported, not raised", len(report.results) == 1 and not report.passed)

print("\nAn artifact by named property list")
propd = os.path.join(WORK, "artifact-property.pdf")
with pikepdf.new() as pdf:
    page = pdf.add_blank_page(page_size=(200, 200))
    image = pikepdf.Stream(pdf, bytes([255, 0, 0]) * 16)
    image["/Type"] = pikepdf.Name("/XObject")
    image["/Subtype"] = pikepdf.Name("/Image")
    image["/Width"] = 4
    image["/Height"] = 4
    image["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
    image["/BitsPerComponent"] = 8
    page.obj["/Resources"] = pikepdf.Dictionary(
        XObject=pikepdf.Dictionary(Im1=image),
        Properties=pikepdf.Dictionary(P1=pikepdf.Dictionary(Type=pikepdf.Name("/Pagination"))))
    # The first image is inside an artifact named through the property
    # list (the form that read as content before the fix, Overseer round
    # 2, defect 11), the second inside tagged content, the third inside a
    # BMC artifact.
    page.obj["/Contents"] = pdf.make_stream(
        b"/Artifact /P1 BDC q 50 0 0 50 20 20 cm /Im1 Do Q EMC "
        b"/P <</MCID 0>> BDC q 50 0 0 50 100 20 cm /Im1 Do Q EMC "
        b"/Artifact BMC q 50 0 0 50 20 100 cm /Im1 Do Q EMC")
    pdf.save(propd)
with pikepdf.open(propd) as pdf:
    index = pdfcheck.TextIndex(pdf)
    marks = index.image_marks(0)
    drawn = index.page(0)["images"]
check("three images are counted", drawn == 3, drawn)
check("the named property list form is untagged, the MCID one tagged, the BMC artifact untagged",
      [m[1] for m in marks] == [False, True, False], marks)
check("every mark carries the image's object number, the same object three times",
      len(marks) == 3 and all(m[0] > 0 for m in marks) and len(set(m[0] for m in marks)) == 1, marks)

print("\nThe text index")
with pikepdf.open(CLEAN) as pdf:
    index = pdfcheck.TextIndex(pdf)
    words = {}
    for elem in pdfcheck.walk_tree(pdf, index):
        if elem.kind in ("/H1", "/Link", "/Caption"):
            words[elem.kind] = pdfcheck.element_text(elem, index)
    descriptions = [(text, uri) for _annot, text, uri in pdfcheck.link_descriptions(pdf)]
    pages = [elem.page for elem in pdfcheck.walk_tree(pdf, index) if elem.kind == "/H2"]
check("the heading text is decoded through the font's ToUnicode map",
      words.get("/H1") == "Sample document", words)
check("spaces are real glyphs, not guessed from positioning",
      words.get("/Caption") == "Figure 1. A yellow circle on a blue background.", words)
check("link descriptions carry the text and the address",
      descriptions == [("a link to TG Studios", "https://tgstudios.app/")], descriptions)
check("elements without their own Pg take their children's page", pages == [0, 0, 1], pages)

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
