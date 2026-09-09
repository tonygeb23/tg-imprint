# Review of Worker C, round 2: the describer

Overseer, 2026-09-09. Files read in full: easypdf/ai.py, easypdf/describe.py,
easypdf/ui/describe_dialog.py, easypdf/ui/ai_settings_page.py,
tests/test_ai.py (harness, fakes and tail), tests/test_describe.py (harness,
consent, budget, dialog and live sections), docs/DESCRIBER.md (the substance
sections), the Worker C section of docs/STRINGS.md, easypdf/secrets.py and
the frame's announce methods. NVDA was not driven; that is round 4.

## What I ran

- python tests/test_ai.py: 124 of 124 checks passed, exit code 0.
- python tests/test_describe.py: 169 of 169 checks passed, exit code 0. The
  one live Gemini call ran once on the Drop Deck key: 2.1 seconds with
  gemini-flash-latest, answer "A solid yellow horizontal oval sits centered
  on a solid blue background. It serves as a sample graphic to demonstrate
  image rendering and description within the test document."
- python tools/nodashes.py: no em or en dashes anywhere.
- Mutation run: with ai.DEFAULT_MODELS["google"] set to "gemini-2.0-flash"
  before running test_ai.py, three checks failed (121 of 124) and the exit
  code was 1. The suite can genuinely fail.
- A fragment check of 122 sentences from the four code files against
  docs/STRINGS.md: 112 present, 10 absent (defect 9).

## Defects

### 1. Silence after pressing Describe (describe_dialog.py lines 327, 361, 402)

- What is wrong: "Measuring the picture." and "Asking {who}. This usually
  takes a few seconds." are written only into the Status static. A static's
  label change is not spoken by NVDA and the static is not in the tab order.
  A blind user presses Describe and hears nothing until the answer or the
  failure arrives, which can be up to 90 seconds (ai.TIMEOUT).
- What right looks like: the same lines through announce_help (a hint, per
  CONVENTIONS.md "The three channels"), as the document dialog already does
  for its progress. The picture dialog needs the announce_help parameter
  and lookup the document dialog has (lines 460 to 462).
- Suspect from reading. Round 4 will confirm.

### 2. A check that cannot fail guards Tony's real key store (test_describe.py line 764)

