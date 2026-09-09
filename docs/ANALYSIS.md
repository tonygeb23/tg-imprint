# Easy PDF, the enhanced analysis (2026-09-09)

What the April 2026 prototype is, what is wrong with it, what was measured
on this machine, and what the revival changes. Written before any code was
touched, so the committee argues from the same facts.

No em dashes or en dashes anywhere in this project. Tony's rule.

---

## 1. What was found

- **Location as found:** `Dropbox\AI\AI Apps\Easy PDF`. Moved on 2026-09-09
  to `Dropbox\TG Studios\Easy PDF`, where every TG Studios product lives.
- **Size:** 37 files, 495 KB. About 1,080 lines in `core/`, 3,571 in `ui/`.
- **State:** a working RICHEDIT prototype plus a half-finished WebView2
  editor behind `--web`. The April session notes record that the WebView2
  path "did not work yet" and was never verified. No tests. No git history.
  No installer, no update channel, no single instance, no icon, no DPI
  awareness, no speech, no selftest. Nothing a TG Studios program ships with.
- **Last touched:** 2026-04-26.

## 2. Measured on this machine, 2026-09-09

These facts decide the architecture. None of them are guesses.

- **WeasyPrint is not installed and cannot run here.** It needs Pango and
  GObject DLLs (the GTK runtime) and none are on this machine. Bundling GTK
  into an installer is 30 to 50 MB of native code for one function.
- **Microsoft Edge headless produces a genuinely tagged PDF.** Measured with
  `msedge --headless=new --print-to-pdf` on a sample document, then read
  back with pikepdf. The structure tree contained `H1, H2, P, Strong, Em,
  Code, Link (with OBJR to the annotation), L/LI/Lbl, BlockQuote, Figure
  with /Alt, Caption, Table/TR/TH/TD`. `/MarkInfo /Marked true`, `/Lang`
  from the html attribute, `/DisplayDocTitle true`, `/Tabs /S`, a parent
  tree, and every font subset-embedded. A decorative image (`alt=""`,
  `role="presentation"`) was correctly left out of the tree. Letter size
  and one inch margins from `@page` were honoured. About two seconds.
- **PyMuPDF cannot write a structure tree.** Its `Story` HTML layout wrote a
  PDF with no `/StructTreeRoot` at all. It reads PDFs well: text blocks,
  an xhtml view with heading guesses, and images. That is the import path.
- **The wx.html2 Edge backend (WebView2) works here.** Measured: backend
  available, `RunScript` returns values synchronously, `AddScriptMessageHandler`
  works, the JavaScript to Python bridge delivers messages, `execCommand`
  edits the DOM (it emits `<b>`, not `<strong>`), and the page reports
  Edge 152. So the April failure was in the app, not the platform. One trap:
  **the process segfaults at interpreter teardown after `MainLoop` returns**
  while a WebView2 is alive. Probes and the selftest must `os._exit`, the
  same rule Drop Deck's selftest already follows.
- **ReportLab, pikepdf, Pillow, PyMuPDF, cryptography, accessible_output2,
  PyInstaller and Inno Setup are all installed.** `google-genai` is
  installed; `anthropic` and `openai` are not, and are not needed: the
  provider layer in TG Drop Deck talks to all three over plain HTTPS.
- **Tony's Gemini key is already in Windows Credential Manager** under the
  Drop Deck name. Easy PDF will keep its own entry; nothing is copied.

## 3. Code and functions, module by module

### main.py
- A modal Welcome dialog blocks before the main window. It has no place in
  a program that must reopen its running copy, open a file from the command
  line, or be launched from a shortcut without a question first.
- No DPI awareness, no AppUserModelID, no single instance, no icon, no
  selftest, no `--finish-update`. All of these are standing rules.

### ui/editor.py (RICHEDIT50W)
- **Headings are stored as font size plus bold.** Change the size and the
  heading silently stops being one. Pasting bold 14pt text makes a heading.
- **The Heading 6 threshold is wrong.** Heading 6 is applied at 13pt, and
  the classifier reads 13pt bold as Heading 5, so every H6 exports as H5.
- **Lists are literal text.** A bullet is the characters "• " at the start
  of a line. A pasted bullet becomes a list item; a deleted space unmakes one.
- **`load()` clears every image and link.** Reopen a saved RTF and the
  export has no images and no link targets, with nothing said.
