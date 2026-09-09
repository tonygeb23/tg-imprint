# tgstudios.app product page, draft for Tony

Every word here is a draft in Tony's voice and ships only when he has read
it. It is written in the shape `Websites\tgstudios.app\content\pages\*.md`
uses (see `drop-deck.md` there for the blocks). The version number and the
download sizes are filled in by the release. The name follows
`docs/DECISIONS.md` decision 6, which is Tony's; "TG Imprint" is the working
assumption.

---

# TG Imprint

Write a document. Get a PDF that screen readers can actually read.

:::hero
TG Imprint is a small word processor for Windows that does one thing well:
every PDF it writes is tagged, so a blind reader hears headings, lists,
links and picture descriptions instead of a wall of text. It also opens a
PDF somebody sent you and helps you make it accessible.
:::

:::actions
- [Download TG Imprint for Windows](/downloads/TGImprint-1.0.0-Setup.exe)
- [Portable zip](/downloads/TG-Imprint-1.0.0-windows.zip)
- [Read the guide](/tg-imprint-guide/)
:::

## What it does

- Headings, lists, links, quotes, tables and pictures, with the keys you
  already know from Word. Ctrl+B is bold, Ctrl+I is italic, Ctrl+K is a
  link, Ctrl+Alt+1 is a heading.
- A screen reader hears the structure while you write: "heading level 2",
  "list, three items", "link". Tested with NVDA.
- Export to PDF, and the PDF is tagged: real headings, real lists, alt
  text on every picture, the document language, the title in the window
  bar. The app checks its own output before it hands it to you and tells
  you what it found.
- Every picture needs a description before it goes in. If you cannot see
  the picture, ask Claude, ChatGPT or Gemini to describe it, on your own
  key, and edit what comes back. Nothing leaves your machine without
  asking you first.
- Open a PDF, a Word document, a Markdown file, a web page or plain text,
  and save it as a TG Imprint document. A PDF that arrived with no picture
  descriptions gets a list of the pictures that need one.
- Free. If it earns its keep, there is a [donate page](/donate/).

## Why not Word or LibreOffice

They can make a tagged PDF, if you know which of eleven boxes to tick,
and they will happily make an untagged one if you do not. TG Imprint has no
untagged setting. It will not write a PDF it cannot tag, it will not let a
picture in without a description, and it reads the result back to you
before you send it.

## What it will not do in this version

- Read scanned PDFs (pictures of text). It says so when it meets one.
- Right to left languages. Arabic and Hebrew text is warned about, not
  promised.
- Footnotes, page numbers, columns, headers and footers, more than one
  font, or more than one open document.
- Tables beyond the basics: no merged cells.
- Run on a Mac.

## Requirements

Windows 10 or 11. The Microsoft Edge WebView2 runtime, which Windows 11
already has and Windows 10 installs in a minute. Microsoft Edge, the
WebView2 runtime or Google Chrome writes the PDF; all three are already on
most machines.

## Get in touch

Feedback and bug reports to info@tonygebhard.me. If you use JAWS or
Narrator rather than NVDA, say what you heard: this version was tested
with NVDA.
