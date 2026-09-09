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

(append here)
