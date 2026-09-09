# Strings for Tony to approve

Every word the app shows or speaks that was written by Claude rather than
by Tony, so he can read them as text before anything ships. Standing rule:
nothing in his voice goes out unread.

Structural furniture is exempt: menu labels that name a function ("Save",
"Export PDF"), field labels, the app's own name and version, and the update
dialog wording, which is the shared TG Studios wording already approved for
Drop Deck and the Prompt Vault.

Each worker appends the strings they add, under their own heading. Mark a
string **approved** only when Tony has said so.

## Coordinator

- Tagline (About box, installer, site): "Write a document, get a PDF that
  screen readers can read." Status: draft.
- Release note 1.0.0 (read aloud in the update dialog): "The first release.
  Write a document with headings, lists, links and pictures, and export a
  tagged PDF that screen readers can read. Open a PDF somebody sent you and
  make it accessible. Describe pictures with Claude, ChatGPT or Gemini on
  your own key." Status: draft.
- Speech level labels (Preferences): "Everything, including confirmations
  and hints" / "Only what I cannot hear or read for myself" / "Nothing. Let
  my screen reader do all of it". Status: the CONVENTIONS.md wording with
  the dash removed; treat as approved unless Tony objects.
- Second-launch message when the running copy cannot be raised: "TG Imprint
  is already running. Press Alt+Tab to switch to it." Status: Drop Deck's
  wording, approved there.
- Credential Manager entry comment: "An AI service key kept by TG Imprint.
  Safe to delete." Status: draft.
- File type description, shown by Explorer for .imprint files: "TG Imprint
  document". Status: draft.
- Startup guard, when the WebView2 runtime is missing (a dialog with a
  read-only field): "<reason> TG Imprint needs the Microsoft Edge WebView2
  runtime, which is part of Windows 11 and a free download for Windows
  10. Install it from this address, then open TG Imprint again:
  https://developer.microsoft.com/microsoft-edge/webview2/ The address
  has been copied to the clipboard." Status: draft.
- Second launch with a document while the app is open: no words; the
  running copy opens it.
- Update client sentences (shown in the shared update dialog, which has
  the approved TG Studios wording around them): "You have the newest
  version." / "Version X is available. You have Y." / "The update was not
  vouched for by the TG Studios signature and was refused: <reason>.
  Nothing was changed." / "The update server lists version X but the
  download for it is not there yet. Try again later." / "Version X is
  available, but this copy was not installed by the installer, so it
  cannot update itself. Get the new version from tgstudios.app." / "Could
  not reach the update server. <reason>" / "The download was stopped.
  Nothing was changed." / "Download failed. <reason>" / "Downloaded X." /
  "Installing. The app will close and reopen by itself." / "Could not
  start the update. <reason>". Status: the Drop Deck wording where it
  exists, drafts for the three Velopack-specific ones.

## Worker A (PDF pipeline)

Every sentence below is a draft until Tony has read it. Where a sentence
carries a count, the singular and plural forms are both given. Sources:
`tgimprint/htmlclean.py`, `pdfengine.py`, `pdfexport.py`, `pdfcheck.py`,
`pdfimport.py`, `docx_in.py`, `docfile.py`.

### The sanitiser's warnings (shown after open, paste, import, save and export)

- "1 picture has no description yet. Pictures lists every picture that
  still needs one." / "N pictures have no description yet. Pictures lists
  every picture that still needs one."
- At export: "1 picture still needs a description. The PDF holds it as a
  picture without one, which the description check reports." / "N
  pictures still need a description. The PDF holds them as a picture
  without one, which the description check reports."
- "A link to <address> was removed. Only web, email and phone addresses
  can be kept. Its text stays."
- "The language mark on \"<words>\" was removed. A mark on a few words
  does not reach the PDF. Put the language on the whole paragraph
  instead."
- "A picture at <address> was left out. Pictures are never fetched from
  the web. Save it to disk and insert it."
- "The picture <name> was copied into the document."
- "The picture <name> was left out because the file could not be found or
  read."
- "The picture <name> is on a network share and was left out. Pictures
  are never fetched from another computer. Copy it to this computer and
  insert it."
- "A picture of type <type> was left out because it cannot go into the
  PDF. Save it as PNG or JPEG and insert it."
- At export: "1 picture description was written by AI and has not been
  checked by somebody who can see the picture." / "N picture descriptions
  were written by AI and have not been checked by somebody who can see
  the picture."
- At export: "1 picture description was recovered from the original PDF
  and has not been checked." / "N picture descriptions were recovered
  from the original PDF and have not been checked."
