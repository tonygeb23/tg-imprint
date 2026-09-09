"""The .epdf document type is registered by the app, per user, and removed
by the app, and nobody else's registration is touched.

Velopack installs the program and knows nothing about file types, so the
app writes its own keys on the install and update hooks and removes them
on the uninstall hook. This test uses a probe extension and a probe ProgId
so the real .epdf registration on this machine is never touched.

    python tests/test_filetype.py
"""

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import winreg   # noqa: E402

from easypdf import filetype   # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


EXT = ".epdfprobe%d" % os.getpid()
PROGID = "TGStudios.EasyPDF.Probe%d" % os.getpid()
OTHER = "Somebody.Else.Probe%d" % os.getpid()
EXE = r"C:\Probe Folder\Easy PDF.exe"


def value(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, "")[0]
    except OSError:
        return None


print("\nRegistering")
check("nothing registered before we start", not filetype.registered(EXT, PROGID))
ok, message = filetype.register(EXE, EXT, PROGID, "Probe document")
check("register reports success", ok, message)
check("the extension points at the ProgId",
      value(r"Software\Classes\%s" % EXT) == PROGID)
check("the ProgId carries the description",
      value(r"Software\Classes\%s" % PROGID) == "Probe document")
check("the icon is the executable",
      value(r"Software\Classes\%s\DefaultIcon" % PROGID) == '"%s",0' % EXE)
check("the open command quotes the executable and passes the file",
      filetype.open_command(PROGID) == '"%s" "%%1"' % EXE, filetype.open_command(PROGID))
check("registered() agrees", filetype.registered(EXT, PROGID))

print("\nRegistering again is harmless, and moves with the program")
ok, _ = filetype.register(r"C:\Elsewhere\Easy PDF.exe", EXT, PROGID, "Probe document")
check("a second registration succeeds", ok)
check("and the command follows the new path",
      '"C:\\Elsewhere\\Easy PDF.exe"' in filetype.open_command(PROGID))

print("\nRemoving")
ok, message = filetype.unregister(EXT, PROGID)
check("unregister reports success", ok, message)
check("the extension key is gone", value(r"Software\Classes\%s" % EXT) is None)
check("the ProgId tree is gone",
      value(r"Software\Classes\%s\shell\open\command" % PROGID) is None)
check("registered() agrees", not filetype.registered(EXT, PROGID))
ok, _ = filetype.unregister(EXT, PROGID)
check("removing what is not there is still a success", ok)

print("\nAnother program's claim on the extension is left alone")
filetype.register(EXE, EXT, PROGID, "Probe document")
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\%s" % EXT) as key:
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, OTHER)
check("the other program now owns the extension", not filetype.registered(EXT, PROGID))
filetype.unregister(EXT, PROGID)
check("our ProgId is removed", value(r"Software\Classes\%s" % PROGID) is None)
check("but the extension still points at the other program",
      value(r"Software\Classes\%s" % EXT) == OTHER)
filetype._delete_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\%s" % EXT)
check("(cleaned up)", value(r"Software\Classes\%s" % EXT) is None)

print("\nThe launcher path")
path = filetype.launcher_path()
check("from source it is the running interpreter",
      os.path.normcase(path) == os.path.normcase(os.path.abspath(sys.executable)), path)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