- **Replace All destroys formatting.** It calls `SetValue` on the plain
  text, so every heading, bold and link in the document is gone.
- **Links are recognised by colour.** Any text in RGB 0,0,180 is a link and
  the URL is guessed by substring matching, so two links whose text overlaps
  can swap targets.
- **Alignment applies to one line**, not the selection.
- **`_extract_runs` calls `GetStyle` per character**, one COM round trip
  each. Export time grows with every character in the document.
- RICHEDIT cannot expose heading, list or link roles to NVDA at all. That
  is the ceiling of this backend and the reason the WebView2 path exists.

### ui/web_editor.py (WebView2, contenteditable)
- The only backend in which NVDA says "heading level 1", "list, two items",
  "link", "graphic, alt text". Keep this one.
- **A failed `AddScriptMessageHandler` is swallowed**, after which the
  modified flag never sets, the toolbar never syncs, and nothing says so.
- **`go_to_next_heading` returns stale state.** The jump happens in JS, the
  Python side returns the style it knew before the jump.
- **Images are linked by absolute `file:///` path**, never embedded. Move
  the document, or send it to someone, and the images are gone.
- **Save writes no title or author**, only `lang`. Document Properties are
  lost between sessions.
- Heading ids are reused (`h_jump`), so two headings can share an id.
- Edit menu Cut, Copy and Paste go through `execCommand`, which Chromium
  refuses for clipboard commands without a user gesture. To be measured.
- `execCommand('bold')` emits `<b>`, not `<strong>`. Chromium tags `<b>`
  and `<strong>` the same in the PDF, but the saved HTML should be semantic.
- The frame's accelerator table and WebView2 both want Ctrl+B. Whether wx
  sees the key before Chromium does has to be measured, not assumed.

### ui/main_window.py
- Two backends selected by `isinstance`, so every feature is written twice
  and some are written once. Font dialog, find, structure navigator and the
  status bar all branch.
- **Export is a synchronous call on the UI thread.** With a two second
  engine that is a frozen window and a screen reader saying nothing.
- Print exports to a temp file and opens the viewer; it does not print.
- `F1` shows a `wx.MessageBox`. A screen reader reads it once and it cannot
  be reviewed. CONVENTIONS.md: help is readable text in a window.
- About has no version number.
- Nothing from CONVENTIONS.md: no `Alt+Enter` properties, no context menu,
  no speech setting, no Help items for updates, guide or donate, no recent
  files, no `Ctrl+W`.
- `_on_doc_props` marks the document modified only on OK. Correct.

### ui/toolbar.py
- `TB_NOICONS | TB_TEXT`: a text-only toolbar. Visually unfinished by the
  standing rule. Every tool wants an icon and a tooltip naming the key.
- The toolbar's Insert Image bypasses the frame and never marks the
  document modified.
- The size spinner on the WebView2 path maps points to `execCommand
  fontSize` 1 to 7, so 11pt and 13pt become the same size.

### ui/image_dialog.py
- **The OK button is unclickable with a mouse.** Content is built on an
  inner `wx.Panel` and `CreateButtonSizer` parents the buttons to the
  dialog, so they render underneath the panel. The April notes list this as
  the next fix; it was never made. Keyboard still works, which is why a
  blind developer could not see it.
- Alt text is required or the image is declared decorative. Correct, keep.
- No placement control at all: no width, no alignment, no caption choice.

### ui/hyperlink_dialog.py, ui/doc_properties_dialog.py
- Both had the same button bug and were fixed. Fine.
- Document Properties returns "Untitled" for a blank title, which then
  satisfies the "title required before export" guard. A PDF titled
  "Untitled" is what a screen reader will announce.

### ui/structure_panel.py
- Operator precedence bug in the frame style: `A | B & ~C & ~D` applies the
  masks to `B` only, so the window keeps its maximise box and resize border.
  Harmless, but not what was written.
- Contains an em dash in a spoken string.

### ui/find_replace_dialog.py, ui/web_find_dialog.py
- RICHEDIT Replace All destroys formatting (above).
- The WebView2 Replace All loops on `window.find` and can run away when
  the replacement contains the search text; the 10,000 guard is the only stop.

### core/pdf_export.py
- Three tiers: WeasyPrint (absent), ReportLab (untagged), pikepdf patch.
- **The byte-level fallback patch corrupts the PDF.** It inserts bytes into
  the file without rebuilding the cross reference table, so every offset
  after the insertion point is wrong. A reader that trusts the xref opens
  garbage.