- At export: "The document holds Arabic or Hebrew text. This release has
  not been checked with a right to left screen reader, and the PDF may
  read in the wrong order."
- "Script in the file was removed. It cannot run inside TG Imprint."

### The engine

- "<engine> <version> will make the PDF." (for example "Microsoft Edge
  152.0.4191.66 will make the PDF.")
- "No PDF engine was found. TG Imprint makes its PDF with Microsoft Edge,
  the Microsoft Edge WebView2 runtime or Google Chrome, and none of them
  is installed. Install one of them, then export again. Until then, Save
  as web page keeps everything."
- "The PDF engine did not finish in <N> seconds and was stopped. Try
  again; if it happens every time, the document may be too large for one
  PDF."
- "The PDF engine ran but wrote no file. <engine> reported: <its last
  words>"
- "The PDF engine wrote a file that is not a PDF. Try the export again."
- "The PDF engine could not be started: <the system's reason>"
- "The PDF cannot be written to <folder> because that folder does not
  exist."

### The export

- Progress steps, spoken through announce_help by Worker B's dialog:
  "Checking the document", "Laying out the pages", "Writing the document
  information", "Checking the PDF", "Adding the PDF/UA identifier".
- "The document has no title. The PDF was written without one, and the
  PDF/UA claim needs one. Set a title in Document properties and export
  again."
- "The PDF/UA identifier was left out because this check did not pass:
  <check>. The PDF is still tagged. Fix that and export again to add the
  claim." / "The PDF/UA identifier was left out because these checks did
  not pass: <check>, <check>. The PDF is still tagged. Fix that and
  export again to add the claim."
- "The PDF could not be written to <path>. Check that the folder allows
  writing and that the file is not open in another program."
- "The PDF could not be written to <path>. The system reported: <the
  system's reason>. The earlier file at that path, if there was one, is
  untouched."
- "The PDF engine wrote a PDF without tags, so nothing was saved. Save as
  web page keeps everything. Try the export again, and if it happens
  every time, update Microsoft Edge."
- "The PDF engine wrote a file that could not be read back as a PDF, so
  nothing was saved. Try the export again, and if it happens every time,
  update Microsoft Edge."
- "The PDF could not be finished because a temporary file could not be
  written. The system reported: <the system's reason>. Nothing was saved.
  Free some disk space and export again."

### The checker's report

Header: "Accessibility checks for <file name>" then "<ok> of <total>
checks passed." or "<ok> of <total> checks passed, 1 warning." / "...,
N warnings." Each check is one line: "PASS: <name>. <detail>", "FAIL:
<name>. <detail>" or "WARN: <name>. <detail>". Last line: "These are the
checks TG Imprint can make from here. A full PDF/UA verdict needs PAC or
veraPDF."

Check names: "Tagged PDF", "Structure tree", "Language", "Title shown in
the window", "Title", "PDF/UA identifier", "Pictures described",
"Heading levels", "Fonts embedded", "Tab order", "Links tagged", "Links
described", "Bookmarks", "Text layer", "All text tagged", "List items",
"File readable".

Details:

- Tagged PDF: "The file says it is tagged." / "The file does not say it
  is tagged (no MarkInfo). A screen reader gets no structure from it.
  Export it again from TG Imprint."
- Structure tree: "The tree holds N elements." / "There is no structure
  tree, so headings, lists, links and pictures have no roles. Export it
  again from TG Imprint."
- Language: "The document language is <code>." / "The document language
  \"<value>\" is not a language code. Set the language in Document
  properties, for example en-US." / "No document language is set, so a
  screen reader cannot pick the right voice. Set it in Document
  properties."
- Title shown in the window: "Viewers show the document title rather than
  the file name." / "Viewers will show the file name instead of the title
  (DisplayDocTitle is off). Export it again from TG Imprint."
- Title: "The title is \"<title>\"." / "The title \"<title>\" is in the
  file's information but not in its XMP metadata, which PDF/UA requires.
  Export it again from TG Imprint." / "The document has no title. Give it
  one in Document properties."
- PDF/UA identifier: "The file identifies itself as PDF/UA-1." / "No
  PDF/UA identifier. TG Imprint writes one only when every other check
  passes."
- Pictures described: "There are no pictures." / "The picture has a
  description." / "All N pictures have a description." / "The picture has
  no description. Give it one in Pictures, or mark it decorative." / "M
  of the N pictures has no description. Give every picture a description
  in Pictures, or mark it decorative." (has or have by M)
- Heading levels: "N headings, and no level is skipped." (or "1 heading,
  ...") / "There are no headings." / "The headings are unnumbered (H), so
  levels cannot be checked here." / "The first heading, \"<text>\", is
  level N. Make the first heading level 1." / "\"<text>\" is level N
  after the level M heading \"<text>\". Make it level M plus 1, or add
  the level in between." (where "a heading" stands in when the text
  cannot be read)
- Fonts embedded: "No fonts are used." / "The 1 font is embedded." / "All
  N fonts are embedded." / "1 font is not embedded: <name>. Every reader
  needs the fonts inside the file. Export it again from TG Imprint." / "N
  fonts are not embedded: <names>. Every reader needs the fonts inside
  the file. Export it again from TG Imprint."
- Tab order: "No page has links or fields." / "Tab order follows the
  structure on every page with links." / "1 page with links or fields has
  no tab order set. Export it again from TG Imprint." / "N pages with links
  or fields have no tab order set. Export it again from TG Imprint."
- Links tagged: "There are no links." / "The 1 link is in the structure
  tree." / "All N links are in the structure tree." / "M of N link is not
  in the structure tree, so a screen reader cannot reach it. Export it
  again from TG Imprint." / "M of N links are not in the structure tree, so
  a screen reader cannot reach them. Export it again from TG Imprint."
- Links described: "Every link carries its text as a description." / "M
  of N link has no description, so some screen readers read only the
  address. TG Imprint writes the link text as the description when it
  exports." (links have, when M is more than 1)
- Bookmarks: "The headings are bookmarks." / "There are no bookmarks.
  Readers of a long document jump by them; TG Imprint makes one per
  heading."
- Text layer: "The pages hold text a screen reader can read." / "This
  PDF is pictures of text. There is no text for a screen reader to read,
  and TG Imprint has no text recognition in this release. Run OCR in
  another program first." / "The PDF has no text at all."
- All text tagged: "Every piece of text is inside tagged content." / "N
  characters of text are outside any tag, where a screen reader may skip
  them. Export it again from TG Imprint." (1 character ... is ... it)
- List items: "There are no lists." / "The 1 list item carries a label
  and a body." / "Each of the N list items carries a label and a body."
  / "M of N list items have no LBody element. The PDF engine does not
  write one; PAC may warn about it and screen readers read the items
  anyway." (item has, when M is 1)
- File readable: "The PDF is protected by a password, so nothing in it
  can be checked." / "The file could not be opened as a PDF. <the
  library's reason>"

### Opening a PDF

- Progress: "Reading page N of M".
- "This PDF is protected by a password, so it cannot be opened."
- "That file is not a PDF."
- "The PDF could not be opened. <the library's reason>"
- "This PDF is pictures of text. Nothing could be read from it, and Easy
  PDF has no text recognition in this release. Run OCR in another
  program first."
- "1 page has no text and may be pictures of text. TG Imprint has no text
  recognition in this release." / "N pages have no text and may be
  pictures of text. TG Imprint has no text recognition in this release."
- "This PDF is tagged. Its headings and lists are re-created here from
  the text layout, not from its tags, so check them."
- "TG Imprint cannot open RTF. Open it in WordPad, save it as a Word
  document or plain text, and open that." (any file with the .rtf
  extension or the RTF signature; RTF is out of 1.0.0, decision 3)
