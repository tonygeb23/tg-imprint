# Brief: Worker A, the PDF pipeline

You own the engine, the export, the checker, the import and the native file
format. Read, in order: `CLAUDE.md`, `docs/ANALYSIS.md`, `docs/DECISIONS.md`,
`docs/PLAN.md` (file ownership and interfaces). If this brief and
`DECISIONS.md` disagree, `DECISIONS.md` wins.

## Files you own

`easypdf/pdfengine.py`, `easypdf/pdfexport.py`, `easypdf/pdfcheck.py`,
`easypdf/pdfimport.py`, `easypdf/docfile.py`, `easypdf/htmlclean.py`,
`easypdf/markdown_in.py`, `easypdf/rtf_in.py`, `tests/test_pdf*.py`,
`tests/test_docfile.py`, `tests/test_import.py`, `docs/PDF-UA.md`.
Fixtures for everyone are in `tests/fixtures/` (`sample-body.html`,
`sample.md`, `sample.txt`, `sample.rtf`, `circle.png`); add to them, do not
rename them.

**Do not delete `easypdf/core/`** even though you are replacing it. The
April window still imports it and the tree must keep running while Worker B
rewrites the UI. The coordinator removes it at integration. Do not edit
anything under `easypdf/ui/`.

## The interfaces (exact names; Worker B is coding against them now)

```python
# pdfengine
find_browser() -> str | None          # path to msedge.exe, else chrome.exe
available() -> (bool, str)             # (ok, one plain sentence)
render_pdf(html_text: str, out_path: str, timeout: float = 90) -> None
class EngineError(Exception)           # message is a sentence a user can act on

# pdfexport
export_html(body_html: str, out_path: str, meta: dict,
            progress: callable | None = None) -> ExportResult
# meta keys: title, author, lang, subject, page_size, margin_inches,
#            font_family, font_points  (defaults from constants for any missing)
# progress(step_text: str) is called from whatever thread runs this; the UI hops.
ExportResult: path, pages, warnings (list of sentences), engine (str)

# pdfcheck
check(path: str) -> Report
Report: results (list of CheckResult(name, passed, detail)), passed, score -> (ok, total),
        format_report() -> str   # plain text, one check per line, PASS/FAIL, no markdown

# pdfimport
import_pdf(path: str, progress=None) -> ImportResult
ImportResult: body_html, meta, images (list of ImportedImage(id, png_bytes, width, height, page)),
              warnings, is_scanned (bool: no text layer)

# docfile
save(path, body_html, meta) -> None            # atomic: temp file, then replace
load(path) -> (body_html, meta)                # dispatches on extension, see below
kind_of(path) -> "native" | "html" | "text" | "markdown" | "rtf" | "pdf"
snapshot(body_html, meta, source_path) -> str  # autosave into paths.autosave_dir()
recoverable() -> list of (snapshot_path, source_path, saved_at, title)
discard_snapshot(snapshot_path) -> None

# htmlclean
normalise(body_html) -> (clean_html, warnings)  # shared by save and export
```

## The engine

Measured on this machine and written in `CLAUDE.md`: `msedge --headless=new
--print-to-pdf` writes a genuinely tagged PDF. Build on that.

- Find the browser through the registry `App Paths` keys for `msedge.exe`
  and `chrome.exe`, then the standard install folders, then `PATH`. Edge
  first. Cache nothing across runs; a browser can be uninstalled.
- Write the HTML to a temp file and pass a `file:///` URI. Paths with
  spaces and non-ASCII characters must work. Use a fresh temporary
  `--user-data-dir` per render so it works while the user's own Edge is open,
  and remove it afterwards. Flags: `--headless=new --disable-gpu
  --no-first-run --no-default-browser-check --no-pdf-header-footer
  --generate-pdf-document-outline` (headings become bookmarks; verify).
  Start the process with `CREATE_NO_WINDOW` so no console flashes. Time out.
- Never fall back to an untagged writer. If there is no browser, `available()`
  says so in a sentence that names Edge and Chrome, and `export_html` raises
  `EngineError` with the same sentence. The UI offers the HTML instead.

## The export

1. `htmlclean.normalise` the editor's HTML: `b` to `strong`, `i` to `em`,
   `strike` to `s`, `div` blocks to `p`, drop empty paragraphs
   (`<p><br></p>`), fold `execCommand` style spans (`font-weight: bold`,
   `font-style: italic`, `text-decoration: underline`) into the semantic
   elements, keep `text-align` and the figure width and placement styles,
   strip `contenteditable`, scripts, event handlers, and ids the editor
   invents. An image with no `alt` attribute gets `alt=""` **and a
   warning**, because a missing description must never silently become
   "decorative". `href` must be http, https, mailto or tel; anything else
   loses the link and gets a warning. Table header cells get
   `scope="col"` (first row) or `scope="row"` (first column when the first
   row is not headers).
2. Wrap it in a full page: `<html lang>` from meta, `<title>`, author meta,
   the print stylesheet (`@page` size and margins from meta, base font,
   heading scale, figure and caption, list spacing, table borders and header
   shading, link colour with underline, blockquote rule, code font). Use the
   fonts a Windows machine has: Arial, Calibri fallback, Consolas for code.
