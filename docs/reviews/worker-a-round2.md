# Worker A, round 2 review: the PDF pipeline

Overseer, 2026-09-09. Scope: `easypdf/htmlclean.py`, `pdfengine.py`,
`pdfexport.py`, `pdfcheck.py`, `pdfimport.py`, `docfile.py`,
`markdown_in.py`, `docx_in.py`, `docs/PDF-UA.md`, the Worker A section of
`docs/STRINGS.md`, and the six test files. Checked against `CLAUDE.md`,
`docs/briefs/worker-a.md` and `docs/DECISIONS.md` (edits A1 to A9,
decisions 2 and 3, risks 3, 5, 6, 8, 10 and 19).

No project file was modified. Scratch output is under
`%LOCALAPPDATA%\Temp\claude\...\scratchpad\overseer-a2`.

## Verdict

Fix these and re-review. Four must-fix defects (1 to 4). The rest can go
in the same pass or the next.

## Test counts I measured

Run from the project root, `python tests/<file>.py`, one at a time:

- `test_pdfclean.py`: 58 of 58.
- `test_pdfengine.py`: 24 of 24.
- `test_pdfexport.py`: 73 of 73.
- `test_pdfcheck.py`: 43 of 43.
- `test_docfile.py`: 43 of 43.
- `test_import.py`: 45 of 45.
- `python tests/test_pdfclean.py --prove-fail` prints one FAIL line,
  reports 57 of 58, and exits 1. So the harness can fail.

## The one measurement

Exported `tests/fixtures/sample-body.html` through
`pdfexport.export_html` into a scratch folder whose path holds a space
and an e acute, then read the file back with pikepdf:

- 1.42 seconds, 2 pages, engine "Microsoft Edge 152.0.4191.66",
  `pdfua_claimed` True, no warnings.
- Tree: Document, H1, H2, H3, P, Strong, Em, Code, Link, L with LI and
  Lbl, BlockQuote, Figure, Caption, Table with TR, TH and TD. 74 elements.
- One Figure, Alt "A yellow circle on a blue background". Two image
  XObjects drawn on the pages, one Figure in the tree: the decorative
  picture is absent.
- The Caption is a sibling of the Figure under Document, not a child.
- XMP `pdfuaid:part` is "1", `dc:title` is the title. The raw bytes hold
  "pdfuaid" three times.
- Info Producer and XMP pdf:Producer are both "Easy PDF 1.0.0 (Microsoft
  Edge 152.0.4191.66)"; Creator and CreatorTool are "Easy PDF 1.0.0".
  Read after the final save, so pikepdf did not stamp itself.
- MarkInfo Marked, Lang en-US, DisplayDocTitle, Outlines present.
- The page text holds no temp path, no "file:", no "document.html".
- Importing that PDF back recovers the described figure's text as
  `data-alt-source="pdf"` and returns the decorative one as needing a
  description; the headings come back in order.
- A copy with MarkInfo stripped and the Alt removed fails "Tagged PDF" and
  "Pictures described".

Then a body with three pictures: one in a figure with a caption and
`alt="" data-needs-alt="1"`, one with no alt attribute, one with a bare
`alt=""`:

- `pdfua_claimed` False. The warnings say two pictures still need a
  description and that the identifier was left out because "Pictures
  described" did not pass.
- The file holds no "pdfuaid" bytes at all.
- Two Figures without Alt in the tree; the bare `alt=""` picture is
  absent; three image XObjects drawn.
- The sanitiser's file-mode output for that body is idempotent.

## Defects

### Must fix

1. `easypdf/pdfexport.py` lines 161 and 168 to 173. `font_family` from
   meta is interpolated into the `<style>` block of the print page with no
   escaping or validation. `docfile.split_page` (lines 360 to 363) carries
   `<meta name="easypdf-font-family">` from any opened `.epdf` or `.html`
   into `meta["font_family"]`, and the window passes meta to the export.
   So a received file can put
   `Arial}</style><script>...</script><style>` into the page the engine
   prints, and the print page has no Content Security Policy. That is a
   bypass of the one sanitiser. Confirmed by running: `settings_from` then
   `build_page` with that string puts `</style><p>INJECTED</p>` into the
   page verbatim, and `split_page` returns the string from the meta. Not
   rendered through the engine. Right: `settings_from` keeps only letters,
   digits, spaces, commas, quotes and hyphens in the font family and falls
   back to `constants.DEFAULT_FONT_FAMILY` when anything else is present;
   the same rule for the `easypdf-*` values on the way in; and
   `build_page` adds a Content Security Policy meta (default-src none,
   img-src data, style-src unsafe-inline) so nothing but the inline
   stylesheet and data images can ever load in the print page. Add a test
   that feeds the injection string and asserts it is not in the page.

