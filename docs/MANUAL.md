# TG Imprint, the manual

TG Imprint is a small word processor for Windows that writes PDFs screen
readers can actually read. This is the whole of it: what it does, how to
do it, and what it will not do in this version.

Version 0.1.0, an open beta. Free.

---

## Contents

1. What it is for
2. Installing it
3. The first five minutes
4. Writing
5. Pictures, and their descriptions
6. Asking Claude, ChatGPT or Gemini to describe a picture
7. Links, tables and quotes
8. Document properties, which the PDF needs
9. Exporting the PDF, and reading the check
10. Opening a PDF, a Word file, Markdown or text
11. Finding your way around a document
12. Saving, and the file it writes
13. Printing
14. Preferences: speech, page defaults, AI
15. Updating
16. What is not in this beta
17. When something goes wrong
18. Every key

---

## 1. What it is for

A PDF that has been "printed" out of most programs is a picture of a page
with text loosely attached. A screen reader can often read the words, but
it cannot tell a heading from a paragraph, it does not know a list is a
list, and it has nothing to say about a picture.

A tagged PDF carries that structure inside it. TG Imprint writes tagged
PDFs and nothing else: headings are real headings, lists are real lists,
links are links, tables have header cells, and every picture carries a
description or is marked as decoration. It then checks its own work and
tells you what it found before you send the file to anybody.

It is built for people who cannot see the page, so everything in it is
reachable from the keyboard and everything it does is said in words.

## 2. Installing it

Download the installer from tgstudios.app and run it. It installs for you
alone, in your own AppData folder, so Windows never asks for an
administrator password. There is also a portable zip if you would rather
unpack a folder and run it from there.

You need Windows 10 or 11 and the Microsoft Edge WebView2 runtime, which
Windows 11 already has and Windows 10 installs in about a minute. If it is
missing, TG Imprint says so on startup and puts the download address on
your clipboard.

The PDF itself is made by the Chromium engine that is already on your
machine: Microsoft Edge, the WebView2 runtime, or Google Chrome, in that
order. Nothing extra to install, and no cloud service.

## 3. The first five minutes

Open TG Imprint. You are in an empty document, in the editor, ready to
type. There is no welcome screen to get past.

Type a line, press Ctrl+Alt+1 to make it a heading. Press Enter and type a
paragraph. Press Ctrl+Alt+8 and type two or three bullets, pressing Enter
between them and twice at the end to leave the list. Press Alt+Enter and
give the document a title. Press Ctrl+Shift+E and save the PDF.

The window that follows is the accessibility check on the file you just
made. Read it, then close it. That is the whole loop.

## 4. Writing

The editor is an ordinary document. Type, arrow around, select with Shift
and the arrow keys, undo with Ctrl+Z.

Your screen reader announces the structure as you move: "heading level 2",
"list, three items", "link", "graphic". The status bar also says what the
caret is in, and the app speaks it when you ask it to.

**Headings** are Ctrl+Alt+1 through Ctrl+Alt+6, and Ctrl+Alt+0 turns a
line back into ordinary text. If your keyboard uses AltGr, which is the
same key as Ctrl+Alt on German, French, Polish, Spanish and Portuguese
layouts, use Ctrl+Shift+1 through Ctrl+Shift+6 instead. Both work
everywhere.

Do not skip a level. Going from a heading 1 to a heading 3 is a real
accessibility fault, and the check at export will name the heading that
did it.

**Lists** are Ctrl+Alt+8 for bullets and Ctrl+Alt+9 for numbers. Enter on
an empty item leaves the list. Tab nests an item, Shift+Tab lifts it back
out. Backspace at the start of an item takes it out of the list.

**Character formatting**: Ctrl+B bold, Ctrl+I italic, Ctrl+U underline,
Ctrl+Shift+K strikethrough, Ctrl+Shift+C code. Bold and italic reach the
PDF as real emphasis, which a screen reader can announce.

**Alignment** is Ctrl+L, Ctrl+E, Ctrl+R and Ctrl+J.

**Paste** from Word, a browser or anywhere else is cleaned on the way in:
headings, lists, links, bold and italic are kept, and fonts, colours and
layout are thrown away. A pasted picture arrives as a figure that needs a
description.

## 5. Pictures, and their descriptions

Ctrl+Shift+P inserts a picture. The dialog asks for the file and for a
description, and it will not let you insert one without either a
description or the decorative box ticked.

