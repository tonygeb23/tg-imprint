# Brief: Worker B, the window, the editor and accessibility

You own everything the user sees and presses. Read, in order: `CLAUDE.md`,
`docs/ANALYSIS.md`, `docs/DECISIONS.md`, `docs/PLAN.md`, then
`Dropbox\TG Studios\CONVENTIONS.md` (the keyboard and speech contract) and
the first 120 lines of `Dropbox\TG Studios\TG Drop Deck\CLAUDE.md` (wx traps
already measured). If this brief and `DECISIONS.md` disagree,
`DECISIONS.md` wins.

Reference implementation for the shape of a TG Studios wx frame:
`Dropbox\TG Studios\TG Drop Deck\dropdeck\ui.py` lines 1618 to 1900 (the
update flow and the announce channels) and `dropdeck\dialogs.py` around
line 2630 (the speech level page in Preferences). Copy the shape.

## Files you own

Everything under `easypdf/ui/` (rewrite freely; delete the RICHEDIT
`editor.py`, `welcome_dialog.py`, `find_replace_dialog.py`,
`web_find_dialog.py` and `structure_panel.py` as you replace them),
`easypdf/editor_page.py` (the HTML, CSS and JavaScript inside the editor),
`easypdf/settings.py`, `tests/test_ui*.py`, `tests/test_menus.py`,
`tests/test_keys.py`, `docs/KEYBOARD.md`. Do not edit `main.py`,
`constants.py`, the shared modules, or anything Worker A or C owns.
Worker C hands you two dialogs and a settings panel (below); leave their
files alone and call them.

## The contract with `main.py`

`easypdf/ui/main_window.py` must export `create_frame(open_path=None) ->
wx.Frame`. The frame sets `self.SetIcons(appicon.bundle())`, owns a status
bar whose first field is wide enough for a sentence, and implements:

- `announce(text)`: spoken unless the level is none; status bar always.
- `announce_help(text)`: spoken only at all; status bar always.
- `announce_answer(text)`: always spoken; for keys whose only job is to
  answer a question. Status bar always.
- The update flow, copied from Drop Deck: a background check about four
  seconds after start through `appupdate.auto_check(paths.config_dir())`,
  Help then Check for updates through `updatedialog.ask_about_update`,
  `DownloadProgressDialog`, then `run_installer` or the portable swap.
  Every branch answers in a dialog, whatever the speech level.

`main.py` builds the frame, tags it for single instance, shows it. It will
pass a document path from the command line; open it.

Two more contract points, added 2026-09-09 after the Challenger's review:

- The frame exposes **`open_document(path)`**: run the unsaved-changes
  prompt, then load the file. `main.py` installs `easypdf/handoff.py`'s
  receiver on the frame, so a second launch with a document (a double
  click in Explorer while the app is open) calls this on the UI thread.
  One window, one document.
- **Crash recovery reads `paths.PREVIOUS_RUN_CRASHED`.** `main.py` writes
  a running marker before the window exists and removes it only after
  `MainLoop` returns cleanly. The frame offers `docfile.recoverable()`
  snapshots only when that flag is True, so a normal restart never nags.
  The frame must therefore close normally; never `os._exit` from the UI.

## The editor

One editor: a WebView2 page (`wx.html2`, Edge backend) holding a
`contenteditable` region. `CLAUDE.md` records that the backend, the
synchronous `RunScript`, the script message bridge and `execCommand` all
work here, that `execCommand` emits `<b>` and `<i>`, and that the WebView
must never be touched after its frame closes.

Things to **measure with NVDA running**, not assume, and to record in your
report:

- Whether NVDA announces "heading level 2", "list, two items", "link" and
  "graphic" while arrowing through the region, with and without
  `role="textbox" aria-multiline="true"` on it. Keep whichever variant
  gives structure announcements and clean typing. NVDA's speech can be
  read from its log when the log level is debug, or through the Speech
  Viewer; the accessibility tree can be read with UI Automation
  (`comtypes` is installed). Say which method you used.
- Which side wins a keyboard shortcut: the frame's accelerator table or the
  page's keydown handler. There must be exactly one handler per key and no
  double firing. Prove it by pressing the key with `wx.UIActionSimulator`
  after taking the foreground with `AttachThreadInput`, and reading the
  DOM back. A synthesised keystroke that goes nowhere looks exactly like a
  key that works, so do a control test first (type a letter, read it back).
- Whether the Applications key and Shift+F10 reach the page or wx. The
  context menu must open either way.
- Whether Edit menu Cut, Copy and Paste work through `execCommand` from
  Python (Chromium refuses clipboard commands without a user gesture in
  some paths). If not, do it with `navigator.clipboard` inside the page or
  with wx's clipboard and DOM insertion.