- "1 picture description was recovered from the PDF's tags. Check each
  one in Pictures." / "N picture descriptions were recovered from the
  PDF's tags. Check each one in Pictures."
- "The PDF's tags hold picture descriptions that could not be matched to
  the pictures on page <numbers>, so they were not used."

### Opening a Word document

- "That file is not a Word document TG Imprint can open. It needs a .docx
  file."
- "The document has tracked changes, which are not read here. Accept the
  changes in Word first, then open it again."
- "Footnotes and endnotes were not read. Put anything you need from them
  in the text."
- "Comments were not read."
- "Headers and footers were not read. Put anything you need from them in
  the text."
- "Text boxes were not read. Put their text in the body of the document."
- "Equations were not read. Write them out in words, or insert them as
  pictures with a description."
- "The table of contents was not read. The PDF gets bookmarks from the
  headings instead."

### Pictures on the way in

- "That file is not a picture TG Imprint can read. PNG, JPEG, GIF, BMP and
  WebP pictures work."
- "That picture is too large to open. Pictures over about 178 million
  pixels are refused. Reduce it in another program and insert it again."
- The note the Insert picture dialog shows when a picture was reduced:
  "Reduced from 4,000 by 3,000 to 2,000 by 1,500 pixels." (the numbers
  vary; empty when nothing was reduced)

