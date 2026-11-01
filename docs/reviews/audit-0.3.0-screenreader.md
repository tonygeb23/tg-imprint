# TG Imprint 0.3.0 screen reader audit

## Verdict

- No blocker. Two serious faults should be fixed before the release goes out: the Accessibility panel summary is never spoken on arrival, and the toolbar buttons have no accessible name in the dark and yellow on black themes and in icons only mode.
- Everything else is minor.
- Score: **73 out of 100**. Deductions are listed at the end.
- Branch release/0.3.0, audited 2026-11-01 on Windows 11, Python 3.13.5, wxPython 4.2.5, Edge 156.

## How this was measured

- **Measured by running.** `python main.py` through a small launcher that wrote every `Speaker.say` call to a log instead of to the screen reader, so I could quote exactly what the app says. Isolated profile (APPDATA and LOCALAPPDATA pointed at a scratch folder), so Tony's settings were not touched.
- **Accessibility tree.** UI Automation through comtypes, and MSAA through oleacc (what NVDA actually reads for native controls). Win event hook (SetWinEventHook) for the events NVDA would receive.
- **Keyboard.** SendInput with scan codes. Delivery proved first: Tab and Shift+Tab walked New, Open, Make accessible, Analyse and back, matching UIA focus each time. Later runs checked the foreground process before every key.
- **Not measured.**
  - NVDA was running on the machine (not started by me). I did not drive it and did not capture what it says. Every statement about what NVDA "will" say is reasoned from the tree and from how NVDA treats these controls, and is marked as reasoned.
  - The desktop screen grab came back solid black (locked session), so nothing visual was measured: focus ring, contrast and layout are reasoned from `theme.py`, and `tests/test_display.py` passed 136 of 136.
  - Acrobat and Edge's viewer were not run. The PDF section is from reading the files with pikepdf.
- **Harness slips, disclosed.** Early on my script tapped Alt (it opened the menu bar; I removed that). Two script runs matched another worker's window called "TG Imprint selftest probe" by name and sent it Ctrl+N and Tab before I switched to matching by process id. Nothing in the repo was edited.

## Direct answers

- **Is every control named, with the right role?** Yes in the default look. Start screen buttons, recent list, panel list, Go button, password field and all report dialogs are named with correct roles (measured). No in the dark and yellow on black themes and in icons only mode: the toolbar buttons are nameless (finding 2).
- **Where does focus land?**
  - Start screen: New document button (measured).
  - After New: the editor, "Document text" (measured).
  - After closing a document (Ctrl+W): New document button, with "Document closed." spoken (measured).
  - After the password, analysis, repair and export dialogs: focus goes into the read only Report field. After the Document properties dialog opened from the panel: Title field. After Escape in each: back to the editor or New document (measured).
- **Does Ctrl+F6 work from inside the WebView2?** Yes (measured). From the editor with the panel shown: panel list, then the Paragraph style choice, then the editor. Ctrl+Shift+F6 goes the other way. Escape in the panel and F6 in the panel both return to the editor.
- **Is the panel summary reachable?** Only in the list's accessible description, and by object navigation to the static (finding 1). Confirmed: list accDescription is "1 to fix, 0 to review"; the focused row has no description.
- **Does anything steal focus or speak unasked?** Measured: typing with the panel hidden or shown moves no focus and speaks nothing from the app. A panel refresh keeps focus in the editor. One thing speaks unasked by design: the first run welcome, 900 ms after start, once. Notes dialog after a PDF import held focus (no theft measured over 15 seconds).
- **Is the password dialog named?** Yes. Title "Password needed", message read as its text, edit named "Password", PROTECTED state set (0x20000000), focus in the field. Wrong password gives "That password did not open the PDF. Type the password for locked.pdf." and asks again with focus intact.
- **Can a keyboard only user reach everything a mouse can?** Everything that does something, yes, through the menus and keys. Not the toolbar tools themselves and not the panel width (findings 6 and 11).
- **Are the sentences plain and first to the point?** Mostly. The export report is the model. The analysis and repair reports put a name or a path before the answer (finding 3).

## Findings

### 1. Panel summary is never spoken on arrival. SERIOUS