- An untagged fallback is the wrong failure for an accessibility product:
  it produces a PDF that looks finished and is not accessible, silently.

### core/pdf_validator.py
- Six checks, all catalogue-level. It cannot tell a tagged document from one
  where half the text is outside the tree. Needs: every figure has Alt,
  heading levels do not skip, fonts embedded, every page's content is
  marked, tab order set, and the XMP identifier.

### core/html_builder.py, core/document.py, core/rtc_parser.py
- The HTML builder is sound: semantic elements, `strong`/`em`, underline
  kept separate from links, decorative images as `alt=""`.
- `Run.code` exists in the model and nothing in the UI ever sets it.
- The Document model only matters for the RICHEDIT path.

## 4. Accessibility, as a screen reader user meets it

- **Editor semantics:** only WebView2 gives NVDA heading, list and link
  roles inside the editor. That is the product; RICHEDIT is the compromise.
- **Nothing is ever spoken by the app.** Export progress, "PDF saved",
  "no next heading" all go to the status bar or a MessageBox. Standing rule:
  three channels, one setting, status bar written at every level.
- **MessageBox for anything longer than a sentence** (F1, About, export
  result) cannot be reviewed. Read-only text controls in real dialogs.
- **Focus after actions** is mostly handled (`SetFocus` after formatting).
- **Alt text enforcement** is right and stays. The decorative checkbox is
  the correct WCAG 1.1.1 shape.
- **Language is set** on the document and the PDF. Correct.
- **Dead tab stop:** the image preview `StaticBitmap` has a name and no
  purpose for a keyboard user; it must refuse focus.
- **No high contrast or dark mode consideration** anywhere.

## 5. Menu structure, as found and as it should be

As found: File, Edit, Format, Insert, View, Help. Missing against
CONVENTIONS.md: `Alt+Enter` Document Properties, `Ctrl+F` present (good),
context menu on the editor, Help with Check for updates, User guide, Donate,
Keyboard shortcuts as a real window; a Tools or Describe menu for the AI
work; Recent files; a speech setting in Preferences.

Keyboard map faults:
- **`Ctrl+I` inserts an image.** In every word processor on earth `Ctrl+I`
  is italic. Nobody has been taught this app's map yet, so this is the one
  moment it can be fixed for free. Proposed: `Ctrl+I` italic, `Ctrl+Shift+I`
  insert image. `Ctrl+Shift+I` italic stays as an alias, since it was in the
  April build.
- `Ctrl+E` centre, `Ctrl+L` left, `Ctrl+R` right, `Ctrl+J` justify: the
  Word map, keep.
- `Ctrl+Alt+1..6` headings, `Ctrl+Alt+0` normal: the Word map, keep.
  Measure that WebView2 does not eat `Ctrl+Alt` (AltGr) combinations.
- `F6`/`Shift+F6` next and previous heading, `Alt+F6` structure: keep.
- `Ctrl+Q` block quote: unusual but harmless, keep.
- `Ctrl+K` hyperlink: the Word map, keep.
- Add `Ctrl+W` close document, `Alt+Enter` properties, `Ctrl+D` describe
  image, `Ctrl+Shift+D` describe document, `Applications` key context menu.

## 6. File encoding, saving, creating, reading

- **Two native formats today:** RTF from RICHEDIT and HTML from WebView2.
  A document made in one cannot be opened by the other.
- **Proposed single native format:** UTF-8 HTML, extension `.html`, with
  the title, author and language in `<head>`, every image embedded as a
  `data:` URI so the file is self-contained, and a `generator` meta so the
  app knows its own files. It opens in any browser, so it is never trapped.
- **Reading:** open `.html` (native), `.txt`, `.md` (Markdown, which Tony
  writes constantly), `.rtf` as plain text, and **`.pdf` via PyMuPDF**,
  which turns a PDF someone sent into an editable document: headings from
  font size, paragraphs, images pulled out, and each image offered to the
  describer for alt text. That is "make this PDF accessible", and it is the
  feature this audience has no tool for.
- **Creating:** New opens a blank document at once. No welcome dialog.
- **Autosave / recovery:** a timed snapshot to the config folder, restored
  on next launch if the app did not close cleanly.

## 7. Tagging, as PDF/UA-1 needs it

