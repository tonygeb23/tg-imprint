# PDF/UA in Easy PDF

What the export guarantees, what the checker can prove, what it cannot,
why the PDF/UA identifier is gated, the sanitiser's allow list, the known
gaps in the engine, what is not in 1.0.0, and how to verify a file in PAC
or veraPDF. Everything marked "measured" was measured on this machine on
2026-09-09 with Edge 152, the WebView2 runtime 152.0.4191.66, Chrome 152,
pikepdf 10.5.1 and PyMuPDF 1.27.2; the numbers are in `CHALLENGE.md` (E1
to E9), `DECISIONS.md` ("What I measured myself") and the tests under
`tests/`.

No em dashes or en dashes anywhere in this file. Tony's rule.

## The pipeline in one paragraph

The editor's HTML goes through the one sanitiser (`htmlclean.normalise`,
export mode), is wrapped in a page with the print stylesheet, is printed
by a Chromium browser running headless (`pdfengine`: the Edge browser,
else the WebView2 runtime's own msedge.exe, else Chrome), is patched with
pikepdf (`pdfexport`: MarkInfo, Lang, DisplayDocTitle, the Info
dictionary, the XMP, a description on every link annotation), is checked
(`pdfcheck.check`), and gets the PDF/UA-1 identifier only if every check
passes. The user always gets a tagged PDF; what varies is whether it
carries the claim, and the report says why. If the engine's own output
turns out to have no MarkInfo or no structure tree (an engine update that
stopped tagging), the export stops with a sentence and nothing is saved,
because an accessibility product that quietly produces an inaccessible
file is worse than one that refuses (`CLAUDE.md`). The same happens when
the engine writes something pikepdf cannot read back.

## What the export guarantees

Measured by reading the app's own export of `tests/fixtures/sample-body.html`
back with pikepdf (`tests/test_pdfexport.py`):

- A structure tree with Document, H1 to H6, P, Strong, Em, Code, Link
  (with an OBJR to the annotation), L with LI and Lbl, BlockQuote, Figure
  with Alt, Caption, Table with TR, TH (Scope Column or Row) and TD (with
  Headers). Text runs sit in NonStruct wrappers, which validators accept.
- `/MarkInfo /Marked true`, `/Lang` from the document language,
  `/ViewerPreferences /DisplayDocTitle true`, `/Tabs /S` on every page.
- Every font subset embedded (Type0, Identity, with ToUnicode). The
  stylesheet uses Arial with Calibri and Helvetica as fallbacks, and
  Consolas for code, so the fonts exist on every Windows machine.
- Info Title, Author, Subject; Creator "Easy PDF 1.0.0"; Producer
  "Easy PDF 1.0.0 (Microsoft Edge 152.0.4191.66)", the engine's name and
  version, so a bad engine batch can be traced. pikepdf never stamps
  itself: the metadata is opened with `set_pikepdf_as_editor=False`, and
  the test asserts the strings after the final save (CHALLENGE.md E9).
- XMP dc:title, dc:creator, dc:description, dc:language,
  xmp:CreatorTool, pdf:Producer, and pdfuaid:part 1 when the gate passes,
  in the namespace `http://www.aiim.org/pdfua/ns/id/`.
- Every link annotation carries the link's text as `/Contents`, decoded
  from the content stream through the font's ToUnicode map, so a screen
  reader that reads the annotation rather than the tagged text says the
  words (ISO 14289-1, PDF/UA-1, clause 7.18.1, which asks every
  annotation for a Contents entry; the Matterhorn checkpoint number is
  not cited here until it has been checked against the protocol).
- Headings become bookmarks (`--generate-pdf-document-outline`).
- No header or footer: the default Chromium page furniture (date, title,
  the temp file path, page numbers) is switched off with
  `--no-pdf-header-footer`, and a test reads the page text to prove it.
- A picture marked decorative (`alt=""` with `role="presentation"`, or
  `alt=""` on its own) is an artifact: absent from the tree. Measured.
- A picture with a description is a Figure with that exact Alt. A
  `<figure>` with a `<figcaption>` is written with `role="presentation"`,
  so the tree holds the picture's Figure and its Caption side by side
  rather than a Figure with no Alt wrapped round both (measured: a plain
  figure element becomes exactly that outer Figure, which PAC and this
  checker would fail).
- The print page loads nothing but its own inline stylesheet and data
  pictures. It carries a Content Security Policy (default-src none,
  img-src data, style-src unsafe-inline), and the font family from the
  document's properties is letters, digits, spaces, commas, quotes and
  hyphens or it falls back to the default, both on the way into a
  document from a received file and on the way into the print page. A
  received `.epdf` cannot put script or markup into the page the engine
  prints.
- The finished PDF is copied beside its destination and swapped in with
  one replace, so a full disk, an interrupted copy or a file held open in
  another program leaves the earlier PDF at that path untouched, and the
  export says which.

## The identifier is gated

`pdfuaid:part` is a claim, and the app writes it only when its own checks
cannot find a fault (`Report.pdfua_gate`: every check except the
identifier check itself passed; warn-only checks count as passed). When
the gate is closed the PDF is still exported, still tagged, without the
identifier, and the export's warnings name the check that closed it:

- a picture without a description (Matterhorn 07-001);
- a skipped heading level, or a first heading that is not level 1
  (Matterhorn 14-003);
- no title, or a title in Info but not in XMP;
- no document language, or one that is not a language code;
- a link annotation outside the tree, or without a description;
- a font that is not embedded;
- a page with links and no tab order;
- text outside any tag;
- no text at all.

A picture that still needs a description is deliberately written into the
PDF with no alt attribute at all, so the engine makes a Figure without Alt
and the checker can see it. Turning it into an artifact would hide the
picture from blind readers silently, which is the one thing this product
must never do (`CLAUDE.md`). In the native file the same picture carries
`alt=""` and `data-needs-alt="1"`, so the Pictures dialog lists it.

## What the checker checks

`pdfcheck.check(path)` reads the file with pikepdf and parses every
content stream (counting BMC as well as BDC, the CHALLENGE.md E6 lesson).
Sixteen checks, each independent, each with a sentence that says what to
do; the report is plain text, one line per check, PASS, FAIL or WARN.

| Check | What it reads |
|---|---|
| Tagged PDF | `/MarkInfo /Marked` |
| Structure tree | `/StructTreeRoot` with at least one element |
| Language | `/Lang` on the catalogue, and that it is a language code |
| Title shown in the window | `/ViewerPreferences /DisplayDocTitle` |
| Title | XMP `dc:title` (Info `/Title` alone is named as not enough) |
| PDF/UA identifier | XMP `pdfuaid:part` equal to 1 |
| Pictures described | every Figure has a non-empty `/Alt` or `/ActualText`; counts them |
| Heading levels | H1 to H6 in document order never deepen by more than one; the offending heading is named by its text |
| Fonts embedded | every font in page resources and form XObjects has a FontFile; Type 3 counts as embedded; names the ones that are not |
| Tab order | every page with annotations has `/Tabs /S` |
| Links tagged | every Link annotation has a `/StructParent` |
| Links described | every Link annotation has a non-empty `/Contents` |
| Bookmarks | an outline with at least one entry (warn only) |
| Text layer | text operators show something on some page; a PDF of pictures fails with "this PDF is pictures of text" |
| All text tagged | no text operator runs outside any marked content (only reported when there is text) |
| List items | every LI has an LBody (warn only: the engine writes none, PAC may warn) |

A file that is not a PDF, is missing, or needs a password gives one failed
"File readable" result and nothing else.

## What the checker cannot check

Nothing a program can prove from the file:

- whether a description is true, useful, or the right length;
- whether a heading is really a heading, or a table really a table;
- whether the reading order makes sense to a person;
- colour contrast, since the text is black on white by the stylesheet
  but pictures are whatever they are;
- whether the document language is the language the text is in;
- whether an inline language change was lost (the sanitiser warns about
  the ones it dropped, but nothing in the PDF records them);
- anything PAC or veraPDF check that is not in the table above. A full
  PDF/UA verdict needs one of them, and every report says so in its last
  line.

## The allow list

The one sanitiser, `htmlclean.normalise`, runs on load, paste, import,
save and export. The same table is in the module's docstring.

- Kept: h1 to h6, p, ul, ol, li, blockquote, strong, em, u, s, code, sup,
  sub, br, hr, a, img, figure, figcaption, table, caption, thead, tbody,
  tfoot, tr, th, td, and pre in the file (a code-block p for export).
- Mapped: b to strong, i to em, strike and del to s, ins to u, tt, kbd,
  samp and var to code, dt and dd to p; div, section, article, center and
  the other containers become a p when they hold inline content and are
  unwrapped when they hold blocks; font and span are unwrapped after
  their styles are folded into strong, em, u and s (any bold weight, any
  italic style, underline, line-through: by rule, never by matching the
  exact markup execCommand writes today).
- Dropped with their content: script, style, template, iframe, object,
  embed, applet, frame, frameset, noscript, noembed, noframes, xmp,
  plaintext, svg, math, form, input, button, select, textarea, option,
  datalist, link, meta, base, head, title, video, audio, canvas, map,
  area.
- Attributes kept: href on a (http, https, mailto, tel only; anything
  else loses the link, keeps its text and gets a warning), src on img
  (data: PNG, JPEG, GIF, WebP or BMP only; a local file is embedded
  through `docfile.embed_image` with a warning, a missing one is dropped
  with a warning, an http one is never fetched and is dropped with a
  warning), alt, role="presentation" on an img with alt="", lang on
  block elements (a span lang covering all of its block's text moves onto
  the block; any other inline lang is dropped with a warning naming the
  words, because Chromium writes no Span element), scope on th, colspan
  and rowspan, class from the app's own set (align-left, align-center,
  align-right, align-justify, width-quarter, width-half,
  width-three-quarters, width-full, place-left, place-centre,
  place-right, code-block), and data-needs-alt and data-alt-source on
  img. Everything else is dropped: every on* attribute, id, style (after
  the text-align and span folding), title, contenteditable, spellcheck,
  dir, width and height.
