# Changelog

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
