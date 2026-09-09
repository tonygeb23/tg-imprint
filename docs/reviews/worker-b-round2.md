# Worker B, round 2 review: the window, the editor page and the dialogs

Overseer, 2026-09-09. Scope: `easypdf/ui/main_window.py`, `keymap.py`,
`web_editor.py`, `toolbar.py`, `icons.py`, the eight dialogs under
`easypdf/ui/`, `easypdf/editor_page.py`, `easypdf/settings.py`, the Worker
B section of `docs/STRINGS.md`, `docs/KEYBOARD.md`, `docs/screenshots/`,
and the five test files. Checked against `CLAUDE.md`,
`docs/briefs/worker-b.md` with its amendment, DECISIONS.md decisions 1, 4,
5 and 9 and edits B1 to B16, and `TG Studios\CONVENTIONS.md`.

No project file was modified except this one. Scratch output is under
`%LOCALAPPDATA%\Temp\claude\...\scratchpad` (`ui_page_out.txt`,
`ui_page_out3.txt`, `probe_b.py`).

## Verdict

Fix these and re-review. Defects 1 to 6 must be fixed; 7 to 19 can go in
the same pass or the next. NVDA was not driven in this round; that is
Round 4.

## Test counts I measured

Run from the project root, `python tests/<file>.py`, one at a time, with
nothing else of mine running.

- `test_ui_page.py`: three runs gave 87 of 98, then 97 of 98, then 98 of
  98. See defect 4. The second run's one failure was "Enter twice at the
  end of a list leaves the list with a paragraph", and the DOM it printed
  was `<li>Tw</li><li><br></li><li>o</li>`: the caret was in the middle of
  the word when Enter was sent.
- `test_menus.py`: 47 of 47.
- `test_ui_names.py`: 33 of 33.
- `test_settings.py`: 32 of 32.
- `test_keys.py`: not run. It sends real keystrokes to the foreground
  window and I could not tell whether the desktop was free, so its "note:"
  lines were not read. Round 4 runs it.
- Each suite prints one deliberate FAIL and then checks that it was
  recorded as a failure, and run two of `test_ui_page.py` failed for real
  and exited 1. So the harness can fail.

## What I confirmed by running or by grep

- `grep -rn "RunScript(" easypdf/` finds nothing but `RunScriptAsync`.
  No synchronous RunScript anywhere under `easypdf/`.
- `python tools/nodashes.py`: no em or en dashes anywhere.
- `grep MessageBox easypdf/`: none in Worker B's files. The one call in
  the project is `main.py` line 601, the coordinator's file (see the note
  at the end).
- The CSP with a nonce is in the page and the onerror marker is never set
  (`test_ui_page.py`, the hostile file section, passes in all three runs).
- Every dialog's focusable controls are named and the preview refuses
  focus (`test_ui_names.py`).
- The two probes in `probe_b.py` (defects 2 and 3).

## Defects

### 1. Worker C's dialogs are mounted without the settings they take

- Files: `easypdf/ui/main_window.py` lines 1367 and 1403;
  `easypdf/ui/image_dialog.py` line 273.
- Wrong: `DescribeImageDialog` is built with `current_alt`, `context` and
  `imported` only, and `DescribeDocumentDialog` with the body and the
  images only. Neither call passes `provider=` or `model=`, and the
  document dialog does not pass `document_name=`. `grep -n "provider=\|model="`
  under `easypdf/ui/` finds no caller. Worker C's constructor at
  `describe_dialog.py` line 213 says "provider and model are the user's
  settings", and line 447 takes `document_name` for the consent question.
  DECISIONS.md line 1589 and 1785 record the mount. Effect: the model the
  user chose on the AI page is ignored, the provider falls back to the
  first one with a key, and the consent question cannot name the document.
- Right: `DescribeImageDialog(..., provider=self.settings.get("ai_provider", ""),
  model=self.settings.get("ai_model", ""))` in both places, and
  `DescribeDocumentDialog(self, body, images, provider=..., model=...,
  document_name=self.document_name())`. `settings.py` already holds both
  keys and `ai_settings_page.apply()` (line 402) writes them.