3. Render through the engine.
4. pikepdf patch: `/MarkInfo /Marked true`, `/Lang`, `/ViewerPreferences
   /DisplayDocTitle true`, Info `Title Author Subject Creator Producer`, XMP
   `dc:title`, `dc:creator`, `dc:description`, `dc:language`,
   `pdfuaid:part = 1`, `xmp:CreatorTool = "Easy PDF <version>"`,
   `pdf:Producer = "Easy PDF <version> (Chromium)"`. Never the byte-level
   patch the prototype had; it corrupts the cross reference table.
5. Return the result with warnings. Nothing prints to stdout.

## The checker

Every check is a `CheckResult` with a plain sentence in `detail` that says
what to do. Checks, each independent: tagged (`/MarkInfo`), structure tree
present, language set, DisplayDocTitle, title present (Info or XMP), XMP
PDF/UA identifier, **every Figure has non-empty Alt** (count them), heading
levels do not skip (H1 then H3 is a fail, with the heading text named),
every font embedded (walk page resources and form XObjects), `/Tabs /S` on
pages that carry annotations, link annotations have a `StructParent`,
outline present (warn only), text layer present (a scanned PDF fails with
"this PDF is pictures of text"). Say clearly in `format_report` that a
full PDF/UA verdict needs PAC or veraPDF and this is the checks that can be
made from here. The checker must **fail** a PDF you deliberately break
(strip `/MarkInfo`, remove an Alt) and **pass** the app's own export of
`tests/fixtures/sample-body.html`; both are tests.

## The import

PyMuPDF is installed (1.27). `import_pdf` turns a PDF into editor HTML:
text blocks in reading order, headings by ranking the font sizes that
appear (largest distinct sizes above the body size become h1, h2, h3; bold
at body size with a short line is h4), paragraphs joined across lines (and
across pages when a sentence continues), hyphenation at a line end joined,
bullets and numbering recognised into `ul`/`ol`, images extracted as PNG
and placed at their position as
`<figure><img src="data:image/png;base64,..." alt="" data-needs-alt="1"></figure>`
so the UI can list the pictures that need a description, links from the
page's link annotations kept as `<a href>`, metadata (title, author, lang)
carried into `meta`. If a page has no text at all, set `is_scanned` and
warn: there is no OCR in this release. Skip images smaller than 24 pixels
on a side (bullets and rules). Report progress per page.

## The native format and the other readers

- **Native:** UTF-8 HTML, self-contained. `<!DOCTYPE html>`, `<html
  lang>`, `<meta charset>`, `<title>`, `<meta name="author">`, `<meta
  name="description">` for the subject, `<meta name="generator"
  content="Easy PDF 1.0.0">`, a small stylesheet so it looks right in a
  browser, then the body. Every image is a data URI; if the body still
  holds a `file:` or local path `src`, embed it on save and warn if the
  file is gone. Save is atomic.
- **Load** dispatches on extension: native and any HTML (take the body,
  normalise); `.txt` (blank-line paragraphs, single newlines joined,
  `&<>` escaped); `.md` (your own converter, no dependency: headings,
  paragraphs, bold, italic, code spans and fenced blocks, links, images
  (embed a local file that exists), nested bullet and numbered lists,
  blockquotes, rules, pipe tables with a header row); `.rtf` (a small group
  parser: control words, `\par`, `\'hh` and `\uN` escapes, `\b`/`\i`
  toggles into `strong`/`em`, everything else dropped); `.pdf` through
  `import_pdf`. Anything imported returns `meta["source_kind"]` so the UI
  can say "opened from Markdown; Save will write Easy PDF's own format".

## Tests, hand-rolled, one file each, `python tests/<file>.py`

Each prints ok/FAIL per check and exits non-zero on any failure. Cover:
the engine is found and renders the fixture; the export's structure tree
holds H1, H2, H3, P, Strong, Em, Link with OBJR, L/LI, BlockQuote, Figure
with the exact Alt, Table/TR/TH/TD; the decorative figure is absent from the
tree; every font embedded; XMP carries `pdfuaid:part` 1 and `dc:title`;
Info carries the app as Creator; the checker passes that file and fails the
broken one; import of the exported fixture recovers the headings and the
text in order and one picture needing a description; Markdown, text and
RTF fixtures convert to the expected HTML; save then load returns the same
body and meta; a save interrupted (simulate by making replace fail) leaves
the previous file intact; snapshot and recover round trip; `normalise`
turns `<b>` into `<strong>` and warns on a missing alt. Prove at least one
test can fail by breaking the input on purpose inside the test.

## Rules that bind you

- No em or en dashes anywhere, including strings and comments.
- Every user-visible sentence you add (warnings, check details, error
  messages) goes into `docs/STRINGS.md` under your heading.
- Nothing here touches wx or the UI thread; nothing prints.
- Measure, do not infer: read the PDF back with pikepdf in your tests.
- Write `docs/PDF-UA.md`: what the export guarantees, what the checker
  checks, what it cannot, and how to verify a file in PAC.

## Report back with

What you built, the test files and the count of checks passing, the
measured export time on the fixture, every warning sentence you wrote,
anything you need from Worker B or the coordinator, and anything you left
out and why.
