# Easy PDF, the challenge (2026-09-09)

The Challenger's brief was to argue against every decision in ANALYSIS.md
section 10, name the biases in the analysis, and force each decision to be
justified or flipped. This is that argument. Nothing here is implemented.

No em dashes or en dashes anywhere in this file. Tony's rule.

## How this was written

- Read, in order: ANALYSIS.md, PLAN.md, CONVENTIONS.md, RELEASING.md, every
  file in main.py, core and ui as found, Drop Deck's vision.py, secrets.py and
  the first 120 lines of its CLAUDE.md.
- Measured on this machine today, with NVDA running, on a 1920 by 1080
  display at 150 percent: Edge 152, Chrome 152, the WebView2 runtime
  152.0.4191.66, wxPython 4.2.5 on wxWidgets 3.2.9, Python 3.13.5,
  pikepdf 10.5.1, PyMuPDF 1.27.2.
- Every claim below that starts with "measured" comes from a script in the
  session scratchpad: edge_render.py, edge_followup.py and wx_harness.py 1
  to 7. Results are in edge_results.json, edge_followup.json and
  wx_results2.json to wx_results7.json there.
- Where I could not measure, I say so. A guess is labelled a guess.

## What I measured, in one place

The verdicts cite these by number.

### The engine

- E1. Edge headless, Chrome headless and the WebView2 runtime's own
  msedge.exe (in Program Files (x86), Microsoft, EdgeCore, 152.0.4191.66)
  all produced the same tagged PDF from the same sample: 85,722 bytes, the
  same structure counts, the same fonts. The runtime is registered at HKLM,
  Software, WOW6432Node, Microsoft, EdgeUpdate, Clients, the WebView2 GUID,
  with pv 152.0.4191.66. Times: 1.0 to 1.7 seconds for one page, 2.9
  seconds for 203 pages (1,500 paragraphs, 885 KB out), 1.7 seconds for
  five 4000 by 3000 photos.
- E2. Chromium's default flags print a header and footer on every page
  (date, title, the source URL, which is a temp file path, and page
  numbers). They are marked as Artifacts, so the structure is fine, but
  they are visible. The flag no-pdf-header-footer removes them. The flag
  generate-pdf-document-outline adds bookmarks from the headings.
- E3. Printing with the default profile while the Edge browser was already
  running worked in 1.7 seconds. No hand-off problem.
- E4. Structure elements in the sample: Document, H1, H3, P, Strong, Em,
  Code, Link, L with ListNumbering (Disc, Circle, Decimal), LI, Lbl,
  BlockQuote, Figure with Alt, Caption, Table, TR, TH with Scope Column
  and Scope Row, TD with Headers, and 33 NonStruct wrappers. No LBody, no
  Div, no Span elements. Lang on the paragraph for fr, ar and ja. Fonts are
  Type0, subset embedded, with ToUnicode and CIDToGIDMap Identity. Tabs S.
  A ParentTree. No RoleMap.
- E5. Inline elements, one file each: strong becomes Strong, em becomes Em,
  code becomes Code, a becomes Link. b, i, u, s, sup, sub, a bold span, a
  font tag, a span with lang, abbr and br become nothing at all. A div
  produces no P: its text sits in NonStruct straight under Document. pre
  produces no P either. An img with no alt attribute becomes a Figure with
  no Alt, which is a PDF/UA failure. An h2 inside a div is still H2.
- E6. Every text operator in the page is inside marked content, once the
  counter counts BMC as well as BDC. My first counter ignored BMC and
  reported exactly half the text as unmarked. That is a lesson for the
  in-app checker, not a fault in Chromium.
- E7. Arabic: the text extracted from the PDF has the lam-alef ligature in
  the wrong order (the word for "the test" came back with its letters
  swapped) and the sentence's full stop at the visual start. ToUnicode
  maps to base letters, not presentation forms. Japanese came back intact.
- E8. Five different 4000 by 3000 JPEGs of 884 to 1,144 KB: the HTML with
  them inline was 6,840 KB, the PDF was 5,162 KB, and it holds five
  DCTDecode images at 4000 by 3000 of 906 to 1,172 KB each. Chromium does
  not downsample.
