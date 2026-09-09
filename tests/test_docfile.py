"""The native format, pictures on the way in, and autosave snapshots.

    python tests/test_docfile.py
"""

import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image  # noqa: E402

from easypdf import constants as C  # noqa: E402
from easypdf import docfile, paths  # noqa: E402
from easypdf.htmlclean import normalise  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


FIXTURES = os.path.join(HERE, "tests", "fixtures")
BODY = open(os.path.join(FIXTURES, "sample-body.html"), encoding="utf-8").read()
WORK = tempfile.mkdtemp(prefix="easypdf docfile é ")

print("\nPictures on the way in")
png = docfile.embed_image(os.path.join(FIXTURES, "circle.png"))
check("a PNG stays PNG at its own size, bytes untouched",
      png.mime == "image/png" and (png.width, png.height) == (320, 200) and png.note == ""
      and png.data == open(os.path.join(FIXTURES, "circle.png"), "rb").read())
check("the data URI is a PNG data URI", png.data_uri.startswith("data:image/png;base64,iVBOR"))
check("png_bytes is the same PNG", png.png_bytes() == png.data)
big = os.path.join(WORK, "photo.jpg")
Image.effect_noise((4000, 3000), 60).convert("RGB").save(big, "JPEG", quality=92)
started = time.perf_counter()
jpeg = docfile.embed_image(big)
elapsed = time.perf_counter() - started
print("  the 4,000 by 3,000 JPEG took %.2f seconds" % elapsed)
check("a 4,000 by 3,000 JPEG comes out 2,000 on the long edge",
      (jpeg.width, jpeg.height) == (C.IMAGE_MAX_EDGE, 1500) and jpeg.mime == "image/jpeg")
check("at a fraction of the bytes", jpeg.kilobytes < jpeg.original_kilobytes / 3,
      (jpeg.kilobytes, jpeg.original_kilobytes))
check("and remembers the original size",
      (jpeg.original_width, jpeg.original_height) == (4000, 3000))
check("with the reduced note", jpeg.note == "Reduced from 4,000 by 3,000 to 2,000 by 1,500 pixels.", jpeg.note)
check("bytes work as a source too", docfile.embed_image(png.data).data == png.data)
tall = os.path.join(WORK, "tall.png")
Image.new("RGBA", (300, 2600), (10, 20, 30, 128)).save(tall)
tall_png = docfile.embed_image(tall)
check("a tall PNG is reduced on its long edge and stays PNG with alpha",
      tall_png.height == 2000 and tall_png.width == 231 and tall_png.mime == "image/png"
      and Image.open(__import__("io").BytesIO(tall_png.data)).mode == "RGBA", (tall_png.width, tall_png.height))
gif = os.path.join(WORK, "a.gif")
Image.new("P", (40, 40)).save(gif)
check("a GIF becomes PNG", docfile.embed_image(gif).mime == "image/png")
try:
    docfile.embed_image(os.path.join(FIXTURES, "sample.txt"))
    check("a file that is not a picture raises ValueError", False)
except ValueError as exc:
    check("a file that is not a picture raises ValueError with a sentence", str(exc) == docfile.MSG_NOT_A_PICTURE)

print("\nSave and load")
meta = {"title": "Sample document", "author": "Tony", "lang": "en-US", "subject": "A fixture",
        "page_size": "A4", "margin_inches": 0.75}
epdf = os.path.join(WORK, "doc ü" + C.DOC_EXTENSION)
warnings = docfile.save(epdf, BODY, meta)
text = open(epdf, encoding="utf-8").read()
check("save returns the sanitiser's warnings", warnings == [], warnings)
check("the file is a whole page with the meta in its head",
      text.startswith("<!DOCTYPE html>\n<html lang=\"en-US\">") and "<title>Sample document</title>" in text
      and '<meta name="author" content="Tony">' in text and '<meta name="description" content="A fixture">' in text
      and '<meta name="generator" content="Easy PDF 1.0.0">' in text and '<meta charset="utf-8">' in text)
