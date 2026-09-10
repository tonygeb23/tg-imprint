"""Names and the few values every part of TG Imprint has to agree on.

Everything user-visible here is a draft until Tony has read it: see
docs/STRINGS.md. The frozen block is different: it may never change after
the first release.
"""

# The display name. One constant, so renaming the product is one line here
# and nothing else. It is NOT used to derive anything that has to stay
# stable; that is what the frozen block below is for. docs/DECISIONS.md
# decision 6 records that the name collides with an existing product and
# is Tony's to settle before the first publish.
APP_NAME = "TG Imprint"
APP_VERSION = "0.2.0"
VENDOR = "TG Studios"
#: docs/STRINGS.md: draft, needs approval.
TAGLINE = "Write a document, get a PDF that screen readers can read."

# ---------------------------------------------------------------------------
# FROZEN at first release. Do not change these even if APP_NAME changes.
#
# INSTANCE_SLUG names the single-instance mutex and the window tag, so a new
# build has to recognise an older build already running. FEED_SLUG names the
# update manifest on tgstudios.app, so every installed copy keeps finding its
# feed. APP_USER_MODEL_ID is how the Windows taskbar groups the app's windows
# and pins it. DOC_PROGID is the registry ProgId behind the .imprint file type;
# a changed ProgId orphans the old key on every machine. CONFIG_FOLDER_NAME
# is the settings folder under TG Studios; a display rename after release
# must not move everybody's settings. The installer's AppId GUID lives in
# tools/tgimprint.iss and is frozen for the same reason: a changed GUID
# installs alongside the old copy instead of over it.
# tests/test_scaffold.py asserts every one of these.
#
# Until the first publish these CAN still change, together, if Tony renames
# the product: this block, tools/tgimprint.iss (names, not the GUID),
# tests/test_scaffold.py, and the TG Stats download rules.
# ---------------------------------------------------------------------------
INSTANCE_SLUG = "TGImprint"
FEED_SLUG = "tg-imprint"
APP_USER_MODEL_ID = "TGStudios.TGImprint.1"
DOC_PROGID = "TGStudios.TGImprint.Document"
CONFIG_FOLDER_NAME = "TG Imprint"
#: The Velopack package id. It names the install folder
#: (%LocalAppData%\TGStudios.TGImprint), the Add or Remove Programs entry
#: and every update package, so a changed id is a different program that
#: installs beside the old one. Tony chose Velopack for every program from
#: this one onward (2026-09-09); the older TG Studios apps keep their own
#: updater.
PACK_ID = "TGStudios.TGImprint"
#: Where the Velopack feed lives: the folder holding releases.win.json and
#: the update packages. The signed TG Studios manifest that vouches for what
#: is in it lives beside the other apps' manifests, see appupdate.py.
RELEASES_URL = "https://tgstudios.app/downloads/%s/" % FEED_SLUG
#: TGImprint-1.0.0-Setup.exe and TG-Imprint-1.0.0-windows.zip. Hyphens rather
#: than spaces because these names become URLs, scp arguments and TG Stats
#: download rules, and a space escapes differently in each.
INSTALLER_BASENAME = "TGImprint"
ZIP_BASENAME = "TG-Imprint"

# Where the app sends people. The guide and the product page do not exist
# until the release that publishes them; the Help menu says so rather than
# opening a 404.
HOME_URL = "https://tgstudios.app/tg-imprint/"
USER_GUIDE_URL = "https://tgstudios.app/tg-imprint-guide/"
DONATE_URL = "https://tgstudios.app/donate/"
FEEDBACK_EMAIL = "info@tonygebhard.me"
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"

# ------------------------------------------------------------------ files ---
#: The native document: self-contained UTF-8 HTML inside a file type the app
#: owns, so double clicking one opens TG Imprint rather than a browser or a
#: mail filter's suspicion. It is still HTML: rename it .html and any
#: browser reads it, so nobody's writing is ever trapped in this app.
DOC_EXTENSION = ".imprint"
DOC_WILDCARD = "TG Imprint documents (*.imprint)|*.imprint"
WEB_PAGE_WILDCARD = "Web page (*.html)|*.html"
#: docs/STRINGS.md: draft. What Explorer shows as the file type.
DOC_TYPE_DESCRIPTION = "TG Imprint document"
#: What Open will take. Anything not native is imported and then saved as
#: native on the first Save.
IMPORT_EXTENSIONS = (".imprint", ".html", ".htm", ".txt", ".md", ".markdown",
                     ".docx", ".pdf")
OPEN_WILDCARD = (
    "All documents (*.imprint;*.html;*.htm;*.txt;*.md;*.docx;*.pdf)|"
    "*.imprint;*.html;*.htm;*.txt;*.md;*.markdown;*.docx;*.pdf|"
    "TG Imprint documents (*.imprint)|*.imprint|"
    "Web pages (*.html;*.htm)|*.html;*.htm|"
    "PDF files (*.pdf)|*.pdf|"
    "Word documents (*.docx)|*.docx|"
    "Markdown (*.md)|*.md;*.markdown|"
    "Plain text (*.txt)|*.txt|"
    "All files (*.*)|*.*"
)
PDF_WILDCARD = "PDF files (*.pdf)|*.pdf"
#: How many recent documents the File menu remembers.
RECENT_FILES = 8
#: Seconds between autosave snapshots of an unsaved document.
AUTOSAVE_SECONDS = 60
#: Pictures are downscaled when they come in. A phone photo is 4000 pixels
#: wide and a page is 8.5 inches; 2000 pixels across the text width is
#: still 300 dots per inch on paper, and five phone photos measured at full
#: size made a 5 MB PDF and a 7 MB document (CHALLENGE.md E8).
IMAGE_MAX_EDGE = 2000
IMAGE_JPEG_QUALITY = 85

# ----------------------------------------------------------------- speech ---
#: One setting, three levels, worded as CONVENTIONS.md says. Three channels:
#:   announce()          what you cannot otherwise know: a failure, a refusal,
#:                       a value you asked for. Silent only at "none".
#:   announce_help()     a confirmation of something you just did, or a hint
#:                       you have read before. Silent below "all".
#:   announce_answer()   a direct answer to a question you asked with a key
#:                       whose only job is to answer it. Always spoken.
#: All of them write the status bar at every level.
SPEECH_ALL, SPEECH_ESSENTIAL, SPEECH_NONE = "all", "essential", "none"
SPEECH_LEVELS = (SPEECH_ALL, SPEECH_ESSENTIAL, SPEECH_NONE)
SPEECH_LABELS = (
    "Everything, including confirmations and hints",
    "Only what I cannot hear or read for myself",
    "Nothing. Let my screen reader do all of it",
)
DEFAULT_SPEECH_LEVEL = SPEECH_ALL

# ------------------------------------------------------------------- page ---
#: The page the PDF is laid out on. Letter with one inch margins, the North
#: American default; A4 is a setting for everyone else.
PAGE_SIZES = ("letter", "A4", "legal")
DEFAULT_PAGE_SIZE = "letter"
DEFAULT_MARGIN_INCHES = 1.0
DEFAULT_FONT_FAMILY = "Arial, Helvetica, sans-serif"
DEFAULT_FONT_POINTS = 11

# ------------------------------------------------------------------- AI ---
#: The providers, in the order Tony named them, and the labels the settings
#: page uses. The real work is in ai.py, copied from TG Drop Deck's vision.py.
AI_PROVIDERS = ("anthropic", "openai", "google")