- Whether `Ctrl+Alt+digit` reaches the page (Windows treats it as AltGr).

The page's job: semantic markup only. `h1` to `h6`, `p`, `ul`/`ol`/`li`
(nested with Tab and Shift+Tab), `blockquote`, `figure > img[alt] +
figcaption`, `a[href]`, `strong`, `em`, `u`, `s`, `code`, `table` with
`th scope="col"`. Enter at the end of a heading starts a paragraph. Enter
on an empty list item leaves the list. Backspace at the start of a list
item unlists it. Paste from Word or a browser is cleaned to that set (strip
styles, spans, classes, fonts; keep structure). Undo must survive every
programmatic edit: use `execCommand` where it exists and
`document.execCommand('insertHTML')` for the rest so the browser's undo
stack sees it.

Selection state (block type, list type, alignment, bold, italic, underline,
strike, whether a figure or link is selected, and the figure's alt) is
posted to Python on every selection change so the toolbar, the status bar
and the properties dialogs read the truth. The status bar's style field
says "Heading 2", "Bullet list item", "Picture: <alt>" and so on.

## Keys

Word's map, plus the TG Studios contract. Every key below is in one
accelerator list that `_build_accelerators()` **returns**, so
`tests/test_keys.py` can assert it (wx offers no way to read a table back).

- File: `Ctrl+N` new, `Ctrl+O` open, `Ctrl+S` save, `Ctrl+Shift+S` save as,
  `Ctrl+W` close document, `Ctrl+Shift+E` export PDF, `Ctrl+P` print,
  `Alt+F4` exit. Recent files, the last eight, under File.
- Edit: `Ctrl+Z` `Ctrl+Y` `Ctrl+X` `Ctrl+C` `Ctrl+V` `Ctrl+A`, `Ctrl+F` find,
  `Ctrl+H` find and replace, `F3` find next, `Shift+F3` find previous.
- Format: `Ctrl+B` bold, **`Ctrl+I` italic** (with `Ctrl+Shift+I` kept as
  an alias only if DECISIONS.md says so), `Ctrl+U` underline,
  `Ctrl+Shift+K` strike, `Ctrl+Alt+1` to `6` headings, `Ctrl+Alt+0`
  normal, `Ctrl+Alt+8` bullets, `Ctrl+Alt+9` numbered, `Ctrl+Q` quote,
  `Ctrl+L` `Ctrl+E` `Ctrl+R` `Ctrl+J` alignment, `Ctrl+Shift+F` font.
- Insert: `Ctrl+K` link, **`Ctrl+Shift+P` picture** (unless DECISIONS.md
  says otherwise), `Ctrl+Shift+T` table.
- Tools: `Ctrl+D` describe picture, `Ctrl+Shift+D` describe document (both
  hand off to Worker C's dialogs), `Ctrl+,` preferences, `Ctrl+Shift+A`
  check accessibility of a PDF.
- View: `F6` `Shift+F6` next and previous heading, `Alt+F6` structure
  navigator, `Ctrl+Shift+Alt+P` pictures needing descriptions.
- Contract: `F1` keyboard help in a window with a read-only field, `F2`
  edit the description of the picture at the caret (or rename the document
  title when no picture is selected), `Alt+Enter` properties (picture
  properties when a picture is selected, else document properties),
  `Delete` removes the selected picture or table with a confirmation,
  `Escape` closes dialogs and never deletes, `Applications` key context
  menu offering what the menu bar offers.

Write `docs/KEYBOARD.md` from the same list the code uses, not by hand.

## Menus

File, Edit, Format (with Paragraph style and Alignment submenus), Insert,
Tools, View, Help. Help holds: Keyboard shortcuts, User guide on the web
(greyed with "not published yet" in the status bar if the page is not
there; `constants.USER_GUIDE_URL`), Check for updates, Donate
(`constants.DONATE_URL`), About (name, version, tagline, TG Studios, the
engine it found, in a read-only field). Nothing multi-line ever goes in a
`wx.MessageBox`.

## Dialogs

- **Document properties** (`Alt+Enter`): title, author, language (the
  BCP-47 picker plus a custom code), subject, page size, margins. Writes
  nothing until OK. Title is required before export: exporting with a blank
  title opens this dialog with focus in the title field; there is no
  "Untitled" default written into a PDF.
- **Insert picture** (`Ctrl+Shift+P`) and **picture properties**
  (`Alt+Enter` on a picture): file, preview (a `StaticBitmap` that refuses
  focus), description (required, or the decorative box ticked), an optional
  caption, width (a quarter, half, three quarters, full text width) and
  placement (left, centre, right), and a Describe button that opens Worker
  C's `DescribeImageDialog` and puts its answer in the description field
  for editing. Build controls directly on the dialog, never on an inner
  panel with `CreateButtonSizer` (the prototype's OK button was unclickable
  for exactly that reason).
- **Insert link** (`Ctrl+K`): text and address, with the WCAG 2.4.4 hint;
  editing an existing link pre-fills both.
- **Insert table**: rows, columns, first row is headers (default on).
- **Find and replace**: modeless, `window.find` for next and previous,
  replacement through DOM edits that keep formatting, Replace All done by
  walking text nodes, never by rewriting the whole document.
- **Structure navigator** (`Alt+F6`): the headings, indented by level,
  Enter jumps and returns focus to the editor.
- **Pictures** (`Ctrl+Shift+Alt+P`): every picture, its description or
  "no description", Edit and Describe buttons. This is what an imported PDF
  needs first.
- **Export**: runs Worker A's `export_html` on a thread with a progress
  dialog that speaks its steps through `announce_help`; then a result
  dialog with the checker's report in a read-only field, focus in the
  field, and buttons Open PDF, Open folder, Close. Warnings from the export
  go in the same field above the report.
- **Open**: `docfile.load` for every kind; PDF import on a thread with
  progress; afterwards, if pictures need descriptions, say how many and
  offer the Pictures dialog. An imported file is marked modified and Save
  becomes Save As in the native format.
- **Print** (`Ctrl+P`): export to a temp PDF, then `os.startfile(path,
  "print")`; if the verb fails, open the PDF and say so.
- **Preferences** (`Ctrl+,`): a notebook: Speech (the one setting, three
  levels, CONVENTIONS wording from `constants.SPEECH_LABELS`), Document
  defaults (page size, margins, font, language), AI (Worker C's
  `AISettingsPage`). Settings persist in `paths.settings_path()` through
  `easypdf/settings.py`, which also holds recent files and window geometry.
- **Autosave and recovery**: `docfile.snapshot` every
  `constants.AUTOSAVE_SECONDS` while modified; at start, if
  `docfile.recoverable()` is non-empty, offer to reopen, in a dialog with a
  read-only field naming the document and the time.
- **Unsaved changes**: Save, Don't Save, Cancel, as the prototype has.

## Speech, exactly as CONVENTIONS.md says

One setting, three levels, three channels, status bar written at every
level. A hint speaks once per session. "Nothing" means nothing except
`announce_answer`. Never rewrite an accessible Name on a value change.

## Visual finish (standing rule; look at a screenshot before calling it done)

A toolbar with real icons (draw them with a `GraphicsContext` the way
`appicon.py` does, sized for the DPI, with tooltips naming the key) and
text labels available; the editor page white like paper with a light grey
surround, a visible caret, focus rings; a status bar with four fields;
sensible minimum sizes; everything readable at 150 and 200 percent scale;
the window icon in the title bar and taskbar; Windows high contrast
respected in the page through `forced-colors`. Leave native controls'
colours alone (wx 3.2.9 has no dark mode for them). Take screenshots of
the main window and every dialog at 100 and 150 percent and put them in
`docs/screenshots/`.

## Tests, hand-rolled, `python tests/<file>.py`

- `test_menus.py`: every menu item has a handler; every accelerator in the
  returned list has a menu item; the contract keys are present; no two
  entries share a key; `docs/KEYBOARD.md` matches the list.
- `test_keys.py`: real keystrokes into the real editor after taking the
  foreground, with the control test first; Ctrl+B, Ctrl+I, Ctrl+Alt+2,
  Ctrl+Alt+8, Enter in a list, Tab in a list, Ctrl+K, read the DOM back.
- `test_ui_names.py`: walk every dialog's children; every focusable
  control has an accessible name or a preceding static label; no dead tab
  stop (the preview bitmap refuses focus); no `wx.MessageBox` with a
  newline in it anywhere under `easypdf/ui/` (grep).
- `test_ui_page.py`: the editor API through `RunScript`: set HTML, apply
  each block style, insert a link, insert a picture with alt, read the
  selection state back, find and replace preserving `strong`.
- `test_settings.py`: round trip, missing file, corrupt file, migration of
  a missing speech level to the default.

Prove at least one test can fail.

## Rules that bind you

- Every string the app shows or speaks goes in `docs/STRINGS.md` under
  your heading; menu labels that name a function are exempt.
- No em or en dashes anywhere. Clean the prototype's 92 as you rewrite.
- Nothing slow on the UI thread. Export, import, describe: a thread, then
  `wx.CallAfter`.
- A key already in the April build stays working unless `DECISIONS.md`
  moves it.
- Test with NVDA running. Say in your report exactly what NVDA said, and
  how you know.

## Report back with

What you built, the measured answers to the questions above, the test
files and counts, the screenshots, every string you added, anything you
need from Worker A, Worker C or the coordinator, and anything you left out
and why.
