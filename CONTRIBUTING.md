# Testing and working on TG Imprint

TG Imprint is open: MIT licensed, built in the open, and made for people who use
screen readers. Testing it, reporting what breaks and sending code all help.

## Test it

Download it from https://tgstudios.app/tg-imprint/ and use it on real work.
The most useful things right now:

- **Bring a PDF that fails.** A scan, a damaged file, a form, a PDF that reads as
  nonsense. Tell us what you expected and what happened.
- **Tell us what you hear.** It is tested with NVDA. JAWS and Narrator reports
  are especially welcome: say which version and what was announced.
- **Check an exported PDF** in Acrobat, Edge, Firefox or Foxit, with a screen
  reader, or with PAC or veraPDF.
- **Look at it.** If you can see the screen, tell us what looks wrong, in light,
  dark, yellow on black and Windows high contrast.
- **Try the low vision settings** at the size you actually use.

Use the issue forms at https://github.com/tonygeb23/tg-imprint/issues/new/choose.
Blind and low vision testers: an email to info@tonygebhard.me is just as good.

**Never post a private PDF.** A public issue is public. Describe the file, or
make a small copy with nothing private in it. Do not attach medical, financial
or legal documents.

## Work on it

Python 3.13 on Windows, wxPython, no virtual environment needed:

```
pip install -r requirements.txt
python main.py
```

`CLAUDE.md` holds the standing rules and every trap measured so far. Read it
first. The rules that decide whether a pull request can go in:

- **Every user facing change is tested with a screen reader running**, and the
  pull request says which one and what it said.
- **Every control has a real accessible name.** Colour and icons only ever
  repeat words already there.
- **No em dashes or en dashes anywhere.** `python tools/nodashes.py` reports them.
- **Keys once taught are never taken away.**
- **Nothing slow on the UI thread**, and no synchronous `RunScript`.
- **Nothing leaves the machine without consent** that names the provider.
- **Every new visible sentence goes in `docs/STRINGS.md`.** Plain, short words.
- **A claim needs a witness.** The PDF/UA identifier is only written when the
  checks pass, and `python tools/verify_ua.py` puts documents through veraPDF.
  If you change the export, run it. Skipped is not passed.

## Tests

The suites are plain scripts, not pytest. `pytest` collects nothing and reports
success, so run each file:

```
python tests/test_pdfrepair.py
```

Add a regression test with every fix. `tests/test_keys.py` needs the foreground
and is known to be noisy: compare the names of the failures, not the count.
`test_describe.py` has a live check that needs an AI key.

## Where to start

`docs/SHIP-0.3.0.md` lists what is planned next, and the issues labelled
`good first issue` and `help wanted` are ready to pick up.
`docs/RESEARCH-2026-11.md` and `docs/PDF-UA.md` explain the standards and
exactly what the program can and cannot prove.
