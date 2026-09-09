# Easy PDF

Write a document with headings, lists, links and pictures, and export a
tagged PDF that screen readers can read. Open a PDF somebody sent you and
make it accessible. Describe pictures with Claude, ChatGPT or Gemini on your
own key. A TG Studios program for Windows.

Documents are `.epdf` files: self-contained HTML inside a file type the
app owns, so a double click opens Easy PDF. Rename one to `.html` and any
browser reads it. The installer registers the type; the zip copy does not,
so from the zip open documents from inside the app.

## Running from source

Python 3.13 with the packages in `requirements.txt`:

```
pip install -r requirements.txt
python main.py
```

Microsoft Edge (or Google Chrome) must be installed: it is the engine that
writes the tagged PDF. Windows 11 ships Edge.

## Keys

Help, then Keyboard shortcuts (F1) lists every key. The full guide is on the
web under Help once published. `docs/KEYBOARD.md` is the map.

## Building a release

See `CLAUDE.md` and `Dropbox\TG Studios\RELEASING.md`.