**The description** is what somebody who cannot see the picture hears
instead of it. Say what the picture shows and what it is doing in the
document. "A bar chart, sales by quarter, rising from twelve thousand in
the first quarter to thirty one thousand in the fourth" is useful. "Chart"
is not. Do not start with "image of" or "picture of"; the screen reader
already says that part.

**Decorative** means the picture carries no information: a rule, a flourish,
a background texture. Ticking that box marks it so screen readers skip it
entirely, which is the correct and kind thing to do for decoration and the
wrong thing to do for anything else.

**Width and placement**: a quarter, a half, three quarters or the full
width of the text, and left, centre or right. A caption is optional and
separate from the description; the caption is read by everybody, the
description only by those who need it.

**Alt+Enter** on a picture opens its properties again. **F2** on a picture
edits its description directly.

**Ctrl+Shift+Alt+P** lists every picture in the document with its
description, and marks the ones that still need one. That list is the fast
way to finish a document, and the first thing to open after importing a
PDF or a Word file that somebody else made.

Pictures are scaled down to two thousand pixels on their longest side when
they come in. A phone photograph is far larger than any page needs, and
the file would otherwise be enormous.

## 6. Asking Claude, ChatGPT or Gemini to describe a picture

**Ctrl+D** on a picture asks an AI service to describe it. The answer
lands in an editable field: read it, change it, then choose Use this
description. Nothing is written into your document until you accept it.

**Ctrl+Shift+D** asks about the whole document: what it is, how it is
structured, what each picture shows, and anything an accessibility check
would flag.

**You need your own key.** TG Imprint has no account and no service of its
own. Open Preferences with Ctrl+comma, go to the AI page, choose Claude
from Anthropic, ChatGPT from OpenAI, or Gemini from Google, and paste in a
key from that provider. The key is kept in Windows Credential Manager
under "TG Imprint AI key", never in a document and never in a settings
file. You can see it there yourself, and Forget this key removes it.

If you already gave TG Drop Deck a key, there is a button to copy that one
across rather than fetch it again.

**What leaves your machine, and when.** Nothing goes anywhere unless you
press one of those two keys. When you do, TG Imprint tells you first what
it is about to send, to whom, and how large it is, and waits for you to
say yes. A single picture of your own asks once per session. A whole
document, a batch of pictures, and any picture that came in with a file
somebody else sent you, all ask every single time.

**Be careful with documents that are not yours.** A PDF a client sent you
is their material, and describing it sends it to a third party. That is
why those ask every time.

**The description is a draft, not an answer.** These services are
confident and sometimes wrong. If the picture matters, have somebody who
can see it check what came back. A description written this way is marked
in the file, and the export warns you how many are in the document.

## 7. Links, tables and quotes

**Ctrl+K** inserts a link, or edits the one at the caret. Write link text
that says where it goes: "the accessibility statement", not "click here".
Somebody moving link by link hears only the link text.

**Ctrl+Shift+T** inserts a table with a header row. Tab moves between
cells and Tab in the last cell adds a row. Header cells reach the PDF as
real header cells, so a screen reader can say which column a value is in.
Tables in this beta are plain grids: no merged cells.

**Ctrl+Q** makes a quotation block.

## 8. Document properties, which the PDF needs

**Alt+Enter**, with no picture selected, opens the document's properties:
title, author, subject, language, page size and margins.

**The title is required before you can export.** It is not bureaucracy: a
screen reader announces the title when the PDF opens, and a PDF with no
title announces its filename instead, which is usually something like
"scan 0143 final v2". The export dialog will send you here if you have not
set one.

**The language** matters as much. It tells a screen reader which
pronunciation rules to use. English text read with German rules is close
to unintelligible. Set it once per document.

## 9. Exporting the PDF, and reading the check

**Ctrl+Shift+E** exports. Choose where to save it, and TG Imprint lays out
the pages, writes the file and then checks it.

The report that follows is a list of checks, each passed or failed with a
sentence saying what to do. It covers: the document is tagged, the
structure tree is there, the language is set, the title is set and shown,
every picture has a description, heading levels do not skip, fonts are
embedded, links are tagged and described, the tab order is set, and there
is a real text layer.

**The PDF/UA identifier**, the mark that claims formal conformance, is
written only when every one of those checks passes. If something failed,
the PDF is still tagged and still far better than an ordinary one, but it
does not make a claim it cannot support. The report says which check
stopped it.