- What is wrong: "no Easy PDF key was stored under the real prefix by this
  test" is `all(secrets.fetch(n, VISION_PREFIX) in ("", secrets.fetch(n,
  VISION_PREFIX)) ...)`. x in ("", x) is always true. This is the one check
  that protects the real Credential Manager entries from the page tests,
  and it passes whatever happened.
- What right looks like: snapshot the three real entries before the page
  section (secrets.fetch(n, secrets.VISION_PREFIX) for each provider) and
  check they are byte for byte the same afterwards.
- Confirmed by reading the expression; the tautology needs no run.

### 3. The consent question misstates what is sent for a long document (describe.py lines 161 to 177, 447 to 456, 711 to 715)

- What is wrong: consent_question says "about {read.words} words" using the
  full count, but describe_document sends only the first 30,000
  (WORD_CAP). payload_estimate's kilobytes also count the full outline, not
  the cut one. The progress line later says min(words, WORD_CAP), so the
  two numbers disagree on a book.
- What right looks like: the question says "the first 30,000 of its
  {n} words" when over the cap, and payload_estimate measures the outline
  as cut. The rule is that the size said in the question is the size that
  goes; the comment at line 414 promises exactly that for pictures.
- Suspect from reading (no fixture over 30,000 words was run).

### 4. The picture count in the question can be wrong (describe.py lines 168 to 172)

- What is wrong: over the cap the question says "the first 12 of its {n}
  pictures", but the number that really goes is len(chosen) from _select,
  which the byte budget and unreadable pictures can reduce below 12.
  payload_estimate already computes chosen and throws it away.
- What right looks like: payload_estimate returns, or the dialog passes,
  the number that will really be attached, and the question says that.
- Suspect from reading.

### 5. Enter in "Who to ask" accepts an empty description (describe_dialog.py lines 411 to 418, 276 to 281)

- What is wrong: StdDialogButtonSizer makes Use this description the
  default button. Enter on the provider Choice fires it, _on_ok takes the
  empty field, sets result to "" (a string, not None) and closes. Worker B
  reads .result as accepted text and may write an empty alt.
- What right looks like: an empty field on Use this description keeps the
  dialog open and says "Type or ask for a description first" (a new string
  for STRINGS.md), or result stays None when the field is empty.
- Suspect from reading.

### 6. Two confirmations on the wrong channel, one not spoken at all (describe_dialog.py line 346; ai_settings_page.py line 298)

- What is wrong: "Nothing was sent." after a no goes through announce, the
  channel for failures and values; CONVENTIONS.md puts a confirmation of
  something you just did on announce_help. "Nothing was copied." after
  Don't copy is written to the status static and never spoken, unlike every
  other outcome on the page.
- What right looks like: both through announce_help.
- Suspect from reading.

### 7. The document dialog loses the question after a failure (describe_dialog.py lines 594 to 614)

- What is wrong: on a failed send the failure sentence replaces the consent
  question in the Message field, then Send is re-enabled. The user can press
  Send again without being able to re-read what Send would send.
- What right looks like: the failure in the Status line and spoken, the
  question restored in the field (call _show_question in the else branch).
- Suspect from reading.

### 8. The preview is decoded on the UI thread (describe_dialog.py lines 237, 95 to 129)

- What is wrong: bitmap_for decodes the whole picture with wx.Image, falls
  back to Pillow, and scales with IMAGE_QUALITY_HIGH, all inside __init__.
  A 4,000 by 3,000 photograph is more than a blink.
- What right looks like: build the dialog with the preview slot empty, decode
  on a thread, and set the bitmap through wx.CallAfter with the generation
  counter; or accept the cost and say so with a measurement.
- Suspect from reading, not measured.

### 9. Ten sentences are not in docs/STRINGS.md

- What is wrong: the prompts are summarised, not listed, and these prompt
  sentences from describe.py lines 561 to 582 appear nowhere in STRINGS.md:
  "The document has no pictures.", "The document's one picture is
  attached.", "All {n} of the document's pictures are attached, in order.",
  "The document has {n} pictures. Only these are attached ... The others
  were not sent; say that they were not described rather than guessing at
  them.", "Picture {n} could not be read by the program that sent this, so
  it is not attached.", "The document is long, so only its first {n} words
  are given.", "(The document has no text.)". They are in DESCRIBER.md lines
  345 to 352. worker-c.md lines 127 to 129 say the prompts go in STRINGS.md
  too.
- What right looks like: the prompts in full under "The prompts, asked in
  Tony's name", or one line there saying they are listed in full in
  DESCRIBER.md and nowhere else, so there is one place to approve.
- Confirmed by running the fragment check.

### 10. Dead single picture builders (ai.py lines 287 to 298, 328 to 337, 359 to 376, 402)

- What is wrong: _anthropic, _openai, _google and _BUILDERS are never called;
  ask() uses only _PART_BUILDERS. They are kept so a Drop Deck fix can be
  pasted, but a fix pasted into a function nothing calls fixes nothing, and
  _anthropic's reader still has the block zero fault that line 317 explains.
  The only use is the test that the pairs agree on address and headers.
- What right looks like: delete them and keep the comparison in the test
  against literal addresses and headers, or say in one line that they are
  reference copies only.
- Suspect from reading (grep shows no caller).

### 11. Thinking may eat the answer budget on Claude Opus 5 (ai.py lines 97, 301 to 314)

- What is wrong: the Anthropic request sends no thinking setting, and on
  claude-opus-5 thinking is on by default inside max_tokens. IMAGE_TOKENS
  4000 is meant to cover it, but a stop_reason of max_tokens is not checked,
  so a cut off answer would be tidied and offered as alt text.
- What right looks like: read stop_reason in _read_anthropic (and
  finishReason MAX_TOKENS for Google, finish_reason length for OpenAI) and
  return a sentence saying the answer was cut off, or set
  output_config effort low for the picture case. Not measured here: there
  is no Anthropic key on this machine.
- Suspect from reading.

## Checked and found right

- Interfaces in DECISIONS.md C2 and C3 are honoured exactly: consent_needed
  (kind, imported, pictures), record_consent(kind), consent_question(kind,
  provider, pictures, words, kilobytes, imported) with an optional
  document_name, payload_estimate returning (words, pictures, kilobytes),
  describe_image and describe_document returning (ok, text),
  DescribeImageDialog(parent, image_bytes, current_alt, context, imported)
  with .result and .provider_used, DescribeDocumentDialog(parent,
  body_html, images) with .result, AISettingsPage(parent, settings) with
  .apply(). Extra keyword arguments all default.
- Consent as built matches decision 8: a document asks every time (the
  document dialog never calls record_consent); a picture asks every time
  when imported (record_consent is skipped at line 348) or when more than
  one, otherwise once per session. Confirmed by the passing consent tests.
- Nothing network bound runs on the UI thread: payload_estimate,
  describe_image, describe_document, list_models and ask all run on daemon
  threads and return through wx.CallAfter with a generation counter that
  drops late answers after Cancel or Close. Credential Manager reads on the
  UI thread are single advapi32 calls.
- Nothing raises out of the public functions: every path in ai.ask,
  list_models, prepare_picture, describe_image, describe_document,
  copy_drop_deck_key and the secrets calls is wrapped and returns a
  sentence.
- The key: no print, no logging, no window title carries it; status lines
  use secrets.redact (last four characters, Drop Deck's convention); the key
  travels in a header for all three providers (confirmed by the fake
  urlopen tests); the fallback error sentence formats the exception, which
  for urllib never contains headers. The Show box reveals it on purpose and
  nowhere else.
- The Drop Deck key copy asks first in a ConsentDialog whose default button
  is Don't copy, then stores only under the page's prefix, which defaults
  to secrets.VISION_PREFIX ("Easy PDF AI key: "). The test proves it with
  probe prefixes and removes every probe entry.
- Every control in both dialogs and the page has a preceding static with a
  mnemonic and a SetName; the preview refuses focus; mnemonics are unique
  within each window.
- Focus lands in the answer field on arrival (lines 385, 598); Escape is
  bound through SetEscapeId plus EVT_BUTTON on ID_CANCEL, not EVT_CLOSE
  alone; Enter in the consent field does nothing and the default button
  sends nothing; Enter in the description accepts it.
- No wx.MessageBox anywhere in the four files.
- The prompts do what decision 8 says: no "image of" (and tidy_alt strips
  one if the model ignores the instruction), numbers and words read out
  exactly, plain sentences with no markdown, context appended when given,
  chart meaning over decoration, the document prompt lists headings with
  levels and asks for the accessibility flags.
- The payload cap is enforced before anything is sent: _select runs in
  describe_document before ai.ask, and the budget test at test_describe.py
  lines 134 to 141 proves the byte budget cuts pictures.
- The model defaults: claude-opus-5, claude-sonnet-5 and claude-haiku-4-5
  are current Anthropic ids (checked against the API reference today);
  gemini-flash-latest was measured on this machine and the reasoning is in
  ai.py lines 61 to 76; gpt-4.1 is unmeasured, which the worker says.
- DESCRIBER.md has the provenance table, the measured picture sizes, the
  three policy summaries with addresses and the date read, rough costs,
  and what the app will never do with the answer.

## Verdict

Fix these and re-review. Defects 1, 2, 3 and 5 must be fixed; 4, 6, 7 and 9
should be; 8, 10 and 11 are the worker's call with one line saying why if
left. The re-review can be a read of the diff and a rerun of the two
suites; no second live call is needed.
