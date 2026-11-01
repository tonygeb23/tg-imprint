# TG Imprint research docket, 2026-11-01

Web research only, about 25 searches and 2 page fetches. No code was edited.
Rule used throughout: a claim has a URL. A line marked UNVERIFIED is my own
knowledge or a secondary source and needs checking before anyone relies on it.
Searches returned a lot of vendor and university pages; primary texts (ISO,
Federal Register, Matterhorn PDF) were mostly not reached. Said so where it matters.

## 1. PDF/UA-1, PDF/UA-2, WTPDF, Matterhorn

- PDF/UA-1 (ISO 14289-1, 2014) targets PDF 1.7. PDF/UA-2 (ISO 14289-2, 2024) targets PDF 2.0. WTPDF and PDF/UA-2 both require PDF 2.0, so a 1.7 file must be upgraded first. https://www.axes4.com/en/blog/post/2024/pdf-ua-2-vs-well-tagged-pdf
- WTPDF is a free PDF Association spec with two levels, Reuse and Accessibility. The Accessibility level has the same normative requirements as PDF/UA-2, so a file meeting it may also be marked PDF/UA-2. https://pdfa.org/WTPDF
- UA-2 over UA-1: rules for PDF 2.0 structure types, annotations, math (MathML), associated files, document fragments, and skipped heading levels. https://pdfa.org/tagged-pdf-q-a/
- UA-2 is a paid ISO standard; WTPDF is free to read. Same source as above (axes4).
- Matterhorn Protocol 1.1: 31 checkpoints, 136 failure conditions, each marked M (machine) or H (human). Counts disagree between sources: 89 machine / 45 human / 2 undetermined, or 89 / 47. I could not reach the primary PDF to settle it. https://www.pdflib.com/pdf-knowledge-base/pdfua/matterhorn-protocol and https://taggedpdfschool.pdfa.org/matterhorn
- Machine examples named by sources: image without alt or replacement text, XMP without a title. Human examples: heading text not tagged as a heading, a visual list not tagged as a list. https://www.powermapper.com/products/sortsite/rules/accmatterhorn/
- Matterhorn is a UA-1 document. No Matterhorn-style published list for UA-2 turned up. UNVERIFIED that none exists.
- Most commonly hit machine-checkable failures in real PDFs (UNVERIFIED as a ranked list; compiled from the checkpoint names and our own pdfcheck table, no frequency study found):
  1. Not tagged / MarkInfo missing (checkpoint 01).
  2. Figure without Alt (07-001, already in pdfcheck).
  3. No document Title in XMP, or DisplayDocTitle false (06).
  4. No document Lang, or invalid code (11).
  5. Text outside any tag, not an artifact (01-005 family; in pdfcheck).
  6. Fonts not embedded, no ToUnicode (31).
  7. Annotations/links not in the tree or lacking Contents (28).
  8. Tab order /Tabs not S (28).
  9. Table cells without header association; TH without Scope (15).
  10. Heading level skips (14-003; in pdfcheck).
  11. Form field without TU and not in a Form element (28, 31).
- Not machine-checkable, so human or guided: reading order sense, alt text quality, real heading vs bold, list vs lookalike, language correctness, contrast. Matches our PDF-UA.md "cannot check" list.

## 2. Legal drivers

