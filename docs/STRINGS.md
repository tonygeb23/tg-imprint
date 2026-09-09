# Strings for Tony to approve

Every word the app shows or speaks that was written by Claude rather than
by Tony, so he can read them as text before anything ships. Standing rule:
nothing in his voice goes out unread.

Structural furniture is exempt: menu labels that name a function ("Save",
"Export PDF"), field labels, the app's own name and version, and the update
dialog wording, which is the shared TG Studios wording already approved for
Drop Deck and the Prompt Vault.

Each worker appends the strings they add, under their own heading. Mark a
string **approved** only when Tony has said so.

## Coordinator

- Tagline (About box, installer, site): "Write a document, get a PDF that
  screen readers can read." Status: draft.
- Release note 1.0.0 (read aloud in the update dialog): "The first release.
  Write a document with headings, lists, links and pictures, and export a
  tagged PDF that screen readers can read. Open a PDF somebody sent you and
  make it accessible. Describe pictures with Claude, ChatGPT or Gemini on
  your own key." Status: draft.
- Speech level labels (Preferences): "Everything, including confirmations
  and hints" / "Only what I cannot hear or read for myself" / "Nothing. Let
  my screen reader do all of it". Status: the CONVENTIONS.md wording with
  the dash removed; treat as approved unless Tony objects.
- Second-launch message when the running copy cannot be raised: "Easy PDF
  is already running. Press Alt+Tab to switch to it." Status: Drop Deck's
  wording, approved there.
- Credential Manager entry comment: "An AI service key kept by Easy PDF.
  Safe to delete." Status: draft.
- File type description, shown by Explorer for .epdf files: "Easy PDF
  document". Status: draft.
- Startup guard, when the WebView2 runtime is missing (a dialog with a
  read-only field): "<reason> Easy PDF needs the Microsoft Edge WebView2
  runtime, which is part of Windows 11 and a free download for Windows
  10. Install it from this address, then open Easy PDF again:
  https://developer.microsoft.com/microsoft-edge/webview2/ The address
  has been copied to the clipboard." Status: draft.
- Second launch with a document while the app is open: no words; the
  running copy opens it.

## Worker A (PDF pipeline)

(append here)

## Worker B (UI and accessibility)

(append here)

## Worker C (describer)

Everything the describer shows, speaks or asks, from `easypdf/ai.py`,
`easypdf/describe.py`, `easypdf/ui/describe_dialog.py` and
`easypdf/ui/ai_settings_page.py`. Curly braces mark a value the app fills
in: `{who}` is the provider's full name ("Claude, from Anthropic",
"ChatGPT, from OpenAI", "Gemini, from Google", Drop Deck's wording,
approved there), `{n}` a number, `{size}` "about 640 KB" or "about
2.3 MB", `{model}` a model name, `{address}` a policy address, `{text}`
the answer. Status: draft unless marked otherwise.

### Window titles

- "Describe this picture"
- "Describe this document"
- "Send the picture?" (the consent dialog for one picture)
- "Use the key from TG Drop Deck?"

### Labels and buttons that are not plain function names

- Picture dialog: "Who to ask", "Describe", "Describe in detail",
  "Status", "Description", "Use this description", "Cancel".
- Document dialog: "Who to ask", "Message", "Status", "Send the
  document", "Copy", "Close".
- Consent dialog: "Question", "Send", "Don't send" (the default), and for
  the Drop Deck key "Copy the key", "Don't copy".
- AI page: "Who to ask", "Their key", "Show the key", "Forget this key",
  "Use the key I gave TG Drop Deck", "Model, if you want a particular
  one", "Get the list", "Test the key and model", "Status".

### The consent questions (every one goes to Tony)

- A whole document: "This sends the whole of {file name} to {who}, over
  the internet, so it can be described to you: about {n} words and {n}
  pictures, {size}. The description comes back as text for you to read;
  nothing is written into your document. Before sending anything
  private, check what {Anthropic, OpenAI or Google} says it does with
  what it receives; the address of its data policy is in Easy PDF's
  guide, DESCRIBER.md, and it is {address}. Send the document?" Without
  a file name, "your whole document". The count reads "no pictures", "one
  picture", "{n} pictures", or over the cap "the first 12 of its {n}
  pictures".
