# Easy PDF, the decisions (2026-09-09)

> **Renamed 2026-09-09.** Tony chose **TG Imprint**. Every path below that
> reads `easypdf/` is now `tgimprint/`, the document extension is
> `.imprint`, and the frozen names are `TGImprint`, `tg-imprint` and
> `TGStudios.TGImprint`. The old name is left in this document because it
> is the record of how the decision was reached.



Round 1 of the Overseer. One entry per decision in `ANALYSIS.md` section
10, then one per risk in `CHALLENGE.md`. Each entry gives the decision, one
paragraph of why, and what it changes in the briefs. The last section,
"Changes to the briefs", is the list of exact edits the coordinator applies
before the workers start. Nothing in this file has been implemented.

No em dashes or en dashes anywhere in this file. Tony's rule.

## How these were settled

- A standing rule in `CONVENTIONS.md`, `RELEASING.md` or the project
  `CLAUDE.md` settles an argument. Where the Challenger argued against a
  rule, the rule stands and the entry says so.
- A measured fact beats an argument. Where the Challenger's measurement
  contradicts `ANALYSIS.md`, the entry says which I believe and why. Two of
  the load bearing ones I measured again myself, below.
- Decisions that are Tony's are recorded as his, with the working
  assumption the work proceeds under. Nobody waits on them.
- Scope: every addition names the brief it lands in; every cut says what is
  lost. The definition of done in `PLAN.md` is the bar.

## What I measured myself

Scripts in the session scratchpad: `tag_probe.py` and `dpi_probe.py`.

- Inline tagging. One probe page rendered with the Edge browser and with the
  WebView2 runtime's own msedge.exe (Program Files (x86), Microsoft,
  EdgeCore, 152.0.4191.66) gave byte identical 65,999 byte PDFs. In the
  structure tree: `strong` became Strong, `em` became Em, `code` became
  Code. `b`, `i`, `u` and a `span` with `lang` became NonStruct with
  nothing semantic. A `div` put its text in NonStruct straight under
  Document with no P. A `p` with `lang` carried Lang. An `img` with no
  `alt` became a Figure with no Alt. The figure with alt became Figure with
  the Alt and a Caption. This confirms the Challenger's E5 and contradicts
  `ANALYSIS.md` section 3, which asserted that `b` and `strong` tag the
  same. They do not. Normalisation before export is mandatory.
- The header and footer flag. With `--no-pdf-header-footer` the page text
  held no date, no file path and no page number. The flag works. A test
  keeps it working (edit A8).
- DPI. The same WebView2 page inside a process that called
  `SetProcessDpiAwarenessContext(c_void_p(-4))`, exactly as `main.py` does,
  reported devicePixelRatio 1.5 and a wx scale factor of 1.5 on this 150
  percent display. Without the call: 1 and 1.0. `main.py`'s call is enough
  for a source run. The frozen build proves it in the selftest (edit K6).
- The runtime's location. The registry key for the WebView2 runtime (HKLM,
  SOFTWARE, WOW6432Node, Microsoft, EdgeUpdate, Clients,
  {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}) has pv 152.0.4191.66 and location
  `C:\Program Files (x86)\Microsoft\EdgeWebView\Application`, which holds
  no msedge.exe. `EdgeCore\152.0.4191.66` holds msedge.exe and
  msedgewebview2.exe. The Challenger's note stands: a finder must try both
  folders and prove the one it picks.

Where I did not measure, and what I believe:

- The synchronous `RunScript` hang (Challenger W2: two of four focused runs
  with NVDA running). `CLAUDE.md` says synchronous `RunScript` works, and it
  was measured before the editor had focus; `main.py`'s selftest calls it on
  page load, before any input. The Challenger's runs had the editor focused
  after a keystroke, which is what production looks like. The two do not
  contradict each other; they were measured under different conditions,
  and the Challenger's is the condition the product lives in. A
  non-deterministic hang that freezes the window and silences the screen
  reader is disqualifying, and ten clean tries of my own would not disprove
  a two in four fault, so I did not try. The editor API is asynchronous.

## Working assumptions (Tony's decisions, recorded as his)

The work proceeds under these. None is decided here.

- The display name is "Easy PDF", as scaffolded. See decision 6 for the
  collision, the rename touch list, and the deadline.
- Version 1.0.0 is free, with the donate link. See decision 7.
- Every string in `docs/STRINGS.md` is a draft until he has read it,
  including the prompts, the consent questions, the first run hint, the
  export warnings and the checker's sentences.
- Nothing is uploaded, no page goes on tgstudios.app and nothing is
  announced until he says go. See decision 10 for the approval packet.
- Two downloads need his yes: veraPDF (Java 17 is here) and PAC 2024. See
  decision 2.

## The ten decisions

### Decision 1: one editor, WebView2. Keep, with eight conditions

Decision: keep. The RICHEDIT backend and its parser go. The eight
conditions the Challenger set are adopted as written, with the changes
noted, and they are conditions, not suggestions.

Why: `CLAUDE.md` already makes this a standing rule (wxPython only; the
editor is a WebView2 contenteditable surface, because RICHEDIT cannot
expose heading, list or link roles). The Challenger's case against is a
list of real costs that the plan had not priced, and every one of them
was measured with a page side fix that works (W1, W3, W6): an asynchronous
API, keys caught in the page, normalisation, undoable edits, a sanitiser,
a startup guard, DPI awareness. Those go into the briefs. The runtime
argument (machines without WebView2) is answered by the startup guard,
which says what is missing and where to get it, and by the fact that
RICHEDIT as a fallback would hand the April defects to the people least
able to tell.

The conditions:

1. The editor API is asynchronous: `RunScriptAsync` with
   `EVT_WEBVIEW_SCRIPT_RESULT`, plus the message bridge. No synchronous
   `RunScript` on the UI thread once the editor exists. Selection state and
   word count come from the page's own messages. A watchdog test issues a
   script 700 milliseconds after a keystroke into a focused editor and
   fails if no answer arrives in five seconds.
2. The keyboard map lives in the page: a capture phase `keydown` handler,
   `preventDefault`, `postMessage` to Python. The wx accelerator table
   serves only when focus is outside the editor. The page blocks F5,
   Ctrl+R, Ctrl+Shift+R, F3, Ctrl+G, F12, Ctrl+Shift+I, Ctrl+Shift+J,
   Ctrl+Shift+C, Ctrl+U, Ctrl+S, Ctrl+O, Ctrl+P, Ctrl+F and every key in
   the app's map, and forwards the app's keys. One list in Python feeds
   the wx table, the page's map, the menus and `KEYBOARD.md`.
3. `defaultParagraphSeparator` is `p`; bare text in the editing host is
   wrapped in a `p`; `b`, `i`, `font`, `div` and style spans are normalised
   before save and before export by Worker A's one sanitiser.
4. Every programmatic edit goes through `execCommand('insertHTML')` or
   `insertText` so the browser's undo stack sees it. Load resets the
   history. Replace All must be undoable with one Ctrl+Z (decision on the
   route under risk 4).
5. One sanitiser, in Python (`htmlclean.normalise`), runs on load, paste
   and import. The page carries a Content Security Policy as the second
   line (risk 3).
6. A startup guard in `main.py`: if the Edge backend is unavailable or
   `WebView2Loader.dll` is missing, a real dialog says so, names the
   WebView2 runtime download, copies the address to the clipboard, and
   exits (coordinator, edit K4).
7. DPI awareness is set before wx loads. Measured working today; the
   frozen build's selftest records devicePixelRatio (edit K6).
8. NVDA is the gate, as the standing rule says. One Narrator pass is added
   to the Round 4 audit as information, not as a gate: its defects are
   listed and fixed when cheap. JAWS is not on this machine; the site says
   the app was tested with NVDA and asks JAWS users to write in.

Brief changes: worker-b.md edits B1 to B6, B15, B16; worker-a.md edits A2,
A4; coordinator edits K4, K6; overseer.md edit O1.

### Decision 2: one engine, Chromium headless print. Modify

Decision: modify, in six places. The engine order is the Edge browser,
then the WebView2 runtime's own msedge.exe, then Chrome. The flags
`--no-pdf-header-footer` and `--generate-pdf-document-outline` are always
on and a test proves the first. The PDF/UA identifier is written only when
the in-app checker's gate passes. `b`, `i`, `div`, `pre`, inline `lang`
and alt-less images are normalised before printing. A test asserts
Producer and Creator. veraPDF runs once on the sample set at the audit if
Tony approves the download; PAC by hand. Right to left text is not claimed
and is warned about at export. Never an untagged PDF stands, as
`CLAUDE.md` says.

Why: measured on three binaries, the output is the same tagged tree (E1,
and my own probe), which no other engine on this machine produces. The
Challenger's order put the runtime first because the editor already needs
it; that argument is satisfied by including the runtime anywhere in the
list, since it is the one that exists wherever the editor runs, and the
Edge browser is the documented headless surface, so it goes first when both
exist. No per session probe render is needed: the checker runs on every
export, so an engine that stopped tagging is caught on the machine it
happens on, and the selftest renders with every candidate it finds. The
gate is right because the identifier is a claim, the checker already runs
after every export, and withholding the claim exactly when a skipped
heading or a missing description is found is what PDF/UA itself asks
(Matterhorn 14-003 and 07-001 are the two the app can detect). What is
lost by gating: nothing a user wants; a file with a fault still exports,
tagged, with the report naming the fault and the identifier left out.

Scope rulings inside this decision:

- veraPDF as a build step: out of 1.0.0. In as one run at the Round 4
  audit, on the exported fixtures, if Tony says yes to the download. What
  is lost if he declines: no independent conformance verdict; the site
  then says "checked by the app; a full PDF/UA verdict needs PAC or
  veraPDF", which is what the checker's own report already says.
- RTL support: out of 1.0.0. In: an export warning when Arabic or Hebrew
  script is found. What is lost: Arabic and Hebrew authors, who are told
  so rather than handed a PDF that reads in the wrong order (E7).
- LBody: the engine writes none. The checker names it as a warning only;
  the veraPDF run decides whether it matters.

Brief changes: worker-a.md edits A2, A3, A4, A5, A8, A9; coordinator edit
K6; overseer.md edit O1.

### Decision 3: one native format. Modify

Decision: modify. The native extension is `.epdf` with the self-contained
UTF-8 HTML inside, exactly the format ANALYSIS.md proposed. `.html` and
`.htm` are imports, and "Save as web page" writes the same bytes to
`.html`. The installer registers `.epdf` per user with the app's icon and
the description "Easy PDF document"; the zip copy registers nothing.
Images are downscaled on insert (longest edge 2,000 pixels, JPEG quality
85 for photographs, PNG kept for PNG sources), through one function in
`docfile`. Import: `.txt`, `.md` (markdown-it-py is allowed), `.docx`
(python-docx, basic scope below), `.pdf`. RTF import is dropped. The
sanitiser's allow list is written out (edit A7). Autosave already has
owners in both briefs; the crash signal is the snapshot itself (risk 14).

Why: the extension argument is about the app's own user, not about mail
filters, which are a wash (a `.epdf` full of base64 looks the same to a
content scanner as a `.html`). On the user's own machine, `.html` belongs
to the browser: double click opens Edge, Explorer shows the browser's
icon, NVDA reads "Microsoft Edge HTML Document", and the app's documents
are indistinguishable from saved web pages in a folder listing. A blind
user browsing Documents needs to hear "Easy PDF document". The content
stays HTML, so nothing is trapped: "Save as web page" is one menu item and
a renamed file opens in any browser. Downscaling: 2,000 pixels across a
letter page's 6.5 inch text width is over 300 dots per inch, so no print
quality is lost and a five photo newsletter stops being a 50 MB file (E8).
docx in, rtf out: python-docx is installed, Word is what students and
offices actually send, and the only RTF files that exist are the April
prototypes; the parser the brief asked for would have cost hours for
nobody. markdown-it-py is on the machine, pure Python, and more correct
than a converter written in an afternoon; the build already bundles far
larger things.

