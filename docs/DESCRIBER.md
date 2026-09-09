# The describer: pictures and documents described on your own key

Easy PDF can ask a model that can see to describe a picture, so its
alternative text can be written, and to describe a whole document, so a
blind reader knows what they have been sent. It does this with Claude,
from Anthropic; ChatGPT, from OpenAI; or Gemini, from Google, on a key
you get from that company yourself. You pay them directly and nothing
goes through TG Studios.

This file says what leaves the machine and when, how to get a key, what
each company says it does with what you send, what it costs in rough
terms, what the app will never do with the answer, and the exact words
that are asked in your name. Written 9 September 2026; the policy and
price pages change, so the addresses are here for you to read for
yourself.

No em dashes or en dashes anywhere in this file. Tony's rule.

## The two commands

- **Describe picture** (`Ctrl+D`, or the Describe button in the picture
  dialog) sends one picture and comes back with one or two sentences for
  its description. **Describe in detail** asks for up to a paragraph, for
  a chart, a diagram or a screenshot with text in it. The answer lands in
  an editable field. Nothing goes into your document until you choose
  **Use this description**, and you can change every word first.
- **Describe document** (`Ctrl+Shift+D`) sends the document's text, with
  its structure marked, and up to twelve of its pictures, and comes back
  with a spoken-style description: what the document is, its headings in
  order, what each picture shows, and anything an accessibility check
  would flag. The answer lands in a read-only field with a Copy button.
  It is never written into the document at all.

## What leaves the machine, and when

Nothing leaves without a yes in a dialog that names the provider. The
question is in a read-only field so it can be read twice, and its
default button is the one that sends nothing. What is asked, and how
often, follows where the picture came from (docs/DECISIONS.md, decision
8):

| What | What is sent | Asks |
|---|---|---|
| A picture you put in from your own disk | The picture, scaled to at most 1,600 pixels wide, and the question below | Once per session. The yes is kept in memory until Easy PDF is closed, and written nowhere |
| A picture that came in with an imported document (a PDF, a Word file, a web page somebody sent you) | The same | Every time. That is somebody else's document leaving the machine, and you cannot look at the picture to check what is in it |
| Several pictures at once | Each picture, scaled | Every time |
| The whole document | Its text with the structure marked (headings with their levels, each paragraph, each list item, each link with its address, each table row, each picture with the description it already has), plus up to twelve pictures, scaled | Every time. The question says how many words, how many pictures and how many kilobytes |
| The Test button on the AI page of Preferences | One 96 by 64 pixel picture Easy PDF draws itself, a red circle on white, about a kilobyte, and a one-line question. Nothing of yours | It says what it sends on the page; no separate question |
| The Get the list button | Only your key, to the provider's own list of models | No question; nothing of yours leaves |

What never leaves: the document's file name (the consent question names
it for you, but it is not sent), your key to anybody but the company
that issued it (it travels in a request header, never in an address), and
anything at all to TG Studios. The key is kept in Windows Credential
Manager under the name **Easy PDF AI key**, never in a document and never
in your settings file, so a file you send to somebody else does not carry
it. You can see it and remove it in Credential Manager yourself.

A picture is scaled before it goes. A JPEG source goes as JPEG at
quality 85. A PNG source stays PNG, so chart labels and screenshot text
survive; a PNG that would be over two megabytes at 1,600 wide is a
photograph saved as PNG, and goes as JPEG. Measured on this machine:

| Picture | Comes in as | Goes out as |
|---|---|---|
| Photograph, 4000 by 3000 JPEG | 2,310 KB | JPEG, 1600 by 1200, 382 KB |
| The same photograph saved as PNG | 12,303 KB | JPEG, 1600 by 1200, 384 KB |
| Screenshot with text, 1920 by 1080 PNG | 129 KB | PNG, 1600 by 900, 324 KB |
| Screenshot with text, 2560 by 1440 PNG | 173 KB | PNG, 1600 by 900, 314 KB |
| A bar chart, 1200 by 800 PNG | 24 KB | PNG, unchanged, 24 KB |
| The test fixture, 320 by 200 PNG | 1 KB | PNG, unchanged, 1 KB |