- A picture from the user's own disk: "This sends one picture to {who},
  over the internet, {size}, so it can be described for you. The
  description comes back for you to read and change before anything goes
  into your document. You will not be asked again for pictures from your
  own files until Easy PDF is next opened. Before sending anything
  private, [the same policy sentence]. Send the picture?"
- A picture that came in with an imported document: "This sends one
  picture to {who}, over the internet, {size}, so it can be described for
  you. The picture came in with a document that was imported, so Easy
  PDF asks every time before any of it leaves this machine. The
  description comes back for you to read and change before anything goes
  into your document. [policy sentence]. Send the picture?"
- A batch: "This sends {n} pictures to {who}, over the internet, {size},
  so they can be described for you. A batch of pictures asks every time.
  Each description comes back for you to read and change before anything
  goes into your document. [policy sentence]. Send the pictures?"
- The Drop Deck key: "Easy PDF will read the key for {who} that TG Drop
  Deck keeps in Windows Credential Manager, and keep its own copy under
  Easy PDF's name. Nothing is sent anywhere. Copy the key?"

### The picture dialog, shown in the Status line or spoken

- "Nothing has been asked yet."
- "The picture could not be shown here." (in place of the preview)
- "Measuring the picture."
- "Asking {who}. This usually takes a few seconds."
- "Nothing was sent." (after a no)
- "Described by {who} in {n} seconds. Read it, change it if you like,
  then choose Use this description."
- Spoken on arrival: "Described by {who}: {text}"
- "No key has been set up for {who} yet. Put one in on the AI page of
  Preferences, then try again."
- "There is no picture to describe."

### The document dialog

- "Measuring what would be sent." (the field, before the question)
- "Sending the document to {who}." (the field, while sending)
- Progress, in the Status line and the hints channel: "Reading the
  document." / "Preparing {n} pictures." / "Sending the document to
  {who}: about {n} words, {n} pictures, {size}. This can take a minute."
- "Described by {who} in {n} seconds."
- Spoken on arrival: "Described by {who} in {n} seconds. The description
  is in the Message field; arrow through it, or choose Copy."
- "Nothing was described." (the Status line after a failure; the field
  holds the failure sentence)
- "The description has been copied to the clipboard."
- "The clipboard would not take the text. Select it in the Message field
  and press Control C."
- Added to the end of an answer when something stayed behind: "Only {n}
  of the document's {n} pictures were sent, so pictures 13, 14 and 15 are
  not described." / "Picture 2 could not be read and was not sent." /
  "The document has about {n} words and only the first 30,000 were sent."
- "The document is empty, so there is nothing to describe."
- "The picture could not be prepared for sending, so nothing has left
  this machine. It may be a kind of picture file Easy PDF cannot read."
- "{who} answered, but with nothing that could be used as a description."

### The AI page of Preferences

- Note at the top: "Describe pictures and whole documents with Claude,
  ChatGPT or Gemini on your own account; you pay them directly and
  nothing goes through TG Studios. Nothing leaves this machine until you
  say so in a dialog that names the provider, and no answer is written
  into your document unread."
