"""Settings: round trip, missing file, corrupt file, the speech migration.

    python tests/test_settings.py

No window, no wx: settings.py must stay importable without either.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from easypdf import constants as C  # noqa: E402
from easypdf.settings import DEFAULTS, Settings  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" and not condition else ""))


folder = tempfile.mkdtemp(prefix="easypdf-settings-")
path = os.path.join(folder, "settings.json")

print("\nA missing file gives the defaults")
s = Settings(path)
check("load reports missing", s.load() == "missing")
check("the speech level defaults to everything", s["speech_level"] == C.DEFAULT_SPEECH_LEVEL)
check("every default key is present", all(k in s for k in DEFAULTS))
check("the page defaults come from constants",
      s.page() == {"page_size": C.DEFAULT_PAGE_SIZE, "margin_inches": C.DEFAULT_MARGIN_INCHES,
                   "font_family": C.DEFAULT_FONT_FAMILY, "font_points": C.DEFAULT_FONT_POINTS})

print("\nA round trip")
s["speech_level"] = C.SPEECH_ESSENTIAL
s["page_size"] = "A4"
s["margin_inches"] = 0.75
s["font_points"] = 12
s["lang"] = "fr-FR"
s["window"] = {"x": 10, "y": 20, "width": 900, "height": 700, "maximised": False}
s.remember(os.path.join(folder, "one.epdf"))
s.remember(os.path.join(folder, "two.epdf"))
s.remember(os.path.join(folder, "one.epdf"))      # moves to the top, no duplicate
check("save writes the file", s.save() and os.path.exists(path))
t = Settings(path)
check("load reports loaded", t.load() == "loaded")
check("the speech level came back", t["speech_level"] == C.SPEECH_ESSENTIAL)
check("the page size came back", t["page_size"] == "A4")
check("the margins came back", t["margin_inches"] == 0.75)
check("the language came back", t["lang"] == "fr-FR")
check("the window geometry came back", t["window"]["width"] == 900)
check("recent files are ordered newest first without duplicates",
      [os.path.basename(p) for p in t["recent"]] == ["one.epdf", "two.epdf"], t["recent"])
check("recent_existing drops files that are gone", t.recent_existing() == [])
t.forget(os.path.join(folder, "two.epdf"))
check("forget removes one", [os.path.basename(p) for p in t["recent"]] == ["one.epdf"])

print("\nThe recent list is capped")
u = Settings(path)
for i in range(C.RECENT_FILES + 5):
    u.remember(os.path.join(folder, "doc%d.epdf" % i))
check("at constants.RECENT_FILES entries", len(u["recent"]) == C.RECENT_FILES, len(u["recent"]))

print("\nA corrupt file gives the defaults and keeps the broken copy")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("{ this is not json")
v = Settings(path)
check("load reports corrupt", v.load() == "corrupt")
check("the defaults are in place", v["speech_level"] == C.DEFAULT_SPEECH_LEVEL)
check("the broken copy is kept beside it", os.path.exists(path + ".broken"))
with open(path, "w", encoding="utf-8") as fh:
    fh.write("[1, 2, 3]")
check("a file holding the wrong shape is corrupt too", Settings(path).load() == "corrupt")

print("\nWrong types are ignored, values are clamped")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"speech_level": 7, "recent": "not a list", "margin_inches": 99,
               "font_points": "big", "page_size": "tabloid", "window": [1, 2]}, fh)
w = Settings(path)
w.load()
check("a wrong speech level falls back to the default", w["speech_level"] == C.DEFAULT_SPEECH_LEVEL)
check("a non-list recent is ignored", w["recent"] == [])
check("margins are clamped", w["margin_inches"] == 3.0, w["margin_inches"])
check("an unreadable font size falls back", w["font_points"] == C.DEFAULT_FONT_POINTS)
check("an unknown page size falls back", w["page_size"] == C.DEFAULT_PAGE_SIZE)
check("a window that is not a dict is ignored", w["window"] == {})

print("\nThe migration of the older on/off narration switch")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"announce": False}, fh)
m = Settings(path)
m.load()
check("announce off becomes the middle level", m["speech_level"] == C.SPEECH_ESSENTIAL, m["speech_level"])
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"announce": True}, fh)
m.load()
check("announce on becomes everything", m["speech_level"] == C.SPEECH_ALL)
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"announce": False, "speech_level": "none"}, fh)
m.load()
check("an explicit level beats the old switch", m["speech_level"] == C.SPEECH_NONE)
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"lang": "de-DE"}, fh)
m.load()
check("a missing speech level takes the default", m["speech_level"] == C.DEFAULT_SPEECH_LEVEL)
check("and other keys still load", m["lang"] == "de-DE")

print("\nSaving into a folder that cannot be written falls open")
blocker = os.path.join(folder, "blocker")
with open(blocker, "w", encoding="utf-8") as fh:
    fh.write("a file where a folder would have to be")
bad = Settings(os.path.join(blocker, "settings.json"))
check("save returns False rather than raising", bad.save() is False)

print("\nThe proof that a check can fail")
check("(deliberate) a wrong expectation is reported as FAIL", Settings(path).load() == "not a real answer")
last = CHECKS.pop()
print("  the line above is the deliberate failure; it is not counted")
check("the deliberate failure was recorded as a failure", last is False)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