### For the UI to build on (Worker B chooses the wording, listed here so it is not lost)

- `meta["source_kind"]` is "native", "html", "text", "markdown", "docx"
  or "pdf"; the "opened from" sentence is Worker B's.
- `ExportResult.pdfua_claimed` is True or False; the first line of the
  export dialog is Worker B's.

## Worker B (UI and accessibility)

Every sentence the window, the editor page and the dialogs show or speak.
Status of all of them: draft, until Tony has read them. Menu labels that
name a function (Save, Export PDF, Bold, Zoom in) and field labels (Title,
Author, Rows) are exempt as structural furniture; the help sentences behind
every key are in `docs/KEYBOARD.md`, generated from `tgimprint/ui/keymap.py`,
and count as strings to approve too.

### The first run and the status bar

- First run hint, spoken once through announce_help: "Welcome to TG Imprint.
  Start typing. F1 lists the keys and Ctrl+Shift+E makes the PDF."
- Word count field: "No words yet", "1 word", "1,234 words".
- Paragraph style field: "Normal text", "Heading 1" to "Heading 6",
  "Bullet list item", "Numbered list item", "Quote", "Table cell", "Table
  header cell", "Picture: <description>", "Picture without a description",
  "Decorative picture", with ", in a link" added inside a link.
- Window title: "<document name> - TG Imprint"; a new document is "Untitled".
- Autosave: "Autosaved."

### Confirmations on the help channel (silent below Everything)

- "Bold on", "Bold off", "Italic on", "Italic off", "Underline on",
  "Underline off", "Strikethrough on", "Strikethrough off", "Code on",
  "Code off".
- "Normal text", "Heading 1" to "Heading 6", "Bullet list", "Numbered list",
  "List removed", "Quote", "Quote removed".
- "Aligned left", "Centred", "Aligned right", "Justified".
- "List level increased", "List level decreased", "Next cell", "Previous
  cell", "Row added".
- "Zoom 115 percent" (and the other steps).
- "Undo", "Redo", "Cut", "Copied", "All selected", "Pasted."
- "New document.", "Document closed.", "Opening <name>.", "Opened <name>.",
  "Saving <name>.", "Saved <name>.", "Saved the web page <name>."
- "Document properties applied.", "Title set to <title>.", "Link
  inserted.", "Link updated.", "Picture inserted.", "Picture updated.",
  "Picture removed.", "Table removed.", "Description added.", "Table
  inserted, 3 rows and 3 columns. The caret is in the first cell."
- "Making the PDF.", "Making <name>.", "Sending the PDF to the printer.",
  "Checking <name>.", "Checking for a new version.", "Downloading version
  <version>.", "Opening the user guide in your browser.", "Opening the
  donate page in your browser."
- Progress steps during export and import are Worker A's sentences,
  spoken as they arrive.

### What you cannot otherwise know (silent only at Nothing)

- "Select the text to make into code first."
- "Heading 2: <heading text>" (F6 and Shift+F6), "No more headings", "No
  headings before this", "No headings in the document yet."
- "Pasted. <first note from the cleaner>", "Nothing on the clipboard to
  paste.", "Picture pasted. It needs a description."
- "Opened from Word. Save will write a TG Imprint document." (also "a web
  page", "a text file", "Markdown", "a PDF").
- "Could not open <name>. <reason>", "Could not save <name>. <reason>".
- "The PDF needs a title first.", "Export cancelled: a title is needed.",
  "PDF written: <name>", "The PDF could not be made. <reason>", "No PDF
  engine was found. <reason> The document can still be saved as a web page
  from the File menu."
- "The PDF/UA identifier was written: every check passed.", "The PDF was
  written without the PDF/UA claim. <the check that stopped it>".
- "The PDF was sent to the printer.", "No printer would take the PDF, so
  it has been opened instead. Print it from there."
- "Checked <name>.", "The PDF could not be checked. <reason>".
- "No picture at the caret. Ctrl+Shift+Alt+P lists every picture.", "No
  picture or empty table at the caret.", "No pictures in the document."
- "3 pictures need a description." and the question "3 pictures in this
  document have no description. Open the Pictures list now to add them?"
  with buttons "Open the Pictures list" and "Not now".
- "Found. <the sentence around the match>", "Not found.", "Type something
  to find.", "Replaced. Next: <sentence>", "Replaced. No more matches.",
  "Nothing to replace.", "Replaced 12. Press Ctrl+Z in the document to put
  them back.", "Replace all failed. <reason>".
- "The user guide is not published yet."
- "You have the newest version.", "Update skipped. Help, check for updates
  when you are ready.", "The download was stopped. Nothing was changed.",
  "Download failed. <reason>", "Updating. TG Imprint will close and open
  again by itself." (Velopack applies the update and restarts the app;
  there is no portable swap and no second question, 2026-09-09).