Scope rulings inside this decision:

- docx import: in, at this scope. Headings by style name (Title and
  Heading 1 to 6), paragraphs, bold, italic, underline and strike runs,
  hyperlinks, bullet and numbered lists (nesting from `ilvl` if it comes
  cheaply, else flattened with a warning), pictures with their Word
  description carried as alt, tables with the first row as headers, core
  properties into meta. Out: footnotes, endnotes, comments, headers and
  footers, text boxes, equations, fields and tables of contents, and
  tracked changes, which are not read; the importer warns "accept tracked
  changes in Word first" when it sees any. What is lost: nothing that the
  PDF export could carry anyway.
- rtf import: out. What is lost: opening the April prototype files, which
  were test documents. Anything real opens in WordPad and saves as `.docx`
  or `.txt`.
- rtf export: not proposed by anyone and out. What is lost: nothing; an
  editable copy leaves as a web page, a read copy as the PDF.
- docx export: out. What is lost: sending an editable Word file. "Save as
  web page" covers editable sharing for 1.0.0.
- Tree aware PDF import: out in its full form (pikepdf can walk the tree,
  but mapping marked content ids to text means decoding content streams
  and fonts, which is a project). In, best effort: the importer reads the
  tree with pikepdf to report that the PDF was tagged, and recovers Figure
  `/Alt` strings per page, in order, attaching them to the extracted images
  on that page only when the counts match, marked `data-alt-source="pdf"`
  and still `data-needs-alt="1"` so the Pictures dialog lists them as
  "recovered, please check". What is lost: a tagged PDF's headings are
  re-guessed from font size on import. The user is told.
- A "keep full size" option for pictures: out. See the 300 dots per inch
  arithmetic above.

Brief changes: worker-a.md edits A1, A2, A6, A7, A8; worker-b.md edits
B7, B11, B12; coordinator edits K1, K2, K3, K8, K10, K11.

### Decision 4: no welcome dialog. Keep, with additions

Decision: keep. Add File, Recent documents (the last eight, as
`constants.RECENT_FILES` says, with numbered mnemonics 1 to 8); one first
run hint (one status bar line, spoken once through `announce_help`, the
words in `STRINGS.md`); and a second launch with a file path hands the
path to the running copy (mechanism under decision 9).

Why: every TG Studios program opens on its work surface, and a modal
before the main window breaks single instance, the command line, "Open
with" and drag and drop. The Challenger's three points are met without a
dialog: recent files answer "reopen yesterday's document", the hint
answers "what is this", and the update check and the missing key moments
already have their own dialogs at the moment they matter.

Brief changes: worker-b.md edits B7, B11, B13.

### Decision 5: Ctrl+I is italic. Modify

Decision: modify. Ctrl+I is italic. Ctrl+Shift+I stays an italic alias,
because it was in the April build and keeping it costs nothing. Insert
picture is Ctrl+Shift+P, as worker-b.md already says. Ctrl+Shift+F (the
font dialog) is struck: there is no per run font in a semantic editor.
Heading keys: Ctrl+Alt+1 to 6 and Ctrl+Alt+0 stay, and the page acts only
when the event's `key` is the digit itself, so an AltGr character on a
European layout is typed, not hijacked; Ctrl+Shift+1 to 6, Ctrl+Shift+0,
Ctrl+Shift+8 and Ctrl+Shift+9 are aliases gated on the physical key code
(`event.code`), the layout proof route. Both are documented together.
Every key is measured by real keystrokes into a focused editor.

Why: the contradiction in ANALYSIS.md section 5 (Ctrl+Shift+I as both
insert image and an italic alias) is resolved by the picture key the brief
had already moved to Ctrl+Shift+P; no key means two things. "A taught key
never goes away" applies to shipped programs, and this one never shipped;
even so the alias is free and the April Ctrl+I insert image never fired
while typing (W4), so nobody was taught it. Chromium forces Ctrl+I italic
inside a focused editor anyway (W5), and the page handler owns the key so
there is one handler and no double toggle. The AltGr rule was measured
only for a US layout (W4); the `event.key` and `event.code` gates cost a
few lines and make the keys safe on layouts nobody here can test. What is
lost by striking the font dialog: mixed fonts inside one document, which
the export stylesheet did not honour anyway; the document font and size
are document properties and Preferences defaults.

Brief changes: worker-b.md edits B4, B6, B8, B9, B10.

### Decision 6: the name and the frozen block. Tony's

Decision: Tony's. The working assumption is "Easy PDF" and the frozen
block as scaffolded (`INSTANCE_SLUG` "EasyPDF", `FEED_SLUG` "easy-pdf",
`APP_USER_MODEL_ID` "TGStudios.EasyPDF.1", installer basename "EasyPDF",
zip basename "Easy-PDF", the Inno AppId
{B194AFF3-AC8A-464F-9440-FB09CC0CDF62}). The Challenger's finding is
recorded for him: BCL Technologies, now part of Apryse, has sold "easyPDF
SDK" in the PDF creation class for decades, and "Easy PDF" apps sit in
the app stores (X3). The name is generic and unsearchable. Options for him
to weigh, not a recommendation: "TG Easy PDF" (keeps the words, adds the
brand, the Challenger's minimum), "TG Readable" (says what the output is,
matches the tagline), or a name of his own. Whatever he chooses gets a
five minute search before release, as the amp names taught.

Why: the name is his, as the overseer brief says. What I can settle is
the freeze. `CLAUDE.md` says the frozen block never changes, and that rule
exists so a shipped copy keeps finding its feed and recognising its
running twin. Nothing has shipped. Until the first publish, the block is
frozen only in the sense that nobody changes it casually; a rename before
release changes it in one commit with `tests/test_scaffold.py`, and that
is free. After the first publish it is locked for good, whatever the
display name does. So the deadline for the name is before the private
repository is created (PLAN.md step 9) and before `release_app.py
publish` (RELEASING step 5); the report to Tony asks the question if he
has not answered by then. No worker is blocked: every worker uses
`constants.APP_NAME` and the constants, and a rename touches no worker
file.

What a rename touches, if the slug changes with it:

- `easypdf/constants.py`: `APP_NAME`, `TAGLINE`, `INSTANCE_SLUG`,
  `FEED_SLUG`, `APP_USER_MODEL_ID`, `INSTALLER_BASENAME`, `ZIP_BASENAME`,
  `HOME_URL`, `USER_GUIDE_URL`, `DOC_WILDCARD`, `OPEN_WILDCARD`, and the
  new `DOC_PROGID`, `DOC_TYPE_DESCRIPTION` and `CONFIG_FOLDER_NAME` (edit
  K1).
- `easypdf/appupdate.py`, the marked block: `MANIFEST_URL`,
  `STAGING_PREFIX`, `INSTALLER_FALLBACK_NAME`.
- `easypdf/secrets.py`: `TARGET_PREFIX` ("Easy PDF AI key: "), which a
  user reads in Credential Manager.
- `easypdf/paths.py`: the config folder, once it derives from the frozen
  `CONFIG_FOLDER_NAME` rather than from `APP_NAME` (edit K1; today a
  display rename after release would move everybody's settings folder,
  which contradicts the "one constant" promise in `constants.py`).
- `tools/easypdf.iss`: `AppName`, `AppExeName`, `OutputBaseFilename`,
  `UninstallDisplayName`, the `[Registry]` ProgId and description, the
  icon file name. The AppId GUID does not change for a rename.
- `tools/build_release.py` (the exe and build folder names),
  `tools/release_app.py` (the feed and product names, `NOTES`).
- `tests/test_scaffold.py`: every asserted string.
- The project `CLAUDE.md`, the workspace `CLAUDE.md` table, `README.md`,
  `CHANGELOG.md`, `docs/STRINGS.md`, the Dropbox folder name, the GitHub
  repository name (`tonygeb23/easy-pdf` is not created yet), the
  tgstudios.app page slug, the TG Stats download rule, and the Desktop
  shortcut name.

Brief changes: none for the workers. Coordinator edit K1 (the two new
frozen constants) and the question in the report to Tony.

### Decision 7: free, with the donate link. Tony's

Decision: Tony's. The working assumption: version 1.0.0 is free with the
donate link, decided for 1.0.0 only, by Tony, and written that way in the
report and on the site. Nothing in the code or the strings says "free
forever". Downloads are counted from day one (the standing rule: wire TG
Stats when the product goes on the site). The ninety day revisit with the
numbers is his call to make or skip.

Why: the Challenger is right that "pricing is Tony's call" followed by
"free" decides it. So it is recorded as his. The working assumption is
free because the audience is Drop Deck's, Word and LibreOffice export
tagged PDF for nothing, and 1.0.0 has no licence code to write. "Hooks
kept" means only this: nothing in the feed, the slug, the describer or the
strings forecloses a paid edition later; no licence module is written for
1.0.0. What is lost if it stays free: the institutional market the
Challenger names, which needs a stronger product than 1.0.0 anyway and
which the download numbers will show or not.

Brief changes: none. The report to Tony carries the framing.

### Decision 8: the describer copies Drop Deck's layer. Modify

Decision: modify, as the Challenger asked, in six places. Copy
`secrets.py` verbatim with the prefix changed (done). Copy the transport,
the error sentences, the model list fetch and `redact` from `vision.py`;
do not copy the camera and screen prompts, the speed tuned
`DEFAULT_MODELS`, `SEND_WIDTH` 1024 or `needs_consent`. Add a multi part
builder per provider (one text part plus N images). Prompts are written
fresh for alt text and for document description, listed in `STRINGS.md`.
Defaults are chosen for accuracy from each provider's live model list and
measured on the fixtures; no model name is fixed in this file. Pictures
go at up to 1,600 pixels wide, JPEG for photographs and PNG for anything
whose source is PNG. AI written alt text is marked in the native file
(`data-alt-source="ai:<provider>"`, never in the PDF) and the export
report counts the ones not checked by a sighted person. A "Use the key I
gave TG Drop Deck" button reads that entry after the user's yes.

Consent, which is a standing rule and is not re-litigated: "A whole
document asks every time; a single picture asks once per session." The
rule stands as written. What this file settles is which case an imported
picture falls under: a picture that arrived inside somebody else's
document, and any batch of pictures, is that document leaving the machine,
so it asks every time, with the count of pictures and the megabytes. A
picture the user inserted from their own disk asks once per session. The
consent text names the provider and says, in one sentence, to check the
provider's data policy before sending anything private, with the policy
addresses in `DESCRIBER.md`. Every consent text is in the approval packet.

Why: the layer's transport, key handling and error sentences are proven
since yesterday and small; rewriting them invites the faults Drop Deck
already found. Its defaults are the wrong shape for this job: a presenter
waiting to go on air wants speed, an author writing a description that
will sit in a distributed file for ever wants accuracy and legible chart
labels, and describe document needs text plus many pictures in one
request, which no builder in `vision.py` can express. The provenance rule
follows the standing rule's own reasoning (Drop Deck asks every time for
the screen because the sender cannot see what is in it; an imported PDF's
pictures are exactly that case) without changing its words. The marker is
honesty in the file: a blind author cannot check a description against
the picture, and a sighted reviewer later can only check what is marked.

Brief changes: worker-c.md edits C1 to C8; worker-a.md edit A4 (the count
at export); worker-b.md edit B12 (the marker written on accept, shown in
the Pictures dialog); coordinator edit K8 (the sentence in PLAN.md).