- **What I measured.**
  - `access_panel.py:52` to `55`: the summary is the list's accDescription only. MSAA `accDescription` on the list: "1 to fix, 0 to review". On the row (child 1): no description.
  - `main_window.py:953` and `971`: arriving by Ctrl+F6 or the Check tool calls `self.note(...)`, which writes the status bar only. Speech log after Ctrl+F6: empty. The status bar field changes silently.
- **What I reasoned.** NVDA reads the description of the focused object, not of its container, and focus lands on a row. So a user hears "Fix: The document has no title..." and never the split "1 to fix, 2 to review". The row position ("1 of 3") gives the total but not the split. Tab into the list from the Go button gives the same.
- **Fix.** After the focus move in `_go_to_pane` and `on_check_document`, queue the summary without interrupting the row: `self.speaker.say(self.panel.summary_text(), interrupt=False)`, gated like `announce_help` or as an answer to an explicit command. Keep the accessible name fixed, as the standing rule says. Optionally make the summary the first line of the detail static so object navigation finds it next to the list.

### 2. Toolbar buttons have no accessible name in drawn and icon only modes. SERIOUS

- **File and line.** `toolbar.py:181`: `AddTool(..., "" if self.drawn else self.label_for(action), ...)`. `label_for` also returns "" in icons only mode (`toolbar.py:159`). The tooltip (`shortHelp`) is not visible to MSAA on this control.
- **Measured.** Dark and icons_labels, yellow_on_black and icons, normal and icons: every button reads name None in MSAA and name '' in UIA (New, Open, Save, Bold, Italic, Bullets, Numbers, Link, Picture, Table, Check, Export PDF). Normal theme with labels, and the default normal icons_labels, are named.
- **Why it matters.** Yellow on black is the theme the low vision users pick. The code comment at `toolbar.py:183` says the name is never lost; it is lost here. Mouse, touch and NVDA object navigation hit blank buttons.
- **Fix.** Attach a `wx.Accessible` subclass to the toolbar whose `GetName(childId)` returns the tool's plain label from `keymap.entry(action).plain_label` (and the Bold and Italic state through GetState), stored on the toolbar so it is not collected. Add a test that reads MSAA names in all three themes and all three label modes. Shared code: the same drawn toolbar pattern is in the Drop Deck lineage, check whether it carries the same blank names.

### 3. Reports start with a name or a path, not the answer. SERIOUS (analysis), MINOR (repair)

- **Analysis.** `pdfanalysis.py:92`: `lines = [self.name, self.verdict]`. The file name is already the dialog title ("Analysis of locked.pdf"). Measured first line of the Report field: "locked.pdf"; the verdict is line 2.
- **Repair.** `main_window.py:161` (`repair_report`): line one is "Repaired copy: " followed by a 150 character path. What changed starts on line 3.
- **Reasoned.** On focus NVDA reads the caret line of a read only multiline edit, so the user hears the name or the path and has to press Down for the answer.
- **Fix.** Verdict first in `format_report`, name dropped (it is in the title). In the repair report put "What changed:" first and the path after it. The export report already leads with "The PDF/UA identifier was written: every check passed." which is right.
- **Also.** `pdfanalysis.py:95` produces "2 pages: 2 pages of text." Say "2 pages, all text." The "What to do:" list gives two alternative routes (rebuild, or repair) one after the other with nothing to say they are alternatives; say "Either open it in TG Imprint and export it, or use Repair a PDF" or number them. On a good file the only step is the PAC and veraPDF line under "What to do:", which asks for nothing; show it as a note.

### 4. Alt+R is claimed twice in the Analysis dialog. MINOR

- **File and line.** `main_window.py:1923` to `1924`: field label "&Report" and button "&Repair it".
- **Measured.** UIA AccessKey: Report edit Alt+r, Repair it Alt+r. The key cycles instead of acting. Nothing destructive.
- **Fix.** "Re&pair it" (Alt+P) or label the field "Re&port". The other report dialogs (Open &PDF, Open &folder, &Close, &Report) have no clash.

### 5. Keys do nothing, silently, on the start screen. MINOR

