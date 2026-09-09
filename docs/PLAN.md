# Easy PDF revival, the plan and the committee (2026-09-09)

> **Renamed 2026-09-09.** Tony chose **TG Imprint**. Every path below that
> reads `easypdf/` is now `tgimprint/`, the document extension is
> `.imprint`, and the frozen names are `TGImprint`, `tg-imprint` and
> `TGStudios.TGImprint`. The old name is left in this document because it
> is the record of how the decision was reached.



Read `ANALYSIS.md` first. This file says who does what, in what order, and
what "done" means. It is the brief every agent works from.

No em dashes or en dashes anywhere in this project.

---

## The committee

Five agents, as Tony asked for, plus the coordinator (the top-level session)
who scaffolds, integrates, builds and ships.

| Role | Count | Job |
|---|---|---|
| Overseer and reviewer | 1 | Settles the decisions after the challenge; reviews every worker's output against the standing rules and this plan; runs the screen reader audit before release; reconciles the audits |
| Worker A: PDF pipeline | 1 | Engine, export, checker, import, native file format, image placement in the output |
| Worker B: UI and accessibility | 1 | The single WebView2 editor, menus and keys per CONVENTIONS.md, dialogs, speech levels, status bar, context menu, visual finish, DPI and icon wiring |
| Worker C: Describer and AI | 1 | The three-provider describer, key storage, consent, the describe-image and describe-document flows and their dialogs |
| Challenger (bias and unbias) | 1 | Argues against every decision in ANALYSIS.md section 10 before work starts, then verifies "done" claims by measurement at the end, including the visual and mouse audit |

The coordinator owns: package scaffold, `main.py`, single instance, update
client, update dialog, installer script, build and release tools, selftest,
tests for those, git, GitHub, shortcut, TG Stats rule, website draft, the
final report to Tony.

## Order of work

1. Coordinator: scaffold the package on the as-found commit. Byte-identical
   copies of `singleinstance.py`, `updatedialog.py`, `speech.py`, and
   Drop Deck's `appupdate.py`, `secrets.py`, `vision.py` with only the
   app-specific block changed. New `constants.py`, `main.py`, `appicon.py`,
   `tools/`, `tests/` harness. Old `core/` and `ui/` moved under
   `easypdf/` untouched, so the workers start from a tree that runs.
2. Challenger: read ANALYSIS.md and PLAN.md, argue the other side of each
   decision, name any that should flip and why.
3. Overseer: read the challenge, settle each decision, write
   `docs/DECISIONS.md`. Anything that contradicts a standing rule in
   `TG Studios\CONVENTIONS.md`, `RELEASING.md` or the memory notes is
   settled by the rule, not by the argument.
4. Workers A, B, C in parallel, each inside their own files (below).
5. Overseer reviews each worker's report against the code, lists defects.
   Workers fix. Repeat once.
6. Coordinator integrates, runs every test file, builds, selftests the
   frozen build, installs it to a throwaway folder and runs it.
7. Overseer runs the screen reader audit with NVDA running, plus a
   Windows High Contrast pass and a Narrator pass; Challenger runs the
   visual and mouse audit with screenshots at 150 percent and once at 200
   percent. Both prove input arrived before trusting a result
   (`AttachThreadInput`, then a control test).
8. Coordinator reconciles the two audits against its own measurement,
   fixes what is real, adds a regression test per real finding, rebuilds.
9. Coordinator: rehearse the release (no upload), private repo and push,
   shortcut in Desktop\TG Apps, memory notes, report and ping.

## File ownership, so three agents can work at once

Nobody edits a file they do not own. If you need a change in another
owner's file, write down exactly what you need in your report and the
coordinator makes it at integration.

