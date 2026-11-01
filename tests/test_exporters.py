"""Word, Markdown and text out, and the document check.

    python tests/test_exporters.py
"""
import base64
import io
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from docx import Document  # noqa: E402
from PIL import Image  # noqa: E402

from tgimprint import doccheck, exporters  # noqa: E402

WORK = tempfile.mkdtemp(prefix="tgimprint-export-test-")
passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  ok   %s" % name)
    else:
        failed += 1
        print("  FAIL %s  %s" % (name, detail))


buffer = io.BytesIO()
Image.new("CMYK", (40, 40), (0, 80, 80, 0)).save(buffer, "JPEG")
PICTURE = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
BODY = ('<h1>Report</h1><p>Some <strong>bold</strong>, <em>italic</em> and '
        '<a href="https://example.com/">a link</a>.</p><h2>Items</h2>'
        '<ul><li>One<ul><li>Nested</li></ul></li><li>Two</li></ul><ol><li>First</li></ol>'
        '<table><caption>Costs</caption><thead><tr><th>Item</th><th>Cost</th></tr></thead>'
        '<tbody><tr><td>Tea</td><td>2</td></tr></tbody></table>'
        '<blockquote><p>Quoted</p></blockquote>'
        '<figure><img src="%s" alt="A red square"><figcaption>Figure one</figcaption></figure>' % PICTURE)
META = {"title": "Report", "author": "Audit", "lang": "es", "subject": "Tests"}

print("Word")
path = os.path.join(WORK, "out.docx")
exporters.export_docx(BODY, path, META)
document = Document(path)
styles = [p.style.name for p in document.paragraphs]
check("real heading styles", "Heading 1" in styles and "Heading 2" in styles, styles)
check("real list styles", "List Bullet" in styles and "List Bullet 2" in styles
      and "List Number" in styles, styles)
check("a quote style", "Quote" in styles)
check("the title and language are in the properties",
      document.core_properties.title == "Report" and document.core_properties.language == "es")
xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
check("the picture carries its description", 'descr="A red square"' in xml)
check("the link is a real hyperlink", "<w:hyperlink" in xml)
check("the table's first row repeats as a header", "w:tblHeader" in xml)
check("bold survives", "<w:b/>" in xml)
check("a CMYK picture from print does not stop the export", zipfile.ZipFile(path).namelist()
      and any(n.startswith("word/media/") for n in zipfile.ZipFile(path).namelist()))

print("\nMarkdown")
text = exporters.to_markdown(BODY, META)
check("headings", "# Report" in text and "## Items" in text)
check("inline", "**bold**" in text and "*italic*" in text and "[a link](https://example.com/)" in text, text)
check("a nested list", "- One\n    - Nested" in text, text)
check("a table with a rule", "| Item | Cost |\n| --- | --- |\n| Tea | 2 |" in text, text)
check("a quote", "> Quoted" in text)
check("the description, not the picture data", "Picture: A red square" in text and "base64" not in text)
check("a control character cannot stop a Word file",
      exporters.build_docx("<p>Words\x01\x08 here</p>", {}) is not None)
check("a title with no level 1 heading is kept", exporters.to_text("<p>Words</p>", {"title": "Mine"}).startswith("Mine"))
check("a picture with no description is still mentioned", "no description" in exporters.to_text(
    '<figure><img src="%s" alt="" data-needs-alt="1"></figure>' % PICTURE, {}))

print("\nPlain text")
text = exporters.to_text(BODY, META)
check("no markup", "<" not in text and "**" not in text, text)
check("a list reads as a list", "* One\n  * Nested" in text, text)
check("the description is there", "Picture: A red square" in text)
check("table rows stay on a line", "Tea    2" in text, text)

for kind, name in (("md", "out.md"), ("txt", "out.txt")):
    target = os.path.join(WORK, name)
    exporters.KINDS[kind](BODY, target, META)
    check("%s writes a file" % kind, os.path.getsize(target) > 20)

print("\nThe document check")
keys = [i.key for i in doccheck.check(BODY, META)]
check("a sound document has nothing to fix",
      not [i for i in doccheck.check(BODY, META) if i.severity == "fix"], keys)
issues = doccheck.check("<h2>Start</h2><h4>Deep</h4><p><img src='x' alt='' data-needs-alt='1'></p>"
                        "<p><a href='http://a'>click here</a> <a href='http://b'>http://b.example</a></p>"
                        "<table><tr><td>A</td></tr></table>", {})
keys = {i.key: i for i in issues}
for key in ("title", "lang", "first_heading", "heading_skip", "picture", "link_vague",
            "link_address", "table_header", "table_caption"):
    check("finds %s" % key, key in keys, sorted(keys))
check("a heading issue says which heading", keys["heading_skip"].kind == "heading"
      and keys["heading_skip"].ordinal == 2, keys["heading_skip"])
check("a picture issue says which picture", keys["picture"].ordinal == 1)
check("a table issue says which table", keys["table_header"].ordinal == 1)
check("review is not fix", keys["link_vague"].severity == "review"
      and keys["picture"].severity == "fix")
issues = doccheck.check('<p><img src="x" alt="Words" data-alt-source="ai:openai"></p>', {"title": "t", "lang": "en"})
check("an AI description wants checking", [i.key for i in issues] == ["ai_picture"], issues)
issues = doccheck.check('<p><img src="x" alt="" role="presentation"></p>', {"title": "t", "lang": "en"})
check("a decorative picture is not a fault", not issues, issues)
check("an empty document does not crash", isinstance(doccheck.check("", {}), list))
check("bad markup does not crash", isinstance(doccheck.check("<h1><p></a></table", {}), list))
check("capitals are noticed", any(i.key == "caps" for i in doccheck.check(
    "<p>%s</p>" % ("THIS IS ALL WRITTEN IN CAPITALS FOR NO GOOD REASON AT ALL " * 2), {"title": "t", "lang": "en"})))

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (passed, passed + failed))
sys.exit(1 if failed else 0)