- ADA Title II web rule (DOJ 2024) adopts WCAG 2.1 AA. DOJ interim final rule of 2026-04-20 moved compliance dates back one year: 2027-04-26 for entities serving 50,000+ people, 2028-04-26 for smaller entities and special districts. It took effect immediately, comments to 2026-06-22. The 2024 rule is not repealed. https://www.duanemorris.com/alerts/doj_extends_ada_title_ii_digital_accessibility_deadlines_one_year_0426.html and https://www.mondaq.com/unitedstates/media-entertainment-law/1782220/doj-extends-ada-title-ii-digital-accessibility-deadlines-by-one-year
- Exact day differs by source (26 vs 27 vs 24 April). Verify in the Federal Register / 28 CFR Part 35 before quoting. https://www.archerlaw.com/print/v2/content/11506/doj-extends-ada-web-accessibility-deadline-to-april-2027.pdf
- One source reports the extension is being challenged in federal court; not verified. https://www.mondaq.com/unitedstates/media-entertainment-law/1782220/doj-extends-ada-title-ii-digital-accessibility-deadlines-by-one-year
- PDFs: the rule treats PDF (and other document formats) on government sites as web content. Exceptions: archived content, pre-existing conventional documents, third-party content, individualized password-protected documents. The pre-existing exception does not cover documents still used to apply for or take part in services. That last point is the forms case. https://www.siteimprove.com/blog/ada-title-ii-document-accessibility/ and https://accessibility.psu.edu/guidelines/doj2024summary
- HHS Section 504 web rule runs on its own schedule; one source says May 11, 2026 for HHS-funded public entities. UNVERIFIED beyond that one law-firm page. https://jacksonlewis.com/insights/doj-extends-public-entities-compliance-deadline-ada-related-website-accessibility-hhss-may-2026-deadline-still-looms
- Section 508 (federal): the Revised 508 Standards incorporate WCAG 2.0 AA. I found no 2026 refresh and no primary GSA source. https://accessibility.psu.edu/guidelines/doj2024summary (secondary; see the comparison line)
- EU European Accessibility Act (Directive 2019/882) enforceable since 2025-06-28. Microenterprise exemption (under 10 staff, turnover or balance sheet at most 2 million euro) is for services only; products stay covered. https://www.ccpc.ie/business/enforcement/accessibility/european-accessibility-act-guidelines-for-microenterprises/ and https://www.qualibooth.com/resources/european-accessibility-act-faq/
- EN 301 549 covers non-web documents including PDF. PDF/UA is the industry route to it, not named in the law's text (one developer blog's reading). https://dev.to/niklasei/accessibility-law-and-your-pdfs-creating-pdfua-with-oicana-54c
- Who needs this: small state and local bodies (schools, libraries, towns, special districts) with few staff and no Acrobat Pro licence; blind staff who author documents; nonprofits and small EU businesses selling to consumers; blind individuals who must fill forms themselves. This is inference from the rules above, not sourced.

## 3. Validators