- Confirmed by reading the signatures and by grep.

### 2. Ctrl+W asks "Save the changes" twice

- File: `easypdf/ui/main_window.py` lines 839 to 843.
- Wrong: `on_close_document` runs `_confirm_discard()` and then calls
  `on_new()`, which runs `_confirm_discard()` again. `modified` is still
  True when the answer was Don't Save, so the prompt appears a second
  time. Probe: with `dialogs.unsaved_changes` answering "discard",
  `on_close_document()` asked twice.
- Right: `on_close_document` does the prompt and then the reset without a
  second prompt (split `on_new` into the prompt and a `_reset_document()`
  that both call).
- Confirmed by running.

### 3. After a crash, opening a document by double click never offers the snapshot

- File: `easypdf/ui/main_window.py` lines 426 to 435.
- Wrong: `_after_show` is `if open_path: load; elif PREVIOUS_RUN_CRASHED:
  offer; elif restarted_after_update(): offer`. A launch with a path skips
  the recovery branches. Probe: with `PREVIOUS_RUN_CRASHED` True,
  `_after_show("some.epdf")` offered nothing and `_after_show(None)`
  offered. Double clicking the document you were working on is the usual
  way back in after a crash.
- Right: offer recovery whenever the flag is set, then load the path if
  the user declined (or load first, then offer; either order, but both
  happen).
- Confirmed by running.

### 4. test_ui_page.py is not deterministic

- File: `tests/test_ui_page.py`, the helpers `caret_end_of`, `run` and
  `call` (lines 74 to 110) and the checks that follow a caret move.
- Wrong: three runs gave 87, 97 and 98 of 98. The one captured failure
  shows Enter landing mid word, so a caret move issued through `run` was
  overtaken by the page's 40 millisecond `postState` timer or by the
  previous action still settling. A suite that passes on the third try
  cannot gate a release (CLAUDE.md: the worst failure mode is a green
  that means nothing).
- Right: after every caret move and every `apply`, wait for the next
  `state` message (bind `EVT_EDITOR_MESSAGE` in the test and wait for a
  state with the expected block) before reading the DOM; pump a fixed
  interval only as a last resort. Run it five times in a row and report
  five identical counts.
- Confirmed by running.

### 5. The 150 percent screenshot does not look like 150 percent

- File: `docs/screenshots/main-window-150.png`, against `main-window-100.png`.
- Wrong: the toolbar icons in the 150 file are smaller than in the 100
  file (about 14 pixels against 20), and the menu bar, status bar and
  title bar text are the same size in both. At 150 percent
  `toolbar.py` line 43 asks for 30 pixel icons. Either the capture was
  taken at 100 percent and named 150, or the bar shrank. Both files are
  1748 pixels wide.
- Right: a capture of the process running at 150 percent (system scaling
  set to 150, or a 150 percent monitor), where the icons are 30 pixels
  and the menu text is half again as large; the same for every dialog's
  150 file, which I did not open one by one.
- Suspect from looking.

### 6. Toolbar labels are never shown and cannot be turned on

- Files: `easypdf/ui/main_window.py` lines 279 to 310 (`_fit_toolbar`);
  `settings.py` `toolbar_labels`; `keymap.py` MENUS.
- Wrong: both main window screenshots show icons only, in a 1745 pixel
  window at 100 percent. `toolbar_labels` defaults to True but
  `_fit_toolbar` drops the labels whenever the labelled bar's best width
  exceeds the client width, and nothing in the menus or Preferences lets
  the user choose. Brief B14: "real icons ... and text labels available".
  As built, labels are available only on a window wider than the labelled
  bar, which at 100 percent on 1920 is not the case.
- Right: a View menu check item "Toolbar labels" that writes
  `toolbar_labels` and rebuilds the bar, and a labelled bar that fits a
  maximised 1920 window at 100 percent (shorter labels, or labels on the
  first two groups only). Then a screenshot with labels on.
- Suspect from reading and looking.

### 7. Recovery loads the snapshot on the UI thread