**What the check cannot tell you**: whether a description is true, whether
a heading is really a heading, or whether the reading order makes sense. A
formal verdict needs PAC or veraPDF, which are separate free tools. This
check is what can be measured from inside the app.

**Ctrl+Shift+A** runs the same checks on any PDF on your disk, whoever
made it.

## 10. Opening a PDF, a Word file, Markdown or text

**Ctrl+O** opens `.imprint` documents, `.html`, `.txt`, `.md`, `.docx` and
`.pdf`.

Opening a **PDF** pulls the text back out and rebuilds it as a document:
headings guessed from the type sizes, paragraphs joined across pages,
lists recognised, links kept, and every picture extracted. Descriptions
already in a tagged PDF are recovered; the rest are listed as needing one.
Then you fix what is wrong and export a proper tagged PDF. That is the
"make this accessible" path, and it is what the Pictures list is for.

A **scanned** PDF, which is photographs of pages with no text in it, cannot
be imported. TG Imprint says so rather than producing an empty document.
There is no text recognition in this beta.

Opening a **Word** document keeps headings, lists, links, bold and italic,
tables and pictures with the descriptions Word held. It warns about
anything it dropped, such as tracked changes, footnotes or text boxes.

Whatever you open, Save writes a TG Imprint document; the original is
never overwritten.

## 11. Finding your way around a document

**F6** and **Shift+F6** move to the next and previous heading, and say
which one you landed on.

**Alt+F6** opens the structure navigator: every heading in a list,
indented by level. Enter jumps to one.

**Ctrl+F** finds, **Ctrl+H** finds and replaces, **F3** and **Shift+F3**
repeat. Replace keeps the formatting of what it replaces.

**Ctrl+Shift+Alt+P** is the picture list described above.

## 12. Saving, and the file it writes

**Ctrl+S** saves. A TG Imprint document is a `.imprint` file, and inside it
is ordinary HTML with the pictures embedded, so the file is
self-contained: one file to send, nothing to lose.

Rename it to `.html` and any browser opens it. Nothing you write is ever
trapped in this program.

**Save as web page** writes that `.html` directly, when you want a web
page rather than a document.

**Autosave** takes a snapshot of an unsaved document every minute. If the
app or the machine goes down, the next start offers what it saved.

## 13. Printing

**Ctrl+P** makes the same tagged PDF and sends it to your printer. It asks
for a title first, for the same reason the export does.

## 14. Preferences: speech, page defaults, AI

**Ctrl+comma** opens Preferences.

**Spoken feedback from the app** has three settings, and it is not the
same thing as your screen reader:

- Everything, including confirmations and hints.
- Only what I cannot hear or read for myself.
- Nothing. Let my screen reader do all of it.

Whatever you choose, everything the app has to say is also written to the
status bar, so nothing is lost by turning it down.

**Document defaults** are the page size, margins, font and language a new
document starts with.

**AI** is the provider, the model and the key, described in section 6.

## 15. Updating

TG Imprint checks once a day, quietly, and tells you only when there is
something. Help, then Check for updates asks on demand and answers either
way in a window you can read.

An update downloads only what changed, verifies it against a TG Studios
signature before it is allowed to run, asks you before it installs, and
then applies itself and reopens the app. There is no installer window to
navigate and nothing to click through.

A copy running from the portable zip updates the same way.

## 16. What is not in this beta

Said plainly, so you can decide whether it is any use to you yet:

- No text recognition, so a scanned PDF cannot be imported.
- No right to left languages. Arabic and Hebrew are not tested and the
  reading order may be wrong. The export warns you if it sees them.
- No footnotes, page numbers, columns, headers or footers.
- No merged table cells.
- One font per document, and one document open at a time.
- No RTF, and no Word export. Save as web page covers most of that.
- Windows only. There is no Mac version.
- Tested with NVDA. JAWS and Narrator should work and are not yet tested;
  tell me what you hear.

## 17. When something goes wrong

Everything the app refuses to do, it explains in a sentence, in a window
you can read back rather than a message that flashes past.

If the editor is an empty grey panel, the WebView2 runtime is missing; see
section 2.

If the export says no PDF engine was found, install Microsoft Edge or
Google Chrome.

If a key does nothing, F1 shows every key the app knows.

It is a beta. If something breaks, or a description reads wrongly, or your
screen reader says something unhelpful, write to hello@tgstudios.app and
say what you did and what you heard.

## 18. Every key

The full list is in the app on F1, and in `docs/KEYBOARD.md` beside this
manual. It is generated from the code, so it cannot go stale.