- After that restart, once, on the help channel: "Updated to version
  1.1.0." If a modified document was open when the update ran, its
  autosave snapshot is offered back through the recovery dialog below.
- The messages Velopack's client itself returns, shown in the "Update
  failed" dialog: "Check for updates first. Nothing was changed.",
  "Download the update first. Nothing was changed.", "Installing. The app
  will close and reopen by itself.", "Could not start the update.
  <reason>", and the check's own sentences (appupdate.py, the
  coordinator's file).
- "Recovered <name>. Save it somewhere safe.", "The recovered documents
  were deleted."
- Guards until the other modules land: "The PDF export is not part of this
  build yet.", "The accessibility checker is not part of this build yet.",
  "Opening <kind> files is not part of this build yet.", "The document
  module is not part of this build yet, so this file was read without
  it.", "The describer is not part of this build yet.", "The AI settings
  page is not part of this build yet. Describing pictures needs it.", "The
  AI settings page could not open. <reason>", "The AI settings could not
  be saved. <reason>", "The HTML cleaner is not part of this build, so the
  text was loaded without any formatting.", "The HTML could not be
  cleaned: <reason>".
- "This PDF has no text layer: it is pictures of text, and there is no OCR
  in this release." (used only when the importer gave no warning of its own).

### Questions and dialogs

- Unsaved changes: "Save the changes to <name>?" with Save, Don't Save,
  Cancel.
- Remove picture: "Remove this picture from the document? Description:
  <description> Ctrl+Z puts it back." with "Remove" and "Keep it". Remove
  table: "Remove this empty table from the document? Ctrl+Z puts it back."
- Recovery: "TG Imprint did not close properly last time, and 1 unsaved
  document can be recovered:" then "<title>, saved <time>" per line, then
  "Recover opens the most recent one. Delete throws them all away. Not now
  leaves them for next time." with buttons "Recover", "Delete them", "Not
  now". Field label "Recovered documents".
- The export report dialog "PDF written": the first line above, the
  warnings, then the checker's report; buttons "Open PDF", "Open folder",
  "Close". Field label "Report". Line two: "<path>, 3 pages, made with
  Microsoft Edge 152".
- "Notes from opening this file" (the cleaner's and importer's warnings,
  field label "Notes"), "Could not open", "Could not save", "The PDF could
  not be made", "Accessibility check: <name>", "Update failed", "Update
  ready", "Document title" with the prompt "Document title:".
- About: "TG Imprint 1.0.0", the tagline, "TG Studios", "PDF engine:
  Microsoft Edge 152.0.4191.66" or "none found. Install Microsoft Edge or
  Google Chrome to make PDFs." or "not checked (the engine module is not
  part of this build yet).", then "Updates: <appupdate.channel_state()>",
  which is "source build, correctly disabled", "frozen but not installed
  by Velopack, so it cannot update itself" or "live, installed copy" (or
  "live, portable copy"), then "A TG Studios program. Questions and
  reports to info@tonygebhard.me. Tested with NVDA." and the home page
  address. Field label "About".
- Keyboard shortcuts (F1): the F1 text generated from keymap.py, including
  its two closing paragraphs about AltGr and lists and tables.
- Progress window (export, import): "Making the PDF" or "Opening a PDF",
  field label "Progress", gauge named "Progress".

### Document properties

- Title tooltip: "Required before the PDF is made. A screen reader says
  this when the PDF opens."
- Language tooltip: "The language of the document, which the PDF carries so
  a screen reader pronounces it right." Custom code tooltip: "A BCP-47 code
  when your language is not in the list, such as en-NZ or fr-CH." The
  extra choice "Other, typed below". Language names as "English (United
  States), en-US". Page sizes "Letter, 8.5 by 11 inches", "A4", "Legal,
  8.5 by 14 inches". Field "Margins, in inches".
- Note: "Title and language go into the PDF, where a screen reader reads
  them before anything else."

### Insert picture and picture properties

- Description tooltip: "What the picture shows and why it is here, for
  somebody who cannot see it. Required unless the picture is decorative."
- Checkbox: "This picture is decorative and needs no description".
  Button "Describe with AI..." with tooltip "Ask Claude, ChatGPT or Gemini
  for a description you can edit before accepting it." Field "Caption,
  optional". Widths: "A quarter of the text width", "Half the text width",
  "Three quarters of the text width", "The full text width". Placements
  "Left", "Centre", "Right". OK button "Insert picture".
