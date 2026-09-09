# Easy PDF, working notes

Accessible document authoring that exports tagged PDF/UA output, reads a
PDF somebody sent so it can be made accessible, and describes pictures with
Claude, ChatGPT or Gemini on the user's own key. wxPython, screen reader
first, a TG Studios program beside [TG Drop Deck](../TG%20Drop%20Deck/CLAUDE.md)
and the Prompt Vault.

Revived 2026-09-09 from an April 2026 prototype. `docs/ANALYSIS.md` is the
audit of what was found, `docs/PLAN.md` the committee and file ownership,
`docs/DECISIONS.md` the settled decisions, `docs/STRINGS.md` every visible
string awaiting Tony's approval.

## Standing rules

- **Every user-facing change is tested with NVDA actually running.**
- **wxPython only.** Never tkinter, never Qt. The editor is a WebView2
  `contenteditable` surface, because RICHEDIT cannot expose heading, list or
  link roles to a screen reader at all.
- **No em dashes or en dashes. Anywhere.** Code, comments, docs, strings,
  commit messages. `python tools/nodashes.py` reports them, `--fix` removes
  them; read the diff afterwards. `tests/test_nodashes.py` fails the build.
- **No new visible strings in Tony's voice ship unread.** List every string
  the app shows or speaks in `docs/STRINGS.md`.
- **Never rewrite a control's accessible Name on a value change.** It
  restarts the announcement under a screen reader.
- **Never `wx.MessageBox` for anything somebody might want to re-read.**
  A dialog with a read-only multiline field, focus in the field.
- **Speech: one setting, three levels, three channels**, and all of them
  write the status bar at every level. See `constants.py` and
  `TG Studios\CONVENTIONS.md`. Drop Deck's `ui.py` `announce*` methods are
  the reference.
- **Nothing on the UI thread that can take more than a blink.** Export,
  import, describing: a thread, then `wx.CallAfter`.
- **Nothing leaves the machine without consent** that names the provider.
  A whole document asks every time; a single picture asks once per session.
- **Never ship an untagged PDF.** If no Chromium browser can be found, say so
  and offer the HTML; an accessibility product that quietly produces an
  inaccessible file is worse than one that refuses.
- **Only sanitised HTML enters the editor page, and the page carries a
  Content Security Policy.** A received file ran its `onerror` handler
  inside the editor when loaded raw (CHALLENGE.md W11). Load, paste,
  import, save and export all go through `htmlclean.normalise`.
- **The native document is `.epdf`**, self-contained HTML inside a file
  type the installer registers. `.html` is an import and an export.
- **The frozen block in `easypdf/constants.py` and the AppId GUID in
  `tools/easypdf.iss` never change.** `tests/test_scaffold.py` asserts them.
- **Runs on the global Python 3.13.5, no venv**, like the other apps.
- **Build outside Dropbox.** `tools/build_release.py` does; do not point
  PyInstaller into this tree.

## Measured on this machine, 2026-09-09

- **Edge headless is the PDF engine.** `msedge --headless=new
  --print-to-pdf` writes a tagged PDF: H1 to H6, P, Strong, Em, Code, Link
  with OBJR, L/LI/Lbl, BlockQuote, Figure with Alt, Caption, Table/TR/TH/TD,
  MarkInfo, Lang from `<html lang>`, DisplayDocTitle, Tabs /S, subset
  embedded fonts, decorative images left out. About two seconds. Chrome has
  the same engine and is the fallback. pikepdf adds the XMP `pdfuaid:part`
  identifier, `dc:title`, and honest Creator and Producer strings.
- **PyMuPDF writes no structure tree** (its Story API), so it is only ever
  the reader. **WeasyPrint needs a GTK runtime that is not here** and is
  not used.
- **wx.html2's Edge backend works:** `AddScriptMessageHandler`, the JS
  to Python bridge, `RunScriptAsync` with `EVT_WEBVIEW_SCRIPT_RESULT`, and
  `execCommand`. **Synchronous `RunScript` works before the editor has
  focus and hung in two of four focused runs with NVDA running**
  (CHALLENGE.md W2), so the editor API is asynchronous, always.
