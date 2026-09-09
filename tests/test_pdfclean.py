"""The one sanitiser: what it maps, what it drops, what it warns about.

Every case from DECISIONS.md edits A7 and A8: b, i, u, font, a div, a span
lang, an img with onerror, an a with a javascript address, an img with an
http source, and the export mode rules. The last section proves this
harness can fail: it runs itself with --prove-fail, where one expectation
is inverted, and asserts the exit code is 1.

    python tests/test_pdfclean.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from easypdf.htmlclean import normalise  # noqa: E402

CHECKS = []
PROVE_FAIL = "--prove-fail" in sys.argv


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


def clean(source, **kw):
    out, warnings = normalise(source, **kw)
    return out.replace("\n", ""), warnings


PNG = "data:image/png;base64,iVBORw0KGgo="

print("\nThe editor's markup becomes the elements the engine tags")
out, warnings = clean('<p>x <b>bold</b> <i>it</i> <u>un</u> <font size="3" color="red">f</font> y</p>')
check("b becomes strong and i becomes em", "<strong>bold</strong>" in out and "<em>it</em>" in out, out)
check("u stays and font is unwrapped", "<u>un</u>" in out and "<font" not in out and " f y" in out, out)
check("no warning for plain mapping", warnings == [], warnings)
out, _w = clean('<p><span style="font-weight: bold">B</span><span style="font-style:italic">I</span>'
                '<span style="text-decoration: underline">U</span>'
                '<span style="text-decoration-line: line-through">S</span><span style="font-weight:700">W</span></p>')
check("style spans fold into strong, em, u and s by rule",
      out == "<p><strong>B</strong><em>I</em><u>U</u><s>S</s><strong>W</strong></p>", out)
out, _w = clean('<div style="text-align: center">centred</div><div>plain</div>')
check("a div with inline content becomes a p, its text-align a class",
      out == '<p class="align-center">centred</p><p>plain</p>', out)
out, _w = clean('<div><p>a</p>bare<p>b</p></div>')
check("a div holding blocks is unwrapped and its bare text gets a p", out == "<p>a</p><p>bare</p><p>b</p>", out)
out, _w = clean('hello <b>world</b><p>para</p>trailing')
check("bare text in the body is wrapped in p", out == "<p>hello <strong>world</strong></p><p>para</p><p>trailing</p>", out)
out, _w = clean('<p></p><p><br></p><p>&nbsp;</p><h2></h2><p>kept<br></p>')
check("empty paragraphs and headings are dropped, a trailing br too", out == "<p>kept</p>", out)
out, _w = clean('<p style="text-align:right" id="x" title="t" contenteditable="true" dir="rtl" class="align-left bogus">t</p>')
check("id, title, contenteditable, dir and unknown classes go; text-align becomes a class",
      out == '<p class="align-left align-right">t</p>' or out == '<p class="align-right">t</p>', out)
out, _w = clean('<p><strike>a</strike><del>b</del><ins>c</ins><tt>d</tt><kbd>e</kbd></p>')
check("strike and del become s, ins becomes u, tt and kbd become code",
      out == "<p><s>a</s><s>b</s><u>c</u><code>d</code><code>e</code></p>", out)
out, _w = clean('<ul><li>a</li><ul><li>nested</li></ul></ul>')
check("execCommand's list inside a list moves into the item before it",
      out == "<ul><li>a<ul><li>nested</li></ul></li></ul>", out)
out, _w = clean('<ul><li>one<br></li><li><br></li></ul>')
check("an empty list item is dropped", out == "<ul><li>one</li></ul>", out)
out, _w = clean('<blockquote>bare quote</blockquote>')
check("bare text in a blockquote gets a p", out == "<blockquote><p>bare quote</p></blockquote>", out)
out, _w = clean('<!DOCTYPE html><html lang="en"><head><title>T</title><style>p{}</style></head><body><p>body</p></body></html>')
check("a whole page loses its head and keeps its body", out == "<p>body</p>", out)
out, _w = clean('<dl><dt>term</dt><dd>definition</dd></dl>')
check("definition lists become paragraphs, text kept", out == "<p>term</p><p>definition</p>", out)
out, _w = clean('<pre>\nline one\n  line two\n</pre>')
check("pre is kept in the file, with its leading newline dropped", out == "<pre>line one\n  line two</pre>".replace("\n", ""), out)

print("\nLanguage marks")
out, warnings = clean('<p><span lang="fr">Bonjour tout le monde</span></p>')
check("a span lang covering the whole block moves onto the block",
      out == '<p lang="fr">Bonjour tout le monde</p>' and warnings == [], (out, warnings))
out, warnings = clean('<p>Say <span lang="fr">bonjour</span> to them</p>')
check("a span lang on a few words is dropped", out == "<p>Say bonjour to them</p>", out)
check("with a warning naming the words", len(warnings) == 1 and '"bonjour"' in warnings[0], warnings)
out, _w = clean('<h3 lang="fr" style="text-align:right">Titre</h3>')
check("lang on a block stays", out == '<h3 class="align-right" lang="fr">Titre</h3>', out)
out, _w = clean('<p lang="not a code">x</p>')
check("a lang that is not a language code is dropped", out == "<p>x</p>", out)

print("\nPictures")
out, warnings = clean('<p><img src="%s"></p>' % PNG)
check("an img with no alt gets alt=\"\" and data-needs-alt in the file",
      out == '<p><img src="%s" alt="" data-needs-alt="1"></p>' % PNG, out)
check("with a warning that a picture has no description yet",
      len(warnings) == 1 and warnings[0].startswith("1 picture has no description yet"), warnings)
out, warnings = clean('<p><img src="%s" alt="x" onerror="alert(1)" width="10" style="width: 50%%"></p>' % PNG)
check("onerror, width and style go; the width becomes a class",
      out == '<p><img src="%s" alt="x" class="width-half"></p>' % PNG, out)
check("and the script warning is given", any("Script" in w for w in warnings), warnings)
out, warnings = clean('<p>a <img src="https://evil.example/x.png" alt="x"> b</p>')
check("an http picture is dropped, never fetched", "<img" not in out and out == "<p>a  b</p>", out)
check("with a warning naming the address", any("evil.example" in w and "never fetched" in w for w in warnings), warnings)
out, warnings = clean('<p><img src="data:image/svg+xml;base64,AAAA" alt="x"></p>')
check("an SVG data picture is dropped with a warning", "<img" not in out and any("svg" in w for w in warnings), warnings)
out, warnings = clean('<p><img src="%s" alt="" role="presentation"> and <img src="%s" alt=""></p>' % (PNG, PNG))
check("alt=\"\" with role presentation is kept as decorative, alt=\"\" alone stays alt=\"\"",
      out == '<p><img src="%s" alt="" role="presentation"> and <img src="%s" alt=""></p>' % (PNG, PNG)
      and warnings == [], (out, warnings))
out, warnings = clean('<p><img src="pictures/local.png" alt="x"></p>', embed=lambda src: PNG if src == "pictures/local.png" else None)
check("a local picture is embedded through the callback", out == '<p><img src="%s" alt="x"></p>' % PNG, out)
check("with a warning that it was copied in", any("copied into the document" in w for w in warnings), warnings)
out, warnings = clean('<p><img src="gone.png" alt="x"></p>', embed=lambda src: None)
check("a local picture that is gone is dropped with a warning",
      "<img" not in out and any("gone.png" in w and "could not be found" in w for w in warnings), warnings)
out, _w = clean('<figure class="width-half place-centre bogus" style="width: 25%%"><img src="%s" alt="A circle"><figcaption>Fig 1</figcaption></figure>' % PNG)
check("figure keeps its own classes only; an inline width wins",
      out == '<figure class="place-centre width-quarter"><img src="%s" alt="A circle"><figcaption>Fig 1</figcaption></figure>' % PNG, out)
out, _w = clean('<figure><figcaption>orphan caption</figcaption></figure>')
check("a figure with no picture keeps its caption as a paragraph", out == "<p>orphan caption</p>", out)

print("\nLinks")
out, warnings = clean('<p><a href="javascript:alert(1)">click</a> <a href="  java\nscript:alert(1)">two</a> '
                      '<a href="https://tgstudios.app/">ok</a> <a href="mailto:a@b.c">m</a> <a href="tel:+1555">t</a> '
                      '<a href="#frag">frag</a> <a href="ftp://x/">f</a></p>')
check("only http, https, mailto and tel links survive; the text always stays",
      out == '<p>click two <a href="https://tgstudios.app/">ok</a> <a href="mailto:a@b.c">m</a> '
             '<a href="tel:+1555">t</a> frag f</p>', out)
check("each dropped link is warned about by its address",
      sum(1 for w in warnings if w.startswith("A link to")) == 4
      and any("javascript:alert(1)" in w for w in warnings), warnings)
check("and the javascript address counts as script", any(w.startswith("Script") for w in warnings))

print("\nHostile markup")
out, warnings = clean('<p onclick="x()">t</p><script>alert(1)</script><style>p{}</style><iframe src="x"></iframe>'
                      '<object></object><textarea><img src=x onerror=alert(1)></textarea><svg onload="x()"></svg><p>after</p>')
check("script, style, iframe, object, textarea and svg vanish with their content", out == "<p>t</p><p>after</p>", out)
check("one script warning", warnings == ["Script in the file was removed. It cannot run inside Easy PDF."], warnings)
out, _w = clean('<p>a &lt;b&gt; &amp; "q" </p>')
check("text is escaped on the way out", out == '<p>a &lt;b&gt; &amp; "q"</p>', out)
out, _w = clean('<p><a href="https://x.y/?a=1&b=2">l</a></p>')
check("attribute values are escaped", out == '<p><a href="https://x.y/?a=1&amp;b=2">l</a></p>', out)

print("\nTables")
out, _w = clean('<table><tr><th>N</th><th>V</th></tr><tr><td>a</td><td>1</td></tr></table>')
check("a header row gets scope col and rows go into a tbody",
      out == '<table><tbody><tr><th scope="col">N</th><th scope="col">V</th></tr><tr><td>a</td><td>1</td></tr></tbody></table>', out)
out, _w = clean('<table><tr><td></td><th>V</th></tr><tr><th>a</th><td>1</td></tr></table>')
check("when the first row is not all headers, first column headers get scope row",
      '<th scope="row">a</th>' in out and '<th scope="col">V</th>' in out, out)
out, _w = clean('<table><caption>Cap</caption><thead><tr><th>a</th></tr></thead><tbody><tr><td colspan="2" rowspan="x">1</td></tr></tbody></table>')
check("caption, thead and tbody are kept, colspan kept, a bad rowspan dropped",
      out == '<table><caption>Cap</caption><thead><tr><th scope="col">a</th></tr></thead><tbody><tr><td colspan="2">1</td></tr></tbody></table>', out)

print("\nExport mode")
out, _w = clean('<pre>\nline one\n  line two\n</pre>', for_export=True)
check("pre becomes a code-block p with br between lines",
      out == '<p class="code-block"><code>line one<br>  line two</code></p>', out)
source = ('<figure><img src="%s" alt="A circle" data-alt-source="ai:openai"><figcaption>Fig 1</figcaption></figure>'
          '<figure><img src="%s" alt="" data-needs-alt="1"></figure>'
          '<p><img src="%s"></p><p><img src="%s" alt="B" data-alt-source="pdf" data-needs-alt="1"></p>' % (PNG, PNG, PNG, PNG))
out, warnings = clean(source, for_export=True)
check("figures are presentational for export, so the picture's Figure and its Caption sit side by side",
      out.startswith('<figure role="presentation"><img src="%s" alt="A circle"><figcaption>Fig 1</figcaption></figure>' % PNG), out)
check("every data attribute is stripped", "data-" not in out, out)
check("a picture still needing a description is written with no alt at all",
      '<figure role="presentation"><img src="%s"></figure><p><img src="%s"></p>' % (PNG, PNG) in out, out)
check("a recovered description keeps its alt", '<p><img src="%s" alt="B"></p>' % PNG in out, out)
check("the AI count, the recovered count and the missing count are each one warning",
      any("2 pictures still need a description" in w for w in warnings)
      and any("1 picture description was written by AI" in w for w in warnings)
      and any("1 picture description was recovered from the original PDF" in w for w in warnings), warnings)
out, warnings = clean("<p>Hello שלום</p>", for_export=True)
check("Hebrew text produces the right to left warning", any("right to left" in w for w in warnings), warnings)
out, warnings = clean("<p>Hello مرحبا</p>", for_export=True)
check("so does Arabic", any("right to left" in w for w in warnings), warnings)
out, warnings = clean("<p>Hello world</p>", for_export=True)
check("and Latin text does not", warnings == [], warnings)
out, _w = clean("<p>Hello world</p>")
check("the same text in file mode gives the same body", out == "<p>Hello world</p>")
out, _w = clean('<p><span lang="fr">Tout</span></p>', for_export=True)
check("the lang hoist works in export mode too", out == '<p lang="fr">Tout</p>', out)

print("\nAddresses and shares")
out, _w = clean('<p><a href="mailto:a@b.com?subject=hello world">m</a> <a href=" https://x.y/path ">s</a></p>')
check("a space inside an address is kept as %20 and the ends are trimmed",
      out == '<p><a href="mailto:a@b.com?subject=hello%20world">m</a> <a href="https://x.y/path">s</a></p>', out)
B = chr(92)
calls = []
out, warnings = clean('<p><img src="%s" alt="s"> <img src="file://server/share/y.png" alt="t"></p>'
                      % (B + B + "server" + B + "share" + B + "x.png"),
                      embed=lambda src: calls.append(src))
check("a picture on a network share is left out before any callback runs", "<img" not in out and calls == [], (out, calls))
check("with the network share sentence, once per picture", sum(1 for w in warnings if "network share" in w) == 2, warnings)

print("\nIdempotence")
sample = open(os.path.join(HERE, "tests", "fixtures", "sample-body.html"), encoding="utf-8").read()
once, _w = normalise(sample)
twice, _w = normalise(once)
check("normalising the fixture twice gives the same bytes", once == twice)
check("the fixture's u became u and its s stayed s", "<u>underlined</u>" in once and "<s>struck</s>" in once)

print("\nThe harness itself can fail")
if PROVE_FAIL:
    check("this expectation is inverted on purpose", "<strong>" not in once)
else:
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--prove-fail"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("run with --prove-fail, this file exits 1 and prints FAIL",
          proc.returncode == 1 and "FAIL this expectation is inverted" in proc.stdout,
          proc.returncode)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