- Structure repairs: bare text gets a p; empty paragraphs, headings and
  list items are dropped; a list written straight inside a list (what
  execCommand's indent does) moves into the item before it; th in the
  first row gets scope="col" and th in the first column of later rows
  gets scope="row".
- Export mode adds: every data-* attribute stripped after the AI written
  and the recovered descriptions are counted into one warning each; a
  picture still needing a description written with no alt; pre turned
  into `<p class="code-block"><code>` with br between lines (Chromium
  tags pre as nothing, measured); figure given role="presentation"; one
  warning if Arabic or Hebrew script is present.

## Pictures, the five states

| In the file | Meaning | In the PDF |
|---|---|---|
| `alt="A yellow circle"` | described | Figure with that Alt |
| `alt="" role="presentation"`, or `alt=""` alone | decorative on purpose | absent (an artifact) |
| `alt="" data-needs-alt="1"`, or no alt attribute | still needs a description | Figure with no Alt; the check fails; no identifier |
| `alt="..." data-alt-source="ai:openai"` | written by AI, unchecked | Figure with the Alt; counted in one export warning |
| `alt="..." data-alt-source="pdf" data-needs-alt="1"` | recovered from the original PDF's tags, unchecked | Figure with the Alt; counted in one export warning; listed in Pictures |

A picture's source is a data URI once it is in the document. On the way
in, a local file is embedded with a warning that says so, a web address
is never fetched, and a source on another computer (a UNC path with
either separator, the device path form, or a file address that names a
host other than this one) is refused before anything probes it, because
a probe opens a connection to that host with the user's credentials the
moment the file is opened. The one exception is a document that itself
lives on a share: a picture inside its own folder is on a host the user
already reached. The rule is applied after percent decoding as well, so
an encoded path cannot slip past it.

## Known gaps in the engine

Measured, and not fixable from here:

- No LBody: a list item is Lbl plus a NonStruct with the text. PAC may
  warn. The checker names it as a warning only; the veraPDF run at the
  audit decides whether it matters.
- NonStruct wrappers around every text run.
- Inline language changes are lost: `span lang` becomes nothing. A
  paragraph's lang is kept, so the sanitiser hoists a whole-paragraph
  span and drops the rest with a warning.
- u, s, sup, sub, br and abbr are tagged as nothing (their text is kept,
  as plain text inside the paragraph).
- hr becomes a NonStruct with drawn content rather than an artifact.
- A plain `<figure>` element becomes a Figure with no Alt around the
  picture's own Figure; the export avoids it with role="presentation".
- Arabic text comes out of the PDF's text layer with letters in the wrong
  order (E7): the ToUnicode map gives base letters, not the visual
  forms. Right to left is out of 1.0.0 and warned about at export.
- Chromium does not downsample pictures (E8); Easy PDF downscales on the
  way in instead (2,000 pixels on the long edge, over 300 dots per inch
  on a letter page's text width).

## Import, what it recovers and what it guesses

`pdfimport.import_pdf` reads the text layer with PyMuPDF. Headings are
guessed from font sizes (the largest distinct sizes above the body size
become h1, h2 and h3; a short bold line at body size becomes h4), lines
are joined into paragraphs with hyphenation healed and sentences carried
across pages, bullets are recognised from marker characters and from a
small filled shape drawn beside an indented line (which is how Chromium
draws a bullet: it is not in the text), numbers from "1." and "a)"
patterns, links from the page's link annotations, pictures extracted and
downscaled and placed where they sat, and the title, author and language
carried into meta.

When the PDF is tagged, pikepdf reads the tree first, the import warns
that the structure is re-created from the layout, and each page's Figure
Alt strings are attached to that page's pictures only when the counts
match, marked `data-alt-source="pdf"` and `data-needs-alt="1"` so
Pictures lists them as recovered and to be checked. Only the pictures
drawn inside tagged content (marked content with an MCID) are counted:
a picture drawn inside an Artifact, or outside any marked content at
all, which is how Chromium draws a decorative picture (measured), is not
in the tree and cannot be the one a Figure describes, so a decorative
picture on the same page never breaks the match for the described one
beside it. A wrong description presented as fact is worse than none, so
a mismatch attaches nothing and warns.

A page with no text is a scanned page. When every page is, `is_scanned`
is set and the warning says there is no text recognition in this
release.

## Not in 1.0.0

- Right to left languages: warned about, not claimed.
- OCR: a scanned PDF cannot be made readable here; the importer says so.
- Tree aware import: a tagged PDF's headings, lists and tables are
  re-guessed from the layout. The checker's content stream decoder
  (`pdfcheck.TextIndex`, text per marked content id) is the piece a later
  release would build it on.
- LBody: not written by the engine; warned about only.
- veraPDF in the build, and PAC: by hand, at the audit, if Tony approves
  the downloads.

## Verifying a file in PAC or veraPDF

PAC 2024 (PDF Accessibility Checker, free, Windows, from the PDF/UA
Foundation): open the exported PDF, read the summary. Expect the
structure checks to pass; expect at most warnings about LBody on list
items. Anything else it reports is a rule for the checker: name it in
the report and add it to `pdfcheck`.

veraPDF (free, needs Java, which is on this machine): install the GUI or
the command line, choose the profile PDF/UA-1, run it on the exported
fixtures in `tests/fixtures` after `python tests/test_pdfexport.py` has
produced them (it writes to a temp folder; export any document from the
app to keep one). The report lists failed rules by clause number; every
failure becomes a named checker rule.

Neither tool can judge whether a description is true. That is what the
Pictures dialog and a sighted reviewer are for.