- Size line: "No picture chosen yet.", "Picture: 1,600 by 1,200 pixels,
  240 KB, reduced from 4,000 by 3,000." (Worker A's note appended), or
  without the picture module "Picture: 4,000 by 3,000 pixels, 1,100 KB,
  not reduced because the picture module is not part of this build."
  When editing: "The picture already in the document".
- Notes: "Choose a picture first.", "Choose a picture file first.", "A
  description is required, or tick the decorative box if the picture
  carries no information.", "That picture could not be read. <reason>".

### Insert link

- Tooltips: "The words people read and hear. Say where the link goes, not
  "click here"." and "A web address, an email address with mailto:, or a
  phone number with tel:."
- Hint: "Link text should make sense on its own, because a screen reader
  can list every link in a document out of context (WCAG 2.4.4). "The
  2026 timetable" is better than "click here"."
- Notes: "The link needs some text.", "The link needs an address.", "The
  address must start with http, https, mailto or tel."

### Insert table

- Checkbox "The first row holds the column headings" with tooltip "Header
  cells tell a screen reader what each column is, in every row. Leave this
  on unless the table really has no headings." Note: "Tab and Shift+Tab
  move between cells, and Tab in the last cell adds a row." Button "Insert
  table".

### Find and replace

- Buttons "Find next", "Find previous", "Replace", "Replace all", "Close";
  checkbox "Match case". The sentences are listed above.

### Structure navigator and Pictures

- "Headings, 3 in the document:", rows "Heading 2: <text>" indented by
  level, "(empty heading)", "No headings yet. Ctrl+Alt+1 makes one.",
  button "Go to heading".
- Pictures: "Pictures: 3 pictures, 1 without a description, 1 recovered
  from a PDF and not yet checked." Rows: "Picture 1: <description>",
  "Picture 2: no description", "decorative, no description needed",
  suffixes ", described by AI (google)", ", recovered from the PDF, please
  check", ", please check", ", caption: <caption>"; "No pictures in the
  document." Buttons "Go to picture", "Edit description...", "Describe with
  AI...".

### Preferences

- Speech tab: the CONVENTIONS wording from constants.SPEECH_LABELS, with
  the tooltip "Everything is the default. The middle setting drops
  confirmations and hints and keeps anything you could not otherwise know.
  Nothing leaves the commentary to your screen reader and the status bar,
  and still answers a key you press to ask a question." and the note
  "Whatever you choose, everything the app says is also written to the
  status bar, so nothing is only spoken."
- Document defaults tab: fields "Page size", "Margins, in inches", "Font"
  (tooltip "A font family list as a web page would write it. The first one
  that is installed is used."), "Font size, in points", the language
  picker, "Author for new documents", note "These apply to new documents.
  Alt+Enter changes the open document."

### The toolbar and the editor page

- Tooltips: "<Command> (<key>)", for example "Bold (Ctrl+B)". The
  paragraph style choice: "Paragraph style. Ctrl+Alt+1 to 6 for headings,
  Ctrl+Alt+0 normal text, Ctrl+Alt+8 bullets, Ctrl+Alt+9 numbers, Ctrl+Q
  quote." Short labels under the icons: New, Open, Save, Bold, Italic,
  Underline, Strike, Bullets, Numbers, Quote, Left, Centre, Right,
  Justify, Link, Picture, Table, Export PDF.
- The editing region's accessible label: "Document text".
- The Recent documents submenu placeholder: "No recent documents".

### docs/KEYBOARD.md and the F1 window

- The introduction, the AltGr paragraph, the lists and tables paragraph
  and every help sentence in the table, all generated from keymap.py.

## Worker C (describer)

Everything the describer shows, speaks or asks, from `tgimprint/ai.py`,
`tgimprint/describe.py`, `tgimprint/ui/describe_dialog.py` and
`tgimprint/ui/ai_settings_page.py`. Curly braces mark a value the app fills
in: `{who}` is the provider's full name ("Claude, from Anthropic",
"ChatGPT, from OpenAI", "Gemini, from Google", Drop Deck's wording,
approved there), `{n}` a number, `{size}` "about 640 KB" or "about
2.3 MB", `{model}` a model name, `{address}` a policy address, `{text}`
the answer. Status: draft unless marked otherwise.

### Window titles

- "Describe this picture"
- "Describe this document"
- "Send the picture?" (the consent dialog for one picture)
- "Use the key from TG Drop Deck?"

