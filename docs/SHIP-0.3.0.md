# TG Imprint 0.3.0: audit result and shipping plan

Written 2026-11-01. Branch `release/0.3.0`, uncommitted, not published.

## Scores

| | Accessibility | Usability |
|---|---|---|
| Audit of the first 0.3.0 build | 73 | 59 |
| Same deduction lists after the fixes | about 90 | about 85 |

- The audit scores are measured, `docs/reviews/audit-0.3.0-*.md`.
- The second row is my own recount, not a fresh audit.
- Neither score includes a person using it with NVDA.

## Proof

- veraPDF PDF/UA-1: 11 of 11 documents pass. 0.2.1 failed all it was given.
- Suites: 27 files. Every suite passes except test_describe at 224 of 226
  (live Gemini). test_altmenu skipped its key checks because keys did not land.
  test_keys was not run on the final tree: it needs the foreground.
- Frozen build: selftest passed, including text recognition and Word export.
  It closes cleanly.
- Update rehearsal passed: swapped package and edited manifest refused.
- Size: delta from 0.2.1 is 4.1 MB. Installer 133.8 MB.

## Before publishing: Tony

1. Read `docs/STRINGS.md`, the two 0.3.0 sections, and the update note in
   `tools/release_app.py`. They are in your voice.
2. NVDA pass, about 20 minutes:
   - start screen: Tab, recent list
   - Accessibility panel: Ctrl+F6, count spoken after the row, Enter on an issue
   - typing with the panel open: nothing speaks
   - open a scanned PDF, then a password PDF
   - Analyse a PDF, Repair a PDF
   - exported PDF in Acrobat: headings, lists, table headers
3. One sighted look at the real window in light, dark, yellow on black and
   Windows High Contrast. The window shots were composites because the desktop
   was locked.
4. Decide on the correction wording. The PDF/UA claim in older exports was
   false, so the note says so. Published copy that says PDF/UA needs the same
   check.

## Before publishing: me

1. Find why the live Gemini check says it cannot reach Gemini. The host answers,
   and this failed before any of this work.
2. Run `test_keys.py` on an unlocked desktop and compare failure names.
3. `python tools/verify_ua.py`, and treat "skipped" as not done.
4. Regenerate the screenshot gallery; `recover-unsaved-work-100.png` still says
   Easy PDF.
5. Add `tools/verify_ua.py` to the release steps in `TG Studios\RELEASING.md`.

## Then, per RELEASING.md

Commit and push the branch, merge, rebuild, selftest the frozen build, upload,
signed manifest, update the site page and manual, deploy and verify, GitHub
release, `check_updates.py`, announce.

## Next version, 0.4.0

In order:

1. Form fields in the structure tree, so a form can carry a defensible claim.
2. Dialogs themed in dark and yellow on black. They are a bright flash today.
3. A keyboard structure editor for an imported PDF: headings, tables, reading
   order, by list and speech. No competitor serves blind authors this way.
4. Batch: a folder in, one report out. Title II deadlines make this the feature
   public bodies will ask for. Verify the dates first.
5. Accessibility minors left from the audit: silent keys on the start screen,
   real keyboard access to the toolbar, keyboard panel width, folders in the
   recent list, thick focus ring on the start screen, password speech wording.
6. Cancel for a long import. Text recognition in more languages.

Later: PDF/UA-2, right to left languages, tagging a PDF in place without
rebuilding its layout.
