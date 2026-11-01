"""The real gate: veraPDF over the app's own exports.

    python tools/verify_ua.py [--keep folder]

pdfcheck is what ships. veraPDF is what decides whether pdfcheck is telling
the truth: 0.2.1 passed its own sixteen checks and failed veraPDF on every
export. So every document below goes through the real pipeline and then
through the PDF/UA-1 profile, and anything that claimed the identifier and
fails is a release blocker.

veraPDF is a build tool here, never shipped: GPL or MPL, needs Java. It
lives at %LOCALAPPDATA%\\TG Studios Build\\verapdf. This reports "skipped"
rather than a failure it cannot stand behind when it is missing, and the
release pipeline treats skipped as not done.
"""
import base64
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

from tgimprint import pdfexport  # noqa: E402

VERA = os.path.join(os.environ.get("LOCALAPPDATA", ""), "TG Studios Build", "verapdf", "verapdf.bat")
META = {"title": "Conformance document", "author": "TG Imprint", "lang": "en-US", "subject": "A test"}


def picture(colour="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (200, 120), colour).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


FIXTURE = open(os.path.join(HERE, "tests", "fixtures", "sample-body.html"), encoding="utf-8").read()
LONG = "".join("<h2>Part %d</h2><p>%s</p><ul><li>One</li><li>Two <strong>bold</strong></li></ul>"
               % (n, "A sentence with <em>emphasis</em> and more words. " * 40) for n in range(1, 30))
DOCUMENTS = {
    "fixture": FIXTURE,
    "plain": "<h1>Title</h1><p>Words.</p>",
    "headings": "".join("<h%d>Level %d</h%d><p>Text.</p>" % (n, n, n) for n in range(1, 7)),
    "nested lists": "<h1>Lists</h1><ul><li>One<ul><li>Two<ol><li>Three</li></ol></li></ul></li></ul>",
    "table": ("<h1>Table</h1><table><caption>Costs</caption><thead><tr><th>Item</th><th>Cost</th></tr></thead>"
              "<tbody><tr><th>Tea</th><td>2</td></tr><tr><th>Bread</th><td>3</td></tr></tbody></table>"),
    "spanned table": ('<h1>Table</h1><table><tr><th colspan="2">Wide</th></tr><tr><td>A</td><td>B</td></tr></table>'),
    "pictures": ('<h1>Pictures</h1><figure><img src="%s" alt="A red box"><figcaption>One</figcaption></figure>'
                 '<p><img src="%s" alt="" role="presentation"></p><p><img src="%s" alt="A blue box"></p>'
                 % (picture(), picture("green"), picture("blue"))),
    "links": ('<h1>Links</h1><p><a href="https://example.com/">One</a> and '
              '<a href="mailto:a@example.com">two</a>.</p>'),
    "quote and code": "<h1>Quote</h1><blockquote><p>Words.</p></blockquote><pre>code\n  more</pre><hr><p>After.</p>",
    "long": "<h1>Long</h1>" + LONG,
    "spanish": "<h1>Título</h1><p>El niño comió piña.</p>",
}


def verdict(path):
    output = subprocess.run([VERA, "-f", "ua1", "--format", "xml", path], capture_output=True,
                            text=True, shell=True, timeout=300).stdout
    compliant = re.search(r'isCompliant="(\w+)"', output)
    rules = re.findall(r'clause="([^"]+)"[^>]*testNumber="(\d+)"[^>]*status="failed"', output)
    return (compliant.group(1) == "true" if compliant else None), rules


def main():
    if not os.path.isfile(VERA):
        print("skipped: veraPDF is not at %s" % VERA)
        return 2
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    work = keep or tempfile.mkdtemp(prefix="tgimprint-ua-")
    os.makedirs(work, exist_ok=True)
    bad = 0
    try:
        for name, body in DOCUMENTS.items():
            path = os.path.join(work, name.replace(" ", "-") + ".pdf")
            result = pdfexport.export_html(body, path, META)
            compliant, rules = verdict(path)
            if result.pdfua_claimed and compliant:
                print("  ok   %s: claimed, and veraPDF agrees" % name)
            else:
                bad += 1
                print("  FAIL %s: claimed %s, veraPDF %s %s %s"
                      % (name, result.pdfua_claimed, compliant, rules, result.report.failed_names()))
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)
    print("%d/%d documents pass PDF/UA-1" % (len(DOCUMENTS) - bad, len(DOCUMENTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
