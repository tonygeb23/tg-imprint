# Changelog

## 0.3.0 (unreleased)

- **The PDF/UA claim is now true, and there is a witness.** A correction: every
  PDF the earlier releases marked as PDF/UA-1 failed veraPDF, the independent
  checker, because the app's own checker did not look at what failed. Bold and
  italic tags were not mapped to a standard type, and a decorative picture was
  neither tagged nor marked as decoration. Both are repaired after the print,
  list items now have a proper label and body, and eleven test documents must
  pass veraPDF before any release. Export again to get a corrected file.
- **Scanned PDFs can be read.** Text recognition, on your own machine, nothing
  sent anywhere, no key. English and Spanish. It also reads a page whose text
  looks right but reads back as symbols, which is the fault a sighted author
  never sees. It tells you how many pages it read that way, because recognition
  can get names and numbers wrong.
- **Damaged PDFs open.** A file cut off half way, with a broken internal index or
  with junk in front of it now opens with whatever survived, and says what
  happened and how many pages were lost. A file that truly cannot be opened gets
  one sentence, never a library error or a temp folder path.
- **A tagged PDF is read from its tags**, not guessed from the look of the page:
  headings, nested lists, tables with their header cells, quotes, links, bold,
  italic and pictures with their descriptions.
- **A PDF with no tags comes in better.** Ruled tables come back as tables with
  a header row, running headers and page numbers are left out, two columns are
  read in order, heading levels start at 1 with none skipped, and the title and
  language are worked out when the file does not say.
- **Eleven new checks**, on what real files fail: form fields with no name, XFA
  forms, tables with no headers, fonts that do not map to letters, text that
  reads as symbols, tags the file itself marks as doubtful, and security that
  blocks screen readers.
- **A start screen.** With nothing open you land on real buttons rather than
  an empty editor: New document, Open a document, Make a PDF accessible,
  Analyse a PDF, Repair a PDF, Fill in a PDF form, and your recent documents.
  Ctrl+W comes back to it. A file on the command line, a second launch and
  crash recovery all go straight to the document.
- **The Accessibility panel.** A list beside the document of what is left to
  do, with a line such as "3 to fix, 1 to review". It looks again a moment
  after you stop typing, without moving focus or saying anything. Enter on an
  issue goes to that heading, picture, link or table. Ctrl+Shift+L shows or
  hides it.
- **Ctrl+F6 and Ctrl+Shift+F6** move between the document, the panel and the
  toolbar, from anywhere. F6 stays the next heading in the document, because
  a key once taught is never taken away.
- **Analyse a PDF** replaces Check a PDF, on the same key, Ctrl+Shift+A. It
  says in a sentence what a screen reader will make of the file and what to
  do next, then offers to open or repair it.
- **Repair a PDF** writes a copy with what can be set without touching a page.
- **Export as** Word, Markdown or plain text, beside PDF.
- **A password prompt** for a protected PDF, on open, analyse and repair.
- **A leaner toolbar.** Twelve tools in groups: New, Open, Save; paragraph
  style; Bold, Italic; Bullets, Numbers; Link, Picture, Table; Check, Export
  PDF. Alignment, underline, strikethrough and quote stay in the Format menu
  with their keys. The paragraph style list now actually applies the style;
  it had been doing nothing. A bar too wide for its window goes to icons
  rather than cutting tools off the end.
- **It looks like a TG Studios program now.** Brand colours, redrawn icons
  that share one hand, a quiet canvas round the page, and a slim spine down
  the page edge in place of the thick blue box. Dark and yellow on black now
  theme the whole window, not just the page; the menu bar is the one part
  Windows will not recolour. Windows high contrast still wins everywhere, and
  an exported PDF is still black on white.
- **A picture at the caret is outlined again.** The stylesheet and the script
  had drifted apart over a class name, so the outline never drew.

## 0.2.1 (2026-09-11)

- **A document with a picture from print now opens.** Reported by Rebecca
  Legowski: "Tried to open a document, to be met with the message: cannot
  write mode CMYK as PNG." CMYK is what any picture that came from print
  carries, and Pillow refuses to write it as a PNG rather than converting
  it. The import asked for a PNG copy of every picture with no conversion
  at all, and that call sat outside the guard protecting the one above it,
  so **one print-origin image anywhere in a PDF took the whole document
  down** and showed the raw library error to somebody who cannot see the
  page.

  Fixed at the root, and for every mode rather than only the one that was
  reported: YCbCr, LAB, HSV and F fail the same way. A picture that will
  not convert now costs that picture's description and never the document.

- **Two faults found while fixing it.** The obvious way to ask whether a
  picture has transparency, looking for an "A" in its mode name, is wrong:
  "LAB" contains an A and has no alpha at all, so a LAB picture was given a
  pointless alpha channel and a third more bytes on every page. And "I" mode
  was still being written as PNG, which Pillow removes on 15 October 2026, so
  a deprecation warning today would have been a broken document next month.

## 0.2.0, open beta (2026-09-09)

- **Fill in PDF forms.** Ctrl+Shift+F opens a PDF and shows its fields as a
  list: label, kind and value, one at a time, in reading order. Saving
  keeps the original page exactly as it was.
- **Forms that have no fields at all.** It reads the page for underscore
  runs, ruled lines, boxes, brackets, a colon at the end of a line and
  ruled tables, and offers the blanks it found for approval before writing
  anything. Claude, ChatGPT or Gemini can look at the page and propose the
  ones the drawing layer cannot see, on your own key, with consent every
  time.
- **Signatures**: a typed name or a picture, placed in the signature box.
  Not a cryptographic signature, and the app says so.
- **Low vision settings**, in a new Display page: text size that survives a
  restart, page themes including dark and yellow on black, a caret you can
  see, focus ring width, bold body text, line spacing, and toolbar labels.
  All on screen only; the PDF is still black on white.
- **The Preferences tabs say what they are.** They had no name a screen
  reader could read. Reported by HarmonicaPlayer.
- The consent question now says how much of a long document really goes,
  and how many pictures really go.

## 0.1.0, open beta (2026-09-09)

The first public build, an open beta. Revived from an April 2026
prototype and renamed from Easy PDF.

- One editor, a WebView2 page, so a screen reader hears headings, lists and
  links while writing.
- One engine: Microsoft Edge (or Chrome) writes the tagged PDF; pikepdf adds
  the PDF/UA identifier and the metadata.
- Self-contained HTML as the native document, with pictures embedded.
- Open a PDF, a Markdown file, plain text or RTF and make it accessible.
- Describe a picture or a whole document with Claude, ChatGPT or Gemini on
  your own key, with consent before anything leaves the machine.
- Self-update, single instance, an installer and a zip, a selftest, an icon,
  DPI awareness, three speech levels, and the TG Studios keyboard contract.