### Decision 9: everything a TG Studios program ships with. Keep, with specifics

Decision: keep. The rule is settled by `CONVENTIONS.md` and
`RELEASING.md`. The specifics the Challenger asked for are decided here:

- One window, one document. Opening another document replaces the current
  one after the save changes prompt. What is lost: side by side documents;
  the clipboard still moves text between them.
- A second launch with a file path hands the path to the running copy.
  The coordinator built this while Round 1 was being written:
  `easypdf/handoff.py` sends the path with WM_COPYDATA through
  `SendMessageTimeout`, `main.py` hands over before raising the window,
  and a `Receiver` subclassed onto the frame calls
  `frame.open_document(path)` on the UI thread; `tests/test_handoff.py`
  proves a real second process delivers a path with an accent and a CJK
  character. Adopted as built, with one fix (edit K5): the receiver's
  callback runs inside the window procedure while the second launch
  waits, so `open_document` must be scheduled with `wx.CallAfter` and
  return at once, or a save changes prompt keeps the second launch
  waiting five seconds and makes it report the hand over failed.
  `singleinstance.py` stays byte identical to Drop Deck's, which is why
  the handoff is its own module.
- The status bar's first field is the message field, wide enough for a
  sentence, and every channel writes it at every level. The other three
  fields are the paragraph style, the word count and the document
  language. That is the "fourth field" `CONVENTIONS.md` says Model Master
  needed.
- The selftest proves the Edge backend, `WebView2Loader.dll`, every engine
  candidate by rendering and reading back, the pikepdf identifier
  namespace, the sanitiser on a hostile snippet, the update key, the
  devicePixelRatio, and that `docx` and `markdown_it` import in the
  frozen build (edit K6).
- `tests/test_keys.py` is a real keystroke harness against a focused
  editor with a control test first. A table check proves nothing (W4).
- DPI: done in `main.py`, measured; the selftest records it.
- Closing: settings, recent files, window geometry are written in
  `EVT_CLOSE` before the frame is destroyed, never in `atexit`. A normal
  close is clean (the coordinator's measurement, `CLAUDE.md`), so the
  Challenger's "every exit is a hard exit" is not the case; only probes,
  the selftest and the update hand over hard exit. The coordinator's
  running marker (`paths.mark_started()` before the window,
  `paths.mark_clean_exit()` after `MainLoop` returns) is the crash
  signal, read by the frame as `paths.PREVIOUS_RUN_CRASHED`; the frame
  also deletes its own snapshot on a clean close (risk 14). The frame
  never calls `os._exit`.
- The public "not in 1.0.0" list is in the section "Scope for 1.0.0"
  below and goes on the site page.

Why: each item is a place the plan was vague and a screen reader user
would meet the gap first. The file handoff is the one that turns "double
click a document while the app is open" from nothing perceptible into the
document opening. The coordinator's WM_COPYDATA module is the right shape
for it: immediate, on the UI thread, proven by a real second process, and
it keeps the proven single instance module untouched. Its one fault, a
callback that blocks the sender, is a one line fix.

Brief changes: worker-b.md edits B13, B15; coordinator edits K5, K6, K8.

### Decision 10: publishing waits for Tony. Keep

Decision: keep. Nothing is uploaded, no page goes up and nothing is
announced until he says go. The first real publish is watched with
`TG Studios Release\check_updates.py`, which RELEASING step 7 already
requires. The approval packet is spelled out in the section "The
approval packet for Tony" below.

Why: it is the standing rule in `CLAUDE.md` and `RELEASING.md`, and the
Challenger's only addition (that a rehearsal against a feed that does not
exist is not proof) is already how the pipeline works: `release_app.py
publish` verifies against the live feed at the end.

Brief changes: none. The packet is the coordinator's report.

## The Challenger's risks, one by one

### Risk 1: synchronous RunScript hangs with a focused editor

Decision: settled under decision 1, condition 1. Asynchronous API only;
the watchdog test. The selftest in `main.py` also moves to
`RunScriptAsync`, because a synchronous hang there would block the very
`wx.CallLater` watchdog meant to catch it (edit K6).

Why: see "Where I did not measure". Brief changes: B1, B15, K6.

### Risk 2: the frame's accelerators are dead while the editor is focused

Decision: settled under decision 1, condition 2. The whole keyboard
contract, `CONVENTIONS.md` keys included, is implemented in the page and
forwarded. The wx table covers focus outside the editor. The Applications
key and Shift+F10 are caught in the page too: the `contextmenu` event is
prevented, a message goes to Python with the caret's client rectangle, and
the wx menu pops up there.

Why: measured (W4, W5, W6) and unanswerable any other way. Brief changes:
B2, B5, B6.

### Risk 3: hostile files run script inside the editor

Decision: three layers, all in 1.0.0. First, the one sanitiser in Python
(`htmlclean.normalise`) on every load, paste and import, with a written
allow list (edit A7). Second, a Content Security Policy in the editor
page: `default-src 'none'; script-src 'nonce-<per load>'; style-src
'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'`, and
the page's own script carries the nonce and binds no inline handlers.
Third, every navigation after the first load is vetoed in
`EVT_WEBVIEW_NAVIGATING`, so no link can ever leave the editor. Remote
images are never fetched: the sanitiser drops an `http` `src` with a
warning, and `file:` sources are embedded on load or dropped with a
warning.

Why: W11 measured an `onerror` handler running through `innerHTML`. A
sanitiser alone is one bug away from the bridge; a nonce policy blocks
inline handlers and `javascript:` addresses even when the sanitiser
misses, and `img-src data:` stops a received file from phoning home. The
cost is one meta tag, a nonce, and one test. `style-src 'unsafe-inline'`
is deliberate: `execCommand` writes `style="text-align: ..."` on blocks
and a stricter policy would blank the user's own alignment in the editor,
and a style attribute cannot run script.

Brief changes: A7, A8, B5, B15.

### Risk 4: undo after programmatic edits

Decision: settled under decision 1, condition 4, with the Replace All
route decided here. Replace All must be undoable with one Ctrl+Z. The
first route to try: compute the new body on a clone by walking text nodes
(formatting kept), then apply it with select all plus
`execCommand('insertHTML')`, which W7 measured as undoable; a test proves
headings, lists and `strong` survive the round trip. If that measurement
fails, the fallback: the page keeps the previous body, the next Ctrl+Z
restores it (one level) before the browser's own undo runs, and the
status bar says "Replaced N. Press Ctrl+Z to put them back." Load resets
the undo history on purpose and says nothing, because a new document has
no history to lose.

Why: W7 measured that `range.insertNode` edits are invisible to undo and
that Ctrl+Z after one removes the user's own typing. A blind user who
replaces all, hears the count, and presses Ctrl+Z must get the document
back. Brief changes: B5, B12, B15.

### Risk 5: semantic drift between the DOM and the PDF

Decision: settled by my own measurement and decision 2, condition 4. The
normaliser maps `b` to `strong`, `i` to `em`, `strike` and `del` to `s`,
`div` to `p` (or unwraps a `div` that holds only blocks), `pre` to a `p`
with class `code-block` holding `code` (Chromium tags `pre` as nothing),
style spans to the semantic elements, `text-align` styles to classes,
hoists a `span lang` that covers its whole block onto the block and
otherwise drops it with a warning, and gives every `img` an `alt`
attribute, with a warning when it had none, because a missing description
must never silently become decorative.

Why: measured twice (E5, and my probe). Brief changes: A4, A7, A8, and
the integration test in B15 that feeds the real editor's DOM to the
normaliser.

### Risk 6: a conformance claim without a validator

Decision: settled under decision 2: the identifier is gated on the
checker; veraPDF once at the audit if Tony approves the download; PAC by
hand. The site's wording is Tony's and is in the approval packet; the
working assumption is "tagged PDF, checked by the app; the PDF/UA
identifier is written when every check passes; a full verdict needs PAC or
veraPDF".

Brief changes: A4, A5, A9, O1.

### Risk 7: the engine drifts with Windows Update

Decision: the Producer string carries the engine's name and version
(`"Easy PDF 1.0.0 (Microsoft Edge 152.0.4191.66)"`), so a bad batch can be
traced. Re-measurement at every release is already the pipeline: the
export tests render with the installed engine and read the tree back, and
RELEASING step 1 runs them before anything ships. The checker on every
export is the per machine guard.

Why: cheap and derived, which is what RELEASING asks of every check. Brief
changes: A2, A4, A8.

### Risk 8: the default header and footer print the temp file path

Decision: the flag is always on (already in worker-a.md line 74) and a
test asserts the page text holds no file path and no date. Measured
working today.

Brief changes: A8.

### Risk 9: Arabic and right to left text

Decision: out of 1.0.0, not claimed, warned at export, listed on the site.
See decision 2. Brief changes: A4, A8, A9.

### Risk 10: file bloat from full resolution pictures

Decision: `docfile.embed_image` downscales on insert, on paste of a
picture, on import from docx and PDF, and on load for a `file:` source
that still exists. The Insert picture dialog states the size going in.
See decision 3. Brief changes: A2, A7, A8, B12.

### Risk 11: the html extension belongs to the browser

Decision: `.epdf`. See decision 3. Brief changes: A7, B7, B11, K1, K2,
K3.

### Risk 12: privacy of the describer

Decision: see decision 8. The consent text names the provider, the count
and the size, and points at the data policy; imported content and batches
ask every time. `DESCRIBER.md` explains in plain words what each provider
says it does with submitted content, with the caveat that policies
change. Brief changes: C2, C5, C8.

### Risk 13: the name collides and the freeze makes it permanent

Decision: Tony's; the freeze is not permanent until the first publish. See
decision 6.

### Risk 14: autosave, crash recovery and the clean exit marker

Decision: autosave has owners already (worker-a.md lines 54 to 56,
worker-b.md lines 194 to 197). The clean exit marker exists: the
coordinator built it in `easypdf/paths.py` while Round 1 was being
written (`running.marker` under the local folder, `mark_started()` at
start, `mark_clean_exit()` after a clean `MainLoop`, and
`PREVIOUS_RUN_CRASHED` for the frame to read), and worker-b.md lines 53
to 57 already bind Worker B to it. Adopted as built. On top of it: a
clean close deletes the document's snapshot after the save prompt, so
stale snapshots do not accumulate, and the frame offers
`docfile.recoverable()` only when `paths.PREVIOUS_RUN_CRASHED` is True.
Two tests in Worker B's suite: after `Close()` of a saved document no
snapshot remains; after a simulated crash (the frame torn down without
`EVT_CLOSE`, the flag forced True) the snapshot remains, is listed, and
the recovery dialog is offered.

Why: the coordinator's reasoning in `paths.py` is right that the update
hand over and the selftest are hard exits, so "the process is gone"
cannot be the signal; a marker written before the window exists and
removed only after a clean loop is. The Challenger's wider premise that
every exit is a hard exit is still not the case (`CLAUDE.md`: a normal
close is clean), and the frame must close normally. Brief changes: B12,
B13, B15; coordinator edit K5.

### Risk 15: single instance with a file argument, one or many documents

Decision: one window, one document; the WM_COPYDATA handoff the
coordinator built in `easypdf/handoff.py`, with the `wx.CallAfter` fix.
See decision 9. Brief changes: B13, B15, K5.

### Risk 16: blur at 150 percent

Decision: measured fixed by `main.py`; the selftest records it. See
decision 1, condition 7. Brief changes: K6.

### Risk 17: tables