- File: `easypdf/ui/main_window.py` lines 1775 to 1799 (`_recover`).
- Wrong: `read_document(snapshot, "native")` and `sanitise(body)` run
  directly on the UI thread, unlike `_load_path`, which does both on a
  thread. A large recovered document (the 200 page, twenty picture case
  B5 asks to measure) blocks the window during the one moment the user
  most wants feedback.
- Right: route recovery through `_load_path`'s worker and set `modified`,
  `path` and `snapshot_path` in the `_loaded` callback.
- Suspect from reading.

### 8. A forced close deletes the snapshot of a modified document

- File: `easypdf/ui/main_window.py` lines 1801 to 1815 (`_on_close`).
- Wrong: when `event.CanVeto()` is False (Windows end session, or any
  forced close) the save prompt is skipped and line 1810 still calls
  `_discard_snapshot()`, so the one copy of the unsaved work goes with the
  process.
- Right: discard the snapshot only when the document is not modified, or
  when the prompt was shown and answered.
- Suspect from reading.

### 9. The export runs the checker twice and names the failed check by substring

- File: `easypdf/ui/main_window.py` lines 1077 and 1108.
- Wrong: line 1077 calls `pdfcheck.check(out)` after `export_html` even
  though `ExportResult.report` (`pdfexport.py` line 101, accepted by the
  amendment) already holds the checker's result, so every export checks
  the file twice. Line 1108 finds "which check stopped it" by searching
  the warnings for the letters "PDF/UA"; when no warning holds them the
  first line of the report reads "The PDF was written without the PDF/UA
  claim. " and nothing after it. B12 says the first line names the check.
- Right: use `result.report` when present, and take the failed check's
  name from it.
- Suspect from reading.

### 10. Strings shown by the window that are not in docs/STRINGS.md

- Files and lines, all Worker B's:
  - `main_window.py` 935: dialog title "Pictures without descriptions".
  - `main_window.py` 1322: dialog title "Remove table".
  - `main_window.py` 1318: "Description: none" (the remove picture
    question when the picture has no description).
  - `main_window.py` 1567: "Could not check. <reason>".
  - `main_window.py` 1228: "Title set to Untitled." when F2 clears the
    title; it reads as if a title were set.
  - `web_editor.py` 151 and 167: "The editor script failed: <reason>",
    which reaches `announce` through the save and export callbacks.
  - `hyperlink_dialog.py` 9: window title "Edit link".
  - `image_dialog.py` 97: window title "Picture properties"; 225: "No
    picture.".
  - The file dialog titles "Open a document", "Save as", "Export PDF",
    "Check a PDF" (`main_window.py` 789, 934, 1044, 1140).
- Right: list each under the Worker B heading, and make the blank rename
  say "Title cleared." (Tony rewrites).
- Suspect from reading (grep counts against STRINGS.md).

### 11. The update check decides failure by a substring of a sentence

- File: `easypdf/ui/main_window.py` line 1579.
- Wrong: `if message and "newest" not in message.lower(): problem = message`.
  The sentence comes from STRINGS.md and Tony has not read it; if it is
  reworded without the word "newest", every successful check is shown as
  a failure in the update dialog.
- Right: `appupdate.auto_check` returns a status the window can test, or
  the window compares against the constant the sentence came from.
- Suspect from reading.

### 12. Replace All takes the innerHTML route without the measurement B5 asked for

- File: `easypdf/editor_page.py` lines 819 to 841 and 854 to 875.
- Wrong: DECISIONS.md edit B5 says first try the clone plus select all
  plus `insertHTML` route, measure that headings, lists and strong
  survive, and fall back to keeping the previous body only if they do
  not. The code goes straight to `ed.innerHTML = clone.innerHTML` with
  `route: 'innerHTML'` and no comment saying the first route was tried.
  The fallback's Ctrl+Z works only while `ed.innerHTML` still equals the
  stored `after`; one keystroke later it is gone, and Chromium's own undo
  never saw the assignment.
- Right: measure the insertHTML route and record the result in the report
  and in a comment; if it fails, keep the fallback and say in the status
  line that Ctrl+Z restores only before the next edit.
- Suspect from reading.

