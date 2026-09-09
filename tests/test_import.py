"""The readers: Markdown, plain text, Word and PDF into editor HTML.

The docx is built here with python-docx, so it is code rather than a
binary fixture. The PDF is the app's own export of the fixture, imported
back: headings and text in order, one picture needing a description, the
described figure's text recovered from the tags.

    python tests/test_import.py
"""

import base64
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fitz  # noqa: E402
import pikepdf  # noqa: E402
from docx import Document  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches  # noqa: E402

from easypdf import docfile, docx_in, markdown_in, pdfexport, pdfimport  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    """Details here can be whole bodies full of data URIs, so they are
    printed only on failure, and cut down."""
    CHECKS.append(bool(condition))
    shown = ""
    if not condition and detail != "":
        shown = "  " + __import__("re").sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "DATA", str(detail))[:600]
    print(("  ok   " if condition else "  FAIL ") + label + shown)


FIXTURES = os.path.join(HERE, "tests", "fixtures")
WORK = tempfile.mkdtemp(prefix="easypdf import é ")
DATA = "data:image/png;base64,"


def flat(body):
    return body.replace("\n", "")


print("\nMarkdown")
raw = markdown_in.to_html(open(os.path.join(FIXTURES, "sample.md"), encoding="utf-8").read())
check("markdown-it renders headings, emphasis, code, links, lists, a quote, a picture and a table",
      all(tag in raw for tag in ("<h1>", "<strong>", "<em>", "<code>", "<a href=", "<ul>", "<ol>", "<blockquote>", "<img", "<table>")))
check("raw HTML in Markdown is escaped, not parsed",
      "&lt;script&gt;" in markdown_in.to_html("<script>x</script> text"))
body, meta = docfile.load(os.path.join(FIXTURES, "sample.md"))
text = flat(body)
check("the title comes from the first heading", meta["title"] == "Sample document" and meta["source_kind"] == "markdown")
check("h1, h2 and h3 in order", text.index("<h1>Sample document</h1>") < text.index("<h2>Lists</h2>")
      < text.index("<h2>A quotation</h2>") < text.index("<h3>A picture with a description</h3>") < text.index("<h2>A table</h2>"))
check("bold, italic, code and the link",
      "<strong>bold</strong>" in text and "<em>italic</em>" in text and "<code>code</code>" in text
      and '<a href="https://tgstudios.app/">a link to TG Studios</a>' in text)
check("bullets and numbers", "<ul><li>First bullet</li><li>Second bullet with <strong>bold</strong></li></ul>" in text
      and "<ol><li>Step one</li><li>Step two</li></ol>" in text, text)
check("the quotation", "<blockquote><p>Quoted text, set apart.</p></blockquote>" in text)
check("the picture is embedded from beside the file with its description",
      '<img src="%s' % DATA in text and 'alt="A yellow circle on a blue background"' in text)
check("with the copied in warning", any("circle.png was copied" in w for w in meta["warnings"]), meta["warnings"])
check("the table has a header row with scope col",
      '<thead><tr><th scope="col">Name</th><th scope="col">Value</th></tr></thead>' in text
      and "<tr><td>Alpha</td><td>1</td></tr>" in text, text)
md_path = os.path.join(WORK, "nested.md")
open(md_path, "w", encoding="utf-8").write("- a\n  - b\n    1. c\n- d\n\n```\ncode block\n```\n\n---\n\n~~gone~~\n")
body, _meta = docfile.load(md_path)
text = flat(body)
check("nested lists, a fenced block, a rule and strikethrough",
      "<ul><li>a<ul><li>b<ol><li>c</li></ol></li></ul></li><li>d</li></ul>" in text
      and "<pre>code block</pre>" in text and "<hr>" in text and "<s>gone</s>" in text, text)