Decision: in, at the basic level, out beyond it. In: Insert table (rows,
columns, first row as headers, default on), typing in cells, Tab and
Shift+Tab between cells, Tab in the last cell adds a row, Delete on a
selected table with a confirmation, `th scope="col"` on the header row.
Out of 1.0.0: merging cells, adding or removing single rows and columns,
column widths, row headers, table captions. The site lists this.

Why: the engine tags tables well (E4) and a PDF/UA document often needs
one; the basic level is a few lines of JavaScript on top of what
contenteditable already does. Editing beyond it is a table editor, which
is not a 1.0.0 feature. NVDA's table reading inside the editor is an audit
item. Brief changes: B5, O1.

### Risk 18: LBody absence and NonStruct wrappers

Decision: the checker names LBody absence as a warning only; the veraPDF
run answers whether it matters; nothing is promised on the site. Brief
changes: A5, A9.

### Risk 19: the app signs what it imports

Decision: covered by three things already decided: every export runs the
checker and reports by name; an imported document is marked modified,
needs a title before export, and carries `data-needs-alt` on every
picture without a description; recovered and AI written descriptions are
marked for review. Creator says "Easy PDF" because that is true; the
report says what the app could not check. Brief changes: none beyond A4,
A6 and B12.

### Risk 20: the structure panel and F6 duplicate NVDA's browse mode

Decision: keep both, for Narrator, JAWS and sighted keyboard users. The
Round 4 audit measures what NVDA's browse mode actually does inside this
editor (quick keys H, K, G, L, T, and NVDA+Space) and the report says.
Brief changes: O1.

### Risk 21: high contrast

Decision: the page respects `forced-colors` (already in worker-b.md line
201); toolbar icons are drawn from system colours
(`wx.SystemSettings.GetColour`) and redrawn on `EVT_SYS_COLOUR_CHANGED`;
the Round 4 audit runs once with Windows High Contrast on. Brief changes:
B14, O1.

### Risk 22: focus mode on entry

Decision: unmeasured by anyone; Worker B measures it with NVDA running
(after Ctrl+N and after Open, do the first letters typed land in the
document, or act as quick navigation keys), keeps the `role="textbox"
aria-multiline` variant if that is what makes it reliable, and the audit
checks it by hand. Brief changes: B2, O1.

### Risk 23: paste

Decision: paste goes through Python. Inside the editor, the page's `paste`
event is prevented, the clipboard's `text/html` (else `text/plain`) is
posted to Python, `htmlclean.normalise` cleans it, and the page inserts
the result with `insertHTML`. Edit, Paste from the menu reads
`wx.TheClipboard` (HTML if present, else text) and takes the same path.
Copy and Cut stay native (W10). Pictures on the clipboard go through
`docfile.embed_image` and become a figure needing a description.

Why: W10 measured `execCommand('paste')` refused and the clipboard
promises never settling; one sanitiser in one language beats two allow
lists that drift. Brief changes: B3, B5, B15.

### Risk 24: execCommand is obsolete on paper

Decision: the normaliser does not trust `execCommand`'s output shape: it
normalises by rule (any bold weight span, any `b`, any `font`) rather than
by matching today's exact markup, and Worker B's integration test feeds
the real editor's DOM after bold, italic, lists and alignment to
`htmlclean.normalise` and asserts the semantic result. Every release runs
it against the installed runtime (RELEASING step 1).

Brief changes: A4, B15.

### Risk 25: bridge volume on big documents

Decision: state messages carry booleans and the block type, never the
document. The document crosses the bridge only on save, export and
autosave, and autosave copies it only when it changed since the last
snapshot. Worker B measures a 200 page document with twenty pictures at
2,000 pixels: time to load, time to get the HTML back, and the memory of
the process, and reports the numbers. No target is set until the numbers
exist.

Brief changes: B5, B15.

### On the biases section

Two of the biases become work; the rest are answered above. "Tony's
machine is the target": the startup guard and the checker on every export
are the per machine proof that the engine and the editor work where the
app is installed, not only here. "The competitor is never named": the site
page must say why this and not Word or LibreOffice (enforced descriptions,
a checker that names the fix, AI descriptions, opening somebody else's PDF
to make it accessible, simplicity, price); that is Tony's copy and it is
in the approval packet.

## Scope for 1.0.0

In, with the brief it lands in:

- docx import, basic scope (Worker A).
- markdown-it-py for Markdown (Worker A).
- `.epdf` native, `.html` import and "Save as web page" (Worker A, Worker
  B, coordinator).
- Downscaling on insert, paste, import and load (Worker A provides, Worker
  B calls).
- The one sanitiser with a written allow list, and the Content Security
  Policy (Worker A, Worker B).
- The PDF/UA identifier gated on the checker (Worker A).
- The Producer string with the engine version, and the header and footer
  test (Worker A).
- The RTL warning and the AI description count at export (Worker A).
- Best effort recovery of figure descriptions from a tagged PDF (Worker
  A).
- Asynchronous editor API, keys in the page, the deny list, the AltGr
  rule and the Ctrl+Shift+digit aliases (Worker B).
- Paste through Python; Replace All undoable (Worker B).
- Recent documents, the first run hint, the file handoff, the pre exit
  flush (Worker B, coordinator).
- Basic tables (Worker B).
- Icons from system colours (Worker B).
- Consent by provenance, the data policy sentence, the multi part builder,
  accuracy defaults, 1,600 pixel PNG or JPEG, the AI marker, the Drop Deck
  key button (Worker C).
- The startup guard, the selftest additions, the two frozen constants, the
  file type registration, and the `wx.CallAfter` fix to the handoff and
  crash marker the coordinator has already built (coordinator).
- One Narrator pass and one High Contrast pass at the audit (Overseer).
- One veraPDF run at the audit, if Tony approves the download (Overseer).

Out of 1.0.0, and what is lost:

- RTF import: the April test files. RTF export: nothing.
- docx export: an editable Word file; the web page covers it.
- Full tree aware PDF import: a tagged PDF's headings are re-guessed.
- OCR: a scanned PDF cannot be imported; the importer says so.
- Right to left languages: Arabic and Hebrew authors, who are warned.
- veraPDF in the build: an automated verdict per build.
- JAWS testing: no JAWS here; the site says NVDA and asks for reports.
- Tables beyond the basic level: merged cells, row and column editing.
- Footnotes, page numbers, columns, headers and footers: long document
  furniture; page numbers wait for a measurement of Chromium's `@page`
  margin boxes.
- A font dialog: mixed fonts in one document.
- More than one open document.
- A "keep full size" option for pictures.
- A Mac version.

## The approval packet for Tony

What the report puts in front of him, as text, before anything ships:

- The name, with the collision and the three options (decision 6).
- The pricing framing: free for 1.0.0, decided by him (decision 7).
- Every string in `docs/STRINGS.md`: the consent questions, the prompts,
  the first run hint, the startup guard, the export warnings, the
  checker's sentences, the release note line, the tagline, the file type
  description.
- The site page copy: what it is, why not Word or LibreOffice, "tested
  with NVDA", the PDF/UA wording, and the "not in 1.0.0" list above.
- Two downloads that need his yes: veraPDF and PAC 2024.
- The go to publish.

## Changes to the briefs

Exact edits, by file. Line numbers are as the files stand on 2026-09-09:
worker-a.md and worker-c.md as written at 08:02 and 08:04, overseer.md at
08:04, and worker-b.md as changed by the coordinator at 08:33 (the
`open_document` and crash marker contract at its lines 46 to 57). If a
file changes again before these are applied, find each spot by the
quoted opening words, not the number. "Replace lines X to Y" means the
whole lines. Apply the edits to one file from the bottom up so the line
numbers hold.

### docs/briefs/worker-a.md

A1. Replace lines 10 to 13 (`easypdf/pdfengine.py`, ... `docs/PDF-UA.md`.)
with:

```
`easypdf/pdfengine.py`, `easypdf/pdfexport.py`, `easypdf/pdfcheck.py`,
`easypdf/pdfimport.py`, `easypdf/docfile.py`, `easypdf/htmlclean.py`,
`easypdf/markdown_in.py`, `easypdf/docx_in.py`, `tests/test_pdf*.py`,
`tests/test_docfile.py`, `tests/test_import.py`, `docs/PDF-UA.md`.
There is no `rtf_in.py`: RTF import is out of 1.0.0 (DECISIONS.md,
decision 3).
```

And replace lines 14 to 16 (Fixtures for everyone ...) with:

```
Fixtures for everyone are in `tests/fixtures/` (`sample-body.html`,
`sample.md`, `sample.txt`, `circle.png`; `sample.rtf` is no longer used by
anything and stays where it is); add to them, do not rename them. The
docx fixture is built by the test itself with python-docx into a temp
folder, so it is code, not a binary.
```

A2. In the interfaces block, lines 25 to 60:

After line 27 (`find_browser() -> str | None`) insert:

```
engines() -> list[Engine]              # Engine(name, path, version), every candidate found, in search order
```

Replace line 38 (`ExportResult: path, pages, warnings ...`) with:

```
ExportResult: path, pages, warnings (list of sentences), engine (str, "<name> <version>"),
              pdfua_claimed (bool: the identifier was written because the checker's gate passed)
```

Replace lines 42 and 43 (`Report: results ...` and `format_report() ...`)
with:

```
Report: results (list of CheckResult(name, passed, detail)), passed, score -> (ok, total),
        pdfua_gate -> bool   # every check passed except the identifier check itself
        format_report() -> str   # plain text, one check per line, PASS/FAIL, no markdown
```

Replace line 47 (`ImportResult: body_html, meta, images ...`) with:

```
ImportResult: body_html, meta, images (list of ImportedImage(id, png_bytes, width, height, page,
              alt, alt_source)),   # alt "" unless recovered from the structure tree; alt_source "" or "pdf"
```

Replace line 53 (`kind_of(path) -> ...`) with:

```
kind_of(path) -> "native" | "html" | "text" | "markdown" | "docx" | "pdf"   # native is .epdf
```

After line 56 (`discard_snapshot(snapshot_path) -> None`) insert:

```
embed_image(source: str | bytes) -> EmbeddedImage
# EmbeddedImage: data_uri, mime, width, height, original_width, original_height,
#                kilobytes, original_kilobytes, note (one sentence, or "")
# Downscales to constants.IMAGE_MAX_EDGE on the longest edge, JPEG at
# constants.IMAGE_JPEG_QUALITY for JPEG sources, PNG kept for PNG sources.
```

Replace line 59 (`normalise(body_html) -> ...`) with:

```
normalise(body_html, for_export=False) -> (clean_html, warnings)
# The one sanitiser. Load, paste, import, save and export all go through it.
# for_export=True also strips every data-* attribute (after counting
# data-alt-source="ai:*" into one warning) and turns pre into a code-block p.
```

A3. Replace lines 67 to 69 (`- Find the browser through the registry ...`)
with:

```
- Find the engine in this order, and stop at the first that exists:
  1. The Edge browser: the registry `App Paths` key for `msedge.exe`, then
     the standard install folders.
  2. The WebView2 runtime's own msedge.exe: read `pv` from HKLM,
     SOFTWARE, WOW6432Node, Microsoft, EdgeUpdate, Clients,
     {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}, then look in
     `%ProgramFiles(x86)%\Microsoft\EdgeCore\<pv>\msedge.exe` and
     `%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application\<pv>\msedge.exe`.
     On this machine the registry `location` points at the second folder
     and the binary is in the first (measured), so try both. It renders
     the same PDF as the browser (measured, byte identical).
  3. Chrome: its `App Paths` key, then the standard folders.
  `find_browser()` returns that path; `engines()` returns every candidate
  found, with its version taken from the parent folder's name (or
  "unknown"), for the selftest and the About box. Cache nothing across
  runs; a browser can be uninstalled.
```

