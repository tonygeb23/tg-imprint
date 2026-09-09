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
    "toolbar_labels": True,
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
