"""The PDF engine: found, versioned, rendering, and honest when it cannot.

Every candidate engine on the machine renders the fixture and pikepdf
reads a structure tree back from each, so an engine that stopped tagging
is caught here, on the machine it happens on (DECISIONS.md decision 2).

    python tests/test_pdfengine.py
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

from easypdf import pdfengine  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


FIXTURE = os.path.join(HERE, "tests", "fixtures", "sample-body.html")
BODY = open(FIXTURE, encoding="utf-8").read()
PAGE = ('<!DOCTYPE html><html lang="en-US"><head><meta charset="utf-8">'
        "<title>Sample document</title></head><body>" + BODY + "</body></html>")
WORK = tempfile.mkdtemp(prefix="easypdf engine é ")


def tree_kinds(path):
    kinds = set()

    def visit(node):
        if isinstance(node, pikepdf.Array):
            for item in node:
                visit(item)
        elif isinstance(node, pikepdf.Dictionary):
            if "/S" in node:
                kinds.add(str(node.S))
            if "/K" in node:
                visit(node.K)

    with pikepdf.open(path) as pdf:
        root = pdf.Root.get("/StructTreeRoot")
        if root is not None:
            visit(root.get("/K"))
    return kinds


print("\nFinding the engine")
found = pdfengine.engines()
check("at least one engine is found", len(found) >= 1, [e.name for e in found])
check("every candidate has a version, not unknown",
      found and all(re.match(r"^\d+(\.\d+){2,3}$", e.version) for e in found),
      [e.version for e in found])
check("every candidate path exists", found and all(os.path.isfile(e.path) for e in found))
check("the Edge browser comes first when it is installed",
      not found or found[0].name in (pdfengine.EDGE_NAME, pdfengine.RUNTIME_NAME, pdfengine.CHROME_NAME))
check("find_browser returns the first candidate's path",
      pdfengine.find_browser() == (found[0].path if found else None))
ok, sentence = pdfengine.available()
check("available() says what will make the PDF", ok and sentence.endswith("will make the PDF."), sentence)
check("no dash in the sentence", chr(8212) not in sentence and chr(8211) not in sentence)

print("\nRendering the fixture with every candidate")
for engine in found:
    out = os.path.join(WORK, "out ü %s.pdf" % engine.name.split()[-1])
    started = time.perf_counter()
    try:
        used = pdfengine.render_pdf(PAGE, out, engine=engine)
        elapsed = time.perf_counter() - started
        kinds = tree_kinds(out)
        check("%s renders a PDF in %.2f seconds" % (engine.name, elapsed),
              os.path.getsize(out) > 1000 and used is engine)
        check("%s writes a structure tree with headings and paragraphs" % engine.name,
              {"/H1", "/H2", "/P", "/Figure", "/Table", "/Link"} <= kinds, sorted(kinds))
    except pdfengine.EngineError as exc:
        check("%s renders" % engine.name, False, exc)

print("\nThe page carries no header or footer")
if found:
    out = os.path.join(WORK, "flags.pdf")
    pdfengine.render_pdf(PAGE, out)
    with fitz.open(out) as doc:
        text = "\n".join(page.get_text() for page in doc)
    lines = [line.strip() for line in text.splitlines()]
    check("no file path in the text", "file:" not in text and ".html" not in text)
    check("no page number line like 1/2", not any(re.match(r"^\d+/\d+$", line) for line in lines))
    check("no date line", not any(re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", line) for line in lines))
    check("the text is still there", "Sample document" in text and "Quoted text" in text)
    with pikepdf.open(out) as pdf:
        outlines = pdf.Root.get("/Outlines")
        check("headings became bookmarks", outlines is not None and outlines.get("/First") is not None)

print("\nWhen the engine cannot")
if found:
    try:
        pdfengine.render_pdf(PAGE, os.path.join(WORK, "slow.pdf"), timeout=0.01)
        check("a timeout raises EngineError", False)
    except pdfengine.EngineError as exc:
        check("a timeout raises EngineError with a sentence", "stopped" in str(exc), exc)
try:
    pdfengine.render_pdf(PAGE, os.path.join(WORK, "no such folder", "x.pdf"))
    check("a missing folder raises EngineError", False)
except pdfengine.EngineError as exc:
    check("a missing folder raises EngineError naming the folder", "no such folder" in str(exc))
bogus = pdfengine.Engine("Bogus", os.path.join(WORK, "nothere.exe"), "0.0.0")
try:
    pdfengine.render_pdf(PAGE, os.path.join(WORK, "bogus.pdf"), engine=bogus)
    check("an engine that cannot start raises EngineError", False)
except pdfengine.EngineError as exc:
    check("an engine that cannot start raises EngineError", "could not be started" in str(exc))
real_engines = pdfengine.engines
pdfengine.engines = lambda: []
try:
    ok, sentence = pdfengine.available()
    check("with no engine, available() names Edge, the runtime and Chrome",
          not ok and "Microsoft Edge" in sentence and "WebView2" in sentence and "Google Chrome" in sentence)
    try:
        pdfengine.render_pdf(PAGE, os.path.join(WORK, "none.pdf"))
        check("with no engine, render_pdf raises EngineError", False)
    except pdfengine.EngineError as exc:
        check("with no engine, render_pdf raises EngineError with the same sentence",
              str(exc) == pdfengine.MSG_NO_ENGINE)
finally:
    pdfengine.engines = real_engines
leftovers = [n for n in os.listdir(tempfile.gettempdir()) if n.startswith("easypdf-render-")]
check("no render folder is left behind", not leftovers, leftovers)

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
