"""Registering the .epdf document type, per user, from inside the app.

Velopack installs the program and knows nothing about file types, so the
app registers its own: on the after-install and after-update hooks it
writes the keys under HKEY_CURRENT_USER\\Software\\Classes, and on the
before-uninstall hook it removes them. Per user, so no administrator
prompt, which is the same decision every TG Studios installer makes.

The command points at Velopack's stub launcher at the root of the install
folder, not at the copy inside current\\. The stub survives updates; the
current folder is replaced by every one of them.

Nothing here raises. A registry that refuses (a locked-down machine) means
double clicking a document does not open the app, which the README covers;
it must never stop an install or an uninstall.
"""
import ctypes
import os
import sys

from . import constants as C

try:
    import winreg
except ImportError:                       # pragma: no cover, not Windows
    winreg = None

CLASSES = r"Software\Classes"


def launcher_path():
    """The executable a document should open: the Velopack stub when this
    is an installed copy, otherwise the executable that is running."""
    exe = os.path.abspath(sys.executable)
    here = os.path.dirname(exe)
    if os.path.basename(here).lower() == "current":
        stub = os.path.join(os.path.dirname(here), os.path.basename(exe))
        if os.path.exists(stub):
            return stub
    return exe


def _open_command(exe):
    return '"%s" "%%1"' % exe


def register(exe=None, ext=None, progid=None, description=None):
    """Write the keys. Returns (ok, message)."""
    if winreg is None:
        return False, "Not Windows."
    exe = exe or launcher_path()
    ext = ext or C.DOC_EXTENSION
    progid = progid or C.DOC_PROGID
    description = description or C.DOC_TYPE_DESCRIPTION
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"%s\%s" % (CLASSES, ext)) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, progid)
        base = r"%s\%s" % (CLASSES, progid)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, description)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              base + r"\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, '"%s",0' % exe)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              base + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _open_command(exe))
    except OSError as exc:
        return False, "The document type could not be registered: %s" % exc
    _notify_shell()
    return True, "Registered %s for %s." % (ext, exe)


def _delete_tree(root, path):
    """Delete a key and everything under it. Silent when it is not there."""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            names = []
            index = 0
            while True:
                try:
                    names.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
    except OSError:
        return
    for name in names:
        _delete_tree(root, path + "\\" + name)
    try:
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def unregister(ext=None, progid=None):
    """Remove the keys this app wrote, and only those. Returns (ok, message).

    The extension key is removed only while it still points at our ProgId;
    if another program has taken .epdf over, its choice is left alone.
    """
    if winreg is None:
        return False, "Not Windows."
    ext = ext or C.DOC_EXTENSION
    progid = progid or C.DOC_PROGID
    try:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"%s\%s" % (CLASSES, ext)) as key:
                current, _kind = winreg.QueryValueEx(key, "")
        except OSError:
            current = None
        if current == progid:
            _delete_tree(winreg.HKEY_CURRENT_USER, r"%s\%s" % (CLASSES, ext))
        _delete_tree(winreg.HKEY_CURRENT_USER, r"%s\%s" % (CLASSES, progid))
    except OSError as exc:
        return False, "The document type could not be removed: %s" % exc
    _notify_shell()
    return True, "Removed %s." % ext


def registered(ext=None, progid=None):
    """Whether the extension points at our ProgId and the open command exists."""
    if winreg is None:
        return False
    ext = ext or C.DOC_EXTENSION
    progid = progid or C.DOC_PROGID
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"%s\%s" % (CLASSES, ext)) as key:
            current, _kind = winreg.QueryValueEx(key, "")
        if current != progid:
            return False
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"%s\%s\shell\open\command" % (CLASSES, progid)) as key:
            command, _kind = winreg.QueryValueEx(key, "")
        return bool(command)
    except OSError:
        return False


def open_command(progid=None):
    """The registered command line, or an empty string."""
    if winreg is None:
        return ""
    progid = progid or C.DOC_PROGID
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"%s\%s\shell\open\command" % (CLASSES, progid)) as key:
            command, _kind = winreg.QueryValueEx(key, "")
        return command
    except OSError:
        return ""


def _notify_shell():
    """Tell Explorer the associations changed, so icons refresh at once."""
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST,
                                             None, None)
    except Exception:
        pass