### Labels and buttons that are not plain function names

- Picture dialog: "Who to ask", "Describe", "Describe in detail",
  "Status", "Description", "Use this description", "Cancel".
- Document dialog: "Who to ask", "Message", "Status", "Send the
  document", "Copy", "Close".
- Consent dialog: "Question", "Send", "Don't send" (the default), and for
  the Drop Deck key "Copy the key", "Don't copy".
- AI page: "Who to ask", "Their key", "Show the key", "Forget this key",
  "Use the key I gave TG Drop Deck", "Model, if you want a particular
  one", "Get the list", "Test the key and model", "Status".

### The consent questions (every one goes to Tony)

- A whole document: "This sends the whole of {file name} to {who}, over
  the internet, so it can be described to you: about {n} words and {n}
  pictures, {size}. The description comes back as text for you to read;
  nothing is written into your document. Before sending anything
  private, check what {Anthropic, OpenAI or Google} says it does with
  what it receives; the address of its data policy is in TG Imprint's
  guide, DESCRIBER.md, and it is {address}. Send the document?" Without
  a file name, "your whole document". The count reads "no pictures", "one
  picture", "{n} pictures", or over the cap "the first 12 of its {n}
  pictures".
- A picture from the user's own disk: "This sends one picture to {who},
  over the internet, {size}, so it can be described for you. The
  description comes back for you to read and change before anything goes
  into your document. You will not be asked again for pictures from your
  own files until TG Imprint is next opened. Before sending anything
  private, [the same policy sentence]. Send the picture?"
- A picture that came in with an imported document: "This sends one
  picture to {who}, over the internet, {size}, so it can be described for
  you. The picture came in with a document that was imported, so Easy
  PDF asks every time before any of it leaves this machine. The
  description comes back for you to read and change before anything goes
  into your document. [policy sentence]. Send the picture?"
- A batch: "This sends {n} pictures to {who}, over the internet, {size},
  so they can be described for you. A batch of pictures asks every time.
  Each description comes back for you to read and change before anything
  goes into your document. [policy sentence]. Send the pictures?"
- The Drop Deck key: "TG Imprint will read the key for {who} that TG Drop
  Deck keeps in Windows Credential Manager, and keep its own copy under
  TG Imprint's name. Nothing is sent anywhere. Copy the key?"

### The picture dialog, shown in the Status line or spoken

- "Nothing has been asked yet."
- "The picture could not be shown here." (in place of the preview)
- "Measuring the picture."
- "Asking {who}. This usually takes a few seconds."
- "Nothing was sent." (after a no)
- "Described by {who} in {n} seconds. Read it, change it if you like,
  then choose Use this description."
- Spoken on arrival: "Described by {who}: {text}"
- "No key has been set up for {who} yet. Put one in on the AI page of
  Preferences, then try again."
- "There is no picture to describe."

### The document dialog

- "Measuring what would be sent." (the field, before the question)
- "Sending the document to {who}." (the field, while sending)
- Progress, in the Status line and the hints channel: "Reading the
  document." / "Preparing {n} pictures." / "Sending the document to
  {who}: about {n} words, {n} pictures, {size}. This can take a minute."
- "Described by {who} in {n} seconds."
- Spoken on arrival: "Described by {who} in {n} seconds. The description
  is in the Message field; arrow through it, or choose Copy."
- "Nothing was described." (the Status line after a failure; the field
  holds the failure sentence)
- "The description has been copied to the clipboard."
- "The clipboard would not take the text. Select it in the Message field
  and press Control C."
- Added to the end of an answer when something stayed behind: "Only {n}
  of the document's {n} pictures were sent, so pictures 13, 14 and 15 are
  not described." / "Picture 2 could not be read and was not sent." /
  "The document has about {n} words and only the first 30,000 were sent."
- "The document is empty, so there is nothing to describe."
- "The picture could not be prepared for sending, so nothing has left
  this machine. It may be a kind of picture file TG Imprint cannot read."
- "{who} answered, but with nothing that could be used as a description."

### The AI page of Preferences

- Note at the top: "Describe pictures and whole documents with Claude,
  ChatGPT or Gemini on your own account; you pay them directly and
  nothing goes through TG Studios. Nothing leaves this machine until you
  say so in a dialog that names the provider, and no answer is written
  into your document unread."