### 13. The context menu never shows the current state

- File: `easypdf/ui/main_window.py` lines 695 to 709.
- Wrong: the context menu is built with `remember=False`, so its Bold,
  Italic, Underline and Strike check items and the style and alignment
  radio items are never checked; on bold text the menu says Bold
  unchecked.
- Right: after building, check the items from `self.state` the way
  `_sync_menus` does.
- Suspect from reading.

### 14. The wx side of the Applications key is bound to nothing

- File: `easypdf/ui/main_window.py` line 711; `keymap.py` `context_menu`
  entry (scope native, in no menu).
- Wrong: `on_context_menu` is reachable from no accelerator (native
  entries are left out of the wx table) and no menu item. With focus on
  the toolbar's Paragraph style choice, the Applications key and
  Shift+F10 do nothing. CONVENTIONS.md: context menu on the focused item.
- Right: bind `EVT_CONTEXT_MENU` on the frame and the toolbar to
  `on_context_menu`, or accept that the toolbar has no context menu and
  say so in KEYBOARD.md.
- Suspect from reading.

### 15. The unsaved changes prompt pumps the loop for up to sixty seconds

- File: `easypdf/ui/main_window.py` lines 551 to 572.
- Wrong: `_save_now_blocking` loops on `wx.Yield()` until the
  asynchronous save reports. While it pumps, the autosave timer, a
  handoff from a second launch and any menu event can run re-entrantly
  inside the save prompt.
- Right: acceptable if kept, but guard it: set `_closing` or a `_busy`
  flag that `_on_autosave_tick`, `open_document` and `_dispatch` respect
  while the pump runs.
- Suspect from reading.

### 16. Paste sanitises on the UI thread

- File: `easypdf/ui/web_editor.py` line 225 (`insert_html`) and
  `main_window.py` line 747.
- Wrong: every paste runs `htmlclean.normalise` on the UI thread. A large
  Word paste may take more than a blink; nothing was measured.
- Right: measure a fifty page Word paste; if it is over about 100
  milliseconds, sanitise on a thread and insert in the callback.
- Suspect from reading.

### 17. A dead expression in the key handler

- File: `easypdf/editor_page.py` line 190.
- Wrong: `if (c === 'f10' || c === 'shift+f10' && false)`. The
  `shift+f10 && false` half is always false. It is harmless because the
  native `context_menu` binding returns before this line, but it reads as
  an unfinished thought.
- Right: `if (c === 'f10')` with a comment that Shift+F10 is the native
  contextmenu path.
- Suspect from reading.

### 18. The describer gets only the title as context

- File: `easypdf/ui/main_window.py` line 1312 (`_context_for`).
- Wrong: the context handed to `DescribeImageDialog` is the document
  title alone. The caption and the paragraph before the figure are what
  make a description specific.
- Right: title, caption and the text of the block before the figure,
  through the page (`figureInfo` already carries the caption).
- Suspect from reading.

### 19. The first run screenshots show a strip of desktop

- Files: `docs/screenshots/main-window-100.png` and `main-window-150.png`.
- Wrong: about eight pixels of the desktop show down the left edge of
  both captures; the capture rectangle is off by the window's shadow
  margin.
- Right: capture the client rectangle from `GetRect()` plus the frame, or
  crop.
- Suspect from looking. Cosmetic.

## The screenshots

- `main-window-100.png`: finished. Icon toolbar with the paragraph style
  choice, white paper on a grey surround with a blue focus ring, four
  status fields (message, "Heading 2", "109 words", "en-US"), the window
  icon in the title bar. Nothing clipped. No toolbar labels (defect 6).
- `main-window-150.png`: not a 150 percent capture as far as I can tell
  (defect 5).
- `preferences-ai-150.png`: finished. Wrapped note, named fields, nothing
  clipped, readable. Half the page is empty below the model row, which is
  fine for a notebook page.
- `pictures-100.png`: finished. Heading line with counts, three readable
  rows, four buttons, nothing clipped.

## Checks the brief asked for, and what I found