2. `easypdf/pdfexport.py` lines 311 to 334, and `MSG_NO_CLAIM` at lines
   66 and 67. When the engine's own output has no structure tree, the
   export still moves the file into place and returns a result. Confirmed
   by running: with `pdfengine.render_pdf` replaced by a function that
   writes a PyMuPDF page with text and no tags, `export_html` returned
   `pdfua_claimed` False, left the file on disk, and the warning read
   "The PDF/UA identifier was left out because these checks did not pass:
   Structure tree, Fonts embedded, All text tagged. The PDF is still
   tagged." That last sentence is false in exactly the case it matters.
   `CLAUDE.md`: never ship an untagged PDF; decision 2: never an untagged
   PDF stands. Right: after `pdfcheck.check`, if the "tagged" or "tree"
   result failed, remove the work file and raise `EngineError` with a
   sentence for `docs/STRINGS.md` (draft: "The PDF engine wrote a PDF
   without tags, so nothing was saved. Save as web page keeps everything.
   Try the export again, and if it happens every time, update Microsoft
   Edge."), so the UI takes the same path as no engine. With that in
   front of it, "The PDF is still tagged" in `MSG_NO_CLAIM` becomes
   always true and can stay. Add a test with the fake engine.

3. `easypdf/docfile.py` lines 158 to 173 (`_local_path`) and 176 to 187
   (`embedder_for`). A UNC image source is accepted and probed with
   `os.path.isfile`, which opens an SMB connection to the named host with
   the user's credentials the moment a received file is opened. Confirmed
   at the function level: a source of two backslashes, server, share,
   x.png comes back unchanged with `isabs` True; the `\\?\UNC\` form
   likewise; and `file:` followed by that UNC path becomes a rooted path
   that is still UNC. The network call itself was not exercised.
   `file://host/...` forms happen to be defused (they turn into
   `C:/host/...`), which is luck, not design. `CLAUDE.md`: nothing leaves
   the machine without consent; risk 3: remote pictures are never
   fetched. Right: after the `file:` prefix is handled, return None for
   any path that starts with two separators of either kind or with
   `\\?\`, and for a `file://` whose host is not empty or "localhost";
   the sanitiser then gives its "left out because the file could not be
   found or read" warning, or a dedicated sentence (draft: "A picture on
   a network share was left out. Copy it to this computer and insert
   it."). Add a function-level test.

4. `easypdf/pdfexport.py` line 210 (`pikepdf.open(source)` in
   `patch_pdf`) and lines 263 to 271 (`write_identifier`). When the
   engine writes a file that begins with the PDF header but is not a
   readable PDF, `pikepdf.PdfError` escapes `export_html` untouched.
   Confirmed by running: the exception text was the temp path of
   `rendered.pdf` followed by "unable to find trailer dictionary while
   recovering damaged file". The brief says `EngineError` is the one
   exception a caller should expect and its message is a sentence; this
   one is a temp path and library words. Right: wrap the pikepdf work in
   `patch_pdf` and `write_identifier`, raise
   `EngineError(pdfengine.MSG_NOT_PDF)` (already in STRINGS.md) or a new
   sentence, and add a test with a fake engine that writes the header
   followed by junk.

### Should fix

5. `easypdf/pdfexport.py` lines 325 to 330. The previous PDF at
   `out_path` is deleted with `os.remove` before `shutil.move` brings the
   new one in. If the move fails (disk full, a cross-volume copy
   interrupted, antivirus holding the new file) the user's earlier PDF is
   gone and nothing replaces it. The native save is atomic; the export
   should be too. Suspected from reading. Right: copy the work file to a
   temporary name in the destination folder, then `os.replace` it over
   `out_path`; a `PermissionError` from the replace is the "open in
   another program" case.

6. `easypdf/pdfimport.py` lines 422 to 425 and 167 to 187. The recovered
   description match compares the count of Figure Alt strings on a page
   with the count of every image drawn on that page, including images the
   producing app marked as artifacts. A decorative picture on the same
   page as a described one always breaks the count, so nothing is
   recovered and the mismatch warning fires. The fixture passes only
   because its two pictures land on different pages (measured: picture-1
   on page 1, picture-2 on page 2). Meets the letter of edit A6, so this
   is a weakness, not a breach. Suspected from reading. Right:
   `pdfcheck.TextIndex._walk` already knows the marked content stack when
   it meets `Do` (lines 458 to 469); count images drawn inside an
   Artifact separately, and match the Alt strings against the images that
   are not artifacts.