check("page settings travel in the head",
      '<meta name="easypdf-page-size" content="A4">' in text and '<meta name="easypdf-margin-inches" content="0.75">' in text)
check("it carries a stylesheet and a body", "<style>" in text and "<body>" in text and text.rstrip().endswith("</html>"))
check("every picture is a data URI", "src=\"data:image/png;base64," in text and "circle.png" not in text)
body, meta_back = docfile.load(epdf)
clean_once, _w = normalise(BODY)
check("load returns the same body the save wrote", body == clean_once)
check("and the same meta", meta_back["title"] == "Sample document" and meta_back["author"] == "Tony"
      and meta_back["lang"] == "en-US" and meta_back["subject"] == "A fixture"
      and meta_back["page_size"] == "A4" and meta_back["margin_inches"] == "0.75", meta_back)
check("a native file reports source_kind native and no warnings",
      meta_back["source_kind"] == "native" and meta_back["warnings"] == [])
web = os.path.join(WORK, "page.html")
docfile.save(web, BODY, meta)
check("save as web page writes the same bytes to .html",
      open(web, "rb").read() == open(epdf, "rb").read())
body2, meta2 = docfile.load(web)
check("a web page loads back the same, as kind html", body2 == body and meta2["source_kind"] == "html")
check("saving twice gives the same bytes", (docfile.save(epdf, body, meta), open(epdf, "rb").read())[1]
      == open(web, "rb").read())

print("\nAn interrupted save leaves the previous file intact")
before = open(epdf, "rb").read()
real_replace = os.replace


def refuse(source, target):
    raise OSError("the disk is full")


os.replace = refuse
try:
    docfile.save(epdf, "<p>new text</p>", meta)
    check("the failure is raised", False)
except OSError as exc:
    check("the failure is raised as OSError", "disk is full" in str(exc))
finally:
    os.replace = real_replace
check("the previous file is untouched", open(epdf, "rb").read() == before)
check("no temp file is left beside it", not [n for n in os.listdir(WORK) if n.startswith(".easypdf-")])

print("\nkind_of")
check("extensions", [docfile.kind_of(n) for n in ("a.epdf", "b.HTML", "c.htm", "d.txt", "e.md", "f.markdown", "g.docx", "h.pdf")]
      == ["native", "html", "html", "text", "markdown", "markdown", "docx", "pdf"])
unknown = os.path.join(WORK, "page.unknown")
shutil.copy(web, unknown)
check("an unknown extension is sniffed: html", docfile.kind_of(unknown) == "html")
check("an unknown extension holding text is text", docfile.kind_of(os.path.join(FIXTURES, "sample.rtf")) == "text")

print("\nPlain text")
body, meta_text = docfile.load(os.path.join(FIXTURES, "sample.txt"))
check("blank lines make paragraphs and single newlines join",
      body.replace("\n", "") == "<p>Sample document</p><p>A first paragraph of plain text.</p>"
      "<p>A second paragraph, wrapped across two lines.</p>", body)
check("kind text, no title", meta_text["source_kind"] == "text" and meta_text["title"] == "")
angle = os.path.join(WORK, "angles.txt")
open(angle, "w", encoding="utf-8").write("a <b> & c\n\nsecond")
body, _m = docfile.load(angle)
check("angle brackets and ampersands are escaped", body.replace("\n", "") == "<p>a &lt;b&gt; &amp; c</p><p>second</p>", body)

print("\nLocal pictures on load")
page = os.path.join(WORK, "pics.html")
open(page, "w", encoding="utf-8").write(
    '<html><body><p>a</p><p><img src="circle.png" alt="local"></p>'
    '<p><img src="gone.png" alt="gone"></p><p><img src="https://x.y/z.png" alt="remote"></p></body></html>')
shutil.copy(os.path.join(FIXTURES, "circle.png"), os.path.join(WORK, "circle.png"))
body, meta_pics = docfile.load(page)
check("a local picture that exists is embedded as a data URI",
      'src="data:image/png;base64,' in body and 'alt="local"' in body)
