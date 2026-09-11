# Changelog

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