7. `easypdf/pdfengine.py` lines 293 to 298 and 251 to 258. On a timeout
   `subprocess.run` kills msedge.exe only; its renderer, GPU and crashpad
   children can outlive it holding the profile folder. `_remove_tree`
   retries for about nine seconds, then gives up silently, leaving an
   `easypdf-render-*` folder in TEMP and possibly orphaned processes. The
   test's 0.01 second timeout passes because the children had not started
   yet. Suspected from reading, not measured. Right: on timeout, kill the
   process tree (`taskkill /T /F /PID`, or a Job Object with kill on
   close) before removing the folder.

8. `easypdf/docfile.py` lines 109 to 112 (`embed_image`). Only
   `UnidentifiedImageError`, `OSError` and `ValueError` are turned into
   the "not a picture" sentence. Pillow raises
   `Image.DecompressionBombError` (an `Exception`, not one of those) for a
   picture over about 178 million pixels, so a hostile local picture, docx
   or PDF crashes the load instead of being refused. Suspected from
   reading. Right: catch `Exception` there and raise `ValueError` with a
   sentence (draft: "That picture is too large to open."), listed in
   STRINGS.md.

9. `easypdf/docfile.py` lines 52 to 55 and 279 to 295, with
   `tests/test_docfile.py` line 129 asserting it. An `.rtf` file is
   opened as plain text, so the user gets paragraphs of RTF control words
   with no explanation. Decision 3 dropped RTF and says "anything real
   opens in WordPad and saves as .docx or .txt"; the app should say that.
   Right: `load` refuses `.rtf` with a sentence for STRINGS.md (draft:
   "Easy PDF cannot open RTF. Open it in WordPad, save it as a Word
   document or plain text, and open that."), and the test asserts the
   refusal.

### Low

10. `easypdf/htmlclean.py` line 426 (`_valid_href`). Every whitespace
    character is stripped from the address, not only the leading and
    trailing ones, so `mailto:a@b.com?subject=hello world` becomes
    `...=helloworld`. Confirmed by running. Right: strip the ends and drop
    control characters; keep or percent-encode interior spaces.

11. `easypdf/pdfcheck.py` line 414. `tag = last("name")` takes the last
    name operand before `BDC`, so the property-list form `/Artifact /P1
    BDC` is read as tagged content rather than an artifact. Chromium
    writes inline dictionaries, so the app's own files are unaffected; a
    PDF from elsewhere could have artifact text counted as content. Right:
    the tag is the first name operand, the property the last. Suspected
    from reading.

12. `easypdf/pdfexport.py` lines 329 and 330. A `PermissionError` from a
    read-only destination folder gets the "open in another program"
    sentence. Right: a sentence that covers both (draft: "The PDF could
    not be written to <path>. Check that the folder allows writing and
    that the file is not open in another program."). Suspected from
    reading.

13. `docs/PDF-UA.md` line 51 cites "Matterhorn 28-011" for the link
    Contents. I did not verify the checkpoint number, and it is quoted
    nowhere public yet. Right: cite the clause, PDF/UA-1 7.18.1, or verify
    the number against the Matterhorn Protocol before it is repeated in
    the site copy.

## The interfaces

Every name in the interfaces block of edit A2 is present with the stated
shape: `engines`, `find_browser`, `available`, `render_pdf`,
`EngineError`, `export_html` and `ExportResult` with `pdfua_claimed`,
`check`, `Report` with `pdfua_gate` and `format_report`, `import_pdf` with
`ImportedImage(id, png_bytes, width, height, page, alt, alt_source)`,
`save`, `load`, `kind_of` with the six kinds, `snapshot`, `recoverable`,
`discard_snapshot`, `embed_image` with every `EmbeddedImage` field, and
`normalise(body_html, for_export=False)`.

The additions are acceptable, and the coordinator should record them in
`docs/PLAN.md` and `docs/DECISIONS.md` so Worker B can rely on them:

- `normalise(..., embed=None)`: keeps file reading out of the sanitiser,
  which the brief demands ("nothing here reads a file"). Accept.
- `ExportResult.report`: the checker's Report on the final file, so the
  UI does not parse every content stream a second time. Accept.
- `render_pdf(..., engine=None)` returning the `Engine` used; `save`
  returning the sanitiser's warnings; `Report.pages`, `Report.producer`,
  `Report.warnings`, `Report.failed_names()`; `CheckResult.warn_only`,
  `key`, `word`; `ImportResult.meta["pages"]` and `["tagged"]`; `load`
  meta carrying `warnings`, `is_scanned` and `images`. All additive.

Checked and clean: no `wx` import, no `print`, no `sys.stdout`, no
logging in the eight modules (grep); no em or en dash in any Worker A
file (`tools/nodashes.py` and my own scan, zero hits); every sentence in
the eight modules is in the Worker A section of `docs/STRINGS.md`
(compared one by one, including every checker detail and its plural).

## Ruling on the alt design

The resolution is right. Accept it, with one condition.

- Why: edit A4 said an image with no alt gets `alt=""` plus a warning,
  and edit A8 said such a picture must export as a Figure without Alt.
  Worker A measured that `alt=""` makes Chromium drop the picture from
  the tree, and I measured the same today (the bare `alt=""` picture is
  absent; three drawn, two in the tree). Both edits cannot hold at once.
  A8 is the one that matters: the PDF must tell the truth that a picture
  is there and undescribed, not the lie that it is decorative. So in the
  file the picture is `alt="" data-needs-alt="1"` with the warning (valid
  HTML, and the Pictures dialog can list it), and at export it is written
  with no alt attribute so the engine makes a Figure without Alt, the
  checker fails "Pictures described" by name, and the identifier is
  withheld. Measured today end to end. A picture with `alt=""` and
  `role="presentation"` is the artifact; that is what the decorative box
  writes.
- Condition: the coordinator amends DECISIONS edit A4 to say this, so
  the brief and the code agree, and writes the contract where Worker B
  reads it: the editor never writes a bare `alt=""` for a picture that
  merely lacks a description; the decorative box writes `alt=""` with
  `role="presentation"`; an empty description without the box is
  `alt="" data-needs-alt="1"`. A bare `alt=""` means decorative on
  purpose (it is what HTML means, and what pasted web pages carry), and
  the sanitiser passes it through without a warning by design.

The figure with `role="presentation"` is also right for 1.0.0 and for
the PDF/UA-1 claim.

- Why: a plain `<figure>` becomes an outer Figure without Alt wrapping
  the picture's Figure (Worker A's measurement; the shape I measured with
  the role in place is consistent with it: Figure and Caption side by
  side under Document). The outer Figure would fail the app's own check
  and Matterhorn 13-004 in PAC, so a plain `<figure>` is out. With the
  role, every Figure carries its Alt and the caption is still a Caption
  element. I know of no PDF/UA-1 checkpoint that requires a Caption to be
  inside the element it describes. The alternatives are worse: an
  `aria-label` on the figure would put the description on the outer
  Figure as well, so a screen reader hears it twice; dropping `<figure>`
  loses the Caption element altogether.
- Condition: the PAC and veraPDF run at Round 4 looks at the Caption
  beside its Figure specifically. If either flags it, the fallback is to
  write the picture in a `p` and the caption as the `p` after it, and
  `docs/PDF-UA.md` says which shape shipped. PDF 2.0's containment rules
  (Annex L) may be stricter, and they are not what `pdfuaid:part` 1
  claims.

## What is right

- The pipeline is the one decision 2 asked for: sanitise, wrap, print
  through Edge, the runtime or Chrome in that order, patch with pikepdf,
  check, gate the identifier, one move into place. Measured end to end.
- The sanitiser is an allow list re-serialised from a tree, so nothing
  survives that was not put back on purpose: `script`, `on*` handlers,
  `javascript:` and `data:` addresses, non-image data sources and remote
  sources all go, each with a warning, and the output is idempotent.
- The checker fails the broken file by name and passes the fixture with
  the identifier written; its report is plain text with the PAC and
  veraPDF sentence at the end; the content stream tokenizer counts BMC as
  well as BDC and names a skipped heading by its words.
- Producer and Creator are read back after the final save and pikepdf is
  not in them.
- Every user-visible sentence is in STRINGS.md. No dashes. Nothing prints
  and nothing touches wx.
- `docs/PDF-UA.md` is accurate against the code, including the five
  picture states and the engine's known gaps.

## For the coordinator and Worker B

- Amend DECISIONS edits A4 and A8 with the alt resolution above, and put
  the decorative contract (bare `alt=""` versus `role="presentation"`
  versus `data-needs-alt="1"`) in Worker B's brief at the Insert picture
  dialog.
- Record the interface additions listed above in PLAN.md.
- Round 4 audit list: Caption beside Figure in PAC and veraPDF; the
  "first heading is not H1" rule (the checker fails it; confirm PAC
  agrees before the site copy says the checker matches PAC).

## What the re-review checks

Run the six files again, then the four new tests: the injection string
never reaches the print page (1); a fake untagged engine makes
`export_html` raise `EngineError` and leave no file (2); the UNC forms
return None from `_local_path` (3); a fake engine writing the PDF header
followed by junk raises `EngineError` with a sentence and no temp path
(4). Then read the diffs for 5 to 13.