print("\nPlain text")
body, meta = docfile.load(os.path.join(FIXTURES, "sample.txt"))
check("three paragraphs, the wrapped one joined",
      flat(body) == "<p>Sample document</p><p>A first paragraph of plain text.</p><p>A second paragraph, wrapped across two lines.</p>")

print("\nWord")
doc = Document()
doc.add_heading("Docx title", 0)
doc.add_heading("First heading", 1)
doc.add_heading("Second level", 2)
paragraph = doc.add_paragraph("A paragraph with a ")
run = paragraph.add_run("bold run")
run.bold = True
paragraph.add_run(" and an ")
run = paragraph.add_run("italic run")
run.italic = True
run = paragraph.add_run(" and underlined")
run.underline = True
run = paragraph.add_run(" and struck")
run.font.strike = True
paragraph.add_run(".")
link_paragraph = doc.add_paragraph("Visit ")
rid = doc.part.relate_to("https://tgstudios.app/",
                         "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                         is_external=True)
hyperlink = OxmlElement("w:hyperlink")
hyperlink.set(qn("r:id"), rid)
link_run = OxmlElement("w:r")
link_text = OxmlElement("w:t")
link_text.text = "TG Studios"
link_run.append(link_text)
hyperlink.append(link_run)
link_paragraph._p.append(hyperlink)
doc.add_paragraph("bullet one", style="List Bullet")
doc.add_paragraph("bullet two", style="List Bullet")
doc.add_paragraph("nested bullet", style="List Bullet 2")
doc.add_paragraph("number one", style="List Number")
doc.add_paragraph("number two", style="List Number")
doc.add_picture(os.path.join(FIXTURES, "circle.png"), width=Inches(2))
doc.paragraphs[-1]._p.xpath(".//wp:docPr")[0].set("descr", "A yellow circle on a blue background")
doc.add_picture(os.path.join(FIXTURES, "circle.png"), width=Inches(1))
table = doc.add_table(rows=2, cols=2)
table.cell(0, 0).text = "Name"
table.cell(0, 1).text = "Value"
table.cell(1, 0).text = "Alpha"
table.cell(1, 1).text = "1"
centred = doc.add_paragraph("Centred")
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
centred.alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.core_properties.title = "Core title"
doc.core_properties.author = "Tony"
doc.core_properties.language = "en-GB"
docx_path = os.path.join(WORK, "sample é.docx")
doc.save(docx_path)
started = time.perf_counter()
body, meta = docfile.load(docx_path)
elapsed = time.perf_counter() - started
print("  the Word file took %.2f seconds" % elapsed)
text = flat(body)
check("Title and Heading styles become h1 and h2",
      text.startswith("<h1>Docx title</h1><h1>First heading</h1><h2>Second level</h2>"), text[:120])
check("bold, italic, underline and strike runs",
      "<strong>bold run</strong>" in text and "<em>italic run</em>" in text
      and "<u> and underlined</u>" in text and "<s> and struck</s>" in text, text)
check("the hyperlink", '<a href="https://tgstudios.app/">TG Studios</a>' in text, text)
check("bullets with the nested level, then numbers",
      "<ul><li>bullet one</li><li>bullet two<ul><li>nested bullet</li></ul></li></ul>" in text
      and "<ol><li>number one</li><li>number two</li></ol>" in text, text)
check("the picture with Word's description as alt, embedded",
      '<figure><img src="%s' % DATA in text and 'alt="A yellow circle on a blue background">' in text)
check("the picture without a description needs one", 'alt="" data-needs-alt="1"' in text)
check("the table with the first row as column headers",
      '<table><tbody><tr><th scope="col">Name</th><th scope="col">Value</th></tr><tr><td>Alpha</td><td>1</td></tr></tbody></table>' in text, text)
check("a centred paragraph keeps its alignment as a class", '<p class="align-center">Centred</p>' in text)
check("core properties into meta", meta["title"] == "Core title" and meta["author"] == "Tony"
      and meta["lang"] == "en-GB" and meta["source_kind"] == "docx", meta)
check("one warning: the picture with no description",
      meta["warnings"] == ["1 picture has no description yet. Pictures lists every picture that still needs one."],
      meta["warnings"])

tracked = Document()
tracked.add_paragraph("Before ")
ins = OxmlElement("w:ins")
ins.set(qn("w:id"), "1")
ins.set(qn("w:author"), "x")
ins_run = OxmlElement("w:r")
ins_text = OxmlElement("w:t")
ins_text.text = "inserted"
ins_run.append(ins_text)
ins.append(ins_run)
tracked.paragraphs[0]._p.append(ins)
tracked.sections[0].header.paragraphs[0].text = "A running header"
tracked_path = os.path.join(WORK, "tracked.docx")
tracked.save(tracked_path)
_body, meta = docfile.load(tracked_path)
check("tracked changes are warned about", docx_in.MSG_TRACKED in meta["warnings"], meta["warnings"])
check("a header with text is warned about", docx_in.MSG_HEADERS in meta["warnings"])
try:
    docx_in.read(os.path.join(FIXTURES, "sample.txt"))
    check("a file that is not a Word document raises ValueError", False)
except ValueError as exc:
    check("a file that is not a Word document raises ValueError with a sentence", str(exc) == docx_in.MSG_NOT_WORD)

print("\nA PDF, the app's own export imported back")
fixture = open(os.path.join(FIXTURES, "sample-body.html"), encoding="utf-8").read()
pdf_path = os.path.join(WORK, "export.pdf")
pdfexport.export_html(fixture, pdf_path, {"title": "Sample document", "author": "Tony Gebhard", "lang": "en-US"})
steps = []
started = time.perf_counter()
result = pdfimport.import_pdf(pdf_path, progress=steps.append)
elapsed = time.perf_counter() - started
print("  the import took %.2f seconds" % elapsed)
text = flat(result.body_html)
check("progress was reported per page", steps == ["Reading page 1 of 2", "Reading page 2 of 2"], steps)
check("not scanned", result.is_scanned is False)
headings = [(m.group(1), m.group(2)) for m in __import__("re").finditer(r"<h(\d)>(.*?)</h\d>", text)]
check("the headings come back at their levels, in order", headings == [
    ("1", "Sample document"), ("2", "Lists"), ("2", "A quotation"), ("3", "A picture with a description"),
    ("3", "A decorative picture"), ("2", "A table")], headings)
check("the text is in order", text.index("A paragraph with") < text.index("First bullet") < text.index("Step one")
      < text.index("Quoted text") < text.index("Centred paragraph") < text.index("Right aligned"))
check("bold, italic and code inside the paragraph",
      "<strong>bold</strong>" in text and "<em>italic</em>" in text and "<code>code</code>" in text, text)
check("the link is kept from the annotation", '<a href="https://tgstudios.app/">a link to TG Studios</a>' in text, text)
check("bullets are recognised from the drawn marker and numbers from the text",
      "<ul><li>First bullet</li><li>Second bullet with <strong>bold</strong></li></ul>" in text
      and "<ol><li>Step one</li><li>Step two</li></ol>" in text, text)
check("two pictures came out, each as a figure needing a description", len(result.images) == 2
      and text.count('data-needs-alt="1"') == 2)
first = result.images[0]
check("the described figure's text is recovered from the tags and marked pdf",
      first.alt == "A yellow circle on a blue background" and first.alt_source == "pdf"
      and 'alt="A yellow circle on a blue background" data-alt-source="pdf" data-needs-alt="1"' in text)
check("the decorative picture, absent from the tags, has no description",
      result.images[1].alt == "" and result.images[1].alt_source == "")
check("images carry an id, PNG bytes, size and a 1-based page",
      first.id == "picture-1" and first.png_bytes.startswith(b"\x89PNG") and (first.width, first.height) == (320, 200)
      and first.page == 1 and result.images[1].page == 2)
check("the ids follow the order of the img elements in the body",
      [i.id for i in result.images] == ["picture-1", "picture-2"])
check("meta carries the title, author, language and kind", result.meta["title"] == "Sample document"
      and result.meta["author"] == "Tony Gebhard" and result.meta["lang"] == "en-US"
      and result.meta["source_kind"] == "pdf" and result.meta["pages"] == 2, result.meta)
check("a tagged PDF is warned about, and the recovered description too",
      result.warnings[0] == pdfimport.MSG_TAGGED and any("recovered from the PDF's tags" in w for w in result.warnings),
      result.warnings)
check("the table's cells are in the text", "Alpha" in text and "Beta" in text)
body, meta = docfile.load(pdf_path)
check("through docfile.load the body is sanitised and the images travel in meta",
      meta["source_kind"] == "pdf" and len(meta["images"]) == 2 and 'data-alt-source="pdf"' in body
      and meta["is_scanned"] is False)

print("\nA decorative picture beside a described one on the same page")
circle = DATA + base64.b64encode(open(os.path.join(FIXTURES, "circle.png"), "rb").read()).decode("ascii")
same = ('<h1>Two pictures</h1><figure><img src="%s" alt="A described circle"><figcaption>Figure 1.</figcaption></figure>'
        '<p>Between them.</p><p><img src="%s" alt="" role="presentation"></p><p>After both.</p>' % (circle, circle))
same_pdf = os.path.join(WORK, "same-page.pdf")
pdfexport.export_html(same, same_pdf, {"title": "Two pictures", "lang": "en-US"})
result = pdfimport.import_pdf(same_pdf)
check("both pictures are on page 1", [i.page for i in result.images] == [1, 1], [i.page for i in result.images])
check("the described picture's text is recovered even with a decorative picture on the same page",
      result.images and result.images[0].alt == "A described circle" and result.images[0].alt_source == "pdf",
      [(i.alt, i.alt_source) for i in result.images])
check("the decorative picture gets no description",
      len(result.images) == 2 and result.images[1].alt == "" and result.images[1].alt_source == "")
check("and no mismatch warning", not any("could not be matched" in w for w in result.warnings), result.warnings)

print("\nA scanned PDF and files that cannot be opened")
scanned = os.path.join(WORK, "scanned.pdf")
with fitz.open() as doc:
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 400, 300), filename=os.path.join(FIXTURES, "circle.png"))
    doc.save(scanned)