The wire adds about a third on top, because pictures travel as base64.

### The picture cap

A document description carries at most **twelve** pictures, and at most
twelve megabytes of them, whichever comes first. Twelve because at the
sizes above twelve pictures is under five megabytes, and even at a
megabyte each, which a dense screenshot can reach, twelve is sixteen
megabytes on the wire, under the twenty megabyte ceiling Gemini and
OpenAI publish for pictures sent inline, with room for a long document's
text. Over the cap the first twelve go, the question the model is asked
says which pictures are attached, and the answer ends with a sentence
saying which were not described. The text is capped at thirty thousand
words the same way, and the answer says so.

## Getting a key

Each company issues keys from its own site. Every key is billable, so
treat it like a card number: paste it into the AI page of Preferences
and nowhere else.

- **Claude, from Anthropic**: sign in at https://console.anthropic.com,
  add credit under Billing, then create a key under API keys. Keys begin
  with `sk-ant-`.
- **ChatGPT, from OpenAI**: sign in at https://platform.openai.com, add
  credit under Billing, then create a key under API keys. Keys begin
  with `sk-`.
- **Gemini, from Google**: sign in at https://aistudio.google.com and
  choose Get API key. A key on a project with no billing is on the free
  tier, which costs nothing and has the data policy described below. Keys
  begin with `AIza`.

If TG Drop Deck already has a key on this machine, the AI page has a
button, **Use the key I gave TG Drop Deck**, that copies it under Easy
PDF's own name after you say yes in a dialog. Nothing is sent anywhere
by that button.

## What each company says it does with what you send

Read on 9 September 2026. Policies change; the addresses are the thing
to trust, and the consent question carries the one for the provider you
chose.

- **Google, Gemini API**: https://ai.google.dev/gemini-api/terms, last
  updated 28 April 2026. On the **unpaid** tier: "Google uses the content
  you submit to the Services and any generated responses to provide,
  improve, and develop Google products and services", and "human
  reviewers may read, annotate, and process your API input and output",
  after "disconnecting this data from your Google Account, API key, and
  Cloud project". Google's own warning: "Do not submit sensitive,
  confidential, or personal information to the Unpaid Services." On the
  **paid** tier: "Google doesn't use your prompts (including associated
  system instructions, cached content, and files such as images, videos,
  or documents) or responses to improve our products", and prompts are
  logged "for a limited period of time, solely for detecting and
  preventing violations of the Prohibited Use Policy". So a free Gemini
  key is the one case here where what you send may be read by a person
  and used to train.
- **OpenAI, API**: https://developers.openai.com/api/docs/guides/your-data
  (the older address https://platform.openai.com/docs/guides/your-data
  redirects there). "Data sent to the OpenAI API is not used to train or
  improve OpenAI models (unless you explicitly opt in)". Abuse monitoring
  logs are "retained for up to 30 days, unless longer retention is
  required by law". Zero data retention exists for approved customers
  only.
- **Anthropic, API**: the commercial terms at
  https://www.anthropic.com/legal/commercial-terms, effective 17 June
  2025, say "Anthropic may not train models on Customer Content from
  Services". The retention page at
  https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-personal-data,
  dated 1 July 2026, says "we automatically delete inputs and outputs on
  our backend within 30 days of receipt or generation", except under a
  zero data retention agreement or when content is flagged for a policy
  violation, when it is kept "for up to 2 years".

In one line each: Anthropic and OpenAI keep what you send for about a
month for abuse checks and do not train on it; Google's paid tier is the
same; Google's free tier may have a person read it and uses it to
improve Google's products.

## What it costs, in rough terms