- E9. pikepdf writes pdfuaid:part in the right namespace
  (http://www.aiim.org/pdfua/ns/id/), syncs dc:title to the Info Title, and
  keeps the structure tree through a save. The Info Producer came out as
  "pikepdf 10.5.1" in four of six patch variants and "Easy PDF" in two. So
  an honest Producer is possible and must be asserted by a test.

### The editor (wx.html2 with the Edge backend)

- W1. AddScriptMessageHandler works; a page posting its state every 200 ms
  delivered about five messages a second for a minute with nothing lost.
  RunScriptAsync with EVT_WEBVIEW_SCRIPT_RESULT returned before focus,
  after focus and after keystrokes, every time.
- W2. Synchronous RunScript hung for ever (the watchdog had to kill the
  process) in two of the four runs in which the editor had keyboard
  focus. Once it was the first sync call 700 ms after a keystroke, once it
  was the first sync call straight after SetFocus. Two later runs with the
  same pattern did not hang. It never hung while the editor was unfocused.
  NVDA was running throughout. Not deterministic; enough.
- W3. An 8 MB string through sync RunScript: 0.37 seconds in, 0.33 seconds
  out, equal on return.
- W4. With the editor focused, not one accelerator in the frame's table
  fired, for any of F1, F6, Shift+F6, Alt+F6, Ctrl+Alt+1, Ctrl+K, Ctrl+N,
  Ctrl+S, Ctrl+I, Ctrl+U, Ctrl+B or Ctrl+Shift+E. The page's keydown
  listener saw every one of them.
- W5. Chromium's own editing bindings act first: Ctrl+B wrapped the next
  character in b, Ctrl+I in i, Ctrl+U in u. Measured output:
  a paragraph containing i, then u, then the letter.
- W6. Chromium's browser keys inside WebView2: F5 reloaded the page, which
  is the document gone. Ctrl+F opened WebView2's own find bar, and the
  document lost focus. Ctrl+P opened the print preview inside the webview,
  and the document lost focus. Ctrl+U, Ctrl+S and Ctrl+Shift+I did
  nothing (DevTools is off by default). A capture phase keydown listener
  calling preventDefault stopped F5, Ctrl+U, Ctrl+F and Ctrl+Shift+I with
  the document intact and focused.
- W7. Undo: an edit made with range.insertNode (the as-found insertLink
  and insertImage) is not on the undo stack; Ctrl+Z after it removed the
  user's previous typing and left the inserted link in place. An edit made
  with execCommand insertHTML is undone properly. After innerHTML is
  assigned (load, Replace All), undo does nothing.
- W8. Enter inside a p makes a new p. Enter in an empty editing host makes
  a div unless defaultParagraphSeparator is set to p. Text typed straight
  into the host root stays a bare text node, which the PDF tags as
  NonStruct, not P (E5).
- W9. execCommand bold, italic and fontSize emit b, i and a font tag. With
  E5, the as-found editor's bold and italic produce no Strong or Em in the
  PDF at all.
- W10. execCommand copy works without a user gesture (the wx clipboard
  received the editor's text). execCommand paste returns false. The
  navigator.clipboard promises never settled.
- W11. Loading HTML that contains an img with an onerror attribute through
  innerHTML ran the handler. A script element did not run. So opening a
  hostile file runs script inside the editor.
- W12. devicePixelRatio was 1 inside a DPI unaware Python process on this
  150 percent display: Windows was stretching the editor. forced-colors was
  false, so high contrast could not be measured here.
- W13. wx.html2.WebView exposes EnableAccessToDevTools, zoom, backend
  version, a raw native pointer and Print. Nothing for browser accelerator
  keys and nothing for printing to PDF. comtypes 1.4.16 is installed, so a
  COM route to both exists but is unbuilt.
- W14. WebView2Loader.dll lives in site-packages, wx. A frozen build must
  carry it.

### The machine and the shelf

- X1. Installed: python-docx 1.2.0, markdown-it-py 4.0.0, beautifulsoup4,
  lxml 6.0, PyMuPDF 1.27.2 (it has markinfo and set_markinfo and no
  structure tree API at all), pikepdf 10.5.1, Pillow 12.1, reportlab 4.2,
  Java 17. Not installed: mammoth, markdown, striprtf, html5lib, bleach,
  nh3, pymupdf4llm.
- X2. Chrome 152 is installed alongside Edge.
- X3. Name search: BCL Technologies, now part of Apryse, sells "easyPDF
  SDK" (easypdf.com, a Visual Studio Marketplace listing, decades old) in
  the PDF creation class. "Easy PDF" and "EasyPDF" apps exist in app
  stores. The name is generic.

## Decision 1: one editor, WebView2; delete RICHEDIT and its parser

### The strongest case against

- The editor now depends on the WebView2 Evergreen runtime. Windows 11 has
  it inbox; Windows 10 got it through Windows Update on consumer machines
  and not on many managed, LTSC or Server images. Where it is missing the
  app has no editor at all. RICHEDIT has been in every Windows since 1995.
  The analysis measured availability on one machine.
- The frozen build must ship WebView2Loader.dll (W14). Miss it and the app
  dies at first launch on every machine, with nothing to fall back to.
- The process segfaults at teardown (the coordinator's finding), so the app
  must hard exit. Every write that happens "on close" has to be flushed
  before os._exit, or settings, recent files and autosave state are lost.
- The keyboard contract cannot be built the way the April code built it.
  Measured: while the editor has focus, no wx accelerator fires (W4),
  Chromium's own bindings act first (W5), F5 destroys the document and
  Ctrl+F and Ctrl+P pull focus into browser chrome (W6). Every key in
  CONVENTIONS.md, F1, F2, Alt+Enter, Ctrl+F, Delete, Escape, the
  Applications key, has to be caught in the page and forwarded. With
  RICHEDIT none of this exists.
- The as-found editor API is built on synchronous RunScript: get_html on
  save and export, word_count on every text change, find, headings. Two
  of four focused runs hung for ever (W2). A hang is a frozen window and a
  screen reader saying nothing, for the audience least able to diagnose
  it. The fix is an asynchronous API, which is a redesign of the wrapper,
  not a port.
- Semantics are not free. execCommand emits b, i, font and div (W8, W9),
  and Chromium's PDF ignores every one of them (E5). "One source of
  truth" needs a normaliser between the DOM and the file and the PDF.
- Undo is broken for every programmatic edit unless every edit goes
  through insertHTML (W7). A blind user who inserts a link and presses
  Ctrl+Z loses the sentence before it and keeps the link.
- A file someone sends runs script inside the editor (W11), and the
  editor's own bridge is reachable from that script.
- Only NVDA is in the plan. JAWS is the screen reader of the institutions
  that must produce PDF/UA. Narrator is free and inbox. Chromium
  contenteditable is a different surface for each and none of the three
  has been tried.
- A Chromium process tree for a text editor costs memory and start time on
  the old laptops blind users keep for years. Not measured; do not
  promise.

### The strongest case for

- It is the only backend in which the editor itself exposes heading, list,
  link and graphic roles. In RICHEDIT a heading is a font size, and the
  April classifier already got Heading 6 wrong. Two backends means every
  feature twice; the as-found code already branches in the font dialog,
  find, the structure navigator and the status bar.
- NVDA's browse mode works inside a Chromium document: H, K, G, L quick
  keys and NVDA+Space to switch. RICHEDIT can never offer that. (Standard
  NVDA behaviour in Chromium; not measured here; the audit should confirm
  it in this editor.)
- The HTML in the editor is the HTML that goes to the engine and the
  file: no parser, no links recognised by colour, no per-character COM
  round trips.
- Everything the design needs was measured working today: the bridge,
  async scripts, 8 MB payloads, keydown capture with preventDefault (W1,
  W3, W6). Every fault found has a page-side fix.
- RICHEDIT is not a fallback worth keeping. It cannot open the HTML
  format, it drops images and links on load, its Replace All destroys
  formatting. Shipping it as the "fallback" gives those defects to the
  people whose machines lack WebView2, who are the least able to tell.

### Measured, and bearing on it

- W1 to W14 above, all of them.

### Verdict: keep, with conditions

These are conditions, not suggestions. Without them the editor is the
April editor with a new coat.

1. The editor API is asynchronous. RunScriptAsync plus the message bridge;
   no synchronous RunScript on the UI thread once the editor exists. Word
   count and selection state come from the page with its state messages.
   A test sends a keystroke, then issues a script, under a watchdog.
2. The keyboard map lives in the page: a capture phase keydown handler,
   preventDefault, postMessage to Python. The wx accelerator table serves
   only when focus is outside the editor. F5, F3, F12, Ctrl+F, Ctrl+P,
   Ctrl+S, Ctrl+O, Ctrl+G, Ctrl+Shift+I and friends are blocked in the
   page (measured working, W6). tests/test_keys.py is a SendInput harness
   against a focused editor, not a table check.
3. defaultParagraphSeparator is p; a block always wraps bare text; b, i,
   font and div are normalised to strong, em, spans with classes and p
   before save and before export (E5, W8, W9).
4. Every programmatic edit goes through execCommand insertHTML or
   insertText so undo works (W7). Load and Replace All reset the undo
   history on purpose and say so in the status bar.
5. A sanitiser runs on every load, paste and import: no script, no event
   handler attributes, no javascript URLs, no remote resources (W11).
6. A startup guard: if the Edge backend is unavailable or the loader DLL
   is missing, a real dialog says so, names the WebView2 runtime download,
   and exits. The selftest checks both (W14).
7. DPI awareness is set before wx.App, and the frozen build's manifest
   says so (W12).
8. Narrator joins the audit. One JAWS pass if any tester has it.

## Decision 2: one engine, Chromium headless print, plus the pikepdf patch; never an untagged PDF

### The strongest case against

- The engine is an installed browser the app does not control. Chromium's
  tagged PDF output is young and changes with releases. A shipped app's
  output drifts with Windows Update, and the only guard is an in-app
  checker that today does six catalogue checks.
- "Edge, then Chrome, else offer HTML" fails exactly the users who must
  produce PDF/UA: locked down desktops, kiosk builds, EU users who removed
  Edge under the Digital Markets Act, Windows Server. An HTML file is not
  a deliverable for a compliance filing.
- The default flags print a header and footer into every page, including
  a file path to the temp file (E2). One forgotten flag and every export
  leaks it.
- Chromium's known gaps are waved at, not measured: no LBody, NonStruct
  wrappers, inline lang lost (E5), b and i untagged (E5), an alt-less img
  becomes a Figure without Alt (E5), Arabic extraction faults (E7). None
  of it has been through veraPDF or PAC. Writing pdfuaid:part equal to 1
  on every export without a validator asserts a conformance the app
  cannot prove. A false claim is worse than no claim.
- Producer honesty is asserted; pikepdf stamped itself in four of six
  variants (E9).
- "About two seconds" is one sample on a fast machine with the browser
  warm in cache. Measured today 1.0 to 1.7 seconds for a page, with
  antivirus and a slow disk unmeasured.

### The strongest case for

- Measured on three binaries: the same output, with H1 to H6, P, Strong,
  Em, Code, Link with OBJR, L and LI and Lbl with ListNumbering,
  BlockQuote, Figure with Alt, Caption, Table with TR, TH with Scope and
  TD with Headers, paragraph level Lang, MarkInfo, DisplayDocTitle, Tabs,
  a ParentTree, subset fonts with ToUnicode, and every text operator
  inside marked content (E4, E6). Nothing else on this machine comes
  close: WeasyPrint needs a GTK runtime, PyMuPDF and ReportLab write no
  tree.
- Zero bundle size and an engine that updates itself.
- Fast enough: 203 pages in 2.9 seconds, five photos in 1.7 (E1).
- Refusing to ship an untagged PDF is right for an accessibility product,
  and the April fallback corrupted the cross reference table.

### Measured, and decisive

- E1: the WebView2 runtime's own msedge.exe renders identically. The
  editor already requires that runtime. So the engine can be found from
  the registry key the runtime writes (pv and location) and its EdgeCore
  sibling folder, and the "no Chromium found" branch shrinks to "the
  editor cannot run either". On this machine the registry location
  pointed at an EdgeWebView folder that does not hold msedge.exe while
  EdgeCore did, so the finder must try both and prove the one it picks.
  Whether Microsoft calls running the runtime binary headless supported
  is unknown; it worked and logged one harmless usagestats warning.
- E2, E3, E9 as above.

### Verdict: modify

1. Engine order: the WebView2 runtime's msedge.exe, then Edge, then
   Chrome. At selftest and at first export each candidate renders a one
   line document and pikepdf reads the tree; the export uses the proven
   one and the selftest names it.
2. Always: no-pdf-header-footer, generate-pdf-document-outline,
   disable-gpu, an own user-data-dir under the config folder, a timeout,
   and the images inline in the temp HTML (E2, E3).
3. The PDF/UA-1 identifier is written only when the in-app checker passes
   every check on the result. Otherwise the file is exported without the
   claim and the report says which check failed.
4. Before printing: b to strong, i to em, every img gets an alt attribute
   (empty plus role presentation means decorative), and inline lang spans
   are promoted to their own block or the language claim is dropped for
   that passage (E5).
5. A test asserts Producer and Creator after the pikepdf pass (E9).
6. veraPDF once, on the sample set, at the build (Java 17 is here; the
   download needs Tony's yes), and PAC 2024 by hand at the audit. Each
   thing Chromium fails becomes a checker rule by name. Without this the
   words "PDF/UA" on the site are a claim.
7. Do not advertise right to left languages until an Arabic or Hebrew
   screen reader user has read a file (E7).

## Decision 3: one native format, self-contained UTF-8 HTML with the html extension; import txt, md, rtf, pdf

### The strongest case against

- The html extension belongs to the browser. Double click opens Edge, the
  Explorer icon is the browser's, NVDA reads "Chrome HTML Document", and
  taking the association would be hostile. The April code already reserved
  epdf in its file wildcard and the analysis dropped it without a word.
- Mail gateways, Teams and Slack quarantine html attachments as a phishing
  vector far more than docx or pdf, and a self-contained file with base64
  images looks exactly like a phishing kit. The "never trapped" sharing
  path is the one most likely to be blocked. Documented policy behaviour;
  not measured here.
- Size: base64 adds a third. Five phone photos made a 6.8 MB file and
  Chromium keeps full resolution (E8). Real phone photos are 3 to 5 MB
  each, so a ten photo newsletter is a 50 MB file that the editor loads
  through innerHTML on open and copies through the bridge on every save.
  8 MB took a third of a second (W3); 50 MB is untested.
- A file the user received runs its handlers inside the editor (W11). The
  generator meta is not a trust signal. The format needs a sanitiser.
- The import list is Tony's shelf, not the audience's. rtf "as plain text"
  means showing rtf1 ansi deff0 control words to the user; that is not an
  import. The only rtf files that exist are the April prototypes. docx is
  what students, offices and institutions actually have; python-docx is
  installed (X1) and Word's heading styles, lists, bold and italic,
  hyperlinks and image descriptions map cleanly. md needs a parser;
  markdown-it-py is installed. pdf: PyMuPDF has no structure tree API (X1),
  so "headings from font size" is the only route, and it throws away the
  tags of a PDF that already has them. The analysis calls PDF import "the
  feature this audience has no tool for" without opening one PDF.
- Round trip fidelity is whatever the DOM was: b, font, div and Word paste
  residue all get saved unless normalised (W9; a Word heading pasted in my
  harness arrived as a bold 16 point span, not an h1).

### The strongest case for

- One format, no parser, readable by anything, greppable, and a screen
  reader user can open it in a browser with full semantics if the app is
  gone. No binary format has that virtue.
- Title, author and language in the head, images inline so the file
  survives being moved or mailed. The April file links lost their images
  when moved; the analysis is right about that.
- txt and md import are cheap and match how Tony works.

### Measured, and bearing on it

- E8, W3, W11, W9, X1.

### Verdict: modify

1. The native extension is the app's own, epdf, HTML inside, registered
   by the installer per user with its own icon and the description "Easy
   PDF document". html is an import and an export ("Save as web page"),
   never the native extension.
2. Images are downscaled on insert: longest edge 2,000 pixels, JPEG at
   quality 85 for photographs, PNG kept for screenshots and diagrams. The
   dialog states the size going in.
3. Import: txt, md through markdown-it-py, docx through python-docx
   (headings by style name, lists, inline formatting, links, images with
   their description), pdf through PyMuPDF text blocks plus pikepdf's
   structure tree when one exists, so a tagged PDF keeps its headings and
   figure descriptions. rtf is dropped; convert the April files once by
   hand.
4. The sanitiser (htmlclean.py is already in Worker A's list; its rules
   are not written anywhere) gets an explicit allow list of elements and
   attributes, runs on load, paste and import, and is what turns b into
   strong, i into em, div into p, and reduces style attributes to
   text-align and the image width and placement classes.
5. Autosave and recovery (analysis section 6) gets an owner and a test. It
   is missing from the decisions and from the file ownership table.

## Decision 4: no welcome dialog

### The strongest case against

- The welcome dialog is the one place a first time user hears what the app
  is. A blank editor with a menu bar tells a blind user nothing about
  PDF/UA, the describer, or where to start.
- Recent files: the fastest way for a screen reader user to reopen
  yesterday's document is a list, not File, Open, and a file dialog. Word,
  LibreOffice and Notepad++ all offer one.
- First launch also has the "no AI key yet" and "update available" moments.
  Without a landing surface they become dialogs interrupting a blank
  editor.

### The strongest case for

- A modal before the main window breaks single instance, command line
  open, "open with" and drag and drop. Every TG Studios program opens on
  its work surface. Notepad's model is the accessible model: focus lands in
  the editor, NVDA reads the title, typing works.
- Onboarding belongs in Help and F1.

### Verdict: keep, with additions

- File, Recent documents: the last ten, with numbered mnemonics.
- One first-run status bar line and one announce_help hint, spoken once,
  the words in STRINGS.md for Tony.
- The command line opens a file. A second launch with a file path hands
  the path to the running copy, which opens it after the save changes
  prompt (see decision 9).

## Decision 5: Ctrl+I is italic; Ctrl+Shift+I inserts an image

### The strongest case against

- The analysis contradicts itself. Section 5 gives Ctrl+Shift+I to Insert
  Image and in the next sentence keeps Ctrl+Shift+I as an italic alias.
  Both cannot hold.
- The alias reasoning applies "a taught key is never taken away" to a
  population of one: nobody but Tony ever used the April build, and he is
  the one deciding.
- Ctrl+Shift+I means DevTools to everyone who has used a Chromium
  browser. WebView2 has DevTools off by default and the page guard blocks
  the key (W6), so it is safe, but it means "insert image" to nobody. Word
  has no image shortcut; Docs has none.
- The Word map for headings, Ctrl+Alt+1 to 6, is the US Word map. On
  German, French, Polish, Spanish and Portuguese layouts Ctrl+Alt with a
  digit is AltGr and types a character. Measured here only that a US
  Ctrl+Alt+1 reaches the page as Ctrl and Alt and the digit (W4); no other
  layout was tried, because switching layouts changes a user setting.

### The strongest case for

- Ctrl+I as italic matches Word, Docs and every editor. It is also what
  Chromium already does inside a focused editor (W5). The April map's
  Ctrl+I insert image never fired while typing, because the wx accelerator
  was dead (W4); it only worked from the menu.
- Making the app's map agree with the engine's native binding removes a
  class of double toggle bugs.

### Verdict: modify

1. Ctrl+I is italic. The engine forces it while the editor is focused.
2. Ctrl+Shift+I inserts an image only if the italic alias sentence is
   struck from ANALYSIS.md. No key means two things.
3. Heading keys: Ctrl+Alt+1 to 6 stay, and the page handler acts only when
   the event's key is the digit itself (so an AltGr character on a
   European layout is typed, not hijacked), plus Ctrl+Shift+1 to 6 gated
   on the physical key code as the layout proof route, documented
   together.
4. Every key in KEYBOARD.md is measured by SendInput into a focused editor,
   because the wx accelerator path does not exist there (W4).

## Decision 6: the app is called Easy PDF; the slug EasyPDF, the mutex, the AppId and the feed name are frozen at first release

### The strongest case against

- The name collides. BCL Technologies, now Apryse, has sold "easyPDF SDK"
  for decades in this exact class (X3). "Easy PDF" apps sit in the app
  stores. TG Studios has already learned that live trademarks must be
  renamed before selling (the amp names). Free reduces the exposure; it
  does not remove it.
- "The display name can change later" is true only for the title bar. The
  frozen slug EasyPDF lands in the mutex, the config folder, the feed file
  name, the repository, the Add or Remove Programs entry, the site URL and
  the Credential Manager entry a user reads. Freezing the colliding string
  now is the opposite of what the decision intends.
- "Easy PDF" is unsearchable and says nothing about what makes the product
  different, which is accessible, tagged output.
- The TG prefix already exists for this reason and is applied to Model
  Master, Chord Caller, Spaces, Drop Deck and Topcoat, and not to Prompt
  Vault, American Explorer or Word Champion. The workspace CLAUDE.md lists
  this folder as "Easy PDF" without the prefix.

### The strongest case for

- The name is Tony's, it is in the folder and the notes, and adding the
  brand keeps the words. Freezing internals early prevents the dead update
  channel that a renamed feed causes, which has happened elsewhere.

### Verdict: modify

- Settle the name before anything is frozen, because the frozen strings are
  the collision. Minimum: "TG Easy PDF", slug TGEasyPDF, repository
  tg-easy-pdf, feed tg-easy-pdf, mutex and AppId derived from that slug,
  credential entry "TG Easy PDF describer key". Better: a distinct name
  that says accessible or tagged; that is Tony's call and the report should
  offer three. A five minute trademark search on the chosen name before
  release. Whatever is chosen, the internal slug is never "EasyPDF" alone.

## Decision 7: free, with the donate link

### The strongest case against

- The framing: "Pricing is Tony's call; nothing here assumes it", followed
  by a decision that assumes it. Free is a pricing decision.
- Two audiences, and one of them pays. Blind individuals pay little and
  already have Word. Institutions that must produce PDF/UA pay for axesPDF,
  CommonLook, Acrobat Pro and MadeToTag. A simple editor that enforces alt
  text, checks its own output by name and describes images has a paying
  market in accessibility offices, and the standing rule "track every
  product download" exists to find out. Free forecloses that without data.
- An editor generates support at a rate a soundboard does not: files,
  imports, formats, other people's PDFs.
- The describer costs the user API money anyway, and the shared TG Studios
  licence system already exists.

### The strongest case for

- Word and LibreOffice Writer already export tagged PDF for free, with alt
  text, headings, lists and tables, and Word has an accessibility checker.
  Charging for a subset of that needs a much stronger product than v1.
  Free removes the comparison.
- The audience is closer to Drop Deck's than to the amp modeller's.
- v1 has no licence code to write, and the update and donate pattern
  exists.

### Verdict: modify

- Free for v1, as a v1 decision, and written that way. Keep the licensing
  hooks (constants, About text) so a paid edition (docx and batch PDF
  remediation, a table editor, validator integration) can exist without a
  rename. Count downloads from day one and revisit at ninety days with the
  numbers. DECISIONS.md should say who decided and for how long.

## Decision 8: the describer copies Drop Deck's provider layer and its rules

### The strongest case against

- vision.py is single image, JPEG only and tuned for speed: one RGB array
  in, downscaled to 1024 wide at quality 85, the fastest models as defaults
  because a presenter is waiting to go on air, a Gemini output ceiling of
  1500 tokens. Alt text is the opposite problem: nobody is waiting,
  accuracy matters more than speed, a chart's labels must stay legible, and
  describe-document needs text plus many images in one request, which no
  builder in vision.py can express. "Copy, do not reinvent" copies the
  wrong defaults and a shape that cannot carry the second feature.
- The prompts are the product and none are written. Alt text has its own
  craft (concise, no "image of", convey the function, the decorative
  decision, long description separate) and document description another.
  Nobody owns prompt quality.
- The consent rule is misapplied. Drop Deck asks every time for a screen
  because the user cannot verify what is in it. The plan says a single
  image asks once per session, but an image from an imported PDF that
  someone sent is exactly the unverifiable case, and section 6 offers
  every image of an imported PDF to the describer, which can send forty
  images of somebody else's document under one consent.
- Provider terms: Google's Gemini API free tier uses submitted content to
  improve its products; the paid tier does not; the app cannot tell which
  tier a key is on. OpenAI and Anthropic retain for abuse monitoring. A
  blind user describing a medical letter should hear that before pressing
  Send. Policies change, so the consent text should point at them rather
  than promise.
- Hallucinated descriptions go into a distributed file as fact and the
  author cannot check them. Drop Deck's answers are advice for a moment;
  these are claims for ever.
- A separate credential entry means pasting the key twice for anyone who
  has Drop Deck.
- Cost: describe-document on a 200 page import with sixty images at full
  size is a real bill; vision.py's sent_kilobytes covers one picture.

### The strongest case for

- Three providers over plain HTTPS with no SDKs, keys in Credential
  Manager, failures as sentences, the model as a setting with a live list,
  and redact: all in production since yesterday. Rewriting invites the
  vanished model names and the exhausted thinking budget that Drop Deck
  already found. The code is small; extending it is cheap.

### Verdict: modify

1. Copy secrets.py verbatim with the prefix changed. Copy the transport,
   the error sentences and the model list from vision.py. Add a multi-part
   message builder per provider: one text part plus N images.
2. Alt text and document prompts are written fresh, listed in STRINGS.md,
   and approved. Defaults are chosen for accuracy; Drop Deck's speed table
   does not transfer.
3. Images go at up to 1,600 pixels wide, PNG for anything that is not a
   photograph.
4. Consent by provenance and size: an image the user just inserted from
   their own disk asks once per session; anything imported, and any batch,
   asks every time with the count and the megabytes. The consent text
   names the provider and links its data policy.
5. AI written alt text is marked in the native file (not the PDF) and the
   checker reports "N descriptions not yet reviewed".
6. A "Use the key I gave TG Drop Deck" button that reads that entry with
   the user's yes.

## Decision 9: everything a TG Studios program ships with, in v1

The rule is settled. What follows are the places the plan misapplies it or
leaves it vague.

### Where the plan is thin

- Single instance for a document editor: "reopen the running copy" is not
  enough. A second launch with a file path must open that file in the
  running copy, or double clicking a document while the app is open does
  nothing a blind user can perceive. The plan never says whether there is
  one document or many. Decide one window, one document, path handed over
  after the save prompt.
- Speech: "all three channels write the status bar" but the as-found
  status bar has four fixed panes and no message pane. Model Master needed
  a fourth field before "Nothing" was honest (CONVENTIONS). Add one.
- Selftest content: this app's selftest must prove the Edge backend, the
  loader DLL (W14), each engine candidate by rendering and reading back
  (E1), pikepdf's namespace (E9), the sanitiser, and the update key. The
  plan lists only the generic items.
- Tests: tests/test_keys.py has to be a SendInput harness against a real
  WebView2 (W4); a table of bindings proves nothing.
- Visual finish: this display is at 150 percent and a DPI unaware process
  renders the editor blurred (W12). Awareness before wx.App and in the
  frozen manifest.
- Teardown: because the exit is os._exit, settings, recent files, window
  geometry and the clean exit marker are written first, and a test kills
  the app and checks the files.
- Scope honesty: v1 also carries the describer, PDF import, image
  placement, the checker, autosave and recent files. Say what is not in
  v1 on the site page: tables (the engine tags them beautifully, E4, and
  there is no table editor), footnotes, page numbers, columns, right to
  left text.

### Verdict: keep, with those specifics written into DECISIONS.md

## Decision 10: publishing waits for Tony

### The strongest case against

- Only that a rehearsal that passes against a feed that does not yet exist
  is not proof; the first real publish has to be watched with
  check_updates.py, and the site copy, the release note line and the
  announcement are all words in Tony's voice that an agent will draft.

### Verdict: keep

- The approval packet holds: the name (decision 6), the pricing framing
  (7), every consent text (8), the site page, the release notes line, the
  first run hint, and the "not in v1" list.

## Risks nobody listed

1. Sync RunScript hangs with a focused editor (W2). The April API calls it
   on every keystroke. Async only, and a watchdog test.
2. The frame's accelerators are dead while the editor is focused (W4),
   Chromium's own bindings win (W5), and F5, Ctrl+F and Ctrl+P damage or
   hijack the document (W6). The entire keyboard contract, CONVENTIONS keys
   included, has to be implemented in the page.
3. Hostile files run script (W11). Remote images in a received file phone
   home when it is opened. The bridge is reachable from document script.
   Sanitise on load, paste and import.
4. Undo: programmatic edits are invisible to it, and undo after an insert
   removes the user's own typing (W7). Replace All and load erase the
   history.
5. Semantic drift between the DOM and the PDF: b, i, font, div, bare text,
   inline lang and alt-less img all lose or break semantics silently, and
   the alt-less img is a hard PDF/UA failure (E5, W8, W9).
6. A conformance claim without a validator (decision 2). Gate the
   identifier; run veraPDF once.
7. The engine drifts with Windows Update. Write the engine name and
   version into the XMP CreatorTool so a bad batch can be traced, and
   re-measure the sample set at every release.
8. The default header and footer print the temp file path into every page
   (E2).
9. Arabic and right to left: measured extraction faults (E7), no direction
   control in the editor, no per-run language. Do not claim it.
10. File bloat: full resolution images pass straight through (E8).
    Downscale on insert and warn above a size.
11. The html extension belongs to the browser and to mail filters
    (decision 3).
12. Privacy of the describer: the whole text and every image go to a third
    party, a free Gemini key trains on it, imported documents belong to
    someone else (decision 8).
13. The name collides and the slug freeze makes it permanent (decision 6).
14. Autosave and crash recovery have no owner, and because every exit is a
    hard exit, "did not close cleanly" is the normal case. Write a clean
    exit marker before os._exit and recover only without it.
15. Single instance with a file argument, and the one or many documents
    question (decision 9).
16. Blur at 150 percent (W12), on Tony's own display.
17. Tables: needed for PDF/UA documents, tagged well by the engine, absent
    from the editor. Decide out loud.
18. LBody absence and NonStruct wrappers: no validator verdict exists.
19. Import scope: each import path produces documents whose accessibility
    the app then signs with its own name.
20. The structure panel and F6 duplicate what NVDA's browse mode gives in
    this editor for free. Keep them for JAWS, Narrator and sighted
    keyboard users; measure what NVDA browse mode actually does here.
21. High contrast: the editor CSS hardcodes white on black; Chromium's
    forced colours may or may not override a contenteditable background;
    unmeasured here (W12). The audit runs with Windows High Contrast on,
    and the toolbar icons need high contrast variants.
22. Focus mode on entry: when the editor receives focus from Ctrl+N or
    Open, does NVDA land in focus mode, or are the first letters typed
    quick navigation keys? My harness lost the first key after each focus
    change to its own Alt tap, so this is unmeasured and must be checked
    by hand.
23. Paste: execCommand paste is refused (W10). Edit, Paste has to read
    wx.TheClipboard (HTML if present, else text), sanitise, and insertHTML.
    Copy works.
24. execCommand is obsolete on paper and permanent in practice; it is also
    the only undo aware editing API Chromium offers. Its HTML shape can
    change per release, so the normaliser must not trust the shape, and
    the tests run against the installed runtime every release.
25. Bridge volume on big documents: every state message and every
    getHTML is a copy of the document. Measure at 200 pages with images
    before shipping.

## Biases in the analysis

- Tony's machine is the target. Edge, Chrome, WebView2 152, pikepdf,
  Python 3.13, NVDA, a US keyboard, English, one display at 150 percent.
  Every "measured" fact in ANALYSIS.md is one machine. Nothing was tried
  without WebView2, on a non US layout, with JAWS or Narrator, in high
  contrast, at 200 percent, or on a slow disk.
- NVDA is the only screen reader in the plan. The institutions that must
  produce PDF/UA mostly run JAWS. Narrator is free and inbox.
- Measurement was thinnest where it mattered most. The two questions the
  analysis itself marked "to be measured" (clipboard, accelerators) were
  left open while decisions 1, 5 and 9, which depend on them, were made.
  Today's numbers on the accelerators flip the editor's design. "About two
  seconds" is one sample. "Chromium tags b and strong the same" is
  asserted and is false (E5). "LBody absent, validators accept" is asserted
  without running a validator. The structure tree was inspected for
  element names, not for completeness, text order or non Latin text. No
  large document, no image sizes, no Arabic.
- Framed as inevitable. Decision 1 is presented as forced by RICHEDIT's
  ceiling, which is true, with none of WebView2's costs (keys, the hang,
  the sanitiser, undo, teardown, the runtime) on the page, so the reader
  cannot weigh it. Decision 2 presents Edge then Chrome as the only shape
  when the runtime the editor already needs does the job (E1) and removes
  the "offer HTML" branch. "Offer HTML" is called a fallback when it is a
  refusal.
- Free is decided while saying it is not decided.
- The competitor is never named. Microsoft Word saves tagged PDF with alt
  text, headings, lists and tables, has an accessibility checker, and
  works with JAWS and NVDA. LibreOffice Writer has a PDF/UA export option
  and costs nothing. The analysis never says why anyone would choose Easy
  PDF over them. The answer (simplicity, enforced alt text, a checker
  that names the fix, AI descriptions, PDF import and remediation, price)
  has to be in the plan or the product has no reason to exist. The one
  differentiator named, PDF import, is the least measured thing in the
  document.
- Tony's habits stand in for user research: Markdown import "which Tony
  writes constantly", RTF import for his April files, the April key map
  as "taught", Desktop shortcuts. Fine as inputs, not as evidence.
- The "copy Drop Deck" reflex treats a provider layer built for a live
  broadcast as domain neutral.
- The checker is described by its future checks, not by what it can prove.
  Nothing on validators, nothing on what no checker can see: reading
  order, alt text quality, colour contrast, language accuracy, whether a
  heading is really a heading, whether a table is really a table.
- The name was chosen by the folder, not by a search.

## Verdicts in one list

1. One editor, WebView2: keep, on the conditions that the API is
   asynchronous, the keys live in the page, the DOM is normalised and
   sanitised, edits are undoable, the runtime is guarded and DPI is set.
2. One engine, Chromium: modify. The WebView2 runtime first, then Edge,
   then Chrome; the header flag and the outline flag always; the PDF/UA
   claim gated on the checker; veraPDF once; no right to left claim.
3. Native format: modify. epdf as the app's own extension with HTML
   inside; html as import and export; images downscaled on insert; docx in,
   rtf out; the sanitiser's rules written; autosave given an owner.
4. No welcome dialog: keep, plus recent files, a once only first run hint,
   and the file argument handed to the running copy.
5. Ctrl+I italic: modify. Italic is forced by the engine; Ctrl+Shift+I
   inserts an image only without the italic alias; a layout proof heading
   route; every key measured in a focused editor.
6. The name and the freeze: modify. Settle the name first; never freeze the
   slug EasyPDF; TG Easy PDF at minimum, a distinct name if Tony wants one.
7. Free: modify. Free for v1 as a v1 decision, licensing hooks kept,
   revisited at ninety days with download numbers.
8. The describer: modify. Copy secrets and the transport, not the defaults,
   the prompts or the consent rule; a multi part builder; consent by
   provenance; AI alt text marked and counted.
9. Everything in v1: keep, with the file handoff, a message pane, the
   selftest content, a SendInput key harness, DPI, the pre-exit flush and a
   public "not in v1" list.
10. Publishing waits for Tony: keep, with the approval packet spelled out.