- veraPDF: latest I could read is 1.30.3, dated 2026-10-07 in the release notes. https://github.com/veraPDF/veraPDF-library/blob/integration/RELEASENOTES.md
- UA-2 first appeared as draft in 1.26 RC (2024-02-09). WTPDF-1 Reuse and Accessibility levels appear in 1.28 RC (2025-02-09). The notes do not say when either left draft; check an installed `verapdf --help`. Same URL.
- 1.30.x notes: pdfuaid:rev validation, relaxed math-in-Formula rules, top-left table cell with no Scope allowed, UA-1 table scope reverted to the PDF 1.7 algorithm. https://newreleases.io/project/github/veraPDF/veraPDF-library/release/v1.30.1
- CLI: `-f` / `--flavour` accepts `ua1` and `ua2` (and others); omit it or pass 0 for auto-detect from metadata; `-p` loads a profile file and overrides `--flavour`. https://docs.verapdf.org/cli/help/
- Practical call (UNVERIFIED flags beyond the help page): `verapdf --flavour ua1 --format json file.pdf`; confirm `--format` values in the installed version.
- A single user reported a ua2 test file flagged as both UA-2 and PDF/A-3a. Not a confirmed bug. https://lists.contextgarden.net/archives/list/ntg-context@ntg.nl/message/4IIHP4EGYVY3K5OTGWAWXKBNGTP6XYV5
- Licence: all veraPDF software is dual-licensed GPLv3+ and MPLv2+. Choosing MPLv2+ is the usual route for bundling in a non-GPL app: MPL is file-level copyleft. MIT app can ship it as a separate program with its licence texts. One module (xmp-core) declares BSD 3-Clause in its POM, so check per-module. Not legal advice; I found no explicit statement about redistribution. https://central.sonatype.com/artifact/org.verapdf/verapdf-library and https://central.sonatype.com/artifact/org.verapdf/verapdf-xmp-core
- veraPDF needs a Java runtime (our PDF-UA.md says Java is on Tony's machine; end users will not have it). Bundling a JRE adds size. UNVERIFIED sizes.
- PAC 2026: free; checks ISO 14289 (PDF/UA) and WCAG 2.2 AA with quality checks; technical tests based on WCAG 2.1. The page does not name UA-1 or UA-2, WTPDF, CLI or batch. https://pac.pdf-accessibility.org/en/resources/quickstart-guide/introducing-pdf-accessibility-checker-2026
- A third-party comparison lists PAC as UA-1 only (secondary). https://venngage.com/blog/pac-accessibility-checker/
- PAC is Windows only; installable by `winget install --id axes4.PAC -e`. I found no CLI. UNVERIFIED that none exists. https://wingetgui.com/apps/axes4-PAC
- New open source validators: none found by search. iText has WTPDF and UA-1 checkers inside its library (library, not a standalone validator; AGPL/commercial, UNVERIFIED). https://api.itextpdf.com/iText/java/9.6.0/com/itextpdf/kernel/validation/class-use/IValidationChecker.html
- Takeaway: veraPDF is the only scriptable, free validator with UA-1 and UA-2 profiles that I could confirm.

## 4. Competitor feature bar

Evidence here is thin; the search returned pricing and product pages for only some products. axesPDF, CommonLook, Foxit, ABBYY, Equidox, Allyant were NOT successfully researched.

- Adobe PDF Accessibility Auto-Tag API: Adobe Sensei, output is a tagged PDF; free tier of 500 document transactions a month; paid rates not public; newer materials say it can check against PDF/UA and WCAG and produce a report. Adobe's own blog says the API alone will not make a file compliant with Section 508 or PDF/UA and recommends human review. https://developer.adobe.com/document-services/pricing/ and https://blog.developer.adobe.com/en/publish/2023/04/tagging-pdf-documents-for-accessibility-at-scale-with-adobe-acrobat-pdf-services
- Adobe says auto-tagging is also in Acrobat Pro/Reader. https://www.engadget.com/adobes-new-ai-automates-pdf-accessibility-tags-130019203.html
- Acrobat Pro workflow (Make Accessible, Accessibility Checker, Tags and Reading Order panels): not researched here. From general knowledge, UNVERIFIED: checker gives pass/fail/manual per rule; repair is manual in the tag tree.
- PDFix: SDK has Python, C#, Java, C++, Node bindings; auto-tagging and PDF to PDF/UA are in paid editions; SDK pricing is quote-based; Desktop Pro listed at 350 euro per user per year or $599 per year (sources disagree); free Lite is watermarked/limited. https://www.softwareadvice.com.au/software/413879/pdfix-sdk and https://europeanpurpose.com/tool/pdfix
- PDFix SDK cannot be bundled in an MIT free app without a commercial licence. Inference.
- Nutrient (PSPDFKit) sells an Accessibility API. https://www.nutrient.io/api/pricing/accessibility-api/ (page title only; not read)
- The bar a free tool must match, by inference from the above and from what the paid tools sell (UNVERIFIED as a feature matrix): fix a tag type, edit alt text, mark artifacts, set table header cells and scope, set reading order, tag form fields with TU and Form elements, set title and language, OCR a scan, run a batch. TG Imprint today rebuilds from layout rather than editing the tree (PDF-UA.md "Import") and has no OCR, no batch, no tree editor.
- Important difference: our users are blind. A visual tag-tree panel (Acrobat, axesPDF) is not the right model. A keyboard tree view with speech is the gap competitors do not fill. Inference.

## 5. OCR for a bundled offline app

- Tesseract via PyMuPDF: needs Tesseract installed separately plus language data; folder passed by `TESSDATA_PREFIX` or `tessdata=`. `get_textpage_ocr(flags=3, language='eng', dpi=72, full=False, tessdata=None)`; no clip parameter, always whole page; OCR text is only visible to extraction if the returned TextPage is passed in; OCR text is written hidden with Tesseract's GlyphLessFont. https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html
- `pdfocr_save`/`pdfocr_tobytes` on a Pixmap makes a one-page searchable PDF (demo script). https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/OCR/tesseract2.py
- Size: the fast English model is about 1.7 MB download, 3.9 MB installed (MSYS2 repackage of tessdata_fast 4.1.0; Apache-2.0). Tesseract binary and DLL size was not found. https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-tesseract-data-eng
- Tesseract is Apache 2.0 (stated by the MSYS2 package licence field above). Redistribution inside an MIT app is fine with notices. Inference.
- Windows.Media.Ocr: `OcrEngine.TryCreateFromLanguage`, `TryCreateFromUserProfileLanguages`, `AvailableRecognizerLanguages`; result is lines then words. https://learn.microsoft.com/en-us/uwp/api/Windows.Media.Ocr.OcrEngine
- From Python through the `winsdk` package (`winsdk.windows.media.ocr`); if no OCR language pack is installed the engine does not create. https://huggingface.co/datasets/dlxjj/comicocr/blob/main/modules/ocr/ocr_windows.py
- Language packs are Windows capabilities installed per machine; I found no source on offline behaviour. UNVERIFIED. Ships nothing in our installer, zero size cost. Returns words with bounding boxes. Accuracy: no independent benchmark found; only a vendor blog saying both are decent and the Windows engine has fewer languages. https://ironsoftware.com/ocr/csharp/blog/ocr-tools/windows-ocr-engine-vs-tesseract/
- RapidOCR (ONNX): PP-OCRv5 mobile rec about 16 MB, server rec about 81 MB, server det about 84 MB; full ONNX set about 208 MB. Licence not confirmed by my search. Adds onnxruntime (tens of MB, UNVERIFIED). https://sdk.airefinery.accenture.com/distiller/model_catalog/DocumentAnalysis/paddlex/PP-OCRv5_server/ and https://huggingface.co/marsena/paddleocr-test/blob/main/README.md?code=true
- ocrmypdf: on Windows needs Tesseract (UB Mannheim build) and, since v17, either pypdfium2 or Ghostscript plus fpdf2; Ghostscript still recommended and needed for PDF/A. Licence not confirmed by my search (MPL-2.0 from memory, UNVERIFIED). https://ocrmypdf.readthedocs.io/en/v15.0.1/installation.html
- ocrmypdf produces a searchable PDF, but it is not tagged, so it does not meet our need on its own; we need text plus a tree. Inference.
- Recommendation for shipping: Windows.Media.Ocr first when a language pack exists (free, no size), Tesseract with tessdata_fast English bundled as the fallback. For Velopack deltas, keep traineddata and the Tesseract binaries in a separate, rarely changing folder so a delta does not re-ship them; extra languages as optional downloads. RapidOCR only if measured accuracy on Tony's real scans justifies roughly 100 MB or more. Delta behaviour is inference, not tested.

## 6. Writing a structure tree into an existing PDF

- No maintained library found that retro-tags an arbitrary PDF from Python. pikepdf is a low-level qpdf binding (objects, no tagging API). PyMuPDF has no structure-tree writer (our own measurement, CLAUDE.md). ocrmypdf does not tag. PDFix SDK does, commercially. Other writers found are Rust crates that tag as they generate (zpdf-writer, lightweight-pdf-writer, forme-pdf), not retrofitters. https://docs.rs/crate/lightweight-pdf-writer/latest/source/src/struct_tree.rs
- A coarse trick exists: wrap each page's whole /Contents in one `/Part << /MCID 0 >> BDC ... EMC`, add StructTreeRoot, ParentTree, MarkInfo. Valid but gives no usable structure. https://docs.rs/crate/zpdf-writer/latest/source/src/tag.rs
- Skia (Chromium's PDF backend) documents the mapping: `StructTreeRoot::ParentTree[Page::StructParent][mcid]` refers to the structure element. https://skia.googlesource.com/skia/+/main/src/pdf/SkPDFTag.h
- Recipe (from the PDF spec, ISO 32000; NOT web-verified in this session, test with veraPDF):
  1. Parse each page content stream with pikepdf (`parse_content_stream`), group operators into runs by text block or drawing. Wrap each run: `/P <</MCID n>> BDC ... EMC`. MCIDs are unique per page, starting at 0.
  2. Anything decorative (headers, footers, page numbers, rules, backgrounds): `/Artifact BMC ... EMC` with `/Type /Pagination /Subtype /Header` or `/Footer` through BDC. Never leave content outside marked content.
  3. Set `/StructParents n` on each page (unique integer per page).
  4. Build `/StructTreeRoot` (`/Type /StructTreeRoot`, `/K` root Document element, `/ParentTree` number tree, `/ParentTreeNextKey`, optional `/RoleMap`).
  5. For each element: `/Type /StructElem /S /P /P <parent> /Pg <page> /K <mcid or array>`. Add `/Alt` on Figure, `/Scope` and `/Headers` on table cells, `/Lang` where it changes.
  6. ParentTree: for page key n, an array indexed by MCID giving the owning element. Mismatched or missing entries are the top trap.
  7. Widgets: add `/StructParent m` on the annotation, a `/Form` element whose `/K` is `<< /Type /OBJR /Obj <widget> /Pg <page> >>`, and ParentTree entry m pointing at the Form element. Same for Link annotations (our export already does this via Chromium).
  8. Catalog: `/MarkInfo << /Marked true >>`, `/Lang`, `/ViewerPreferences << /DisplayDocTitle true >>`, XMP `dc:title` and `pdfuaid:part`. Page `/Tabs /S`.
  9. Save with pikepdf, then validate with veraPDF `--flavour ua1`.
- Traps (UNVERIFIED, from experience with the spec): Form XObjects have their own content streams, so MCIDs inside them belong to the page that draws them and need ParentTree handling; Type 3 and inline images; marked content split across q/Q nesting (BDC/EMC must nest inside a graphics state level); text with no ToUnicode makes a tag useless; an empty element that points at no MCID; a page with `/StructParents` but no ParentTree entry; encrypted files. veraPDF release notes show it recently fixed Artifact propagation into untagged Form XObjects and tiling patterns, which confirms these cases matter. https://github.com/veraPDF/veraPDF-library/blob/integration/RELEASENOTES.md
- Real value of retro-tagging comes from deciding the structure (heading vs paragraph, table grid). That needs layout analysis (which pdfimport already approximates) plus user confirmation by keyboard. Inference.
- Chromium headless state: the flag was `--export-tagged-pdf` in 2020, tagged output in headless since. https://blog.chromium.org/2020/07/using-chrome-to-generate-more.html
- A forum claim says a Chromium bug was fixed so headless always includes tags (secondhand, undated). https://forum.jsreport.net/post/10314
- Chromium retrieves the full tag tree for the AX layer and its mapping adds Lbl and LBody types. That is the reading side (viewer), not the printing side. https://chromium.googlesource.com/chromium/src/+/f4abba09e5218240897a367a8f6cde39bdac16e0%5E%21/
- I could NOT confirm any 2025 or 2026 change that makes print-to-pdf emit LBody, Span lang, or a PDF/UA flag, nor the existence of `--no-pdf-tagged`. The nine-point gap list in PDF-UA.md was measured on Edge 152 and stays the authority. Re-measure each Edge release, since a Skia change could land any time. Source for the generation side: https://chromium.googlesource.com/chromium/src/+/20d0aa1d03e1e2295ef8fd513db937af9cf4f39a/printing/common/metafile_utils.cc (it builds the tree from AX nodes, which explains NonStruct wrappers).

## 7. Screen readers with PDFs

Thin evidence; mostly user reports. No official NVDA/JAWS PDF matrix found.

- January 2026 Adobe Community thread: an accessible form that passed Acrobat's checker, NVDA could not announce fields in Acrobat 2025, Edge read none of the fields; Firefox 147 (PDF.js) read it fully. https://community.adobe.com/questions-9/adobe-pro-2025-perfectly-accessibility-pdf-form-not-reading-with-nvda-in-edge-chrome-and-acrobat-1547119
- 2025-2026 thread: Acrobat crashes with NVDA when an InDesign-exported interactive PDF contains a checkbox or radio button. https://community.adobe.com/t5/acrobat-discussions/acrobat-crashing-when-attempting-to-read-forms-with-nvda/m-p/15469746
- PDF.js tries to honour tagged PDF but tag support is an active area; open bugs include merged table header cells. https://webaim.org/discussion/mail_message?id=50254
- AcroForm fields read cleanly in PDF.js, PDFium and PDFKit; XFA forms render in no browser viewer (secondary, May 2026). https://www.testmuai.com/learning-hub/pdf-viewer-browser-support/
- Untagged PDFs: PowerMapper keeps a screen reader test page. https://powermapper.com/tests/screen-readers/pdf/pdf-untagged
- Not researched, no sources: JAWS, Foxit, Narrator, VoiceOver behaviour; which structure types NVDA honours in Edge.
- Test implication (inference): test every export in at least Acrobat Reader, Edge, and Firefox with NVDA, and read the form fields in each. A file passing a checker does not mean NVDA speaks it. Record what NVDA said, as the team rule says.

## 8. Repairing broken PDFs

- pikepdf is qpdf based and repairs structural damage on open; `open` then `save` is the first attempt. qpdf's checker via `Job(['pikepdf','--check', file]).run()`. https://pypi.org/project/pikepdf/10.17.0/
- Repair strategy shared by qpdf and MuPDF: scan raw bytes for `N G obj` headers and rebuild the xref, ignoring the damaged one. Cannot repair encrypted files (object streams stay encrypted). https://docs.rs/crate/pdq/latest/source/src/repair.rs (describes the technique for several tools)
- qpdf recovers broken xref tables, truncated streams, invalid object references. https://www.bentopdf.com/docs/tools/repair-pdf
- PyMuPDF/MuPDF repair specifics: search found nothing. From memory, UNVERIFIED: MuPDF rebuilds silently on open when xref fails; `doc.is_repaired` reports it; `save(garbage=4, clean=True)` writes a fresh file.
- Corruption kinds (UNVERIFIED, general knowledge): bad or missing xref, wrong startxref, truncated at EOF, junk before the header, broken streams, bad Length, missing endobj, damaged object streams, wrong page tree counts.
- Garbled text detection (UNVERIFIED, general knowledge, to be built and tested): fonts with no ToUnicode and a non-standard encoding give private-use or control characters; extraction returns U+FFFD or `(cid:n)` strings; ligatures come out as single glyphs like U+FB01 or are dropped; Identity-H CID fonts without ToUnicode extract as nothing sensible. Detect with a per-page ratio of replacement, private-use and control characters to letters, plus dictionary-word ratio. Our own TextIndex already decodes through ToUnicode.
- Remedy for a garbled page: render and OCR the page, then use the OCR text (section 5); warn the user the text was recognised, not original.

## What TG Imprint should do

1. Add veraPDF as the real gate: run `--flavour ua1` over every fixture in CI now, and ship it as an optional "full check" (separate download, MPLv2 chosen, Java requirement stated). Our own pdfcheck stays as the fast check. Check `verapdf --help` for the ua2 and WTPDF names on 1.30.3.
2. Add OCR so scanned PDFs stop being a dead end: Windows.Media.Ocr when a language pack exists, bundled Tesseract tessdata_fast English as fallback, installed in a stable folder so Velopack deltas stay small. Measure accuracy on Tony's own scans before choosing anything bigger.
3. Do not bet on Chromium adding LBody, Span lang or a PDF/UA flag. Keep the gap list, re-measure on every Edge update, and keep the refuse-to-save rule.
4. Build a keyboard-first, speech-first structure editor for imported PDFs (list of headings, tables, figures, forms) rather than a visual tag-tree panel. This is where a blind-authored tool beats Acrobat and axesPDF.
5. Retro-tag in pikepdf for the form-filling case: write Form elements with OBJR, TU, StructParent and ParentTree, so a filled or field-added form can carry a defensible tag set. Follow the recipe in section 6; validate each step with veraPDF.
6. Add a text-quality detector on import (replacement, private-use and control character ratios; missing ToUnicode) and offer OCR over the page when it trips.
7. Add a repair-on-open step: pikepdf open and save, then qpdf check, report what was repaired in plain words, never silently.
8. Add batch: a folder in, a report and exported files out, with one line per file in the report. Public bodies facing Title II dates have piles of PDFs.
9. Write a screen reader test protocol: each export tried with NVDA in Acrobat Reader, Edge and Firefox, form fields included, the speech recorded. The Acrobat 2025 and Edge form reports make this necessary.
10. Positioning: lead with Title II (2027-04-26 for 50,000+, 2028-04-26 smaller, verify exact dates) and the EAA, state plainly what a checker cannot prove, and do not claim compliance. Document the free versus Adobe Auto-Tag (500 free transactions a month, human review still needed) choice for users who want AI tagging, as an optional provider with consent like the picture describer.
