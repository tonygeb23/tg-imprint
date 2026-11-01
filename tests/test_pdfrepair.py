"""Damaged, scanned, garbled and hostile PDFs, built here so the test owns them.

    python tests/test_pdfrepair.py

Every file is made in this script. Each check asserts what a user gets: the
words, or one sentence that says why not, never a library error and never a
temp path.
"""
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import fitz  # noqa: E402
import pikepdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from tgimprint import pdfanalysis, pdfcheck, pdfimport, pdfocr, pdfrepair  # noqa: E402

WORK = tempfile.mkdtemp(prefix="tgimprint-repair-test-")
passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  ok   %s" % name)
    else:
        failed += 1
        print("  FAIL %s  %s" % (name, detail))


def path(name):
    return os.path.join(WORK, name)


PARA = ("The council meets on the first Tuesday of each month. Residents may speak for "
        "three minutes. Minutes are published within ten working days.")


def flat(name, pages=3, header=True):
    doc = fitz.open()
    for number in range(pages):
        page = doc.new_page()
        if header:
            page.insert_text((72, 40), "City of Example Annual Report", fontsize=9)
            page.insert_text((280, 770), "Page %d" % (number + 1), fontsize=9)
        page.insert_text((72, 90), "Section %d" % (number + 1), fontsize=22, fontname="hebo")
        page.insert_textbox(fitz.Rect(72, 120, 540, 400), PARA, fontsize=11)
    doc.save(path(name))
    doc.close()
    return path(name)


def scan(name, lines):
    image = Image.new("L", (1275, 1650), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 36)
    for index, line in enumerate(lines):
        draw.text((120, 200 + index * 60), line, font=font, fill=0)
    picture = path(name + ".png")
    image.save(picture)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, filename=picture)
    doc.save(path(name))
    doc.close()
    return path(name)


good = flat("good.pdf", pages=2, header=False)
raw = open(good, "rb").read()

print("Opening, or one sentence")
for name, data, sentence in (("empty.pdf", b"", pdfrepair.MSG_EMPTY),
                             ("text.pdf", b"plain words\n" * 40, pdfrepair.MSG_NOT_PDF),
                             ("web.pdf", b"<html>404</html>", pdfrepair.MSG_WEB_PAGE)):
    open(path(name), "wb").write(data)
    try:
        pdfimport.import_pdf(path(name))
        check("%s is refused" % name, False)
    except pdfrepair.PdfOpenError as exc:
        check("%s says what is wrong, with no path in it" % name,
              str(exc) == sentence and WORK not in str(exc), str(exc))
try:
    pdfimport.import_pdf(path("nowhere.pdf"))
    check("a missing file is refused", False)
except pdfrepair.PdfOpenError as exc:
    check("a missing file says so", str(exc) == pdfrepair.MSG_MISSING, str(exc))

