# TG Imprint keyboard reference

Generated from `tgimprint/ui/keymap.py` by `python tgimprint/ui/keymap.py docs/KEYBOARD.md`. `tests/test_menus.py` fails if this file and the code disagree, so edit the code and regenerate.

Every key works while you are typing in the document. The same keys are in the menus, and the Applications key (or Shift+F10) opens a context menu offering the editing and formatting items.

## The headings and the AltGr rule

Ctrl+Alt+1 to Ctrl+Alt+6 set heading levels 1 to 6, Ctrl+Alt+0 makes normal text, Ctrl+Alt+8 a bullet list and Ctrl+Alt+9 a numbered list. On German, French, Polish, Spanish and Portuguese keyboards Ctrl+Alt is AltGr and some of those chords type a character instead, so TG Imprint acts on them only when the key really was the digit. The same commands are also on Ctrl+Shift+0 to Ctrl+Shift+9, which work on every layout.

## Inside lists and tables

Enter at the end of a heading starts a normal paragraph. Enter on an empty list item leaves the list. Backspace at the start of a list item takes it out of the list. Tab and Shift+Tab nest and unnest a list item; in a table they move between cells, and Tab in the last cell adds a row. Outside a list or table, Tab leaves the document for the toolbar, and Shift+Tab comes back.

## Moving between panes

Ctrl+F6 moves from the document to the Accessibility panel, then the toolbar, then back. Ctrl+Shift+F6 goes the other way. F6 and Shift+F6 stay the next and previous heading while you are in the document, because those keys were taught first. In the panel or on the toolbar F6 goes straight back to the document, and so does Escape in the panel. Enter on an issue goes to that place in the document.

## Every key

