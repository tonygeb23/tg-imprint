"""Settings, recent documents and window geometry, in one JSON file.

paths.settings_path() names the file. Everything here falls open: a missing
file gives the defaults, a corrupt file gives the defaults and keeps the
broken copy beside it for anyone who wants to look, and a key that a newer
version added is filled in from DEFAULTS. Nothing here touches wx, so
tests/test_settings.py runs without a window.

The one migration: an April-style boolean "announce" (False meaning "do not
narrate") becomes the middle speech level, because that is what the person
was asking for (CONVENTIONS.md).
"""
import json
import os
import shutil
import tempfile

from . import constants as C
from . import paths

# ------------------------------------------------------------ the screen ---
# The low vision settings live here rather than in constants.py because
# constants.py belongs to the coordinator. Everything below changes what is
# on the screen and nothing else; docs/DECISIONS.md and the Display page say
# so in one sentence, and tests/test_display.py checks that no theme colour
# can reach an exported PDF.

#: Editor text size, as a percentage of the document's own font size. The
#: zoom keys step through ZOOM_STEPS; the Display page takes any whole
#: number in the range, because somebody who needs 210 should get 210.
MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM = 70, 300, 100
ZOOM_STEPS = (70, 85, 100, 115, 130, 150, 175, 200, 250, 300)

#: The page themes, on screen only.
PAGE_THEMES = ("normal", "dark", "high_contrast", "yellow_on_black")
PAGE_THEME_LABELS = (
    "Normal: black text on a white page",
    "Dark: light text on a dark page",
    "High contrast: follow the Windows colours",
    "Yellow on black",
)
DEFAULT_PAGE_THEME = "normal"

#: The caret. One pixel is invisible at 200 percent, so two is the floor.
MIN_CARET_WIDTH, MAX_CARET_WIDTH, DEFAULT_CARET_WIDTH = 2, 6, 2

#: The focus ring, on the editor and on the lists that draw their own.
MIN_FOCUS_RING, MAX_FOCUS_RING, DEFAULT_FOCUS_RING = 2, 6, 3

#: Line spacing, on screen only.
LINE_SPACINGS = ("normal", "one_and_a_half", "double")
LINE_SPACING_LABELS = ("Normal", "One and a half", "Double")
LINE_SPACING_VALUES = {"normal": 1.5, "one_and_a_half": 2.0, "double": 2.6}
DEFAULT_LINE_SPACING = "normal"

#: What the toolbar shows.
TOOLBAR_LABEL_MODES = ("icons", "icons_labels", "labels")
TOOLBAR_LABEL_LABELS = ("Icons only", "Icons with labels", "Labels only")
DEFAULT_TOOLBAR_LABELS = "icons_labels"

#: Every key the Display page owns, so the window can put them all back
#: when somebody presses Cancel.
DISPLAY_KEYS = ("editor_zoom", "page_theme", "caret_width", "focus_ring_width",
                "bold_body", "line_spacing", "toolbar_labels_mode",
                "toolbar_labels")


DEFAULTS = {
    "speech_level": C.DEFAULT_SPEECH_LEVEL,
    "recent": [],
    "window": {},                    # x, y, width, height, maximised
    "page_size": C.DEFAULT_PAGE_SIZE,
    "margin_inches": C.DEFAULT_MARGIN_INCHES,
    "font_family": C.DEFAULT_FONT_FAMILY,
    "font_points": C.DEFAULT_FONT_POINTS,
    "lang": "en-US",
    "author": "",
    "ai_provider": "",
    "ai_model": "",
    "first_run_done": False,
    "last_folder": "",
    "toolbar_labels": True,             # kept so an older file still loads
    # The low vision settings. Every one of them is the screen only: the PDF
    # is always black text on a white page at the size Document properties
    # says. tests/test_display.py proves it.
    "toolbar_labels_mode": DEFAULT_TOOLBAR_LABELS,
    "editor_zoom": DEFAULT_ZOOM,        # percent, 70 to 300
    "page_theme": DEFAULT_PAGE_THEME,
    "caret_width": DEFAULT_CARET_WIDTH,     # pixels, 2 to 6
    "focus_ring_width": DEFAULT_FOCUS_RING,  # pixels, 2 to 6
    "bold_body": False,
    "line_spacing": DEFAULT_LINE_SPACING,
}