print("\nDamage")
open(path("half.pdf"), "wb").write(raw[:len(raw) // 2])
result = pdfimport.import_pdf(path("half.pdf"))
check("a file cut in half opens with what survives", "Section 1" in result.body_html)
check("and says it was repaired", pdfrepair.NOTE_REPAIRED in result.warnings, result.warnings)
check("and says how many pages were lost",
      any("only 1 of its 2 pages" in w for w in result.warnings), result.warnings)
open(path("junk.pdf"), "wb").write(b"<html>proxy</html>\n" * 20 + raw)
result = pdfimport.import_pdf(path("junk.pdf"))
check("junk in front of the header is ignored and reported",
      "Section 2" in result.body_html and pdfrepair.NOTE_JUNK in result.warnings, result.warnings)
open(path("xref.pdf"), "wb").write(raw.replace(b"startxref", b"startxrfe"))
result = pdfimport.import_pdf(path("xref.pdf"))
check("a broken cross reference is rebuilt", "Section 2" in result.body_html
      and pdfrepair.NOTE_REPAIRED in result.warnings, result.warnings)

print("\nPasswords")
with pikepdf.open(good) as pdf:
    pdf.save(path("locked.pdf"), encryption=pikepdf.Encryption(user="abc", owner="xyz"))
    pdf.save(path("restricted.pdf"), encryption=pikepdf.Encryption(
        user="", owner="xyz", R=4, allow=pikepdf.Permissions(extract=False, accessibility=False)))
try:
    pdfimport.import_pdf(path("locked.pdf"))
    check("a locked file asks", False)
except pdfrepair.PdfPasswordError as exc:
    check("a locked file asks for the password", not exc.wrong, str(exc))
try:
    pdfimport.import_pdf(path("locked.pdf"), password="nope")
    check("a wrong password is refused", False)
except pdfrepair.PdfPasswordError as exc:
    check("a wrong password says so", exc.wrong and str(exc) == pdfrepair.MSG_WRONG_PASSWORD, str(exc))
result = pdfimport.import_pdf(path("locked.pdf"), password="abc")
check("the right password opens it", "Section 1" in result.body_html)
analysis = pdfanalysis.analyse(path("locked.pdf"))
check("analysis of a locked file asks rather than fails", analysis.needs_password)
analysis = pdfanalysis.analyse(path("locked.pdf"), "abc")
check("and analyses it given the password", analysis.report is not None and analysis.pages == 2)
report = pdfcheck.check(path("restricted.pdf"))
check("a file that forbids copying but allows accessibility passes Permissions",
      any(r.key == "permissions" and r.passed for r in report.results))
# pikepdf will not write the accessibility bit cleared, so the refusal is
# exercised on a stand-in with the same two attributes.
got = []
pdfcheck._check_permissions(types.SimpleNamespace(is_encrypted=True, allow=types.SimpleNamespace(
    accessibility=False, extract=False)), got.append)
check("a file forbidding accessibility access fails Permissions", got and not got[0].passed)

print("\nText recognition")
check("the language data is in the repository", pdfocr.available("eng") and pdfocr.available("spa"))
scanned = scan("scan.pdf", ["Your bin collection day changes on Monday.",
                            "Please call the council on 555 0100."])
result = pdfimport.import_pdf(scanned)
check("a scan comes back as words", "bin collection" in result.body_html, result.body_html[:200])
check("the number survived", "555 0100" in result.body_html, result.body_html[:300])
check("the whole page picture is not kept as a figure", not result.images, len(result.images))
check("it is not reported as unreadable", not result.is_scanned)
check("recognition is said out loud", any("text recognition" in w for w in result.warnings), result.warnings)
result = pdfimport.import_pdf(scanned, ocr=False)
check("with recognition off a scan is reported as pictures of text", result.is_scanned, result.warnings)
steps = []
pdfimport.import_pdf(scanned, progress=steps.append)
check("recognition reports progress", any(s.startswith("Recognising") for s in steps), steps)

print("\nGarbled text")
garbled = flat("garbled.pdf", pages=1, header=False)
with pikepdf.open(garbled, allow_overwriting_input=True) as pdf:
    cmap = (b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"1 begincodespacerange <00> <FF> endcodespacerange\n"
            b"1 beginbfrange <20> <7E> <E020> endbfrange\nendcmap end end\n")
    for font in pdf.pages[0].obj.Resources.Font.values():
        font.ToUnicode = pdf.make_stream(cmap)
    pdf.save(garbled)
result = pdfimport.import_pdf(garbled)
check("text that reads as symbols is recognised from the page", "council" in result.body_html,
      result.body_html[:200])
report = pdfcheck.check(garbled)
check("the checker fails it", any(r.key == "garbled" and not r.passed for r in report.results))
check("text_quality counts private use characters", pdfcheck.text_quality("ab") == 0.5)
check("and clean text is clean", pdfcheck.text_quality("Plain words.") == 0.0)

print("\nA real document")
report_pdf = flat("report.pdf")
result = pdfimport.import_pdf(report_pdf)
check("a running header is left out", "City of Example" not in result.body_html, result.body_html[:200])
check("a page number footer is left out", "Page 2" not in result.body_html)
check("and that is said", any("running header" in w for w in result.warnings), result.warnings)
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 60), "Quarterly figures", fontsize=20, fontname="hebo")
y = 90
for row in (("Quarter", "Income"), ("Q1", "100"), ("Q2", "120")):
    x = 72
    for cell in row:
        page.draw_rect(fitz.Rect(x, y, x + 130, y + 24), color=(0, 0, 0))
        page.insert_text((x + 5, y + 16), cell, fontsize=11)
        x += 130
    y += 24
doc.save(path("table.pdf"))
doc.close()
result = pdfimport.import_pdf(path("table.pdf"))
check("a ruled table becomes a table with a header row",
      '<th scope="col">Quarter</th>' in result.body_html and "<td>120</td>" in result.body_html,
      result.body_html[:300])
doc = fitz.open()
page = doc.new_page()
right = fitz.Rect(315, 90, 560, 740)
left = fitz.Rect(50, 90, 295, 740)
page.insert_textbox(right, "RIGHT words on the right. " * 6, fontsize=10)
page.insert_textbox(left, "LEFT words on the left. " * 6, fontsize=10)
doc.save(path("columns.pdf"))
doc.close()
result = pdfimport.import_pdf(path("columns.pdf"))
check("columns are read left then right, whatever order they were drawn in",
      result.body_html.index("LEFT") < result.body_html.index("RIGHT"), result.body_html[:120])
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 60), "Only big text", fontsize=14)
page.insert_text((72, 100), "Middle text here", fontsize=12)
page.insert_textbox(fitz.Rect(72, 130, 540, 400), PARA * 6, fontsize=9)
doc.save(path("levels.pdf"))
doc.close()
result = pdfimport.import_pdf(path("levels.pdf"))
check("the first heading is level 1 and none is skipped", "<h1>" in result.body_html
      and "<h3>" not in result.body_html, result.body_html[:160])
