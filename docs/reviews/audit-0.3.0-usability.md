# TG Imprint 0.3.0 usability audit (Ryder)

Scope: backend driven from Python on the 26 corpus files and 9 real PDFs, plus the screenshots in docs/screenshots. The running app was not driven (see "Not tested"). Ratings are mine. "Gap" means a real fault. "Preference" means taste.

Usability score: **59 / 100**.

Deductions, one line each:

- 7: a fillable form loses every field on Make a PDF accessible, silently.
- 5: exporting an empty document blames Microsoft Edge.
- 5: Repair always sets en-US and can title a file with its file name or with symbols.
- 5: import warnings (pages lost, OCR guesses) vanish at export, which then says "every check passed".
- 4: OCR output turns body sentences into headings, and the title comes from the wrong page.
- 3: Word export crashes with a library message on imported text.
- 3: the manual says the opposite of the product (no OCR, no Word export, version 0.2.0).
- 2: a false "pictures of text" warning on a page that is one table and a logo.
- 2: Repair's suggested step never changes the verdict.
- 2: Markdown and text exports lose pictures and the title without a word.
- 2: visual polish faults (below).
- 1: wording that contradicts itself (below).
- Total deducted: 41.

## Blockers

- **None found in the backend.** Nothing crashed the process, no file was left half written, and every unopenable file got one plain sentence. A blocker may still sit in the live UI, which I did not drive.

## Serious

1. **Make a PDF accessible deletes the form fields and says nothing (gap).**
   - Try: import a fillable form, export a tagged PDF.
   - Reproduce: `corpus\form-field-no-label.pdf` has 1 widget; the exported PDF has 0. A real one page form with 41 fields came out with 0 fields and 2 pages. No import warning mentions fields.
   - Why it matters: the person gets a tagged PDF that cannot be filled in. The start screen sells this path as "fix what is left, export a tagged copy".
   - Fix: when the source has fields, say at import: "This PDF has 41 form fields. Making it accessible this way removes them. Use Fill in a PDF form to keep them." Better, offer that route.

2. **Export of an empty document blames the PDF engine (gap, misleading).**
   - Reproduce: `pdfexport.export_html("", out, {"title":"T","lang":"en-US"})`, and with `"<p></p>"`. Same result when importing `corpus\blank.pdf` and exporting. A first time user presses Ctrl+Shift+E on New document.
   - Said: "The PDF engine wrote a PDF without tags, so nothing was saved. ... update Microsoft Edge."
   - Better: "There is nothing in this document to export yet. Type something, then export again." Check for an empty body before calling the engine.

3. **Repair picks the language and title blindly (gap).**
   - The UI never passes a language (`main_window.py` line 1976), so every repaired file becomes en-US. A Spanish test PDF that import correctly guessed as `es` was repaired as `en-US`. The manual itself says wrong rules make speech "close to unintelligible".
   - `corpus\garbled-tounicode.pdf`: Repair reports a title made of private use symbols. A screen reader reads that as noise.
   - `scanned.pdf` and `scanned-skewed-noisy.pdf`: the title becomes the file name, the exact fault the manual warns about.
   - Fix: reuse import's language guess; show title and language in a confirm field before writing; never take a title from text that fails the readable check.

4. **Warnings stop at import, but the export report certifies the result (gap, trust).**
   - `truncated-half.pdf`: import says "only 1 of its 2 pages could be recovered". Export then says nothing and claims PDF/UA.
   - OCR'd files (`scanned.pdf`, `garbled-tounicode.pdf`): "recognition can get names and numbers wrong" appears once, at open; export reports a pass.
   - A blind user cannot see the missing page or check the recognised text. "Passed" speaks about structure, not truth.
   - Fix: carry these warnings into the export report, for example "Not verified: 1 page was read by text recognition."

5. **OCR heading guesses are wrong on mixed files (gap).**
   - `mixed-scan.pdf`: the four body sentences of the scanned page each become a level 2 heading; the first heading is level 2 ("Cover letter"); the document title becomes "Notice to residents", a heading from page 2. Repair on the same file titles it "Cover letter", so the two paths disagree.
   - Export result: no PDF/UA claim, the check names "Heading levels". Correct, but the user must fix 5 headings by hand. The changelog says heading levels start at 1 with none skipped; here they do not.
   - Also inconsistent: `scanned.pdf` makes each line a paragraph, `scanned-skewed-noisy.pdf` joins them.

6. **Word export fails with a library message (gap).**
   - `corpus\type3-no-tounicode.pdf` imports with control characters (U+0001 to U+0008) at the end of its text. `export_docx` raises `ValueError: All strings must be XML compatible: Unicode or ASCII, no NULL bytes or control characters`. The UI would show it as "That file could not be written. All strings must be XML compatible...". The changelog promises "never a library error".
   - Also: import and analyse say nothing about those symbols. Strip control characters on import and say how many were removed. This is the backend path; the editor may clean some of it first, so retest in the UI.