| Menu | Command | Keys | What it does |
|---|---|---|---|
| File | New | Ctrl+N | Start a new, empty document. |
| File | Open... | Ctrl+O | Open a document: .imprint, .html, .txt, .md, .docx or .pdf. |
| File | Make a PDF accessible... |  | Bring a PDF in as a document. The Accessibility panel then lists what is left to do before you export a tagged copy. |
| File | Save | Ctrl+S | Save the document. |
| File | Save As... | Ctrl+Shift+S | Save the document under a new name, as a TG Imprint document. |
| File | Save as web page... |  | Write the same document to a .html file any browser can open. |
| File | Close document | Ctrl+W | Close the document and go back to the start screen. |
| File, Export as | PDF... | Ctrl+Shift+E | Make the tagged PDF and check it. |
| File, Export as | Word... |  | Write the document to a Word file, with its headings, lists and tables. |
| File, Export as | Markdown... |  | Write the document to a Markdown file. |
| File, Export as | Plain text... |  | Write the words of the document to a plain text file. |
| File | Print... | Ctrl+P | Make a PDF and send it to the printer. |
| File | Analyse a PDF... | Ctrl+Shift+A | Find out what a screen reader will make of any PDF, and what to do about it. Nothing is changed. |
| File | Repair a PDF... |  | Write a copy of a PDF with its title, language, link descriptions and field names set. Every page stays exactly as it looks. |
| File | Document properties... | Alt+Enter | Properties of the picture at the caret, or of the document: title, author, language, subject, page size and margins. |
| File | Exit | Alt+F4 | Close TG Imprint. |
| Edit | Undo | Ctrl+Z | Undo the last change. |
| Edit | Redo | Ctrl+Y | Redo the change you undid. |
| Edit | Cut | Ctrl+X | Cut the selection to the clipboard. |
| Edit | Copy | Ctrl+C | Copy the selection to the clipboard. |
| Edit | Paste | Ctrl+V | Paste. Text from Word or a web page is cleaned to headings, lists, links, bold and italic; a picture becomes a figure that needs a description. |
| Edit | Select all | Ctrl+A | Select the whole document. |
| Edit | Find... | Ctrl+F | Find text in the document. |
| Edit | Find and replace... | Ctrl+H | Find text and replace it, one at a time or all at once. |
| Edit | Find next | F3 | Find the next match. |
| Edit | Find previous | Shift+F3 | Find the previous match. |
| Edit | Edit picture description or document title | F2 | Edit the description of the picture at the caret, or rename the document when there is no picture. |
| Edit | Remove picture or table | Delete | Remove the picture at the caret, or an empty table, after a confirmation. Elsewhere Delete deletes text as usual. |
| Format | Bold | Ctrl+B | Bold on or off. |
| Format | Italic | Ctrl+I, Ctrl+Shift+I | Italic on or off. Ctrl+Shift+I is kept from the April build. |
| Format | Underline | Ctrl+U | Underline on or off. |
| Format | Strikethrough | Ctrl+Shift+K | Strikethrough on or off. |
| Format | Code | Ctrl+Shift+C | Code, in a fixed width font, on or off. |
| Format, Paragraph style | Normal text | Ctrl+Alt+0, Ctrl+Shift+0 | Make this an ordinary paragraph. |
| Format, Paragraph style | Heading 1 | Ctrl+Alt+1, Ctrl+Shift+1 | Heading level 1. |
| Format, Paragraph style | Heading 2 | Ctrl+Alt+2, Ctrl+Shift+2 | Heading level 2. |
| Format, Paragraph style | Heading 3 | Ctrl+Alt+3, Ctrl+Shift+3 | Heading level 3. |
| Format, Paragraph style | Heading 4 | Ctrl+Alt+4, Ctrl+Shift+4 | Heading level 4. |
| Format, Paragraph style | Heading 5 | Ctrl+Alt+5, Ctrl+Shift+5 | Heading level 5. |
| Format, Paragraph style | Heading 6 | Ctrl+Alt+6, Ctrl+Shift+6 | Heading level 6. |
| Format, Paragraph style | Bullet list | Ctrl+Alt+8, Ctrl+Shift+8 | A bullet list, on or off. |
| Format, Paragraph style | Numbered list | Ctrl+Alt+9, Ctrl+Shift+9 | A numbered list, on or off. |
| Format, Paragraph style | Quote | Ctrl+Q | A quotation block, on or off. |
| Format, Alignment | Left | Ctrl+L | Align left. |
| Format, Alignment | Centre | Ctrl+E | Centre. |
| Format, Alignment | Right | Ctrl+R | Align right. |
| Format, Alignment | Justify | Ctrl+J | Justify. |
| Format | Increase list level | Tab | In a list, Tab nests the item one level deeper. |
| Format | Decrease list level | Shift+Tab | In a list, Shift+Tab moves the item out one level. In a table, Tab and Shift+Tab move between cells and Tab in the last cell adds a row. |
| Insert | Link... | Ctrl+K | Insert a link, or edit the link at the caret. |
| Insert | Picture... | Ctrl+Shift+P | Insert a picture with a description. |
| Insert | Table... | Ctrl+Shift+T | Insert a table with a header row. |
| Insert | Picture properties... |  | Description, caption, width and placement of the picture at the caret. Alt+Enter opens this when the caret is on a picture. |
| Tools | Describe picture... | Ctrl+D | Ask Claude, ChatGPT or Gemini to describe the picture at the caret. |
| Tools | Describe document... | Ctrl+Shift+D | Ask an AI service to describe the whole document. |
| Tools | Check this document |  | Show the Accessibility panel, check the document now and move to the list of what is left to do. |
| Tools | Analyse a PDF... | Ctrl+Shift+A | Find out what a screen reader will make of any PDF, and what to do about it. Nothing is changed. |
| Tools | Fill in a PDF form... | Ctrl+Shift+F | Open a PDF that has form fields and fill them in from a list, one field at a time. A PDF with no fields can be looked over for the blanks first. |
| Tools | Preferences... | Ctrl+, | Spoken feedback, document defaults, the screen and the AI services. |
| View | Next heading | F6 | Move the caret to the next heading. |
| View | Previous heading | Shift+F6 | Move the caret to the previous heading. |
| View | Structure navigator... | Alt+F6 | Every heading in a list; Enter jumps to it. |
| View | Pictures... | Ctrl+Shift+Alt+P | Every picture with its description, or the ones still needing one. |
| View | Accessibility panel | Ctrl+Shift+L | Show or hide the list of what is left to do in this document. |
| View | Next pane | Ctrl+F6 | Move between the document, the Accessibility panel and the toolbar. F6 alone is the next heading while you are in the document; in the panel or on the toolbar it goes back to the document. |
| View | Previous pane | Ctrl+Shift+F6 | The same, the other way round. |
| View | Zoom in | Ctrl+= | Make the page larger on screen. |
| View | Zoom out | Ctrl+- | Make the page smaller on screen. |
| View | Actual size | Ctrl+0 | Show the page at its normal size, one hundred percent. |
| View, Toolbar labels | Icons only |  | Show the toolbar as icons with no words. |
| View, Toolbar labels | Icons with labels |  | Show the toolbar as icons with a word under each one. |
| View, Toolbar labels | Labels only |  | Show the toolbar as words with no icons. |
| View | Display options... |  | Text size, page colours, the caret, the focus ring, bold text and line spacing. All of them are the screen only: an exported PDF is always black text on a white page. |
| Help | Keyboard shortcuts | F1 | This list, in a window you can read. |
| Help | User guide on the web |  | Open the user guide in your browser. |
| Help | Check for updates |  | Ask whether a newer version exists. |
| Help | Donate |  | Support TG Studios. |
| Help | About TG Imprint |  | The version, the tagline and the PDF engine that was found. |
| Everywhere | Context menu | Applications, Shift+F10 | The context menu, offering what the menu bar offers. |

