"""Where TG Imprint keeps its own files, and where it is running from.

Settings, recent files and autosave snapshots live under the user's roaming
AppData in a TG Studios folder, the same place every TG Studios app uses, so
uninstalling the program never deletes somebody's recovery snapshot.

Secrets do not live here. See secrets.py.
"""
import os
import sys

from . import constants as C


def is_frozen():
    """Whether this is the packaged executable rather than source."""
    return bool(getattr(sys, "frozen", False))


def app_folder():
    """The folder the program runs from: the bundle when frozen, else the
    repository root."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(*parts):
    """A file shipped with the program, wherever PyInstaller put it."""
    base = getattr(sys, "_MEIPASS", None) or app_folder()
    return os.path.join(base, *parts)


def config_dir():
    """%APPDATA%\\TG Studios\\TG Imprint, created on first use.

    Roaming rather than local on purpose: settings and recent files are
    small and are the user's, and following them to another machine is a
    kindness. Autosave snapshots are the exception and go under local (see
    autosave_dir), because they can be large and are only ever wanted on
    the machine that crashed.
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, C.VENDOR, C.CONFIG_FOLDER_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def local_dir():
    base = (os.environ.get("LOCALAPPDATA")
            or os.path.join(os.path.expanduser("~"), "AppData", "Local"))
    path = os.path.join(base, C.VENDOR, C.CONFIG_FOLDER_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def settings_path():
    return os.path.join(config_dir(), "settings.json")


def recent_path():
    return os.path.join(config_dir(), "recent.json")


def autosave_dir():
    path = os.path.join(local_dir(), "autosave")
    os.makedirs(path, exist_ok=True)
    return path


def documents_dir():
    """Where Save As opens the first time: the user's Documents folder."""
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    return docs if os.path.isdir(docs) else home


# ------------------------------------------------------------ clean exit ---
#
# Crash recovery needs to know whether the last run ended on purpose. Some
# exits here are hard exits (the selftest, the update hand-over), so "the
# process is gone" cannot be the signal. A marker file is: written when the
# app starts, removed when it closes cleanly. If it is there at the next
# start, the last run did not close cleanly and any autosave snapshot is
# worth offering.

def _marker():
    return os.path.join(local_dir(), "running.marker")


#: Set by mark_started() and read by the window when it decides whether to
#: offer a recovered snapshot. None until mark_started has run.
PREVIOUS_RUN_CRASHED = None


def mark_started():
    """Call once at start. Returns True if the previous run did NOT end cleanly."""
    global PREVIOUS_RUN_CRASHED
    crashed = os.path.exists(_marker())
    try:
        with open(_marker(), "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass
    PREVIOUS_RUN_CRASHED = crashed
    return crashed


def mark_clean_exit():
    """Call on a clean close, before the process ends, however it ends."""
    try:
        os.remove(_marker())
    except OSError:
        pass


def last_run_crashed():
    """Whether the marker is present. Read-only; mark_started consumes it."""
    return os.path.exists(_marker())