check("the title falls back to the first heading", result.meta["title"] == "Only big text", result.meta)
check("the language is guessed from the words", result.meta["lang"] == "en-US", result.meta["lang"])
check("Spanish is recognised as Spanish", pdfocr.guess_language(
    "el perro de la casa es de los vecinos que viven en una calle para todos " * 3) == "es")
check("a blank file says so", any(pdfimport.MSG_NOTHING == w for w in pdfimport.import_pdf(
    (lambda d: (d.new_page(), d.save(path("blank.pdf")), d.close(), path("blank.pdf"))[3])(fitz.open())
).warnings))

print("\nWhat the audit found")
form_import = None
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 80), "A form", fontsize=20)
widget = fitz.Widget()
widget.field_name = "one"
widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
widget.rect = fitz.Rect(200, 125, 400, 150)
page.add_widget(widget)
doc.save(path("fields.pdf"))
doc.close()
result = pdfimport.import_pdf(path("fields.pdf"))
check("bringing in a form says the fields will be lost",
      any("1 form field" in w and "Fill in a PDF form" in w for w in result.warnings), result.warnings)
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 90), "Cover letter", fontsize=20, fontname="hebo")
page.insert_textbox(fitz.Rect(72, 120, 540, 400), PARA * 3, fontsize=11)
page = doc.new_page(width=612, height=792)
picture = path("mixed.png")
image = Image.new("L", (1275, 1650), 255)
draw = ImageDraw.Draw(image)
font = ImageFont.truetype("arial.ttf", 36)
for index, line in enumerate(("Your bin day changes on Monday.", "Please call the council today.",
                              "Large print copies are available.")):
    draw.text((120, 200 + index * 60), line, font=font, fill=0)
image.save(picture)
page.insert_image(page.rect, filename=picture)
doc.save(path("mixed.pdf"))
doc.close()
result = pdfimport.import_pdf(path("mixed.pdf"))
check("a scanned page beside a typed one gives body text, not headings",
      "<h" not in result.body_html.split("Cover letter", 1)[1].split("</h1>", 1)[1], result.body_html[:400])
check("and the title is from the first page", result.meta["title"] == "Cover letter", result.meta["title"])
doc = fitz.open()
page = doc.new_page()
y = 90
for row in (("Name", "Value"), ("A", "1")):
    x = 72
    for cell in row:
        page.draw_rect(fitz.Rect(x, y, x + 130, y + 24), color=(0, 0, 0))
        page.insert_text((x + 5, y + 16), cell, fontsize=11)
        x += 130
    y += 24
logo = path("logo.png")
Image.new("RGB", (120, 60), "navy").save(logo)
page.insert_image(fitz.Rect(72, 300, 192, 360), filename=logo)
doc.save(path("table logo.pdf"))
doc.close()
result = pdfimport.import_pdf(path("table logo.pdf"))
check("a table and a logo is not called pictures of text",
      not any("pictures of text" in w for w in result.warnings), result.warnings)
spanish = fitz.open()
page = spanish.new_page()
page.insert_textbox(fitz.Rect(72, 72, 540, 500),
                    "El ayuntamiento de la ciudad se reune con los vecinos para hablar de que "
                    "el presupuesto es para todos y por eso se publica en la red. " * 4, fontsize=11)
spanish.save(path("es.pdf"))
spanish.close()
fixed = pdfrepair.repair_copy(path("es.pdf"), path("es fixed.pdf"))
with pikepdf.open(path("es fixed.pdf")) as pdf:
    check("repair guesses the language from the words", str(pdf.Root.Lang) == "es", str(pdf.Root.Lang))
check("and says it was a guess", any("guess" in c for c in fixed.changes), fixed.changes)
fixed = pdfrepair.repair_copy(garbled, path("garbled fixed.pdf"))
check("repair never takes a title from symbols",
      not any(chr(0xE053) in c for c in fixed.changes) and any("file name" in c for c in fixed.changes), fixed.changes)
empty = (lambda d: (d.new_page(), d.save(path("nothing.pdf")), d.close(), path("nothing.pdf"))[3])(fitz.open())
analysis = pdfanalysis.analyse(empty)
check("a blank file is called blank", analysis.level == pdfanalysis.LEVEL_EMPTY, analysis.verdict)
analysis = pdfanalysis.analyse(flat("said once.pdf"))
check("the same fix is not read out seven times",
      analysis.format_report().count(pdfanalysis.SAME_FIX) == 0, analysis.format_report().count(pdfanalysis.SAME_FIX))