- **File and line.** `main_window.py:857` to `863` disables menu items that need a document; wx does not fire the accelerators of disabled items, so `perform()` at `main_window.py:643` to `645` never speaks "Nothing is open...".
- **Measured.** Ctrl+S, Ctrl+F6, Ctrl+Shift+F6, Ctrl+Shift+L, F6 on the start screen: no focus change, no speech.
- **Fix.** Either leave the accelerators live and let `perform()` answer, or say it from the frame's accelerator path. Greyed menu items are correct and can stay.

### 6. The toolbar is not keyboard reachable, and the "toolbar" pane is one choice box. MINOR

- **Measured.** UIA: every tool button focusable=0; only "Paragraph style" is a tab stop. `main_window.py:973` sends Ctrl+F6 to `toolbar.style` and nothing else. Tab from the panel goes list, Go, editor, list: the toolbar is outside the Tab ring.
- **Why only minor.** Every tool has a menu item and most have keys, so nothing is lost. But the manual says Ctrl+F6 goes to "the toolbar", which promises more than it gives.
- **Fix.** Word the help for `next_pane` as "the paragraph style box", or give the toolbar a real keyboard model (arrow keys between tools).

### 7. Panel detail text is hard wrapped and repeats the row. MINOR

- **File and line.** `access_panel.py:201`: `Wrap()` puts newlines into the label.
- **Measured.** Static name: "The document has no title. Set one in Document\nproperties." The same sentence is already the row text minus the "Fix:" prefix, so the detail adds nothing a screen reader user does not already hear.
- **Fix.** Put the useful extra sentence (why it matters, what to do) in the detail, or remove the detail for screen reader use. If it stays, use a read only multiline field so it wraps natively and can be focused.

### 8. Two small speech faults in the password flow. MINOR

- **Measured.** After a wrong password the app says "Checking locked.pdf." twice (`main_window.py:1890` runs again for the retry).
- **Cancel wording.** `main_window.py:163` and `1475`: Cancel on the password prompt says "Nothing was opened." even when the job was Analyse or Repair.
- **Fix.** Pass the job's noun into `_ask_for_password`, say it once.

### 9. Recent list shows file names only. MINOR

- **File and line.** `start_panel.py:156`. Two documents with the same name in different folders cannot be told apart by ear.
- **Fix.** "name, in folder" as the row text, or the folder as a second column.

### 10. Strings in the code are not all in `docs/STRINGS.md`. MINOR (process rule)

- **Checked by grep.** Not found in STRINGS.md: "That password did not open the PDF." (`pdfrepair.py:48`), the five analysis verdict sentences (`pdfanalysis.py:38` to `48`). The password sentence there also differs: STRINGS.md line 236 says "This PDF is protected by a password, so it cannot be opened." while `pdfrepair.py:47` ships "This PDF is protected by a password." The standing rule is that nothing in Tony's voice ships unread.
- **Fix.** Sync STRINGS.md with the code before Tony reads it.

### 11. The panel width can only be changed with the mouse. MINOR

- **File and line.** `main_window.py:912` (`_on_sash_moved`). The splitter sash has no keyboard route. A low vision keyboard user cannot widen the panel.
- **Fix.** Two View menu items, wider and narrower panel, or a width in Display options.

### 12. Selection event fires on the unfocused list at every rebuild. WATCH

- **Measured.** Showing the panel produced `EVENT_OBJECT_SELECTION` on the SysListView32 plus name change events on its statics and the status bar. No focus event, no app speech.
- **Not measured.** Whether NVDA voices the selection event. It normally ignores selection on an unfocused list, but this has to be listened to once with NVDA before release, as the standing rule requires.

### 13. Start screen buttons have no thick focus ring. MINOR, reasoned

- **File and line.** `start_panel.py:117` to `122`. The panel list gets the Display page ring through `focus_ring` (`access_panel.py:102`), the start screen buttons do not and rely on the system focus rectangle. On the owner drawn buttons in the dark themes I could not see what is drawn (screen grab was black).
- **Fix.** Register the buttons and the recent list with `focus_ring` in `StartPanel`, as the panel does.

### 14. Incidental, not part of this scope: the frozen selftest crashes with no console. MINOR

