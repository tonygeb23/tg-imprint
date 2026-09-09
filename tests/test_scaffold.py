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

from tgimprint import constants as C   # noqa: E402

check("the instance slug is TGImprint", C.INSTANCE_SLUG == "TGImprint", C.INSTANCE_SLUG)
check("the feed slug is tg-imprint", C.FEED_SLUG == "tg-imprint", C.FEED_SLUG)
check("the taskbar identity is TGStudios.TGImprint.1",
      C.APP_USER_MODEL_ID == "TGStudios.TGImprint.1", C.APP_USER_MODEL_ID)
check("the installer is named TGImprint-<version>-Setup.exe",
      C.INSTALLER_BASENAME == "TGImprint", C.INSTALLER_BASENAME)
check("the zip is named TG-Imprint-<version>-windows.zip",
      C.ZIP_BASENAME == "TG-Imprint", C.ZIP_BASENAME)
check("the version has three parts",
      len(C.APP_VERSION.split(".")) == 3 and all(p.isdigit() for p in C.APP_VERSION.split(".")),
      C.APP_VERSION)
check("the document ProgId is frozen", C.DOC_PROGID == "TGStudios.TGImprint.Document", C.DOC_PROGID)
check("the settings folder name is frozen, apart from the display name",
      C.CONFIG_FOLDER_NAME == "TG Imprint", C.CONFIG_FOLDER_NAME)

print("\nThe file types")
check("the native document is .imprint", C.DOC_EXTENSION == ".imprint")
check("Open takes .imprint and .docx", ".imprint" in C.IMPORT_EXTENSIONS and ".docx" in C.IMPORT_EXTENSIONS)
check("and not .rtf, which is out of 1.0.0", ".rtf" not in C.IMPORT_EXTENSIONS)
check("pictures are downscaled to 2000 pixels", C.IMAGE_MAX_EDGE == 2000 and 50 <= C.IMAGE_JPEG_QUALITY <= 95)

check("the Velopack package id is frozen", C.PACK_ID == "TGStudios.TGImprint", C.PACK_ID)
check("the Velopack feed lives under the site's downloads by the feed slug",
      C.RELEASES_URL == "https://tgstudios.app/downloads/tg-imprint/", C.RELEASES_URL)
check("Inno Setup is gone: Velopack builds the installer",
      not os.path.exists(os.path.join(HERE, "tools", "tgimprint.iss")))
build_tool = open(os.path.join(HERE, "tools", "build_release.py"), encoding="utf-8").read()
check("the build tool packs with vpk under the frozen package id",
      '"pack"' in build_tool and "C.PACK_ID" in build_tool and "--mainExe" in build_tool)
check("and collects the velopack module into the frozen build",
      '"velopack"' in build_tool)
main_src = open(os.path.join(HERE, "main.py"), encoding="utf-8").read()
check("main.py runs Velopack's hooks before wx is imported",
      main_src.index("_velopack_first()") < main_src.index("import wx"))
check("and the hooks register and remove the document type",
      "on_after_install_fast_callback(register)" in main_src
      and "on_before_uninstall_fast_callback(unregister)" in main_src)


print("\nThe update client")

from tgimprint import appupdate   # noqa: E402

check("the signed manifest URL agrees with the feed slug",
      appupdate.MANIFEST_URL == "https://tgstudios.app/updates/%s-app.json" % C.FEED_SLUG,
      appupdate.MANIFEST_URL)
update_src = open(os.path.join(HERE, "tgimprint", "appupdate.py"), encoding="utf-8").read()
check("and is a literal the TG Studios update checker can read out of the source",
      'MANIFEST_URL = "https://tgstudios.app/updates/tg-imprint-app.json"' in update_src)
check("the Velopack feed URL is the constant", appupdate.RELEASES_URL == C.RELEASES_URL)
check("the public key is baked in", "REPLACE" not in appupdate.PUBLIC_KEY_B64
      and len(appupdate.PUBLIC_KEY_B64) > 40)
try:
    bogus = base64.b64encode(bytes(64)).decode()
    verdict = appupdate._verify(b"probe", bogus)
    check("a bad signature is refused rather than raising", verdict is False)
except Exception as exc:
    check("a bad signature is refused rather than raising", False, repr(exc))
check("a source build correctly reports no channel", appupdate.is_frozen() is False
      and not appupdate.is_installed())
check("version tuples compare as numbers, not strings",
      appupdate.parse_version("0.10.0") > appupdate.parse_version("0.9.0"))
import velopack   # noqa: E402
check("the velopack SDK is importable", hasattr(velopack, "UpdateManager"))


print("\nShared modules stay byte-identical to the proven copies")

DROP_DECK = os.path.join(os.path.dirname(HERE), "TG Drop Deck", "dropdeck")
if os.path.isdir(DROP_DECK):
    for name in ("singleinstance.py", "updatedialog.py", "speech.py"):
        mine = open(os.path.join(HERE, "tgimprint", name), "rb").read()
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

from tgimprint import secrets   # noqa: E402

check("the credential prefix names TG Imprint",
      secrets.TARGET_PREFIX.startswith("TG Imprint"), secrets.TARGET_PREFIX)
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

from tgimprint import paths   # noqa: E402

cfg = paths.config_dir()
check("the config folder is under AppData in a TG Studios folder",
      os.path.isdir(cfg) and "TG Studios" in cfg and cfg.endswith(C.APP_NAME), cfg)
check("autosave is under local AppData, not roaming",
      "Local" in paths.autosave_dir() and os.path.isdir(paths.autosave_dir()))
check("running from source is not frozen", paths.is_frozen() is False)
check("the app folder is the repository", os.path.samefile(paths.app_folder(), HERE))

print("\nThe clean exit marker")
# Point the marker at a throwaway folder so this never touches the real one.
real_local = paths.local_dir
scratch = tempfile.mkdtemp()
paths.local_dir = lambda: scratch
try:
    paths.mark_started()
    paths.mark_clean_exit()
    check("a start followed by a clean exit leaves no marker",
          not paths.last_run_crashed())
    first = paths.mark_started()
    check("and the next start knows the last run was clean", first is False)
    # No clean exit this time: the next start must notice.
    second = paths.mark_started()
    check("a marker left behind makes the next start report a crash",
          second is True and paths.PREVIOUS_RUN_CRASHED is True)
    paths.mark_clean_exit()
finally:
    paths.local_dir = real_local


print("\nThe icon")

import wx   # noqa: E402
app = wx.App(False)
from tgimprint import appicon   # noqa: E402

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
spec = importlib.util.spec_from_file_location("tgimprint_main", os.path.join(HERE, "main.py"))
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
check("a file on the command line is found", main_module.file_argument(
    ["x", "--flag", __file__]) == os.path.abspath(__file__))
check("and a flag is not mistaken for one", main_module.file_argument(["x", "--selftest"]) is None)
check("the single instance uses the frozen slug",
      "SingleInstance(C.INSTANCE_SLUG)" in open(os.path.join(HERE, "main.py"), encoding="utf-8").read())

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