Every provider charges per token, and a picture at 1,600 pixels wide is
worth somewhere between about 800 and 2,600 tokens depending on the
company's arithmetic. At the prices the companies published in 2026, as
read by the author of this file, one picture costs a fraction of a cent
on every one of the three: about one cent on Claude Opus 5, half a cent
on Claude Sonnet 5, a quarter of a cent on GPT-4.1, and a twentieth of a
cent on Gemini Flash. A whole document with a dozen pictures and five
thousand words is about twenty cents on Claude Opus 5, a few cents on the
others, and free on a free Gemini key. The price pages are
https://www.anthropic.com/pricing, https://openai.com/api/pricing and
https://ai.google.dev/pricing; check them rather than this paragraph.

## What the app will never do with the answer

- **Write it into the document unread.** A picture's description lands
  in an editable field and only goes into the document when you choose
  Use this description. A document's description never goes into the
  document at all; it is for you to read or copy.
- **Hide where a description came from.** When you accept an AI written
  description, the picture is marked in the native file
  (`data-alt-source="ai:<provider>"`, never in the PDF). The Pictures
  dialog says "described by AI", editing the text by hand clears the
  mark, and the export report counts the descriptions no sighted person
  has checked. A blind author cannot check a description against the
  picture; a sighted reviewer later can only check what is marked.
- **Remember a yes about a document.** A document asks every time.
- **Speak, log or show a whole key.** The AI page shows the last four
  characters; the Show box reveals the key in the box only while you tick
  it.

## Which model, and why

The model is a setting with a default, because model names change
faster than this app ships. Leave the Model box empty for the default;
type a name into it, or choose Get the list to fill it from your own
account, when the provider has moved on.

The defaults are chosen for accuracy, not speed. TG Drop Deck, which
this layer comes from, picks the quick model because a presenter is
waiting to go on air; a description that will sit in a distributed file
for years wants the accurate one. Measured on this machine on
9 September 2026 with Tony's Gemini key, on `tests/fixtures/circle.png`
(a yellow ellipse on blue, 320 by 200) and on a bar chart with six
labelled bars (Jan 12, Feb 19, Mar 7, Apr 24, May 15, Jun 31, axis 0 to
35 in fives):

| Model | Circle | Chart |
|---|---|---|
| gemini-flash-lite-latest | 0.8 s. Called it "the national flag of Palau", an invention | 1.4 s. All six values right |
| gemini-flash-latest | 7.2 s. Right: a yellow ellipse centred on solid blue, its purpose in the document | 5.9 s. All six values, the axis and the trend right |
| gemini-pro-latest | 16.5 s. Right shape, dropped the colours | 25.0 s. All six values right |
| gemini-3.8-flash | 4.6 s. Right shape, dropped the colours | 5.2 s. All six values right |
| gemini-3.7-flash | 3.5 s. Right, with colours | 3.5 s. All six values right |

The lite model's Palau answer is exactly the kind of invention that must
not reach a file, so the Google default is `gemini-flash-latest`: right
on both, at a usable speed. (The dropped colours showed the first draft
of the prompt told the model not to describe colour; it now asks for the
colours of a simple graphic, and the live test afterwards came back "A
solid yellow horizontal oval sits centered on a dark blue background. It
serves as a simple sample graphic to demonstrate image rendering and text
descriptions within the test document." in 1.9 seconds, and on the next
run "A solid yellow oval sits in the centre of a solid blue background,
serving as a simple test graphic for the document." in 2.4 seconds. The
answer varies a little from run to run; the facts in it did not.) There
are no Anthropic or OpenAI keys on this machine, so
those defaults are not measured: `claude-opus-5` and `gpt-4.1` are each
company's current general model with vision as published in September
2026, and Get the list replaces them with what the account can really
see.

## The dialogs, by keyboard