7. **Manual contradicts the product (gap, promise).** docs/MANUAL.md says version 0.2.0, "There is no text recognition in this beta", "a scanned PDF ... cannot be imported", and "no Word export". All three are false in 0.3.0. A blind reader trusting it would never try a scanned PDF or Word export. Update sections 10 and 18 and the version line.

## Minor

8. **False "scanned" warning (gap).** Repro: a page that is one ruled table plus a logo (`repro_table_logo.pdf` in the session scratchpad). Import says "This PDF is pictures of text, and nothing could be read from it. The text recognition data is missing from this copy of TG Imprint" beside "1 table was rebuilt". It happened on a real two page statement with nine tables. Cause: `pdfimport.py` line 1066 counts a page as scanned when its text blocks are empty after tables were taken out. The second sentence also tells the user to fix something that is not broken.

9. **Repair never moves the verdict (gap, wording).** For every untagged, text-bearing file the analyse step says "Use Repair a PDF ... keep every page looking as it does now", and the verdict after Repair is the same: "there are no headings, lists or other structure". Add: "Repair will not change this verdict."

10. **Analyse says odd things about nothing and about scans.**
    - `blank.pdf`: "A screen reader can read the words" when there are none. Say "This PDF has no content."
    - The list says "Pictures described: There are no pictures" on a scan that is one picture of text, and counts absent things as passes ("8 of 18 checks passed").
    - "Open it in TG Imprint and export it again." appears 7 times in one report. Say it once, near the top.

11. **Markdown and text lose things silently (gap).** A picture exports as `![A red bar chart](picture)`, a link to nothing. A picture with no description is dropped from text. The title and author never appear. After export the app only says "Exported as ...". Say what was left out.

12. **Not a PDF (gap, minor).** `html-saved-as.pdf` is a web 404 page and gets "That file is not a PDF." with "Ask the sender for a new copy." Say "This looks like a web page, probably an error from a failed download. Download it again."

13. **Dropped running headers are not shown (gap, minor).** "6 lines repeated on the pages left out as a running header or footer." A blind user cannot tell whether a real line went. Offer the lines in the notes dialog.

14. **Owner restricted PDFs import without a note (preference).** `owner-restricted.pdf` denies extraction, allows accessibility. Importing is legitimate; a one line notice would be honest.

15. **Recover dialog opens only the newest snapshot (preference).** "Recover opens the most recent one." With several there is no way to choose.

## Visual polish (from screenshots)

16. **Dialogs stay Windows white** while Yellow on black recolours the rest (manual section 15 says so). For a low vision user that is a bright flash on every dialog. Serious for that audience, a design call for the team.
17. **Accessibility panel rows are cut with an ellipsis** at 100 percent ("is level 4 after ..."); the full text appears only after selecting. Wrap the rows.
18. **Toolbar labels stay small** in the 150 percent yellow on black shot while the rest scales.
19. **Menu bar stays white** in dark and yellow on black (documented limit).
20. **Stale screenshot:** `recover-unsaved-work-100.png` (9 Sep) still reads "Easy PDF did not close properly". The source no longer has that string; regenerate the gallery.
21. **Export report path** shows `C:/Users/tony/Documents/...` with forward slashes. Use backslashes for a Windows user.
22. **Mouse affordances** (not verified): no screenshot shows double click on a panel or picture list row, and both rely on a button after selection.
23. **Contradiction** in the Pictures list: "Picture 2: no description, recovered from the PDF, please check". Both cannot be true. Say "recovered from the PDF, not checked" or "no description".

## Performance

- Largest real file (487 KB, 1 page): import 0.23 s. Other real files: 0.03 to 0.51 s. Export 1.4 to 1.8 s each.
- Stress: a made up 300 page text PDF (256 KB): analyse 0.93 s, import 42.6 s (about 0.14 s a page), export 17.7 s. Import speaks "page N of M", so the wait is heard; I found no Cancel for it.
- OCR: 0.4 to 0.75 s for one or two pages.

## Corpus summary

- Never crashed or hung: 26 of 26. Plain sentence on empty, not-a-PDF, password and wrong password.
- Damaged files (no startxref, bad xref, truncated tail, junk prepended) open and say so; truncated-half reports the pages lost.
- Word counts matched through PDF, Word and text for text files; the untagged report dropped 21 words as furniture, with a notice. Two column order and tables came out correct.
- Language and title survive to Word (a Spanish test file carried `es`).

## What is genuinely good

Failures are one honest sentence with a next step, damaged files open with a clear note, and the analyse verdict says first what a screen reader will do. Protect that.

## Not tested

- The running app: no keyboard run, no NVDA, no JAWS, no focus order, no mouse.
- Dialogs beyond the supplied screenshots (about 14 read).
- Passwords that open a PDF (none known), PAC and veraPDF verdicts, AI describing, Fill in a PDF form beyond the manual, updates, install, print.
- Word, Markdown and text import.
- Real world sample: 9 PDFs read from Life Admin and TG Studios. One 487 KB file was timed only and never output. Nothing was copied off the machine and no content is quoted.