- **Observed.** Another worker's `TG Imprint.exe --selftest` showed a dialog "Failed to execute script 'main' ... 'NoneType' object has no attribute 'flush'". `main.py:643` calls `sys.stdout.flush()`; in a windowed frozen build `sys.stdout` is None.
- **Fix.** `if sys.stdout: sys.stdout.flush()`. Worth confirming before the build is signed off.

## Confirmed good

- Start screen tree: heading statics, Tab order New, Open, recent list, then the four PDF jobs; each button named, description set, decorative mark unfocusable; recent list named "Recent documents" and hidden when empty (measured).
- Panel: list named "Accessibility issues" with a stable name; rows say Fix or Review; the name never changes on refresh (measured: no NAME event on the list).
- Status bar: fields hold the message, style, words and language; skin has no name and is invisible to MSAA (measured).
- Escape in dialogs, Escape in the panel, Enter on a Title issue opening Document properties with focus in Title (measured).
- Export: title prompt with focus in the field, a spoken progress, a Report dialog led by the PDF/UA result, Close as default (measured).
- Page script keys: Ctrl+F6, Ctrl+Shift+F6, F6, Shift+F6 all arrive through the page handler (measured); F6 outside the document returns to it (code, `main_window.py:989`).

## The exported PDF

- **Measured by reading the 11 files `tools/verify_ua.py --keep` wrote** (fixture, plain, headings, nested lists, table, spanned table, pictures, links, quote and code, long, spanish) plus two of my own. The tool itself reported 11 of 11 pass veraPDF PDF/UA-1.
- **Present in every file:** MarkInfo Marked true, Lang en-US on the Document element, Info and XMP title, XMP pdfuaid part 1, DisplayDocTitle true, Tabs /S, outline entry per heading (the long file: 30 entries over 18 pages), all fonts embedded with ToUnicode.
- **Structure:** H1 to H6, P, L with LI, Lbl, LBody and nested lists with the right numbering, BlockQuote, Code, Table with Caption and TH Scope Column or Row and Headers on TD, Figure with Alt, the decorative picture left out, Link elements with annotations carrying /Contents and /StructParent.
- **Language:** a paragraph with `lang="fr"` gets /Lang on its P. A language mark on a few words is dropped, and the export says so in its report ("A mark on a few words does not reach the PDF. Put the language on the whole paragraph instead."). Honest and plain.
- **What NVDA in Acrobat will do (reasoned, not run):** headings by H, list and table navigation, header cells announced, figure alt read, links listed with names, title shown, language set so the voice is right. Every text run sits inside a `/NonStruct` wrapper under its H1 or P; that is valid and Acrobat treats it as transparent, so reading order should be intact.
- **What NVDA in Edge will do:** not known. I did not run Edge's viewer and cannot say how completely it exposes tables and lists. The file gives it everything the format allows.
- **Caveat on repaired and analysed PDFs.** The repaired copy of an untagged PDF stays untagged ("FAIL: Tagged PDF" in its own report). The repair dialog does not say that in its first lines; the user learns it ten lines down. Say it first: "The pages look the same but there is still no structure for a screen reader."
- **Odd title.** Repair set the title of a test file to its whole first sentence ("Hello world. This is an untagged test document with some words in it."). Long, and read at every open. Cap the guess or prefer the file name when the first line is a sentence.

## Score: 73 of 100

- **minus 6**: panel summary never spoken on arrival (1).
- **minus 6**: toolbar buttons nameless in dark, yellow on black and icons only (2).
- **minus 3**: analysis and repair reports lead with a name or path, wording of the steps (3).
- **minus 2**: keys silent on the start screen (5).
- **minus 2**: toolbar not keyboard reachable and "toolbar pane" is one box (6).
- **minus 1 each**: Alt+R clash (4), hard wrapped duplicate detail (7), double and wrong password speech (8), recent list without folders (9), STRINGS.md out of step (10), sash mouse only (11), no thick focus ring on the start screen (13).
- **minus 1**: unverified, not heard: the unfocused selection event (12).
- Not deducted, but open: nothing here was heard through NVDA, and the visuals could not be captured. Both must be done by a person before shipping, per CLAUDE.md.