**Describe this picture.** The picture is shown for anybody who can see
it and refuses focus. Then: Who to ask (a list of the three, defaulting
to the provider whose key is on this machine), Describe, Describe in
detail, a Status line, the Description field (editable, holding the
current description if there is one), Use this description, Cancel.
Focus starts on Describe. When the answer arrives, focus moves into the
Description field and the app says "Described by Gemini, from Google:"
and the text. Enter in the Description field accepts it; Escape cancels.
Cancel works while the request is running: the dialog closes at once and
the answer, when it arrives, is dropped.

**Describe this document.** Who to ask, then the Message field (read
only, focus starts in it) which holds first "Measuring what would be
sent.", then the consent question with the counts, then the answer.
Send the document is offered once the size is known. Progress is spoken
through the hints channel and shown in the Status line. When the answer
arrives, focus is in the Message field and the app says so. Copy puts
the whole answer on the clipboard. Close keeps the answer as the
dialog's result. Escape is Close.

**The consent question** is its own small dialog for a picture, and is
the Message field itself for a document. Its default button sends
nothing, so Enter from the field does not send. Tab to Send and press it
to send.

**The AI page of Preferences.** Who to ask; Their key (masked) with a
Show the key box; a line saying whether a key is kept and its last four
characters; Forget this key; Use the key I gave TG Drop Deck; Model with
Get the list; Test the key and model; a Status line. Clearing the key
box and choosing OK forgets the kept key; Forget this key does it at
once. Get the list and Test run on a thread, so Preferences never
freezes.

## The words that are asked in your name

These are the prompts, in full, as `easypdf/describe.py` sends them.
They are also listed in `docs/STRINGS.md`.

### One picture, one or two sentences

> You are writing the alternative text for one picture in a document.
> The person who will use your words is blind and cannot see the
> picture, so they cannot check what you write against it. Be accurate,
> be plain, and if something is unclear say that it is unclear rather
> than guessing.
>
> Start with the subject itself: never with "image of", "picture of",
> "photo of", "this shows" or "the picture". Read out every number and
> every word that appears in the picture, exactly as written. If it is a
> chart, a graph or a diagram, say what it means: what is compared, the
> biggest and the smallest values, and the direction of any trend. Give
> the colours of a simple graphic, a logo, a flag or anything where
> colour is the point; otherwise do not spend words on colour, style or
> decoration. Plain sentences, no markdown, no headings, no bullet
> characters, no quotation marks around the whole answer, and nothing
> before or after the description itself.
>
> Write one or two sentences saying what the picture shows and what it
> is for in the document.

### One picture, in detail

The same first two paragraphs, then:

> Write one paragraph of up to about a hundred and fifty words. First
> one sentence saying what the picture is and what it is for in the
> document, then the detail a reader would otherwise miss: every number,
> label and word in it, exactly as written; the layout, from top to
> bottom and from left to right; and for a chart, a graph, a diagram or
> a table, what it means, including what the arrows or lines connect.

### Where the picture sits

When the editor knows the heading the picture is under and the paragraph
before it, this is added to either prompt, followed by that text:

> Where the picture sits in the document, so the description fits it:

### The whole document

> You are describing a whole document to its reader, who is blind and
> cannot see it. They will hear your answer read aloud, so write plain
> spoken sentences: no markdown, no headings, no bullet characters, no
> tables, no numbered lists. Nothing you write is checked against the
> document by a sighted person, so be accurate, and say when you are
> unsure.
>
> The document's text follows at the end of this message, with its
> structure marked: each heading is given with its level, each picture
> is marked where it appears with its number and any description it
> already has, each link is given with its address, and each table row
> is given in order. The pictures themselves are attached to this
> message in the same order, numbered to match.
>
> Answer in this order, as short paragraphs.
>
> First, what the document is, in one or two sentences: its kind, its
> subject, and who it seems to be for.
>
> Second, its structure: the headings in order, each with its level,
> said as sentences. If there are no headings, say so.
>
> Third, each picture by number: what it shows, and where the document
> already gives a description, whether that description is accurate and
> complete.
>
> Fourth, anything an accessibility check would flag, saying where each
> one is: a heading level that is skipped, a first heading that is not
> level one, a link whose text says only click here or here or read more
> or shows a bare address, a picture with no description, a picture
> whose description is wrong or empty, a table with no header row, and
> text that seems to be in a different language from the rest. If
> nothing needs flagging, say so in one sentence.
>
> Do not pad, do not compliment the document, and do not say "appears to
> be" where you can say what is there.