| Owner | Files |
|---|---|
| Coordinator | `main.py`, `launch.pyw`, `easypdf/constants.py`, `easypdf/singleinstance.py`, `easypdf/appupdate.py`, `easypdf/updatedialog.py`, `easypdf/speech.py`, `easypdf/secrets.py`, `easypdf/appicon.py`, `easypdf/paths.py`, `easypdf/handoff.py`, `easypdf/filetype.py`, `tools/*`, `tests/test_update.py`, `tests/test_scaffold.py`, `tests/test_handoff.py`, `tests/test_filetype.py`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `.gitignore` |
| Worker A | `easypdf/pdfengine.py`, `easypdf/pdfexport.py`, `easypdf/pdfcheck.py`, `easypdf/pdfimport.py`, `easypdf/docfile.py`, `easypdf/docx_in.py`, `easypdf/markdown_in.py`, `easypdf/htmlclean.py`, `tests/test_pdf*.py`, `tests/test_docfile.py`, `tests/test_import.py`, `docs/PDF-UA.md` |
| Worker B | `easypdf/ui/*.py` (the frame, editor, toolbar, every dialog except the describer's), `easypdf/ui/keymap.py`, `easypdf/editor_page.py` (the HTML, CSS and JS inside the editor), `easypdf/settings.py`, `tests/test_ui*.py`, `tests/test_menus.py`, `tests/test_keys.py`, `docs/KEYBOARD.md` |
| Worker C | `easypdf/ai.py`, `easypdf/describe.py`, `easypdf/ui/describe_dialog.py`, `easypdf/ui/ai_settings_page.py`, `tests/test_ai.py`, `tests/test_describe.py`, `docs/DESCRIBER.md` |

Interfaces between them, fixed before work starts. **The exact, settled
signatures are in `docs/DECISIONS.md` under "Changes to the briefs"**
(`docfile.kind_of` and `docfile.embed_image`, `pdfengine.engines()`,
`ExportResult.pdfua_claimed`, `Report.pdfua_gate`, `ImportedImage.alt` and
`alt_source`, `normalise(body_html, for_export=False)`,
`consent_needed(kind, imported, pictures)`, `DescribeImageDialog(...,
imported=False)` with `.provider_used`); where this list and that section
differ, that section wins:

- Worker B calls `pdfexport.export_html(body_html, path, meta, progress)` and
  `pdfimport.import_pdf(path) -> (body_html, meta, images)`, both of which
  Worker A provides and which run on a worker thread the UI starts.
- Worker B calls `docfile.save(path, body_html, meta)` and
  `docfile.load(path) -> (body_html, meta)` from Worker A. `meta` is a dict:
  `title, author, lang, subject`.
- Worker B opens `describe_dialog.DescribeImageDialog(parent, image_bytes,
  current_alt)` and `describe_dialog.DescribeDocumentDialog(parent,
  body_html, images)` from Worker C, which return text or None. The AI
  settings page is a panel Worker B mounts inside Preferences.
- Worker C uses `secrets.py` and `ai.py` (from `vision.py`) as the
  coordinator scaffolded them, and never touches the credential prefix.
- Everyone uses `constants.APP_NAME`, `constants.APP_VERSION`, and
  `paths.config_dir()`; nobody hardcodes a path or a name.

## What every worker must read before writing a line

- `docs/ANALYSIS.md`, then `docs/DECISIONS.md` when it exists.
- `Dropbox\TG Studios\CONVENTIONS.md` and `RELEASING.md`.
- `CLAUDE.md` in this project, which carries the standing rules.
- For the shape of a TG Studios wx app: `Dropbox\TG Studios\TG Drop Deck`
  (`dropdeck/ui.py` for the announce channels and the update flow,
  `dropdeck/dialogs.py` for the Preferences speech page, `tests/` for the
  hand-rolled test style, `CLAUDE.md` for the wx traps already measured).

## Standing rules that apply, in one place

- **Every user-facing change is tested with NVDA actually running.**
- **wxPython only.** No tkinter, no Qt.
- **No em dashes or en dashes anywhere**, including strings, comments,
  docs and commit messages. `python tools/nodashes.py` reports them.
- **No new visible strings in Tony's voice ship unapproved.** Every string
  the app shows or speaks is listed in `docs/STRINGS.md` by the worker who
  wrote it, so Tony can read them as text before release.
- **Never rewrite a control's accessible Name on a value change.**
- **Never `wx.MessageBox` for anything a user might want to re-read.**
  A dialog with a read-only multiline field, focus in the field.
- **All three speech channels write the status bar at every level.**
- **Nothing leaves the machine without consent**, and consent names the
  provider. The screen path in Drop Deck asks every time; here, a whole
  document asks every time and a single image asks once per session. A
  picture that arrived inside an imported document, and any batch of
  pictures, is that document leaving the machine and asks every time.
- **Nothing on the UI thread that can take more than a blink.** Export,
  import and every network call run on a thread and report back with
  `wx.CallAfter`.
- **Build outside Dropbox** (`%LOCALAPPDATA%\TG Studios Build\easy-pdf`).
- **Tests are hand-rolled scripts, one per file, `python tests/x.py`.**
  Each prints ok/FAIL per check and exits non-zero on any failure. A test
  that cannot fail is a bug; prove each one can.
- **Measure, do not infer.** A claim about what NVDA says, what a key does,
  or what a PDF contains is backed by a run, a screenshot or a pikepdf read.
- **Version 1.0.0 until it ships.** The slug, mutex, AppId and feed name are
  frozen now. The display name is one constant.

## Definition of done, for the whole thing

- `python tests/*.py` all green, and the count of checks is in the report.
- `python tools/build_release.py` produces the installer and the zip.
- The frozen exe passes `--selftest` and reports the update channel as
  live-capable (key baked in, verification working).
- The installer installs to a throwaway folder, the app opens, creates a
  document with a heading, a list, a link and an image with alt text,
  exports it, and the in-app checker passes every check on the result.
  pikepdf confirms the structure tree from the outside.
- `python tools/release_app.py rehearse` passes. Nothing is uploaded.
- The export's PDF/UA identifier was written (`pdfua_claimed` True) on the
  definition-of-done document.
- A fixture holding an `img` with an `onerror` handler opens without
  running it.
- A second launch with a document path opens it in the running copy.
- NVDA reads the editor with heading, list and link roles; every dialog
  field has a name; the status bar carries every announcement.
- A screenshot of the running app looks finished: icon, toolbar with icons,
  proper spacing, readable at 150 percent scale.
- Private repo `tonygeb23/easy-pdf` holds every commit; nothing secret in
  it.
- A shortcut in `Desktop\TG Apps` opens the app.
- The report to Tony lists what was built, what was verified and how, what
  each agent found, what was left out and why, and the one decision that is
  his: the go to publish, with the strings to approve.