- "A key for {who} is kept in Windows Credential Manager, set, ending
  {xxxx}. Clear the box and choose OK to forget it." / "No key for {who}
  is kept yet. Paste one in the box; it goes into Windows Credential
  Manager as TG Imprint AI key, never into a document or your settings."
  ("set, ending xxxx" is `secrets.redact`, Drop Deck's wording.)
- "Empty means {model}, chosen for accuracy. Get the list asks {who} what
  it really has. Test sends a tiny picture TG Imprint draws itself, nothing
  of yours." (the first sentence adapted from Drop Deck's "which is the
  quick one")
- "The key for {who} has been forgotten."
- "Windows Credential Manager would not remove the key for {who}. Remove
  it there yourself, listed as TG Imprint AI key."
- "Nothing was copied."
- "TG Drop Deck has no key for {who} on this machine, so there is nothing
  to copy."
- "The {who} key was found, but Windows Credential Manager would not
  keep a copy for TG Imprint. Paste the key into the box instead."
- "The {who} key from TG Drop Deck is now kept for TG Imprint as well, set,
  ending {xxxx}."
- "Put a key in first, then ask for the list." (Drop Deck's, approved)
- "Asking {who} what it has." (Drop Deck's, without the dots)
- "{n} models. Arrow through the list, or leave the box empty for
  {model}." (Drop Deck's, adapted)
- "Put a key in first, then test it."
- "Testing with {who}."
- "{who} answered in {n} seconds: {text}"

### Failures, from `ai.py`

Drop Deck's sentences, with "the show" replaced by "your document".

- "{who} would not accept that key. Check it has been pasted in full, and
  that it is a key for {who} rather than another service." (approved in
  Drop Deck)
- "{who} does not know that model name. Model names change; put the
  current one in the Model box on the AI page of Preferences, or use Get
  the list there."
- "{who} is rate limiting, or the account has run out of credit. Wait a
  moment and try again, or check the billing on your account." (approved
  in Drop Deck)
- "{who} refused the request. The most likely cause is a model name that
  cannot look at pictures; the other is a document too big for it. Try
  the default model again, or describe fewer pictures."
- "{who} said the request was too big. Describe fewer pictures at a time."
- "{who} is having trouble at their end. Nothing is wrong here, so try
  again in a minute." (approved in Drop Deck)
- "Could not reach {who}. Check this machine is online. Nothing in your
  document has changed."
- "{who} did not answer in time. Try again, or try a quicker model.
  Nothing in your document has changed."
- "The description could not be done: {the error}. Nothing in your
  document has changed."
- "{who} declined to describe this. Its content filter stopped the
  answer, which happens with some pictures of people and some documents.
  Nothing is wrong with your key."
- "No key has been set up yet. Put one in on the AI page of Preferences,
  then try again."
- "That provider is not one this app knows. Choose Claude, ChatGPT or
  Gemini on the AI page of Preferences."
- "There is nothing to ask."
- "One of the pictures could not be prepared for sending, so nothing has
  left this machine."
- "{who} answered in a shape this app did not expect, so there is nothing
  to read out." (approved in Drop Deck)
- "{who} looked at the picture and said nothing back." (approved in Drop
  Deck)
- Model list: "That is not a service this app knows." / "The list came
  back in a shape this app did not expect." / "That account has no models
  that can look at pictures." (all Drop Deck's)

### The prompts, asked in Tony's name

Not spoken. Listed in full in `docs/DESCRIBER.md` under "The words that
are asked in your name"; summarised here.

- One picture, short: the alternative text prompt ending "Write one or
  two sentences saying what the picture shows and what it is for in the
  document."
- One picture, in detail: the same, ending with the paragraph that asks
  for "up to about a hundred and fifty words".
- The context line: "Where the picture sits in the document, so the
  description fits it:" followed by the heading and paragraph the editor
  passes.
- The whole document: the four-part prompt (what it is, its structure,
  each picture, what an accessibility check would flag), then the
  attachment sentences and the outline with its labels "Heading level
  {n}:", "Paragraph:", "List item:", "Quotation:", "Caption:", "Picture
  {n}, described as:", "Picture {n}, no description.", "Picture {n},
  marked decorative, no description.", "(this description was written
  by AI and has not been checked by a sighted person)", "(this
  description was recovered from a file and has not been checked)",
  "(link to {address})", "Table starts.", "Header row:", "Row:", "Table
  ends, {n} rows and {n} columns."
- The Test button: "In at most ten words, say what shape and colour is
  in this picture." and, without a picture, "Reply with the single word:
  ready."

- Added 2026-09-09 after the Overseer's review: "Type or ask for a description first." (picture dialog, empty description on Use this description). The consent question now says "the first 30,000 of its N words" when a document is over the cap, and names the number of pictures that will really go. Status: draft.
