# TG Imprint

Write a document with headings, lists, links and pictures, and export a
tagged PDF that screen readers can read. Open a PDF somebody sent you and
make it accessible. Describe pictures with Claude, ChatGPT or Gemini on your
own key. A TG Studios program for Windows.

Documents are `.imprint` files: self-contained HTML inside a file type the
app owns, so a double click opens TG Imprint. Rename one to `.html` and any
browser reads it. An installed copy registers the type; the portable zip
does not, so from the zip open documents from inside the app.

The installer is Velopack: it installs per user with no administrator
prompt, and an installed copy updates itself in place, with your say-so,
downloading only what changed. Nothing is downloaded or applied without
asking, and every update is checked against the TG Studios signature.

Free and MIT licensed. The source is at
https://github.com/tonygeb23/tg-imprint, and pull requests are welcome.

## Running from source

Python 3.13 with the packages in `requirements.txt`:

```
pip install -r requirements.txt
python main.py
```

The tagged PDF is written by the Chromium engine already on the machine:
Microsoft Edge, the Edge WebView2 runtime that the editor itself needs,
or Google Chrome, in that order. Windows 11 ships the first two.

## Keys

Help, then Keyboard shortcuts (F1) lists every key. The full guide is on the
web under Help once published. `docs/KEYBOARD.md` is the map.

## Building a release

See `CLAUDE.md` and `Dropbox\TG Studios\RELEASING.md`.