Then one of: "The document has no pictures." / "The document's one
picture is attached." / "All N of the document's pictures are attached,
in order." / "The document has N pictures. Only these are attached, in
this order: 1, 2 and 3. The others were not sent; say that they were not
described rather than guessing at them." Then, when it applies:
"Picture 4 could not be read by the program that sent this, so it is not
attached." and "The document is long, so only its first 30,000 words are
given." Then "The document:" and the outline, one line per block, in
this shape:

> Heading level 1: Sample document
> Paragraph: A paragraph with a link to TG Studios (link to https://tgstudios.app/).
> List item: First bullet
> Quotation: Quoted text, set apart.
> Picture 1, described as: A yellow circle on a blue background
> Caption: Figure 1. A yellow circle on a blue background.
> Picture 2, marked decorative, no description.
> Table starts.
> Header row: Name, Value
> Row: Alpha, 1
> Table ends, 3 rows and 2 columns.

A picture with no description is "Picture 3, no description." A
description written by AI is followed by "(this description was written
by AI and has not been checked by a sighted person)", and one recovered
from a PDF by "(this description was recovered from a file and has not
been checked)".

### The Test button

> In at most ten words, say what shape and colour is in this picture.

or, if the tiny picture cannot be drawn: "Reply with the single word:
ready."

## When it goes wrong

Every failure is a sentence that names the provider and the thing to
change; never a number. A key the company will not accept says to check
it was pasted in full and is for that company. A model name it does not
know says to put the current one in the Model box or use Get the list.
Rate limiting or no credit says to wait or check the billing. A refused
request says the model may not be able to look at pictures or the
document may be too big. Trouble at the company's end says to try again
in a minute. No internet says to check the machine is online and that
nothing in the document has changed. A content filter that declines to
describe a picture says so, and that nothing is wrong with the key.

## For whoever maintains this

- `easypdf/ai.py` is TG Drop Deck's `vision.py` with the camera and
  screen material removed. The transport, the three single-picture
  builders, `_trouble`, `list_models`, `providers_with_keys` and
  `best_provider` keep their shape so a fix in Drop Deck can be pasted
  across. Beside each single-picture builder is a `_parts` builder that
  takes one text part plus any number of pictures of either type; when
  one of a pair changes, change both, and `tests/test_ai.py` checks the
  pairs agree on their address and headers.
- Two things in the `_parts` builders are worth carrying back to Drop
  Deck. The Anthropic reader joins the text blocks instead of taking
  block zero, because on the current Claude models thinking is on unless
  switched off and a thinking block comes first; Drop Deck's reader would
  report "answered in a shape this app did not expect" on such an
  answer. The OpenAI builder sends `max_completion_tokens`, which every
  current OpenAI model takes, where `max_tokens` is refused by the
  reasoning models a user can type into the box.
- `easypdf/describe.py` holds the prompts, the consent rules, the
  outline, the picture cap and the two public calls. `describe_image`
  and `describe_document` read the key themselves through `key_for`, so
  a dialog never handles one; a test stands in a key by replacing
  `key_for`.
- Cancel does not abort the request in flight; the daemon thread
  finishes on its own and the dialog, having moved its generation
  counter on, drops the answer. That is the whole of the mechanism, and
  it is what makes the dialogs testable without a modal loop.
- `python tests/test_ai.py` and `python tests/test_describe.py` are the
  checks. The second sends `tests/fixtures/circle.png` to Gemini once
  on the Drop Deck key if it is on the machine, and skips that check
  otherwise, saying so.