class Settings(dict):
    """A dict with defaults, a path, and load and save that never raise."""

    def __init__(self, path=None):
        super().__init__()
        self.path = path or paths.settings_path()
        self.reset()

    def reset(self):
        self.clear()
        for key, value in DEFAULTS.items():
            self[key] = json.loads(json.dumps(value))     # a fresh copy

    # ----------------------------------------------------------- load --
    def load(self):
        """Read the file. Returns "loaded", "missing" or "corrupt"."""
        self.reset()
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return "missing"
        except (OSError, ValueError):
            self._keep_broken_copy()
            return "corrupt"
        if not isinstance(raw, dict):
            self._keep_broken_copy()
            return "corrupt"
        self._absorb(raw)
        return "loaded"

    def _absorb(self, raw):
        for key in DEFAULTS:
            if key in raw and _same_shape(raw[key], DEFAULTS[key]):
                self[key] = raw[key]
        # Migration: the older on/off narration switch.
        if "speech_level" not in raw and "announce" in raw:
            self["speech_level"] = (C.SPEECH_ALL if raw.get("announce", True)
                                    else C.SPEECH_ESSENTIAL)
        if self["speech_level"] not in C.SPEECH_LEVELS:
            self["speech_level"] = C.DEFAULT_SPEECH_LEVEL
        if self["page_size"] not in C.PAGE_SIZES:
            self["page_size"] = C.DEFAULT_PAGE_SIZE
        try:
            self["margin_inches"] = min(3.0, max(0.25, float(self["margin_inches"])))
        except (TypeError, ValueError):
            self["margin_inches"] = C.DEFAULT_MARGIN_INCHES
        try:
            self["font_points"] = min(36, max(6, int(self["font_points"])))
        except (TypeError, ValueError):
            self["font_points"] = C.DEFAULT_FONT_POINTS
        self["recent"] = [p for p in self["recent"] if isinstance(p, str)][:C.RECENT_FILES]
        self._absorb_display(raw)

    def _absorb_display(self, raw):
        """The screen settings, each clamped to its own range.

        The one migration: a file written before the Display page existed
        has the older boolean "toolbar_labels" and no mode, so the mode is
        taken from it. A file with both keeps the mode.
        """
        if "toolbar_labels_mode" not in raw and "toolbar_labels" in raw:
            self["toolbar_labels_mode"] = ("icons_labels" if raw.get("toolbar_labels")
                                           else "icons")
        if self["toolbar_labels_mode"] not in TOOLBAR_LABEL_MODES:
            self["toolbar_labels_mode"] = DEFAULT_TOOLBAR_LABELS
        self["toolbar_labels"] = self["toolbar_labels_mode"] != "icons"
        self["editor_zoom"] = _whole(self["editor_zoom"], MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM)
        self["caret_width"] = _whole(self["caret_width"], MIN_CARET_WIDTH,
                                     MAX_CARET_WIDTH, DEFAULT_CARET_WIDTH)
        self["focus_ring_width"] = _whole(self["focus_ring_width"], MIN_FOCUS_RING,
                                          MAX_FOCUS_RING, DEFAULT_FOCUS_RING)
        if self["page_theme"] not in PAGE_THEMES:
            self["page_theme"] = DEFAULT_PAGE_THEME
        if self["line_spacing"] not in LINE_SPACINGS:
            self["line_spacing"] = DEFAULT_LINE_SPACING
        self["bold_body"] = bool(self["bold_body"])

    def _keep_broken_copy(self):
        try:
            shutil.copyfile(self.path, self.path + ".broken")
        except OSError:
            pass

    # ----------------------------------------------------------- save --
    def save(self):
        """Write atomically. Returns True when the file was written."""
        folder = os.path.dirname(self.path) or "."
        try:
            os.makedirs(folder, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix="settings-", suffix=".json", dir=folder)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(dict(self), fh, indent=1, ensure_ascii=False)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    # --------------------------------------------------------- recent --
    def remember(self, path):
        """Put `path` at the top of the recent list, without duplicates."""
        path = os.path.abspath(path)
        recent = [p for p in self["recent"] if os.path.normcase(p) != os.path.normcase(path)]
        recent.insert(0, path)
        self["recent"] = recent[:C.RECENT_FILES]

    def forget(self, path):
        self["recent"] = [p for p in self["recent"]
                          if os.path.normcase(p) != os.path.normcase(path)]

    def recent_existing(self):
        """The recent documents that are still there, in order."""
        return [p for p in self["recent"] if os.path.isfile(p)]

    # ---------------------------------------------------------- pages --
    def page(self):
        """The document defaults as the dict the page and the export take."""
        return {"page_size": self["page_size"],
                "margin_inches": self["margin_inches"],
                "font_family": self["font_family"],
                "font_points": self["font_points"]}

    # -------------------------------------------------------- the screen --
    def display(self):
        """The screen settings as the dict the editor page takes.

        Nothing in here reaches an exported PDF: the export takes the body
        HTML, and every one of these is a CSS variable or an attribute on
        the page's own html element, never a style on the text.
        """
        return {"zoom": self["editor_zoom"],
                "theme": self["page_theme"],
                "caret": self["caret_width"],
                "focus": self["focus_ring_width"],
                "bold": bool(self["bold_body"]),
                "spacing": self["line_spacing"]}

    def zoom_step(self, direction):
        """The next zoom percentage up (1), down (-1) or back to 100 (0)."""
        if not direction:
            return DEFAULT_ZOOM
        now = self["editor_zoom"]
        steps = list(ZOOM_STEPS)
        if direction > 0:
            for step in steps:
                if step > now:
                    return step
            return steps[-1]
        for step in reversed(steps):
            if step < now:
                return step
        return steps[0]


def _whole(value, low, high, fallback):
    """A whole number inside its range, whatever the file held."""
    try:
        return min(high, max(low, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


def _same_shape(value, default):
    """A loaded value is taken only when it is the kind the default is."""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        return isinstance(value, list)
    if isinstance(default, dict):
        return isinstance(value, dict)
    return True