check("with a warning that says it was copied in",
      any("circle.png was copied into the document" in w for w in meta_pics["warnings"]), meta_pics["warnings"])
check("a picture that is gone is dropped with a warning",
      'alt="gone"' not in body and any("gone.png" in w for w in meta_pics["warnings"]))
check("an http picture is dropped with a warning and never fetched",
      'alt="remote"' not in body and any("never fetched" in w for w in meta_pics["warnings"]))
file_uri = os.path.join(WORK, "fileuri.html")
open(file_uri, "w", encoding="utf-8").write(
    '<p><img src="file:///%s" alt="uri"></p>' % os.path.join(WORK, "circle.png").replace("\\", "/"))
body, _m = docfile.load(file_uri)
check("a file:/// source is embedded too", 'src="data:image/png;base64,' in body and 'alt="uri"' in body, body[:80])

print("\nPictures on another computer are never probed")
B = chr(92)
UNC = B + B + "server" + B + "share" + B + "x.png"
FORMS = [UNC, B + B + "?" + B + "UNC" + B + "server" + B + "share" + B + "x.png", "//server/share/x.png",
         "file://server/share/x.png", "file:" + B + B + "server" + B + "share" + B + "x.png",
         "file:////server/share/x.png", "%5C%5Cserver%5Cshare%5Cx.png", "file:///%5C%5Cserver/share/x.png"]
probed = []
real_isfile = os.path.isfile


def recording_isfile(path):
    probed.append(str(path))
    return real_isfile(path)


local_base = "C:" + B + "docs"
os.path.isfile = recording_isfile
try:
    check("every share form returns None from _local_path",
          all(docfile._local_path(f, local_base) is None for f in FORMS),
          [(f, docfile._local_path(f, local_base)) for f in FORMS])
    embed = docfile.embedder_for(local_base)
    check("and the embedder returns None for each", all(embed(f) is None for f in FORMS))
    check("nothing on a share was probed", not [p for p in probed if p.startswith((B + B, "//")) or "server" in p], probed)
finally:
    os.path.isfile = real_isfile
check("a file address for this machine still resolves",
      docfile._local_path("file:///C:/pictures/x.png", local_base) == os.path.normpath("C:/pictures/x.png")
      and docfile._local_path("file://localhost/C:/pictures/x.png", local_base) == os.path.normpath("C:/pictures/x.png"))
check("a relative source resolves beside the document",
      docfile._local_path("pictures/x.png", local_base) == os.path.normpath(os.path.join(local_base, "pictures/x.png")))
share_base = B + B + "nas" + B + "docs"
inside = docfile._local_path("pic.png", share_base)
outside = docfile._local_path(B + B + "other" + B + "share" + B + "x.png", share_base)
climbed = docfile._local_path(".." + B + ".." + B + "escape.png", share_base)
check("a document that lives on a share may use a picture in its own folder",
      inside == os.path.normpath(os.path.join(share_base, "pic.png")), inside)
check("but not one on another share, nor one that climbs out of its folder",
      outside is None and (climbed is None or os.path.normcase(climbed).startswith(os.path.normcase(share_base) + os.sep)),
      (outside, climbed))
share_page = os.path.join(WORK, "share.html")
open(share_page, "w", encoding="utf-8").write('<p><img src="%s" alt="share"></p>' % UNC)
probed = []
os.path.isfile = recording_isfile
try:
    body, meta_share = docfile.load(share_page)
finally:
    os.path.isfile = real_isfile
check("a share picture in a received file is left out with the network share sentence",
      "<img" not in body and any("network share" in w for w in meta_share["warnings"]), meta_share["warnings"])
check("and nothing on a share was probed while opening it", not [p for p in probed if "server" in p], probed)

print("\nA picture too large to open")
real_max = Image.MAX_IMAGE_PIXELS
Image.MAX_IMAGE_PIXELS = 1000
try:
    try:
        docfile.embed_image(os.path.join(FIXTURES, "circle.png"))
        check("a picture over the pixel limit raises ValueError", False)
    except ValueError as exc:
        check("a picture over the pixel limit raises ValueError with the too large sentence",
              str(exc) == docfile.MSG_TOO_LARGE, exc)
    except Exception as exc:
        check("a picture over the pixel limit raises ValueError, not %s" % type(exc).__name__, False, exc)