print("\nAnalysis")
analysis = pdfanalysis.analyse(scanned)
check("a scan is called what it is", analysis.level == pdfanalysis.LEVEL_PICTURES
      and analysis.kinds["scanned"] == 1, analysis.verdict)
check("and the first thing to do is open it", analysis.steps[0] == pdfanalysis.STEP_OPEN, analysis.steps)
analysis = pdfanalysis.analyse(report_pdf)
check("flat text is called flat", analysis.level == pdfanalysis.LEVEL_FLAT, analysis.verdict)
check("rebuild first, repair second", analysis.steps[:2] == [pdfanalysis.STEP_REBUILD,
                                                             pdfanalysis.STEP_REPAIR], analysis.steps)
text = analysis.format_report()
check("the report starts with the answer", text.splitlines()[0]
      == pdfanalysis.VERDICTS[pdfanalysis.LEVEL_FLAT], text[:120])
check("it counts the pages by kind", "3 pages, all text." in text, text[:200])
analysis = pdfanalysis.analyse(garbled)
check("garbled pages are counted", analysis.kinds["garbled"] == 1, analysis.kinds)
open(path("bad.pdf"), "wb").write(b"nope")
analysis = pdfanalysis.analyse(path("bad.pdf"))
check("a file that will not open gets a verdict, not an exception",
      analysis.level == pdfanalysis.LEVEL_UNREADABLE and "not a PDF" in analysis.verdict, analysis.verdict)

print("\nRepair a PDF")
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 80), "Application form", fontsize=20, fontname="hebo")
page.insert_text((72, 140), "Full name", fontsize=12)
widget = fitz.Widget()
widget.field_name = "f1"
widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
widget.rect = fitz.Rect(200, 125, 400, 150)
page.add_widget(widget)
page.insert_text((72, 300), "See our site", fontsize=12)
page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(72, 288, 160, 304), "uri": "https://example.com/"})
doc.save(path("form.pdf"))
doc.close()
before = fitz.open(path("form.pdf"))[0].get_pixmap().samples
fixed = pdfrepair.repair_copy(path("form.pdf"), path("form repaired.pdf"))
check("it says what it changed", any("Named 1 form field" in c for c in fixed.changes)
      and any("title" in c for c in fixed.changes), fixed.changes)
with pikepdf.open(path("form repaired.pdf")) as pdf:
    annots = list(pdf.pages[0].Annots)
    widgets = [a for a in annots if str(a.get("/Subtype")) == "/Widget"]
    links = [a for a in annots if str(a.get("/Subtype")) == "/Link"]
    check("the field is named from the label beside it", str(widgets[0].TU) == "Full name",
          str(widgets[0].get("/TU")))
    check("the link says its words", "See our site" in str(links[0].Contents), str(links[0].get("/Contents")))
    check("a flat file tabs by row", str(pdf.pages[0].Tabs) == "/R")
    check("the language is set", str(pdf.Root.Lang) == "en-US")
    check("the title shows in the window", bool(pdf.Root.ViewerPreferences.DisplayDocTitle))
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        check("the title came from the biggest text", str(meta.get("dc:title")) == "Application form")
        check("nothing claims PDF/UA", not meta.get("pdfuaid:part"))
with pikepdf.open(path("form repaired.pdf")) as pdf:
    check("nobody is told it is tagged", "/MarkInfo" not in pdf.Root)
after = fitz.open(path("form repaired.pdf"))[0].get_pixmap().samples
check("the page looks exactly as it did", before == after)
check("a repair of a repaired file changes nothing it need not",
      not any("Named" in c for c in pdfrepair.repair_copy(path("form repaired.pdf"), path("again.pdf")).changes))
fixed = pdfrepair.repair_copy(path("half.pdf"), path("half fixed.pdf"))
check("a damaged file is rebuilt and that is reported", pdfrepair.CHANGE_REBUILT in fixed.changes, fixed.changes)
check("and the result opens cleanly", fitz.open(path("half fixed.pdf")).page_count == 1)
check("repair leaves no temp file beside the target", not [n for n in os.listdir(WORK) if n.endswith(".part")])

print("\nHostile tags")
with pikepdf.open(good) as pdf:
    element = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructElem, S=pikepdf.Name.P))
    element.K = element
    pdf.Root.StructTreeRoot = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.StructTreeRoot, K=element))
    pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
    pdf.save(path("cycle.pdf"))
result = pdfimport.import_pdf(path("cycle.pdf"))
check("a structure tree that points at itself does not hang, and the layout is used",
      "Section 1" in result.body_html and pdfimport.MSG_TAGGED in result.warnings, result.warnings)

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (passed, passed + failed))
sys.exit(1 if failed else 0)