- **`execCommand` emits `<b>`, `<i>`, `<font>` and `<div>`, and Chromium
  tags `b`, `i`, `u`, `span lang`, `div` and `pre` as nothing in the PDF**
  (a div's text lands in NonStruct with no P; measured 2026-09-09 by the
  Challenger and again by the Overseer). Only `strong`, `em`, `code`, `a`,
  headings, `p`, lists, `blockquote`, `figure` and tables are tagged. So
  normalisation before save and export is mandatory, not tidy-up.
- **With the WebView2 focused, no wx accelerator fires at all** (W4); the
  page sees every key, Chromium's own bindings act first (W5), and F5,
  Ctrl+F and Ctrl+P damage or hijack the document (W6). The whole keyboard
  contract lives in the page, in a capture-phase keydown handler that
  calls preventDefault and forwards to Python.
- **Never touch the WebView after its frame has closed.** A probe that
  called a WebView method after `MainLoop` returned segfaulted (exit 139)
  with no output. A normal frame close is clean; `app.Destroy()` after the
  loop is clean. **Do not `Destroy()` the WebView yourself in `EVT_CLOSE`**
  before skipping the event: measured, that crashes too. Let the frame own
  it.
- **Probes and the selftest that build a WebView and then stop the loop
  themselves must `os._exit`**, as Drop Deck's selftest does.
- **`WebView2Loader.dll` is not collected by PyInstaller.**
  `tools/build_release.py` adds it beside wx's own DLLs; the selftest loads a
  page and reads the DOM back to prove it shipped.
- **wx traps already measured in Drop Deck apply here** (its `CLAUDE.md`):
  `SetProcessDpiAwarenessContext` needs `c_void_p(-4)`, native `wx.Button`
  clips labels, `&` in a label is eaten by MSAA (`&&`), `wx.SL_LABELS`
  destroys a slider's name, `wx.StaticText` never wraps without `Wrap()`,
  `FindWindowById` is a global lookup, `Freeze()` clears WS_VISIBLE for MSAA
  while frozen, an unset `wx.TextAttr` field is not applied on MSW, and
  `wx.SearchCtrl`'s inner edit is unnamed.
- **`CreateButtonSizer` buttons belong to the dialog, not to an inner
  panel.** Build dialog content directly on the dialog; the April image
  dialog's OK button was unclickable with a mouse because of this.

## Layout

```
main.py                 DPI, taskbar identity, single instance, selftest, entry
launch.pyw              what the desktop shortcut runs (pythonw, no console)
easypdf/constants.py    names, the frozen block, speech levels, page defaults
easypdf/paths.py        config, recent, autosave folders; frozen or source
easypdf/singleinstance.py, updatedialog.py, speech.py   byte-identical to Drop Deck
easypdf/appupdate.py    Drop Deck's update client; only the marked block differs
easypdf/secrets.py      Credential Manager; prefix "Easy PDF AI key: "
easypdf/ai.py           the three-provider layer (from Drop Deck's vision.py)
easypdf/appicon.py      the mark, drawn at any size; feeds the .ico
easypdf/ui/             the window, the editor page, every dialog
tools/build_release.py  PyInstaller + Inno Setup, outside Dropbox
tools/release_app.py    sign, rehearse, publish, verify the update feed
tools/easypdf.iss       the installer; AppId frozen
tools/nodashes.py       the dash rule
tests/                  hand-rolled, one file each: python tests/<file>.py
```

## Running, testing, building

```
python main.py
python main.py "some document.html"
python tests/test_scaffold.py          # and every other tests/*.py, one at a time
python main.py --selftest --selftest-out report.txt
python tools/build_release.py
"%LOCALAPPDATA%\TG Studios Build\easy-pdf\dist\Easy PDF\Easy PDF.exe" --selftest --selftest-out report.txt
python tools/release_app.py rehearse   # never publish without Tony's go
```

The suites are hand-rolled scripts, not pytest. `python -m pytest` collects
nothing and reports success, which is the worst possible failure mode. Run
each file.

## Publishing

`TG Studios\RELEASING.md` is the pipeline. Nothing is uploaded, no page goes
on tgstudios.app and nothing is announced until Tony says go, because the
strings in `docs/STRINGS.md` are in his voice and he has not read them yet.