Replace lines 77 to 79 (`- Never fall back to an untagged writer ...`)
with:

```
- Never fall back to an untagged writer. If there is no engine,
  `available()` says so in a sentence that names Microsoft Edge, the
  WebView2 runtime and Google Chrome, and `export_html` raises
  `EngineError` with the same sentence. The UI offers the web page
  instead.
```

A4. Replace lines 83 to 94 (`1. `htmlclean.normalise` the editor's HTML ...`)
with:

```
1. `htmlclean.normalise(body, for_export=True)`. The rules, in full, are
   the allow list in "The native format" below. In short: `b` to
   `strong`, `i` to `em`, `strike` and `del` to `s`, `div` blocks to `p`
   (a `div` holding only blocks is unwrapped), `pre` to `<p
   class="code-block"><code>` with line breaks as `br` (Chromium tags
   `pre` as nothing, measured), bare text wrapped in `p`, empty
   paragraphs (`<p><br></p>`) dropped, `execCommand` style spans
   (`font-weight: bold`, `font-style: italic`, `text-decoration:
   underline` or `line-through`) folded into the semantic elements,
   `text-align` styles turned into the `align-*` classes, every other
   `style` dropped, `contenteditable`, scripts, event handlers and
   invented ids stripped. Normalise by rule (any bold weight, any `b`,
   any `font`), never by matching the exact markup `execCommand` writes
   today; it changes per release. An image with no `alt` attribute gets
   `alt=""` **and a warning**, because a missing description must never
   silently become "decorative". A `span lang="xx"` that covers all the
   text of its block moves its `lang` onto the block; any other inline
   `lang` is dropped with a warning naming the words, because Chromium
   writes no Span element (measured). `href` must be http, https, mailto
   or tel; anything else loses the link and gets a warning. Table header
   cells get `scope="col"` (first row) or `scope="row"` (first column
   when the first row is not headers). Every `data-alt-source="ai:*"`
   is counted into one warning ("N picture descriptions were written by
   AI and have not been checked by somebody who can see the picture"),
   then every `data-*` attribute is stripped. If the text holds Arabic or
   Hebrew script, one warning: this release has not been checked with a
   right to left screen reader and the PDF may read in the wrong order.
```

Replace lines 101 to 106 (`4. pikepdf patch: ...`) with:

```
4. pikepdf patch, then the gate. Set `/MarkInfo /Marked true`, `/Lang`,
   `/ViewerPreferences /DisplayDocTitle true`, Info `Title Author Subject
   Creator Producer`, XMP `dc:title`, `dc:creator`, `dc:description`,
   `dc:language`, `xmp:CreatorTool = "Easy PDF <version>"`,
   `pdf:Producer = "Easy PDF <version> (<engine name> <engine version>)"`
   so a bad engine batch can be traced. Then run `pdfcheck.check` on the
   file. Write `pdfuaid:part = 1` **only if `Report.pdfua_gate` is
   true**; otherwise leave the identifier out, set `pdfua_claimed` False,
   and add a warning that names the check that failed and says the PDF
   was written without the PDF/UA claim. Never the byte-level patch the
   prototype had; it corrupts the cross reference table. pikepdf stamps
   itself as Producer in some save paths (measured); assert the strings
   in a test after the final save.
```

A5. Replace lines 111 to 123 (`Every check is a `CheckResult` ...`) with:

```
Every check is a `CheckResult` with a plain sentence in `detail` that says
what to do. Checks, each independent: tagged (`/MarkInfo`), structure tree
present, language set, DisplayDocTitle, title present (Info or XMP), XMP
PDF/UA identifier (when absent, the detail says "No PDF/UA identifier.
Easy PDF writes one only when every other check passes."), **every Figure
has non-empty Alt** (count them), heading levels do not skip (H1 then H3
is a fail, with the heading text named), every font embedded (walk page
resources and form XObjects), `/Tabs /S` on pages that carry annotations,
link annotations have a `StructParent`, outline present (warn only), text
layer present (a scanned PDF fails with "this PDF is pictures of text"),
and LBody present under LI (warn only; the engine writes none, and the
detail says PAC may warn). `Report.pdfua_gate` is true when every check
except the identifier check passed; warn-only checks count as passed. Say
clearly in `format_report` that a full PDF/UA verdict needs PAC or
veraPDF and this is the checks that can be made from here. The checker
must **fail** a PDF you deliberately break (strip `/MarkInfo`, remove an
Alt) and **pass** the app's own export of `tests/fixtures/sample-body.html`
with the identifier written; both are tests.
```

A6. Replace lines 127 to 139 (`PyMuPDF is installed (1.27). ...`) with:

```
PyMuPDF is installed (1.27). `import_pdf` turns a PDF into editor HTML:
text blocks in reading order, headings by ranking the font sizes that
appear (largest distinct sizes above the body size become h1, h2, h3; bold
at body size with a short line is h4), paragraphs joined across lines (and
across pages when a sentence continues), hyphenation at a line end joined,
bullets and numbering recognised into `ul`/`ol`, images extracted, passed
through `docfile.embed_image`, and placed at their position as
`<figure><img src="data:..." alt="" data-needs-alt="1"></figure>`
so the UI can list the pictures that need a description, links from the
page's link annotations kept as `<a href>`, metadata (title, author, lang)
carried into `meta`. If a page has no text at all, set `is_scanned` and
warn: there is no OCR in this release. Skip images smaller than 24 pixels
on a side (bullets and rules). Report progress per page.

Before that, one pass with pikepdf over the structure tree when there is
one. Count the headings and figures and, if the PDF was tagged, warn that
its structure is re-created from the text layout here. Collect every
Figure's `/Alt` per page in order; when a page's count of Alt strings
equals its count of extracted images, attach them in order with
`data-alt-source="pdf"` and keep `data-needs-alt="1"` so the Pictures
dialog lists them as recovered and to be checked; when the counts differ,
attach nothing and warn. A wrong description presented as fact is worse
than none. Full tree aware import (mapping marked content to text) is out
of 1.0.0 and `docs/PDF-UA.md` says so.
```

A7. Replace lines 143 to 159 (the two bullets `- **Native:** ...` and
`- **Load** dispatches ...`) with:

```
- **Native:** `.epdf` (`constants.DOC_EXTENSION`), self-contained UTF-8
  HTML inside. `<!DOCTYPE html>`, `<html lang>`, `<meta charset>`,
  `<title>`, `<meta name="author">`, `<meta name="description">` for the
  subject, `<meta name="generator" content="Easy PDF 1.0.0">`, a small
  stylesheet so it looks right in a browser, then the body. Every image is
  a data URI. Save is atomic. "Save as web page" is the same bytes written
  to a `.html` path; `save` dispatches on nothing, it writes the one
  format. The installer registers `.epdf` per user (coordinator); the app
  never registers `.html`.
- **Load** dispatches on `kind_of`: native `.epdf` and any `.html`/`.htm`
  (take the body, normalise); `.txt` (blank-line paragraphs, single
  newlines joined, `&<>` escaped); `.md`/`.markdown` through markdown-it-py
  4.0.0, which is installed and pure Python (headings, paragraphs, bold,
  italic, code spans and fenced blocks, links, images (embed a local file
  that exists through `embed_image`), nested bullet and numbered lists,
  blockquotes, rules, pipe tables with a header row); `.docx` through
  python-docx 1.2 (`docx_in.py`: Title and Heading 1 to 6 by style name,
  paragraphs, bold, italic, underline and strike runs, hyperlinks, bullet
  and numbered lists from `numPr` with nesting from `ilvl` if it comes
  cheaply and otherwise flattened with a warning, pictures with their Word
  description as `alt` through `embed_image`, tables with the first row as
  `th scope="col"`, core properties into `meta`; footnotes, comments,
  headers and footers, text boxes, fields and tracked changes are not
  read, and when `w:ins` or `w:del` is present warn "accept tracked
  changes in Word first"); `.pdf` through `import_pdf`. Anything imported
  returns `meta["source_kind"]` so the UI can say "opened from Word; Save
  will write Easy PDF's own format". A `file:` image source that still
  exists is embedded through `embed_image` on load with a warning that
  says so; one that is gone is dropped with a warning; an `http` or
  `https` source is never fetched and is dropped with a warning.
- **The allow list**, which is `normalise` and lives as one table in
  `htmlclean.py` and in `docs/PDF-UA.md`. Elements kept: `h1` to `h6`,
  `p`, `ul`, `ol`, `li`, `blockquote`, `strong`, `em`, `u`, `s`, `code`,
  `sup`, `sub`, `br`, `hr`, `a`, `img`, `figure`, `figcaption`, `table`,
  `caption`, `thead`, `tbody`, `tfoot`, `tr`, `th`, `td`, and `pre` in the
  file (a code-block `p` for export). Mapped: `b`, `i`, `strike`, `del`,
  `div`, `section`, `article`, `center`, `font`, `span` and every other
  inline or sectioning element are mapped or unwrapped as step 1 of the
  export says, text always kept. Dropped with their content: `script`,
  `style`, `template`, `iframe`, `object`, `embed`, `applet`, `frame`,
  `noscript`, `svg`, `math`, `form`, `input`, `button`, `select`,
  `textarea`, `link`, `meta`, `base`, `head`, `title`, `video`, `audio`,
  `canvas`, `map`, `area`. Attributes kept: `href` on `a` (http, https,
  mailto, tel), `src` on `img` (`data:` only, after embedding), `alt`,
  `role="presentation"` on an `img` with `alt=""`, `lang` on block
  elements, `scope` on `th`, `colspan` and `rowspan`, `class` from the
  app's own set only (`align-left`, `align-center`, `align-right`,
  `align-justify`, `width-quarter`, `width-half`, `width-three-quarters`,
  `width-full`, `place-left`, `place-centre`, `place-right`,
  `code-block`), and `data-needs-alt` and `data-alt-source` on `img`.
  Everything else is dropped, including every `on*` attribute, `id`,
  `style` (after the text-align and span folding), `title`,
  `contenteditable`, `spellcheck` and `role` elsewhere. A test feeds
  `<b>`, `<i>`, `<u>`, `<font>`, a `div`, a `span lang`, an `img` with
  `onerror`, an `a` with a `javascript:` address and an `img` with an
  `http` source, and asserts each outcome and each warning.
```

A8. Replace lines 163 to 175 (`Each prints ok/FAIL per check ...`) with:

```
Each prints ok/FAIL per check and exits non-zero on any failure. Cover:
the engine is found and renders the fixture, and `engines()` lists at
least one candidate with a version; the export's structure tree holds H1,
H2, H3, P, Strong, Em, Link with OBJR, L/LI, BlockQuote, Figure with the
exact Alt, Table/TR/TH/TD; the decorative figure is absent from the tree;
every font embedded; the page text holds no file path, no date and no
page number (the header and footer flag); XMP carries `pdfuaid:part` 1
and `dc:title` on the clean fixture and `pdfua_claimed` is True; a
fixture with a figure lacking a description exports tagged, without the
identifier, with `pdfua_claimed` False and a warning naming the check;
Info and XMP carry "Easy PDF" as Creator and a Producer that names the
engine and its version, after the final save; the checker passes the
clean file and fails the broken one; import of the exported fixture
recovers the headings and the text in order, one picture needing a
description, and the described figure's text as a recovered description
marked `data-alt-source="pdf"`; Markdown, text and docx fixtures (the
docx built in the test with python-docx: a heading, a bold run, a
hyperlink, a picture with a description, a two row table) convert to the
expected HTML; save then load returns the same body and meta, for `.epdf`
and for the same bytes written to `.html`; a save interrupted (simulate by
making replace fail) leaves the previous file intact; snapshot and
recover round trip; `normalise` turns `<b>` into `<strong>`, warns on a
missing alt, strips an `onerror`, drops a `javascript:` address and an
`http` image, hoists a whole-block `span lang` and warns on a partial one,
maps `pre` to a code-block `p` on export and strips `data-*` on export
while counting the AI ones; `embed_image` turns a 4,000 by 3,000 JPEG into
2,000 on the long edge at a fraction of the bytes and keeps a PNG as PNG;
Arabic text produces the right to left warning. Prove at least one test
can fail by breaking the input on purpose inside the test.
```