- "A key for {who} is kept in Windows Credential Manager, set, ending
  {xxxx}. Clear the box and choose OK to forget it." / "No key for {who}
  is kept yet. Paste one in the box; it goes into Windows Credential
  Manager as Easy PDF AI key, never into a document or your settings."
  ("set, ending xxxx" is `secrets.redact`, Drop Deck's wording.)
- "Empty means {model}, chosen for accuracy. Get the list asks {who} what
  it really has. Test sends a tiny picture Easy PDF draws itself, nothing
  of yours." (the first sentence adapted from Drop Deck's "which is the
  quick one")
- "The key for {who} has been forgotten."
- "Windows Credential Manager would not remove the key for {who}. Remove
  it there yourself, listed as Easy PDF AI key."
- "Nothing was copied."
- "TG Drop Deck has no key for {who} on this machine, so there is nothing
  to copy."
- "The {who} key was found, but Windows Credential Manager would not
  keep a copy for Easy PDF. Paste the key into the box instead."
- "The {who} key from TG Drop Deck is now kept for Easy PDF as well, set,
  ending {xxxx}."
- "Put a key in first, then ask for the list." (Drop Deck's, approved)
- "Asking {who} what it has." (Drop Deck's, without the dots)
- "{n} models. Arrow through the list, or leave the box empty for
  {model}." (Drop Deck's, adapted)
- "Put a key in first, then test it."
- "Testing with {who}."
- "{who} answered in {n} seconds: {text}"

### Failures, from `ai.py`

Drop Deck's sentences, with "the show" replaced by "your document".

- "{who} would not accept that key. Check it has been pasted in full, and
  that it is a key for {who} rather than another service." (approved in
  Drop Deck)
- "{who} does not know that model name. Model names change; put the
  current one in the Model box on the AI page of Preferences, or use Get
  the list there."
- "{who} is rate limiting, or the account has run out of credit. Wait a
  moment and try again, or check the billing on your account." (approved
  in Drop Deck)
- "{who} refused the request. The most likely cause is a model name that
  cannot look at pictures; the other is a document too big for it. Try
  the default model again, or describe fewer pictures."
- "{who} said the request was too big. Describe fewer pictures at a time."
- "{who} is having trouble at their end. Nothing is wrong here, so try
  again in a minute." (approved in Drop Deck)
- "Could not reach {who}. Check this machine is online. Nothing in your
  document has changed."
- "{who} did not answer in time. Try again, or try a quicker model.
  Nothing in your document has changed."
- "The description could not be done: {the error}. Nothing in your
  document has changed."
- "{who} declined to describe this. Its content filter stopped the
  answer, which happens with some pictures of people and some documents.
  Nothing is wrong with your key."
- "No key has been set up yet. Put one in on the AI page of Preferences,
  then try again."
- "That provider is not one this app knows. Choose Claude, ChatGPT or
  Gemini on the AI page of Preferences."
- "There is nothing to ask."
- "One of the pictures could not be prepared for sending, so nothing has
  left this machine."
- "{who} answered in a shape this app did not expect, so there is nothing
  to read out." (approved in Drop Deck)
- "{who} looked at the picture and said nothing back." (approved in Drop
  Deck)
- Model list: "That is not a service this app knows." / "The list came
  back in a shape this app did not expect." / "That account has no models
  that can look at pictures." (all Drop Deck's)

### The prompts, asked in Tony's name

Not spoken. Listed in full in `docs/DESCRIBER.md` under "The words that
are asked in your name"; summarised here.

- One picture, short: the alternative text prompt ending "Write one or
  two sentences saying what the picture shows and what it is for in the
  document."
- One picture, in detail: the same, ending with the paragraph that asks
  for "up to about a hundred and fifty words".
- The context line: "Where the picture sits in the document, so the
  description fits it:" followed by the heading and paragraph the editor
  passes.
- The whole document: the four-part prompt (what it is, its structure,
  each picture, what an accessibility check would flag), then the
  attachment sentences and the outline with its labels "Heading level
  {n}:", "Paragraph:", "List item:", "Quotation:", "Caption:", "Picture
  {n}, described as:", "Picture {n}, no description.", "Picture {n},
  marked decorative, no description.", "(this description was written
  by AI and has not been checked by a sighted person)", "(this
  description was recovered from a file and has not been checked)",
  "(link to {address})", "Table starts.", "Header row:", "Row:", "Table
  ends, {n} rows and {n} columns."
- The Test button: "In at most ten words, say what shape and colour is
  in this picture." and, without a picture, "Reply with the single word:
  ready."