result = pdfimport.import_pdf(scanned)
check("a PDF of pictures is scanned, with the warning and the picture kept",
      result.is_scanned and result.warnings == [pdfimport.MSG_SCANNED] and len(result.images) == 1, result.warnings)
locked = os.path.join(WORK, "locked.pdf")
with pikepdf.open(pdf_path) as pdf:
    pdf.save(locked, encryption=pikepdf.Encryption(owner="o", user="u"))
try:
    pdfimport.import_pdf(locked)
    check("a password protected PDF raises PdfImportError", False)
except pdfimport.PdfImportError as exc:
    check("a password protected PDF raises PdfImportError with the password sentence", str(exc) == pdfimport.MSG_PASSWORD)
try:
    pdfimport.import_pdf(os.path.join(FIXTURES, "sample.txt"))
    check("a file that is not a PDF raises PdfImportError", False)
except pdfimport.PdfImportError as exc:
    check("a file that is not a PDF raises PdfImportError", True, exc)

print("\nHyphenation and paragraphs across lines")
long_body = "<p>" + ("A sentence that runs on and on with many words so that it wraps across several lines, " * 6) + "end.</p>"
long_pdf = os.path.join(WORK, "long.pdf")
pdfexport.export_html(long_body, long_pdf, {"title": "Long", "lang": "en-US"})
result = pdfimport.import_pdf(long_pdf)
check("a wrapped paragraph comes back as one paragraph",
      flat(result.body_html).count("<p>") == 1 and "end." in result.body_html, result.body_html[:100])

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