finally:
    Image.MAX_IMAGE_PIXELS = real_max

print("\nRTF is refused with a sentence")
try:
    docfile.load(os.path.join(FIXTURES, "sample.rtf"))
    check("an .rtf file is refused", False)
except ValueError as exc:
    check("an .rtf file is refused with the WordPad sentence", str(exc) == docfile.MSG_RTF, exc)
disguised = os.path.join(WORK, "disguised.txt")
open(disguised, "w", encoding="utf-8").write("{" + B + "rtf1" + B + "ansi Hello" + B + "par}")
try:
    docfile.load(disguised)
    check("a .txt that starts with the RTF signature is refused too", False)
except ValueError as exc:
    check("a .txt that starts with the RTF signature is refused too", str(exc) == docfile.MSG_RTF)
check("kind_of keeps its six kinds", docfile.kind_of(os.path.join(FIXTURES, "sample.rtf")) == "text")

print("\nPage settings from a received file are checked on the way in")
received = os.path.join(WORK, "received.html")
open(received, "w", encoding="utf-8").write(
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>R</title>'
    '<meta name="easypdf-font-family" content="Arial}</style><script>alert(1)</script><style>">'
    '<meta name="easypdf-page-size" content="huge"><meta name="easypdf-margin-inches" content="1in">'
    '<meta name="easypdf-font-points" content="12"></head><body><p>r</p></body></html>')
_body, meta_received = docfile.load(received)
check("a font family that could close the style element is dropped",
      "font_family" not in meta_received, meta_received.get("font_family"))
check("a page size that is not one of the app's is dropped, and a margin that is not a number",
      "page_size" not in meta_received and "margin_inches" not in meta_received)
check("a font size that is a number is kept", meta_received.get("font_points") == "12")
good_font = os.path.join(WORK, "good-font" + C.DOC_EXTENSION)
docfile.save(good_font, "<p>g</p>", dict(meta, font_family='Georgia, "Times New Roman", serif'))
_body, meta_good = docfile.load(good_font)
check("a font family of letters, commas and quotes round trips",
      meta_good.get("font_family") == 'Georgia, "Times New Roman", serif', meta_good.get("font_family"))

print("\nSnapshots")
real_autosave = paths.autosave_dir
snap_folder = os.path.join(WORK, "autosave")
os.makedirs(snap_folder)
paths.autosave_dir = lambda: snap_folder
try:
    source = os.path.join(WORK, "draft.epdf")
    path = docfile.snapshot("<p>unsaved <b>work</b></p>", {"title": "Draft"}, source)
    check("a snapshot is written into the autosave folder with a sidecar",
          path.startswith(snap_folder) and os.path.isfile(path) and os.path.isfile(path + ".json"))
    check("snapshot_path_for gives the same path", docfile.snapshot_path_for(source) == path)
    found = docfile.recoverable()
    check("recoverable lists it with the source, a datetime and the title",
          len(found) == 1 and found[0][0] == path and found[0][1] == os.path.abspath(source)
          and hasattr(found[0][2], "isoformat") and found[0][3] == "Draft", found)
    body, meta_snap = docfile.load(path)
    check("loading the snapshot sanitises it", body == "<p>unsaved <strong>work</strong></p>" and meta_snap["title"] == "Draft")
    untitled = docfile.snapshot("<p>x</p>", {}, None)
    check("an untitled document gets its own snapshot", untitled != path and len(docfile.recoverable()) == 2)
    docfile.discard_snapshot(path)
    docfile.discard_snapshot(untitled)
    check("discard removes the snapshot and its sidecar", docfile.recoverable() == [] and os.listdir(snap_folder) == [])
    docfile.discard_snapshot(path)
    check("discarding twice is quiet", True)
finally:
    paths.autosave_dir = real_autosave

shutil.rmtree(WORK, ignore_errors=True)
print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
