# Brief: Worker C, the describer

You own the AI: describing a picture for its alt text, and describing a
whole document, with Claude, ChatGPT or Gemini on the user's own key. Read,
in order: `CLAUDE.md`, `docs/ANALYSIS.md` section 9, `docs/DECISIONS.md`,
`docs/PLAN.md`. If this brief and `DECISIONS.md` disagree, `DECISIONS.md`
wins.

The provider layer already exists: `easypdf/ai.py` is a verbatim copy of
`Dropbox\TG Studios\TG Drop Deck\dropdeck\vision.py`, which shipped on
2026-09-08 and is proven against all three services. Its rules are yours:
nothing here raises, every failure is a sentence somebody can act on,
model names are settings with a moving-alias default, the model list is
fetched live, keys go in a header never a URL, the picture is scaled before
it leaves, and nothing leaves without consent. Read all of it before
changing a line, and keep the provider functions' shape so a fix in Drop
Deck can be carried across.

## Files you own

`easypdf/ai.py`, `easypdf/describe.py`, `easypdf/ui/describe_dialog.py`,
`easypdf/ui/ai_settings_page.py`, `tests/test_ai.py`,
`tests/test_describe.py`, `docs/DESCRIBER.md`. You may read
`easypdf/secrets.py` and must use it; never change its prefix. Do not edit
anything else under `easypdf/ui/`.

## The interfaces (exact; Worker B is coding against them now)

```python
# describe.py
describe_image(image_bytes: bytes, provider: str, model: str,
               context: str = "", long: bool = False) -> (bool, str)
describe_document(body_html: str, images: list[bytes], provider: str, model: str,
                  progress=None) -> (bool, str)
consent_needed(kind: str) -> bool            # "image" once per session, "document" every time
record_consent(kind: str) -> None
consent_question(kind: str, provider: str, images: int, words: int) -> str
payload_estimate(body_html, images) -> (words: int, pictures: int, kilobytes: float)

# ui/describe_dialog.py
DescribeImageDialog(parent, image_bytes, current_alt="", context="") -> wx.Dialog
    .result -> str | None      # the text the user accepted, edited or not
DescribeDocumentDialog(parent, body_html, images) -> wx.Dialog
    .result -> str | None      # the description, for the user to copy or insert

# ui/ai_settings_page.py
AISettingsPage(parent, settings) -> wx.Panel    # mounted in Preferences by Worker B
    .apply() -> None            # writes provider and model into settings; the key into secrets
```

`settings` is a dict-like from Worker B's `easypdf/settings.py` with keys
`ai_provider` and `ai_model`. **The key never goes into settings.** It
goes through `secrets.store(provider, key)` under `secrets.TARGET_PREFIX`,
and `secrets.fetch(provider)` reads it back.

## What to build

- **Prompts.** Rewrite `ai.py`'s camera and screen prompts for this job.
  Alt text: one or two sentences, what the picture shows and what it is
  for in the document, no "image of" or "picture of", no markdown, numbers
  and words in the picture read out, a chart's meaning given rather than its
  decoration; a `long` variant for a complex picture (a chart, a diagram, a
  screenshot with text) of up to a paragraph. Pass `context`: the heading
  the picture sits under and the paragraph before it, so the description
  fits the document. Document description: what the document is, its
  structure (headings in order), what each picture shows, anything an
  accessibility check would flag (a heading level skipped, a link that says
  "click here", a picture with no description), in plain spoken sentences,
  no markdown, because it is read aloud. Write these for somebody who
  cannot check the answer against the picture.
- **Multi-image requests** for the document description: text plus up to a
  cap of pictures (choose the cap and say why; measure payload size). Over
  the cap, send the first N and say so in the answer. Scale every picture
  before it goes, as `as_jpeg` does.
- **Consent.** A whole document leaving the machine asks every time, naming
  the provider, the number of pictures and the number of words. A single
  picture asks once per session. The question is a dialog with a read-only
  field, the same shape as everything else here.
- **The dialogs.** `DescribeImageDialog`: the picture (a `StaticBitmap`
  that refuses focus), provider choice (defaulting to `best_provider`),
  Describe and Describe in detail buttons, the answer in an **editable**
  multiline field so the user changes it before accepting, Use this
  description and Cancel. Focus lands in the answer field when it arrives,
  and `announce` says it arrived. The request runs on a thread; the dialog
  stays responsive and Cancel works during it. `DescribeDocumentDialog`:
  the consent text, then progress, then the answer in a read-only field
  with focus, Copy and Close.
- **The settings page.** Provider choice, the key field (masked, with a
  Show box), a "Get the list" button that fills the model combo from the
  live account, a Test button that sends a tiny request and reports in a
  status static (never the key), and a Forget key button. Every control
  named. `apply()` writes provider and model to settings and the key to
  Credential Manager; a blank key forgets the stored one.
- **Errors** through `_trouble`, adapted so the sentences make sense here
  (there is no show going live).

## Keys on this machine

Tony's Gemini key is in Windows Credential Manager under Drop Deck's name,
`TG Drop Deck vision key: google`. You may read it through
`easypdf.secrets.fetch("google", "TG Drop Deck vision key: ")` for **one
live verification of the Gemini path** in a test that skips cleanly when
the key is absent. Never store it under Easy PDF's name, never print it,
never put it in a file. There are no OpenAI or Anthropic keys here; those
paths are tested against a fake server.

## Tests, hand-rolled, `python tests/<file>.py`

`test_ai.py`: the three request builders produce the right envelope for one
picture and for text plus several pictures (inspect the JSON); the readers
dig the text out of each provider's answer shape; `_trouble` maps 401, 404,
429, 400, 5xx and a network error to sentences that name the provider; the
model list digger handles each shape; a picture is scaled and JPEG-encoded
below the size cap; a fake `urlopen` end to end. `test_describe.py`:
consent state (document every time, picture once, reset per session);
`payload_estimate` counts words and pictures; the alt prompt contains the
context; the document prompt lists the headings; the live Gemini check
(skipped without the key) gets a non-empty sentence back for
`tests/fixtures/circle.png` and reports how long it took. Prove at least
one test can fail.

## Rules that bind you

- No em or en dashes anywhere, including prompts.
- Every sentence the app shows or speaks (consent questions, errors,
  status lines, button labels that are not plain function names) goes in
  `docs/STRINGS.md` under your heading. The prompts themselves are not
  spoken, but list them there too so Tony can read what is being asked in
  his name.
- Nothing on the UI thread; never raise out of the public functions.
- Write `docs/DESCRIBER.md`: what leaves the machine and when, how to get a
  key from each provider, what it costs in rough terms, and what the app
  will never do with the answer (write it into the document unread).

## Report back with

What you built, the tests and counts, the measured live Gemini timing and
the answer it gave for the fixture, every string you added, the payload cap
you chose and why, anything you need from Worker B or the coordinator, and
anything you left out and why.