A9. Replace lines 184 and 185 (`- Write `docs/PDF-UA.md`: ...`) with:

```
- Write `docs/PDF-UA.md`: what the export guarantees, what the checker
  checks, what it cannot, why the PDF/UA identifier is gated and what
  withholds it, the allow list, the known engine gaps (no LBody, NonStruct
  wrappers, inline lang lost, right to left extraction faults), what is
  not in 1.0.0 (right to left, OCR, tree aware import), and how to verify
  a file in PAC or veraPDF.
```

### docs/briefs/worker-b.md

B1. Replace lines 61 to 65 (`One editor: a WebView2 page ...`) with:

```
One editor: a WebView2 page (`wx.html2`, Edge backend) holding a
`contenteditable` region. `CLAUDE.md` records that the backend, the
script message bridge and `execCommand` all work here, that `execCommand`
emits `<b>` and `<i>`, and that the WebView must never be touched after
its frame closes.

Two facts from the challenge shape the wrapper (DECISIONS.md, decision 1):

- **The editor API is asynchronous.** Synchronous `RunScript` hung for
  ever in two of four runs with the editor focused and NVDA running
  (CHALLENGE.md W2). Use `RunScriptAsync` with `EVT_WEBVIEW_SCRIPT_RESULT`
  and the message bridge; no synchronous `RunScript` anywhere once the
  editor exists. Selection state and the word count arrive in the page's
  own messages; the wrapper offers `run(js, callback)` and every caller
  continues in the callback. `tests/test_ui_names.py` greps `easypdf/ui/`
  and `editor_page.py` for `RunScript(` and fails on any.
- **The keyboard contract lives in the page.** With the editor focused,
  not one accelerator in the frame's table fired and the page's `keydown`
  listener saw every key (W4); Chromium's own bindings act first (W5); F5
  reloaded the page and Ctrl+F and Ctrl+P pulled focus into browser chrome
  (W6). A capture phase `keydown` handler with `preventDefault` stopped
  all of them (measured). So: the page's handler owns every key while the
  editor has focus, and forwards the app's keys to Python with
  `postMessage`; the wx accelerator table serves only when focus is
  outside the editor. See "Keys".
```

B2. Replace lines 77 to 82 (`- Which side wins a keyboard shortcut: ...`)
with:

```
- That exactly one handler fires per key and nothing double fires: press
  the key with `wx.UIActionSimulator` after taking the foreground with
  `AttachThreadInput`, and read the DOM back. A synthesised keystroke
  that goes nowhere looks exactly like a key that works, so do a control
  test first (type a letter, read it back). Then prove the deny list:
  type text, press F5, the text is still there; press Ctrl+F, the app's
  find dialog opens and WebView2's own bar does not; press Ctrl+P, the
  app's print runs.
- Whether NVDA is in focus mode when the editor receives focus after
  Ctrl+N and after Open: do the first letters typed land in the document,
  or act as quick navigation keys? Keep the `role="textbox"` variant if
  that is what makes it reliable, and say what you saw.
```

B3. Replace lines 85 to 88 (`- Whether Edit menu Cut, Copy and Paste ...`)
with:

```
- Paste goes through Python, because `execCommand('paste')` is refused and
  the clipboard promises never settle (W10), while copy works. Inside the
  editor: prevent the `paste` event, post the clipboard's `text/html` (else
  `text/plain`; else a picture as bytes) to Python; Python runs
  `htmlclean.normalise` (a picture goes through `docfile.embed_image` and
  becomes a figure needing a description); the page inserts the result
  with `insertHTML` so undo sees it. Edit, Paste from the menu reads
  `wx.TheClipboard` (HTML if present, else text) and takes the same path.
  Cut and Copy stay native. Measure that a paste from Word arrives as
  `strong`, `em`, `h1` and a list, not as spans.
```

B4. Replace line 89 (`- Whether `Ctrl+Alt+digit` reaches the page ...`)
with:

```
- `Ctrl+Alt+digit` reaches the page as Ctrl, Alt and the digit on a US
  layout (W4). On German, French, Polish, Spanish and Portuguese layouts
  the same chord is AltGr and types a character, so the page acts on
  Ctrl+Alt+digit only when `event.key` is the digit itself, and the
  Ctrl+Shift+digit aliases are gated on `event.code` (`Digit1` and so on),
  which is layout proof. Both are documented together in `KEYBOARD.md`.
```

B5. After line 100 (`stack sees it.`, the end of "The page's job")
insert:

```

The page's rules, from DECISIONS.md:

- `document.execCommand('defaultParagraphSeparator', false, 'p')` at
  load, and any bare text typed into the editing host is wrapped in a
  `p` on `input`; text outside a block is tagged as nothing in the PDF.
- Only sanitised HTML enters the page: every load, paste and import goes
  through Worker A's `htmlclean.normalise` in Python before `innerHTML`
  or `insertHTML`.
- A Content Security Policy in the page's `<head>`: `default-src 'none';
  script-src 'nonce-<n>'; style-src 'unsafe-inline'; img-src data:;
  base-uri 'none'; form-action 'none'`, with a fresh nonce per page load
  on the page's own `<script>`. Bind every handler with
  `addEventListener`; no inline handlers in the page's own HTML, since
  the policy blocks them. Test: load a body holding an `img` with an
  `onerror` handler that would set a marker; the marker is never set.
- Veto every navigation after the first load in `EVT_WEBVIEW_NAVIGATING`,
  so no link, address or drop can ever take the editor away.
- The `contextmenu` event is prevented and posted to Python with the
  caret's client rectangle; the wx context menu pops up there. That is
  how the Applications key and Shift+F10 work inside the editor.
- Load resets the undo history (a new document has none to lose).
  Replace All must be undoable with one Ctrl+Z: first try computing the
  new body on a clone by walking text nodes, then applying it with
  select all plus `execCommand('insertHTML')`, which is undoable (W7), and
  measure that headings, lists and `strong` survive; if they do not, the
  page keeps the previous body and the next Ctrl+Z restores it before the
  browser's own undo runs, and the status bar says "Replaced N. Press
  Ctrl+Z to put them back."
- Tables, the basic level: Tab and Shift+Tab move between cells, Tab in
  the last cell adds a row, and that is all the table editing in 1.0.0.
- State messages carry booleans and the block type, never the document.
  The document crosses the bridge only on save, export and autosave, and
  autosave copies it only when it changed since the last snapshot.
  Measure a 200 page document with twenty pictures at 2,000 pixels: time
  to load, time to get the HTML back, process memory. Report the numbers.
```

B6. Replace lines 110 to 112 (`Word's map, plus the TG Studios contract.
Every key below is in one accelerator list ...`) with:

```
Word's map, plus the TG Studios contract. Every key below lives in **one
list** in `easypdf/ui/keymap.py` (yours), and that list feeds four
things: the wx accelerator table (used only when focus is outside the
editor), the key map generated into the page's JavaScript (used whenever
the editor has focus), the menu labels, and `docs/KEYBOARD.md`. The page
also holds the deny list of browser keys it swallows with nothing
forwarded: F5, Ctrl+R, Ctrl+Shift+R, F3 when not the app's find next,
Ctrl+G, F12, Ctrl+Shift+I when not the italic alias, Ctrl+Shift+J,
Ctrl+Shift+C, Ctrl+U when not underline, Ctrl+S, Ctrl+O, Ctrl+P, Ctrl+F
and every key in the app's map; the app's own keys are forwarded and
handled once. `tests/test_menus.py` asserts the list; `tests/test_keys.py`
presses the keys.
```

B7. Replace lines 114 to 116 (`- File: `Ctrl+N` new, ...`) with:

```
- File: `Ctrl+N` new, `Ctrl+O` open, `Ctrl+S` save, `Ctrl+Shift+S` save
  as (`.epdf`), Save as web page (no key; the same bytes to `.html`),
  `Ctrl+W` close document, `Ctrl+Shift+E` export PDF, `Ctrl+P` print,
  `Alt+F4` exit. Recent documents, the last `constants.RECENT_FILES`
  (eight), each with a numbered mnemonic 1 to 8, under File.
```

B8. Replace lines 119 to 123 (`- Format: `Ctrl+B` bold, **`Ctrl+I` italic**
...`) with:

```
- Format: `Ctrl+B` bold, `Ctrl+I` italic, `Ctrl+Shift+I` italic as well
  (the April alias, kept), `Ctrl+U` underline, `Ctrl+Shift+K` strike,
  `Ctrl+Alt+1` to `6` headings, `Ctrl+Alt+0` normal, `Ctrl+Alt+8`
  bullets, `Ctrl+Alt+9` numbered, with `Ctrl+Shift+1` to `6`,
  `Ctrl+Shift+0`, `Ctrl+Shift+8` and `Ctrl+Shift+9` as the layout proof
  aliases (gated on `event.code`), `Ctrl+Q` quote, `Ctrl+L` `Ctrl+E`
  `Ctrl+R` `Ctrl+J` alignment. There is no font dialog and no
  `Ctrl+Shift+F`: the document font and size are document properties and
  Preferences defaults, not a per run choice.
```

B9. Replace lines 124 and 125 (`- Insert: `Ctrl+K` link, **`Ctrl+Shift+P`
picture** ...`) with:

```
- Insert: `Ctrl+K` link, `Ctrl+Shift+P` picture (settled), `Ctrl+Shift+T`
  table.
```

B10. Replace line 139 (`Write `docs/KEYBOARD.md` from the same list ...`)
with:

```
Write `docs/KEYBOARD.md` from `keymap.py`, by a script, not by hand, and
have `test_menus.py` fail when they differ. Document the AltGr rule and
the aliases together.
```

B11. Replace lines 143 to 149 (`File, Edit, Format ...`) with:

```
File (New, Open, Recent documents, Save, Save As, Save as web page, Close,
Export PDF, Print, Exit), Edit, Format (with Paragraph style and Alignment
submenus), Insert, Tools, View, Help. Help holds: Keyboard shortcuts
(`F1`), User guide on the web (greyed with "not published yet" in the
status bar if the page is not there; `constants.USER_GUIDE_URL`), Check
for updates, Donate (`constants.DONATE_URL`), About (name, version,
tagline, TG Studios, the engine it found with its version from
`pdfengine.engines()`, in a read-only field). Nothing multi-line ever
goes in a `wx.MessageBox`.
```

B12. In the dialogs list:

Replace lines 158 to 166 (`- **Insert picture** (`Ctrl+Shift+P`) ...`)
with:

```
- **Insert picture** (`Ctrl+Shift+P`) and **picture properties**
  (`Alt+Enter` on a picture): file, preview (a `StaticBitmap` that refuses
  focus), description (required, or the decorative box ticked), an
  optional caption, width (a quarter, half, three quarters, full text
  width) and placement (left, centre, right), and a Describe button that
  opens Worker C's `DescribeImageDialog` and puts its answer in the
  description field for editing. The file goes through
  `docfile.embed_image`, and the dialog states what went in, in one
  sentence in a read-only static: "Picture: 1,600 by 1,200 pixels, 240
  KB, reduced from 4,000 by 3,000" (the words in `STRINGS.md`). When the
  user accepts a description that came from the describer, the `img` gets
  `data-alt-source="ai:<provider>"` (from the dialog's `provider_used`);
  editing the text by hand afterwards clears it. Build controls directly
  on the dialog, never on an inner panel with `CreateButtonSizer` (the
  prototype's OK button was unclickable for exactly that reason).
```

Replace lines 170 to 172 (`- **Find and replace**: modeless, ...`) with:

```
- **Find and replace**: modeless, `window.find` for next and previous,
  replacement through DOM edits that keep formatting, Replace All by the
  undoable route in "The editor" above, never by rewriting the whole
  document through `innerHTML`.
```

Replace lines 175 to 177 (`- **Pictures** (`Ctrl+Shift+Alt+P`): ...`)
with:

```
- **Pictures** (`Ctrl+Shift+Alt+P`): every picture, its description or
  "no description", with "described by AI" or "recovered from the PDF,
  please check" where `data-alt-source` says so, Edit and Describe
  buttons. This is what an imported PDF needs first.
```

Replace lines 178 to 182 (`- **Export**: runs Worker A's `export_html`
...`) with:

```
- **Export**: runs Worker A's `export_html` on a thread with a progress
  dialog that speaks its steps through `announce_help`; then a result
  dialog with the checker's report in a read-only field, focus in the
  field, and buttons Open PDF, Open folder, Close. Warnings from the
  export go in the same field above the report, and the first line says
  whether the PDF/UA identifier was written (`pdfua_claimed`) and, if
  not, which check stopped it.
```

Replace lines 183 to 186 (`- **Open**: `docfile.load` for every kind;
...`) with:

```
- **Open**: `docfile.load` for every kind (`.epdf`, `.html`, `.txt`,
  `.md`, `.docx`, `.pdf`); PDF import on a thread with progress;
  afterwards, if pictures need descriptions, say how many and offer the
  Pictures dialog. An imported file is marked modified and Save becomes
  Save As in the native format, and the status bar says where it came
  from ("opened from Word", from `meta["source_kind"]`).
```

Replace lines 194 to 197 (`- **Autosave and recovery**: ...`) with:

```
- **Autosave and recovery**: `docfile.snapshot` every
  `constants.AUTOSAVE_SECONDS` while modified and changed since the last
  snapshot; at start, if `paths.PREVIOUS_RUN_CRASHED` is True and
  `docfile.recoverable()` is non-empty, offer to reopen, in a dialog with
  a read-only field naming the document and the time. A clean close
  deletes the snapshot after the save prompt, so stale snapshots never
  pile up; the crash signal itself is the coordinator's marker.
```

B13. After line 198 (`- **Unsaved changes**: ...`) insert:

```
- **First run**: one status bar line and one `announce_help` hint, spoken
  once, the first time the app opens with no settings file. Draft for
  `STRINGS.md`: "Welcome to Easy PDF. Start typing. F1 lists the keys and
  Ctrl+Shift+E makes the PDF." Tony rewrites it.
- **A second launch with a file** arrives through `open_document(path)`
  (the contract above): `main.py` installs `handoff.Receiver` on the
  frame and the callback runs inside the window procedure while the
  second launch waits, so `open_document` must return at once and do its
  work through `wx.CallAfter`: the save changes prompt, then the load.
  One window, one document: opening replaces the current document after
  the prompt.
- **Closing**: in `EVT_CLOSE`, after the save prompt, write settings,
  recent files and window geometry, delete the snapshot, then let the
  frame close and own the WebView (`CLAUDE.md`). Nothing is written in
  `atexit`, and the frame never calls `os._exit`; `main.py` removes the
  running marker after `MainLoop` returns.
```

B14. Replace lines 208 to 217 (`A toolbar with real icons ...`) with:

```
A toolbar with real icons (draw them with a `GraphicsContext` the way
`appicon.py` does, sized for the DPI, in the system colours from
`wx.SystemSettings.GetColour` so they hold up in High Contrast, redrawn
on `EVT_SYS_COLOUR_CHANGED`, with tooltips naming the key) and text
labels available; the editor page white like paper with a light grey
surround, a visible caret, focus rings; a status bar with four fields
(message, paragraph style, word count, document language); sensible
minimum sizes; everything readable at 150 and 200 percent scale; the
window icon in the title bar and taskbar; Windows high contrast respected
in the page through `forced-colors` and the system colour keywords. Leave
native controls' colours alone (wx 3.2.9 has no dark mode for them). Take
screenshots of the main window and every dialog at 100 and 150 percent
and put them in `docs/screenshots/`.
```

B15. Replace lines 221 to 235 (the five test bullets) with:

```
- `test_menus.py`: every menu item has a handler; every entry in
  `keymap.py` has a menu item; the contract keys are present; no two
  entries share a key; the page's generated key map lists every entry;
  `docs/KEYBOARD.md` matches the list.
- `test_keys.py`: real keystrokes into the real editor after taking the
  foreground, with the control test first; Ctrl+B, Ctrl+I, Ctrl+Shift+I,
  Ctrl+Alt+2, Ctrl+Shift+2, Ctrl+Alt+8, Enter in a list, Tab in a list,
  Tab in a table cell, Ctrl+K, read the DOM back; F5 leaves the text in
  place; Ctrl+F opens the app's dialog; Ctrl+Z after an inserted link
  restores the typing (W7); Replace All then Ctrl+Z restores the body;
  the watchdog: a script issued 700 milliseconds after a keystroke into
  the focused editor answers within five seconds.
- `test_ui_names.py`: walk every dialog's children; every focusable
  control has an accessible name or a preceding static label; no dead tab
  stop (the preview bitmap refuses focus); no `wx.MessageBox` with a
  newline in it anywhere under `easypdf/ui/` (grep); no synchronous
  `RunScript(` anywhere under `easypdf/ui/` or in `editor_page.py` (grep).
- `test_ui_page.py`: the editor API through the asynchronous wrapper (a
  helper pumps the loop until the result event arrives, under a
  timeout): set HTML, apply each block style, insert a link, insert a
  picture with alt, read the selection state back, find and replace
  preserving `strong`; a body holding an `img` with an `onerror` that
  would set a marker never sets it; the real DOM after bold, italic, a
  list and centre alignment, passed to `htmlclean.normalise`, comes back
  as `strong`, `em`, `ul` and the `align-center` class (the drift test);
  `handoff.send_path(int(frame.GetHandle()), path)` from the test's own
  process returns True at once and the document opens after the loop
  pumps, with a modified document's save prompt answered by the test;
  after `Close()` of a saved document no snapshot remains, and after
  tearing the frame down without `EVT_CLOSE`, with
  `paths.PREVIOUS_RUN_CRASHED` forced True, the snapshot remains,
  `docfile.recoverable()` lists it and the recovery dialog is offered.
- `test_settings.py`: round trip, missing file, corrupt file, migration
  of a missing speech level to the default.
```

B16. After line 249 (`how you know.`, the last rule) insert:

```
- The words in DECISIONS.md are conditions, not suggestions: asynchronous
  API, keys in the page, one sanitiser in Python, the Content Security
  Policy, undoable edits, the navigation veto. A worker report that
  reads "not needed" on any of them is a defect.
```

### docs/briefs/worker-c.md

C1. Replace lines 9 to 17 (`The provider layer already exists: ...`) with:

```
The provider layer already exists: `easypdf/ai.py` is a verbatim copy of
`Dropbox\TG Studios\TG Drop Deck\dropdeck\vision.py`, which shipped on
2026-09-08 and is proven against all three services. Keep from it, with
their shape, so a fix in Drop Deck can be carried across: the transport
(`_request`, the three provider functions and their readers), `_trouble`
and its sentences, `list_models` and the model list diggers,
`providers_with_keys`, `best_provider`, `redact`, and the rules that
nothing here raises, every failure is a sentence somebody can act on,
model names are settings with a moving-alias default, keys go in a
header never a URL, and nothing leaves without consent. Do **not** keep
the camera and screen prompts, `DEFAULT_MODELS` (tuned for a presenter
waiting to go on air), `SEND_WIDTH` 1024, `needs_consent` or
`consent_question` (built for the screen case). Replace them as below
(DECISIONS.md, decision 8). Defaults are chosen for accuracy: pick each
provider's default from its live model list, measure the answer for
`tests/fixtures/circle.png` and for a chart with labels with the
candidate models you can reach, and say in your report which you chose
and why. Pictures go at up to 1,600 pixels wide (`SEND_WIDTH`), JPEG for
a JPEG source and PNG for a PNG source, so chart labels and screenshots
stay legible.
```

C2. Replace lines 35 to 37 (`consent_needed(kind: str) -> bool ...` to
`consent_question(...)`) with:

```
consent_needed(kind: str, imported: bool, pictures: int) -> bool
    # "document": every time. "image" from the user's own disk: once per session.
    # An image that arrived inside an imported document (imported=True), and any
    # batch (pictures > 1): every time. DECISIONS.md decision 8 says why.
record_consent(kind: str) -> None
consent_question(kind: str, provider: str, pictures: int, words: int,
                 kilobytes: float, imported: bool) -> str
    # names the provider, the count and the size, and says to check the
    # provider's data policy before sending anything private
```

C3. Replace lines 41 and 42 (`DescribeImageDialog(...)` and `.result`)
with:

```
DescribeImageDialog(parent, image_bytes, current_alt="", context="",
                    imported=False) -> wx.Dialog
    .result -> str | None      # the text the user accepted, edited or not
    .provider_used -> str      # "anthropic", "openai" or "google"; Worker B writes it into data-alt-source
```

C4. Replace lines 75 to 78 (`- **Consent.** A whole document leaving the
machine ...`) with:

```
- **Consent.** A whole document leaving the machine asks every time,
  naming the provider, the number of pictures, the number of words and
  the megabytes. A single picture the user inserted from their own disk
  asks once per session. A picture that came in with an imported document
  (a PDF or a Word file somebody sent) and any batch of pictures ask every
  time: that is somebody else's document leaving the machine. The
  question is a dialog with a read-only field, the same shape as
  everything else here, and it ends with one sentence that says to check
  the provider's data policy before sending anything private; the policy
  addresses are in `docs/DESCRIBER.md` and the dialog names the file.
  Every consent text goes to Tony.
```

C5. Replace lines 88 to 93 (`- **The settings page.** Provider choice, ...`)
with:

```
- **The settings page.** Provider choice, the key field (masked, with a
  Show box), a "Get the list" button that fills the model combo from the
  live account, a Test button that sends a tiny request and reports in a
  status static (never the key), a Forget key button, and a "Use the key
  I gave TG Drop Deck" button that, after a yes in a dialog naming the
  provider, reads `secrets.fetch(provider, "TG Drop Deck vision key: ")`
  and stores it under Easy PDF's own prefix, saying whether it found one.
  Every control named. `apply()` writes provider and model to settings
  and the key to Credential Manager; a blank key forgets the stored one.
```

C6. Replace lines 109 to 120 (`test_ai.py`: the three request builders
...`) with:

```
`test_ai.py`: the three request builders produce the right envelope for one
picture and for text plus several pictures (inspect the JSON); the readers
dig the text out of each provider's answer shape; `_trouble` maps 401, 404,
429, 400, 5xx and a network error to sentences that name the provider; the
model list digger handles each shape; a JPEG source is scaled and JPEG
encoded below the size cap and a PNG source stays PNG, both at most 1,600
wide; a fake `urlopen` end to end. `test_describe.py`: consent state
(document every time; a picture from disk once, then not again; a picture
marked imported every time; a batch every time; reset per session);
`payload_estimate` counts words, pictures and kilobytes; the alt prompt
contains the context; the document prompt lists the headings; the Drop
Deck key button's helper reads the other prefix and stores under this
one (against a probe entry it creates and removes, never Tony's real
key); the live Gemini check (skipped without the key) gets a non-empty
sentence back for `tests/fixtures/circle.png` and reports how long it
took. Prove at least one test can fail.
```

C7. Replace lines 131 to 133 (`- Write `docs/DESCRIBER.md`: ...`) with:

```
- Write `docs/DESCRIBER.md`: what leaves the machine and when (the
  provenance rule above), how to get a key from each provider, what each
  provider says it does with submitted content (Google's Gemini API free
  tier uses content to improve its products and the paid tier does not;
  OpenAI and Anthropic retain for abuse monitoring; policies change, so
  give the addresses and the date you read them), what it costs in rough
  terms, and what the app will never do with the answer (write it into
  the document unread). The prompts, in full, so Tony can read what is
  asked in his name.
```

C8. Replace lines 71 to 74 (`- **Multi-image requests** ...`) with:

```
- **Multi-image requests** for the document description: a builder per
  provider that takes one text part plus up to a cap of pictures (choose
  the cap and say why; measure payload size). Over the cap, send the first
  N and say so in the answer. Scale every picture before it goes, at the
  1,600 pixel width and the PNG or JPEG rule above.
```

### docs/briefs/overseer.md

O1. Replace lines 50 to 62 (the Round 4 paragraph) with:

```
With NVDA running, drive the built app (the coordinator will tell you the
path to the frozen exe) as a blind user would: open it, write a document
with a heading, a list, a link, a table and a picture with a description,
export, read the checker's report, open a PDF, run the describer's
dialogs and read every consent text back, change the speech level, check
for updates, double click a second document while the app is open. Take
the foreground with `AttachThreadInput` before any synthesised input, and
do a control test first. Read NVDA's output from its log or the
accessibility tree, and say which. Measure what NVDA's browse mode does
inside the editor (H, K, G, L, T quick keys and NVDA+Space), whether
focus mode is on when the editor receives focus after Ctrl+N and Open,
and how the table reads. Repeat the main flow once with Windows High
Contrast on, and once with Narrator instead of NVDA; the Narrator pass is
information, not a gate, and its defects are listed and fixed when cheap.
If Tony approved the download, run veraPDF on the exported fixtures and
turn every failure into a named checker rule for the report. List every
place where the app said nothing, said the wrong thing, put focus
somewhere useless, or left a control unnamed. Then reconcile with the
Challenger's visual audit: where you disagree on a fact, measure it, and
say who was right.
```

### For the coordinator (files outside the three briefs)

These are not brief edits but the decisions above do not hold without
them. Apply before the workers start, so the constants and interfaces
they code against are the settled ones.

K1. `easypdf/constants.py`:

- Add to the frozen block, with the same comment discipline:
  `DOC_PROGID = "TGStudios.EasyPDF.Document"` (the registry ProgId; a
  changed ProgId orphans the old key on every machine) and
  `CONFIG_FOLDER_NAME = "Easy PDF"` (the settings folder under `TG
  Studios`; a display rename after release must not move everybody's
  settings). Make `paths.config_dir()` and `paths.local_dir()` use
  `CONFIG_FOLDER_NAME` instead of `APP_NAME`.
- Files section: `DOC_EXTENSION = ".epdf"`, `DOC_WILDCARD = "Easy PDF
  documents (*.epdf)|*.epdf"`, `WEB_PAGE_WILDCARD = "Web page
  (*.html)|*.html"`, `IMPORT_EXTENSIONS = (".epdf", ".html", ".htm",
  ".txt", ".md", ".markdown", ".docx", ".pdf")`, `OPEN_WILDCARD` rebuilt
  from that with "Word documents (*.docx)" and without Rich Text,
  `DOC_TYPE_DESCRIPTION = "Easy PDF document"` (STRINGS.md, draft),
  `IMAGE_MAX_EDGE = 2000`, `IMAGE_JPEG_QUALITY = 85`.
- `tests/test_scaffold.py` asserts the two new frozen constants and that
  `IMPORT_EXTENSIONS` holds `.docx` and `.epdf` and not `.rtf`.

K2. `tools/easypdf.iss`: add `ChangesAssociations=yes` to `[Setup]` and a
`[Registry]` section, per user, with `uninsdeletekey`:
`HKCU\Software\Classes\.epdf` default value `TGStudios.EasyPDF.Document`;
`HKCU\Software\Classes\TGStudios.EasyPDF.Document` default value `Easy PDF
document`; its `DefaultIcon` default value `"{app}\Easy PDF.exe",0`; its
`shell\open\command` default value `"{app}\Easy PDF.exe" "%1"`. The zip
copy registers nothing and the README says so.

K3. `tests/test_scaffold.py`: assert the `[Registry]` lines and
`ChangesAssociations=yes` are in the `.iss`, the same way the AppId is
asserted.

K4. `main.py`, the startup guard: before `build_main_window`, if
`wx.html2.WebView.IsBackendAvailable(WebViewBackendEdge)` is false or
`WebView2Loader.dll` cannot be found beside wx (source) or the exe
(frozen), show a dialog with a read-only multiline field (not a
`wx.MessageBox`), focus in the field, that says the app needs the
Microsoft Edge WebView2 runtime, names the download page
(https://developer.microsoft.com/microsoft-edge/webview2/), copies that
address to the clipboard and says so, and exit. Words to `STRINGS.md`
under Coordinator, draft.

K5. `main.py`, the file handoff, which is built (`easypdf/handoff.py`,
`tests/test_handoff.py`, main.py lines 319 to 324 and 381 to 386 as of
08:32). One fix: `OnInit` installs `frame.open_document` as the
receiver's callback, and the callback runs inside the window procedure
while the second launch waits in `SendMessageTimeout` (five seconds,
`SMTO_ABORTIFHUNG`). A save changes prompt inside `open_document` would
keep the second launch waiting until the timeout and make `hand_over`
report False. Install `lambda path: wx.CallAfter(opener, path)` instead,
so the message returns at once and the prompt runs from the main loop.
Add a check to `test_handoff.py` with a callback that sleeps two seconds:
the child must still print "sent True" and finish in well under two
seconds. `singleinstance.py` stays byte identical. The crash marker in
`paths.py` (`mark_started`, `mark_clean_exit`, `PREVIOUS_RUN_CRASHED`) is
adopted as built; add a check to `test_scaffold.py` that `mark_started()`
then `mark_clean_exit()` leaves no marker, and that a marker left behind
makes the next `mark_started()` return True.

K6. `main.py`, the selftest: switch the editor probe to `RunScriptAsync`
with `EVT_WEBVIEW_SCRIPT_RESULT` (a synchronous hang would block the
`wx.CallLater` watchdog on the same thread); have the same probe report
`window.devicePixelRatio` and fail if it is below `frame.GetDPIScaleFactor()`;
render the one line document with every engine `pdfengine.engines()`
finds, read each tree back with pikepdf, and name each one in the notes;
write and read back `pdfuaid:part` in the right namespace on the selftest
PDF; run `htmlclean.normalise` on a snippet holding an `onerror` and a
`javascript:` address and fail if either survives; import `docx` and
`markdown_it` so a missing hidden import shows up in the frozen build.

K7. `main.py` docstring line 4 and `README.md`: the file list is html,
epdf, txt, md, docx, pdf; rtf is gone.

K8. `docs/PLAN.md`:

- File ownership: add `easypdf/docx_in.py` to Worker A and remove any
  mention of `rtf_in.py`; add `easypdf/ui/keymap.py` to Worker B; add
  `easypdf/handoff.py` and `tests/test_handoff.py` to the coordinator.
- Interfaces: update `docfile.kind_of`, add `docfile.embed_image`,
  `pdfengine.engines()`, `ExportResult.pdfua_claimed`,
  `Report.pdfua_gate`, `ImportedImage.alt` and `alt_source`,
  `normalise(body_html, for_export=False)`, `consent_needed(kind,
  imported, pictures)`, `consent_question(...)`,
  `DescribeImageDialog(..., imported=False)` with `.provider_used`.
- Standing rules, the consent sentence: append "A picture that arrived
  inside an imported document, and any batch of pictures, is that
  document leaving the machine and asks every time."
- Definition of done: add "the export's PDF/UA identifier was written
  (`pdfua_claimed` True) on the definition-of-done document; a fixture
  holding an `img` with an `onerror` handler opens without running it; a
  second launch with a document path opens it in the running copy."
- Order of work, step 7: the Overseer's audit adds the High Contrast and
  Narrator passes; the Challenger's visual audit runs at 150 percent and
  once at 200 percent.

K9. The project `CLAUDE.md`, "Measured on this machine": change the
`execCommand` bullet to say that `execCommand` emits `<b>` and `<i>` and
that Chromium tags `b`, `i`, `u`, `span lang`, `div` and `pre` as nothing
in the PDF (measured 2026-09-09 by the Challenger and again by the
Overseer), so normalisation before save and export is mandatory; qualify
"synchronous `RunScript`" with "works before the editor has focus; hung
in two of four focused runs with NVDA running (CHALLENGE.md W2), so the
editor API is asynchronous"; add a standing rule "Only sanitised HTML
enters the editor page, and the page carries a Content Security Policy";
and change the native format line to `.epdf`.

K10. `docs/STRINGS.md`, under Coordinator: the file type description
"Easy PDF document"; the startup guard text; the "opened from" sentences
are Worker A's and B's under their own headings.

K11. `CHANGELOG.md`: nothing yet; the 1.0.0 entry lists the "not in
1.0.0" items above when it is written.

K12. The report to Tony: the name question with the three options and the
deadline, the pricing framing, the approval packet, and the two downloads
that need his yes.


## Amendment, 2026-09-09, after the Overseer's review of Worker A

Edit A4 read literally cannot hold with edit A8: `alt=""` measurably makes
Chromium drop the picture from the structure tree, so a picture with a
bare `alt=""` is an artifact and can never fail "Pictures described". The
Overseer ruled for Worker A's resolution, and this is the contract every
part of the app follows:

- In the document file, a picture whose description is missing carries
  `alt="" data-needs-alt="1"` and the sanitiser warns. Nothing is silently
  decorative; the Pictures dialog lists it.
- At export, that picture is written with NO alt attribute, so it becomes a
  Figure without Alt, the checker fails "Pictures described" by name, and
  the PDF/UA identifier is withheld.
- A decorative picture is `alt=""` with `role="presentation"`, and only the
  decorative box in the picture dialog writes that. The editor must never
  write a bare `alt=""` for a picture that simply has no description yet.
- The export writes `role="presentation"` on every figure element and the
  Caption sits beside the Figure, because a plain figure makes an outer
  Figure without Alt (Matterhorn 13-004). Round 4 looks at that shape in
  PAC and veraPDF specifically, if Tony approves the downloads.
- The `embed` keyword on `normalise` and the `report` field on
  `ExportResult` are accepted additions to the interfaces.


## Additions after 0.1.0, recorded so the interfaces stay honest

- `describe.payload_estimate(body_html, images)` still returns three values
  (words, pictures, kilobytes), as C2 says. `describe.payload_plan` is the
  additive four value version (words, pictures, attached, kilobytes) that
  the consent question uses, so the number it says is the number that goes.
- `describe.find_form_fields(page_image, page_index, page_width,
  page_height, provider, model, known=None, progress=None)` returns
  `(True, [Proposal])` or `(False, sentence)`. Consent kind is
  `"form page"`, and it asks every time.
- `tgimprint/pdfforms.py` is a new module owned by Worker A: filling PDF
  forms in place, and proposing fields for a form that has none. It never
  goes through the import path, which would destroy the layout.