- One handler per bound key: `keymap.py` is the one list; the page map,
  the wx table, the menus, the F1 text and `KEYBOARD.md` are all derived
  from it and `test_menus.py` asserts them (47 of 47). F5 is in
  `DENY_CHORDS`; Ctrl+F, Ctrl+P, Ctrl+U, Ctrl+Shift+I are app or page
  keys, so the page swallows them; DevTools is switched off in
  `web_editor.py` line 79. Real keystrokes are `test_keys.py`, not run
  here.
- Only sanitised HTML enters the page: `web_editor.load_body` and
  `insert_html` run `sanitise`; `_load_path` and `_recover` sanitise
  before `load_clean_body`; the drop and paste events post to Python.
  The CSP is proven by the test.
- Nothing slow on the UI thread: open, save, export, print, check,
  update check and download, autosave, the guide probe all run on threads
  with `wx.CallAfter` back; `BusyDialog.step` and
  `DownloadProgressDialog.step` use `wx.CallAfter`. Exceptions: defect 7
  (recovery) and defect 16 (paste, unmeasured).
- The three channels: `announce`, `announce_help`, `announce_answer` all
  call `note()`, which writes status field 0 at every level;
  `announce_help` speaks only at "all"; `hint()` speaks once per session.
  `announce_answer` is defined but has no caller, which is fine while no
  key only answers a question.
- No multi-line `wx.MessageBox` in Worker B's files; the questions go
  through `TextDialog`; `unsaved_changes` is a one line `wx.MessageDialog`.
- Accessible names: `test_ui_names.py` walks every dialog; `add_row`
  moves the static before the control in the tab order; `name_field`
  keeps the accessible object alive on the control.
- The undescribed picture contract: `editor_page.py` `figureHtml` (line
  794) writes `alt="" role="presentation"` only when `decorative` is
  set, `alt="" data-needs-alt="1"` when the description is blank, and a
  pasted picture gets `alt=""` with `data-needs-alt` (main_window.py 764).
  `image_dialog._on_ok` refuses a blank description unless the box is
  ticked. Honoured.
- Crash recovery gate: reads `paths.PREVIOUS_RUN_CRASHED` or
  `appupdate.RESTARTED_AFTER_UPDATE`, never `os._exit` from the frame.
  Defect 3 is the gap.
- Title before export: `_ensure_title` opens the properties with focus in
  the title for both Export and Print, and the PDF's file name and meta
  come from the title; "Untitled" reaches only the window title and the
  `.epdf` default file name.
- Worker C's mounts: `data-alt-source` is written as `ai:<provider>` from
  `provider_used` and cleared on a hand edit (`image_dialog.py` 249);
  Preferences uses `SetSizerAndFit` (`preferences_dialog.py` 42).
  Provider, model and document_name are defect 1.

## What is right

- The asynchronous wrapper: request ids in the returned JSON, results
  matched by id, errors drained oldest first, no synchronous RunScript.
- One key list feeding five consumers, with the AltGr gate on
  `event.key` and the layout proof aliases on `event.code`, exactly as
  decision 5 says.
- Lists rebuilt from measured Chromium behaviour with the measurements
  written beside the code; `defaultParagraphSeparator` p and bare text
  wrapped on input.
- The Velopack update path: body fetched before the flush, settings and
  geometry and a snapshot written in `_flush_for_restart`, the refused
  start shown in a dialog and the window carrying on.
- Recent documents with numbered mnemonics, the first run hint once, the
  guide item greyed when the page is not there.
- Every dialog built directly on the dialog, the preview refusing focus,
  the WCAG 2.4.4 hint on the link dialog, the header row default on.
- The status bar's four fields with the style field saying "Picture:
  <alt>" and ", in a link".
- `tools/nodashes.py` clean across the tree.

## For the coordinator

- `main.py` line 601 is a `wx.MessageBox` holding two lines ("is already
  running" and "Press Alt+Tab"). Not Worker B's file, but it breaks the
  standing rule; a `TextDialog` from `easypdf/ui/dialogs.py` fits.
- `test_keys.py` needs a quiet desktop; schedule it for Round 4 with the
  NVDA pass and read its "note:" lines then.
