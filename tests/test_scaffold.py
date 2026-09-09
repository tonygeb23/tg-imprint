"""The TG Studios scaffold: the frozen names, the shared modules, the key.

Everything here is something that would break silently if it drifted: a
renamed slug that stops a new build recognising an old one, a shared module
that quietly diverged from the copy that has been proven, an update key that
is not the TG Studios key. None of it raises at runtime.

    python tests/test_scaffold.py
"""

import base64
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


print("\nThe frozen block never changes")

from easypdf import constants as C   # noqa: E402

check("the instance slug is EasyPDF", C.INSTANCE_SLUG == "EasyPDF", C.INSTANCE_SLUG)
check("the feed slug is easy-pdf", C.FEED_SLUG == "easy-pdf", C.FEED_SLUG)
check("the taskbar identity is TGStudios.EasyPDF.1",
      C.APP_USER_MODEL_ID == "TGStudios.EasyPDF.1", C.APP_USER_MODEL_ID)
check("the installer is named EasyPDF-<version>-Setup.exe",
      C.INSTALLER_BASENAME == "EasyPDF", C.INSTALLER_BASENAME)
check("the zip is named Easy-PDF-<version>-windows.zip",
      C.ZIP_BASENAME == "Easy-PDF", C.ZIP_BASENAME)
check("the version has three parts",
      len(C.APP_VERSION.split(".")) == 3 and all(p.isdigit() for p in C.APP_VERSION.split(".")),
      C.APP_VERSION)

iss = open(os.path.join(HERE, "tools", "easypdf.iss"), encoding="utf-8").read()
check("the installer AppId GUID is the frozen one",
      "{{B194AFF3-AC8A-464F-9440-FB09CC0CDF62}" in iss)
check("the installer output name agrees with the constants",
      "OutputBaseFilename=EasyPDF-{#AppVersion}-Setup" in iss)
check("the installer is per user with no admin prompt",
      "PrivilegesRequired=lowest" in iss)
check("the installer closes and restarts the running app",
      "CloseApplications=yes" in iss and "RestartApplications=yes" in iss)
check("and reopens the app after a silent self-update",
      "Check: WantsRestart" in iss and "/restartapp" in iss)


print("\nThe update client")

from easypdf import appupdate   # noqa: E402

check("the feed URL is derived from the feed slug",
      appupdate.MANIFEST_URL == "https://tgstudios.app/updates/easy-pdf-app.json",
      appupdate.MANIFEST_URL)
check("the public key is baked in", "REPLACE" not in appupdate.PUBLIC_KEY_B64
      and len(appupdate.PUBLIC_KEY_B64) > 40)
try:
    bogus = base64.b64encode(bytes(64)).decode()
    verdict = appupdate._verify(b"probe", bogus)
    check("a bad signature is refused rather than raising", verdict is False)
except Exception as exc:
    check("a bad signature is refused rather than raising", False, repr(exc))
check("the staging prefix is this app's own",
      appupdate.STAGING_PREFIX == ".easypdf-update-", appupdate.STAGING_PREFIX)
check("the fallback installer name is this app's own",
      appupdate.INSTALLER_FALLBACK_NAME == "EasyPDF-Setup.exe")
check("a source build correctly reports no channel", appupdate.is_frozen() is False)
check("version tuples compare as numbers, not strings",
      appupdate.parse_version("0.10.0") > appupdate.parse_version("0.9.0"))


print("\nShared modules stay byte-identical to the proven copies")

DROP_DECK = os.path.join(os.path.dirname(HERE), "TG Drop Deck", "dropdeck")
if os.path.isdir(DROP_DECK):
    for name in ("singleinstance.py", "updatedialog.py", "speech.py"):
        mine = open(os.path.join(HERE, "easypdf", name), "rb").read()
        theirs = open(os.path.join(DROP_DECK, name), "rb").read()
        check("%s is byte-identical to Drop Deck's" % name, mine == theirs)
    theirs = open(os.path.join(DROP_DECK, "appupdate.py"), encoding="utf-8").read()
    key_line = [l for l in theirs.splitlines() if l.startswith("PUBLIC_KEY_B64")]
    check("the update key is the TG Studios key Drop Deck carries",
          key_line and key_line[0].split("=", 1)[1].strip().strip('"')
          == appupdate.PUBLIC_KEY_B64)
else:
    print("  skip Drop Deck is not beside this project; cannot compare copies")


print("\nSecrets live in Credential Manager under this app's own name")

from easypdf import secrets   # noqa: E402

check("the credential prefix names Easy PDF",
      secrets.TARGET_PREFIX.startswith("Easy PDF"), secrets.TARGET_PREFIX)
check("the AI prefix is the same store",
      secrets.VISION_PREFIX == secrets.TARGET_PREFIX)
if secrets.available():
    probe = "selftest-probe-%d" % os.getpid()
    stored = secrets.store(probe, "sk-probe-1234")
    check("a key can be stored", stored)
    check("and read back", secrets.fetch(probe) == "sk-probe-1234")
    check("and shown only by its tail", secrets.redact("sk-probe-1234") == "set, ending 1234")
    check("and forgotten", secrets.forget(probe) and secrets.fetch(probe) == "")
else:
    print("  skip credential store not available here")


print("\nPaths")

from easypdf import paths   # noqa: E402

cfg = paths.config_dir()
check("the config folder is under AppData in a TG Studios folder",
      os.path.isdir(cfg) and "TG Studios" in cfg and cfg.endswith(C.APP_NAME), cfg)
check("autosave is under local AppData, not roaming",
      "Local" in paths.autosave_dir() and os.path.isdir(paths.autosave_dir()))
check("running from source is not frozen", paths.is_frozen() is False)
check("the app folder is the repository", os.path.samefile(paths.app_folder(), HERE))


print("\nThe icon")

import wx   # noqa: E402
app = wx.App(False)
from easypdf import appicon   # noqa: E402

for size in (16, 32, 256):
    bmp = appicon.bitmap(size)
    check("the mark draws at %d pixels with alpha" % size,
          bmp.IsOk() and bmp.GetWidth() == size and bmp.HasAlpha())
ico = os.path.join(tempfile.mkdtemp(), "probe.ico")
appicon.write_ico(ico)
check("the .ico it writes is one Windows will load",
      wx.Icon(ico, wx.BITMAP_TYPE_ICO).IsOk())
check("the bundle carries every size", appicon.bundle().GetIconCount() == len(appicon.ICO_SIZES))


print("\nThe speech setting is the CONVENTIONS wording")

check("three levels", C.SPEECH_LEVELS == ("all", "essential", "none"))
check("three labels, none with a dash",
      len(C.SPEECH_LABELS) == 3 and not any(chr(8212) in s or chr(8211) in s for s in C.SPEECH_LABELS))
check("the default is everything", C.DEFAULT_SPEECH_LEVEL == C.SPEECH_ALL)


print("\nmain.py")

import importlib.util   # noqa: E402
spec = importlib.util.spec_from_file_location("easypdf_main", os.path.join(HERE, "main.py"))
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
check("a file on the command line is found", main_module.file_argument(
    ["x", "--flag", __file__]) == os.path.abspath(__file__))
check("and a flag is not mistaken for one", main_module.file_argument(["x", "--selftest"]) is None)
check("the single instance uses the frozen slug",
      "SingleInstance(C.INSTANCE_SLUG)" in open(os.path.join(HERE, "main.py"), encoding="utf-8").read())

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