What PDF/UA-1 requires and where each requirement is met:

| Requirement | Met by |
|---|---|
| All content tagged, structure tree present | Chromium engine (measured) |
| Headings H1 to H6, no skipped levels | Editor enforces; validator reports |
| Figures carry Alt; decorative are artifacts | Image dialog (required alt); Chromium (measured) |
| Links as Link elements with OBJR | Chromium (measured) |
| Lists as L/LI/Lbl/LBody | Chromium (measured, LBody absent; NonStruct used) |
| `/MarkInfo /Marked true` | Chromium (measured) |
| `/Lang` on the catalogue | Chromium from `<html lang>` (measured) |
| `/ViewerPreferences /DisplayDocTitle true` | Chromium (measured); patch re-asserts |
| Title in XMP `dc:title` and Info | Info measured; XMP by pikepdf patch |
| XMP `pdfuaid:part = 1` | pikepdf patch |
| Fonts embedded | Chromium (measured, subsets) |
| Tab order `/Tabs /S` | Chromium (measured) |
| Creator and Producer honest | pikepdf patch sets the app name |

Gaps to watch: Chromium wraps text runs in `NonStruct`, which validators
accept; it emits no `LBody`, which PAC may flag as a warning; tables need
`<th scope>` for header semantics. The in-app checker will report each of
these by name.

## 8. Image placement

As found: RICHEDIT shows a text marker and never the picture; WebView2
drops a `<figure>` at the caret with no options. Proposed: the Insert Image
dialog gains **Width** (a quarter, half, three quarters, or the full text
width) and **Placement** (left, centre, right), and the caption is optional
and separate from the alt text, because a caption is for everyone and alt
text is for people who cannot see the picture. `Alt+Enter` on a figure
opens its properties to change any of these; `F2` on a figure edits its
alt text. Chromium honours the resulting CSS in the PDF.

## 9. Document describer with Claude, ChatGPT or Gemini

Not present today. TG Drop Deck shipped exactly this provider layer on
2026-09-08 (`dropdeck/vision.py`, `dropdeck/secrets.py`): three providers
over plain HTTPS, keys in Windows Credential Manager, model as a setting
with a moving-alias default, a model list fetched live, every failure
translated into a sentence a blind user can act on, and consent before
anything leaves the machine. Copy it, do not reinvent it.

What it does here:
- **Describe image (`Ctrl+D`)**: the selected figure, or the one being
  inserted, is sent and the answer lands in the alt text field for the user
  to edit. Never written into the document without the user seeing it.
- **Describe document (`Ctrl+Shift+D`)**: the document text and every
  image go out, and the answer is a spoken and readable summary: what the
  document is, its structure, what each picture shows, and anything an
  accessibility check would flag. For an imported PDF this is the first
  thing a blind user wants to know.
- **Consent every time** a whole document leaves the machine, naming the
  provider. An image on its own asks once per session.
- **Keys never in a document file, never in the config JSON**, never shown
  in full.

## 10. Decisions proposed to the committee

1. **One editor: WebView2.** Delete the RICHEDIT backend and its parser.
2. **One engine: Chromium** (Edge, then Chrome) headless print, plus the
   pikepdf metadata patch. Delete WeasyPrint and ReportLab. If no Chromium
   browser exists, say so and offer HTML; never ship an untagged PDF.
3. **One native format: self-contained UTF-8 HTML.** Import txt, md, rtf,
   pdf.
4. **No welcome dialog.** Open to a blank document or the file named on
   the command line.
5. **`Ctrl+I` is italic.** `Ctrl+Shift+I` inserts an image.
6. **The app is called Easy PDF**, a TG Studios program. The display name is
   one constant; the slug `EasyPDF`, the mutex name, the AppId GUID and the
   feed name are frozen at first release and must not change if the display
   name does.
7. **Free, with the donate link**, like Drop Deck and the Prompt Vault.
   Pricing is Tony's call; nothing here assumes it.
8. **The describer copies Drop Deck's provider layer** and its rules.
9. **Everything a TG Studios program ships with, in v1:** self-update,
   single instance, installer plus zip, selftest, icon, DPI awareness,
   three speech levels, CONVENTIONS keys, tests, private GitHub repo,
   TG Stats rule ready.
10. **Publishing waits for Tony.** Build, rehearse and prove; do not upload
    the manifest, the site page or the announcement until he says go.
