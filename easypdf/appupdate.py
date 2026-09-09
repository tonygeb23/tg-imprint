"""Update the app itself: Velopack does the work, the TG Studios key decides.

Tony, 2026-09-09: Velopack (velopack.io) is the updater for every TG Studios
program from this one onward. The older apps keep their own. What Velopack
gives us over the hand-rolled updater in those apps is measured in
Dropbox\\TG Studios\\TG Drop Deck's notes and in the Velopack evaluation:
delta updates instead of a whole installer per point release, and no
installer window appearing while the app vanishes underneath it. The update
is applied in place and the app is restarted, which is the shape a screen
reader user can follow.

What Velopack does not give us is a signature. Its releases.win.json is not
signed: integrity is TLS plus a SHA256 written inside that same file, so
whoever rewrites the file rewrites the hash. That is exactly the trap the
TG Studios updater was designed around, and the server it protects against
has been attacked before. So the signed manifest stays, and it is the gate:

  1. tgstudios.app/updates/<feed>-app.json is ed25519 signed with the
     TG Studios update key. It names the version, the SHA256 and the size
     of the Velopack package for that version, and the release notes.
  2. Velopack is asked what it can see. Its answer is accepted only when the
     version, the SHA256 and the size match what the signed manifest vouches
     for. Anything else is refused and nothing is changed.
  3. Velopack downloads, verifies the package against that same SHA256,
     applies it and restarts the app. Nothing is downloaded or applied
     without the user saying yes, in a dialog, every time.

The public API keeps the names the TG Studios frames already use (check,
auto_check, download, run_installer, is_frozen, is_portable, Stopped) so
the update flow in the window reads the same as in the other apps. Only the
inside changed.
"""
import base64
import json
import os
import ssl
import time
import urllib.request

from . import constants as C

# Public half of the TG Studios installer-update key. Baked in; it must never
# change once shipped or every installed copy silently stops seeing updates.
# The same key as every other TG Studios app.
PUBLIC_KEY_B64 = "kJOlcZKYCyYBk/1JrmyfxFSX5Vf6JiM7oXf+0PEDZ04="

# ---------------------------------------------------------------------------
# The app-specific block.
# ---------------------------------------------------------------------------
#: The signed manifest. check_updates.py in TG Studios Release reads this
#: line and the key above out of the source TEXT, so it has to be a literal
#: and not derived; tests/test_scaffold.py asserts it agrees with FEED_SLUG.
MANIFEST_URL = "https://tgstudios.app/updates/easy-pdf-app.json"
#: The Velopack feed: the folder holding releases.win.json and the packages.
RELEASES_URL = C.RELEASES_URL
#: The manifest key that names the Velopack package. The manifest also
#: carries url, sha256 and size for the Setup.exe on the site, so the
#: release checker that reads every app's manifest keeps working unchanged.
PACKAGE_KEYS = ("package", "package_sha256", "package_size")
# ---------------------------------------------------------------------------

TIMEOUT = 30
STAMP_FILE = "last_app_check.json"
DEFAULT_INTERVAL_HOURS = 24
RELEASES_FILE = "releases.win.json"


class Stopped(Exception):
    """The user pressed Stop. Raised by a progress callback, honoured here."""


def parse_version(text):
    """"0.2.0" -> (0, 2, 0). Unreadable parts sort as 0 rather than raising.

    Comparing version tuples and not strings, because "0.10.0" is older than
    "0.9.0" as a string and newer as a version.
    """
    out = []
    for part in str(text or "0").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


# ------------------------------------------------------------ the manifest

def _fetch(url, limit=4 * 1024 * 1024):
    """A small file over HTTPS. Only the manifest and the feed index come
    through here; the packages are Velopack's to fetch."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "%s/%s" % (C.APP_NAME.replace(" ", ""), C.APP_VERSION)})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError("the file was larger than expected")
    return data


def _head(url):
    """Content-Length of a URL, or -1. Used when a release is verified."""
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": "%s/%s" % (C.APP_NAME.replace(" ", ""), C.APP_VERSION)})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return int(resp.headers.get("Content-Length") or -1)
    except Exception:
        return -1


def _verify(manifest_bytes, signature_b64):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey)
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        # Loud on purpose. Returning False here would look exactly like a
        # tampered manifest, and nobody would ever find out updates had
        # stopped working.
        raise RuntimeError(
            "The cryptography package is missing, so updates cannot be "
            "verified. Reinstall the app.")
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
    try:
        key.verify(base64.b64decode(signature_b64), manifest_bytes)
        return True
    except InvalidSignature:
        return False


def canonical(obj):
    """The exact bytes that get signed. Client and release tool must agree."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_envelope(raw):
    """Parse and verify a signed manifest. Returns (manifest_or_None, message)."""
    try:
        envelope = json.loads(raw.decode("utf-8"))
        payload = canonical(envelope["manifest"])
        signature = envelope["signature"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None, "The update server sent something unreadable."
    try:
        if not _verify(payload, signature):
            return None, ("The update was signed by the wrong key and was "
                          "rejected. Nothing was changed.")
    except RuntimeError as exc:
        return None, str(exc)
    return envelope["manifest"], ""


def fetch_manifest():
    """The signed manifest from the server. Returns (manifest_or_None, message)."""
    try:
        raw = _fetch(MANIFEST_URL, limit=1024 * 1024)
    except Exception as exc:
        return None, "Could not reach the update server. %s" % exc
    return read_envelope(raw)


def vouches(manifest, version, sha256, size=None):
    """The gate. Does the signed manifest vouch for this package?

    Returns (ok, reason). Every mismatch is named, because a refusal that
    says only "no" cannot be told from a broken updater.
    """
    if not manifest:
        return False, "there is no signed manifest"
    if str(manifest.get("version", "")).strip() != str(version or "").strip():
        return False, ("the signed manifest names version %s, not %s"
                       % (manifest.get("version"), version))
    wanted = str(manifest.get("package_sha256", "")).strip().lower()
    got = str(sha256 or "").strip().lower()
    if not wanted or wanted != got:
        return False, "the package checksum is not the one the manifest signed"
    try:
        expected = int(manifest.get("package_size") or 0)
    except (TypeError, ValueError):
        expected = 0
    if size is not None and expected and int(size) != expected:
        return False, ("the package is %d bytes and the manifest signed %d"
                       % (int(size), expected))
    return True, ""


# ------------------------------------------------------------- velopack

def is_frozen():
    import sys
    return bool(getattr(sys, "frozen", False))


_manager_cache = {}
#: Tests replace this to hand the client a stand-in manager.
_make_manager = None


def _manager():
    """The Velopack UpdateManager for this install. Raises when this copy was
    not installed by Velopack (a source run, a plain folder)."""
    if _make_manager is not None:
        return _make_manager()
    if "manager" not in _manager_cache:
        import velopack
        _manager_cache["manager"] = velopack.UpdateManager(
            velopack.HttpSource(RELEASES_URL))
    return _manager_cache["manager"]


def is_installed():
    """Whether Velopack installed this copy, so updates can be applied.

    A source run and a bare unpacked folder both answer False, and for the
    same reason: there is no installed copy for an update to replace.
    """
    try:
        _manager()
        return True
    except Exception:
        return False


def is_portable():
    """A Velopack portable copy. It updates the same way as an installed one,
    so nothing in the flow branches on this; it is here for the About box
    and the selftest."""
    try:
        return bool(_manager().get_is_portable())
    except Exception:
        return False


def installed_version():
    try:
        return str(_manager().get_current_version())
    except Exception:
        return C.APP_VERSION


def channel_state():
    """One sentence for the About box and the selftest."""
    if not is_frozen():
        return "source build, correctly disabled"
    if not is_installed():
        return "frozen but not installed by Velopack, so it cannot update itself"
    return "live, %s" % ("portable copy" if is_portable() else "installed copy")


# ------------------------------------------------------------- the flow

def check(current_version=None):
    """Is there a newer build the TG Studios key vouches for?

    Returns (available, info, message). `info` is a plain dict the window can
    read (version, notes, size, url) and carries the Velopack update object
    under "velopack" for download() and run_installer().
    """
    current = current_version or C.APP_VERSION
    manifest, message = fetch_manifest()
    if manifest is None:
        return False, None, message

    listed = manifest.get("version", "")
    info = {"version": listed, "notes": manifest.get("notes", ""),
            "url": manifest.get("url", ""), "size": manifest.get("package_size", 0),
            "manifest": manifest}
    if parse_version(listed) <= parse_version(current):
        return False, info, "You have the newest version."

    try:
        manager = _manager()
    except Exception:
        return False, info, ("Version %s is available, but this copy was not "
                             "installed by the installer, so it cannot update "
                             "itself. Get the new version from tgstudios.app."
                             % listed)
    try:
        update = manager.check_for_updates()
    except Exception as exc:
        return False, info, "Could not reach the update server. %s" % exc
    if update is None:
        return False, info, ("The update server lists version %s but the "
                             "download for it is not there yet. Try again "
                             "later." % listed)
    target = update.TargetFullRelease
    ok, why = vouches(manifest, target.Version, target.SHA256, target.Size)
    if not ok:
        return False, None, ("The update was not vouched for by the TG "
                             "Studios signature and was refused: %s. Nothing "
                             "was changed." % why)
    info.update({"version": target.Version, "size": target.Size,
                 "velopack": update,
                 "delta": bool(getattr(update, "DeltasToTarget", None))})
    return True, info, ("Version %s is available. You have %s."
                        % (target.Version, current))


_downloaded = {}


def download(info, progress=None, portable=False):
    """Fetch the update. Returns (token_or_None, message).

    Velopack fetches the packages into its own store and verifies each one
    against the SHA256 in the feed, which is the SHA256 the signed manifest
    vouched for in check(). `progress(done, total)` is called from the
    download thread with bytes, so the shared progress dialog can say how
    far along it is; raising Stopped from it stops the download.

    The token is the version string; hand it to run_installer(). `portable`
    is accepted for the shared flow's sake and makes no difference here: a
    portable Velopack copy updates in place like an installed one.
    """
    update = (info or {}).get("velopack")
    if update is None:
        return None, "Check for updates first. Nothing was changed."
    try:
        total = int(info.get("size") or update.TargetFullRelease.Size or 0)
    except Exception:
        total = 0
    state = {"stopped": False}

    def step(percent):
        if progress is None:
            return
        try:
            done = int(total * float(percent) / 100.0) if total else int(percent)
            progress(done, total)
        except Stopped:
            state["stopped"] = True
            raise
        except Exception:
            # A failing progress bar must never lose an update that is
            # otherwise arriving perfectly well.
            pass

    try:
        _manager().download_updates(update, step)
    except Stopped:
        return None, "The download was stopped. Nothing was changed."
    except Exception as exc:
        if state["stopped"]:
            return None, "The download was stopped. Nothing was changed."
        return None, "Download failed. %s" % exc
    if state["stopped"]:
        return None, "The download was stopped. Nothing was changed."
    version = str(info.get("version") or update.TargetFullRelease.Version)
    _downloaded[version] = update
    return version, "Downloaded %s." % version


def run_installer(token, before_restart=None):
    """Apply the downloaded update and restart the app.

    The name is the one the shared flow calls; there is no installer window
    any more. Velopack swaps the current folder and starts the new version,
    and this process ends as part of that. Everything that must be written
    before the process ends (settings, the autosave, the clean exit marker)
    happens here first: `before_restart` is the window's flush, and the
    marker is cleared so the next start does not offer a recovery for a
    close that was on purpose.
    """
    update = _downloaded.get(str(token))
    if update is None:
        return False, "Download the update first. Nothing was changed."
    if before_restart is not None:
        try:
            before_restart()
        except Exception:
            pass
    try:
        from . import paths
        paths.mark_clean_exit()
    except Exception:
        pass
    try:
        _manager().apply_updates_and_restart(update)
        return True, "Installing. The app will close and reopen by itself."
    except Exception as exc:
        return False, "Could not start the update. %s" % exc


apply = run_installer


# ------------------------------------------------------------ throttling

def _stamp_path(config_dir):
    return os.path.join(config_dir, STAMP_FILE)


def last_checked(config_dir):
    try:
        with open(_stamp_path(config_dir), encoding="utf-8") as fh:
            return float(json.load(fh).get("last_check", 0))
    except (OSError, ValueError, TypeError):
        return 0.0


def stamp_check(config_dir, when=None):
    payload = {"last_check": float(when if when is not None else time.time())}
    try:
        with open(_stamp_path(config_dir), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except OSError:
        pass


def should_check(config_dir, interval_hours=DEFAULT_INTERVAL_HOURS, now=None):
    now = time.time() if now is None else now
    elapsed = now - last_checked(config_dir)
    # A clock that moved backwards must not lock out checking until it
    # catches up, so a negative gap counts as due.
    return elapsed < 0 or elapsed >= interval_hours * 3600


def auto_check(config_dir, force=False, interval_hours=DEFAULT_INTERVAL_HOURS):
    """Returns (available, info, message_or_None).

    None as the message means nothing happened and the user should not be
    told anything, so a normal launch stays silent. Only an installed copy
    checks on its own; a source run never does unless forced.
    """
    if not is_installed() and not force:
        return False, None, None
    if not force and not should_check(config_dir, interval_hours):
        return False, None, None
    stamp_check(config_dir)      # stamp first, so a dead server is not retried every launch
    available, info, message = check()
    if not available:
        return False, info, (message if force else None)
    return True, info, message


# ------------------------------------------- after a restart, and first run

#: Set by main.py from Velopack's hooks before the window exists, so the
#: window can say "updated to version X" once, or show the first run hint.
RESTARTED_AFTER_UPDATE = ""
FIRST_RUN = False


def note_restarted(version=None):
    global RESTARTED_AFTER_UPDATE
    RESTARTED_AFTER_UPDATE = str(version or C.APP_VERSION)


def note_first_run(version=None):
    global FIRST_RUN
    FIRST_RUN = True


# ------------------------------------------------------- release checking

def inspect_feed(fetch=None):
    """Read the live feed the way a release check should, from any machine.

    Fetches the signed manifest and the Velopack index, checks that the
    newest full package in the index is the one the manifest vouches for,
    and that the package and the Setup on the site are really there at the
    sizes claimed. Returns (ok, lines) where lines say what was found. Used
    by tools/release_app.py verify and by the TG Studios release checker;
    it needs no Velopack install, only the network.
    """
    fetch = fetch or _fetch
    lines = []
    try:
        manifest, message = read_envelope(fetch(MANIFEST_URL, 1024 * 1024))
    except Exception as exc:
        return False, ["could not fetch the manifest: %s" % exc]
    if manifest is None:
        return False, [message]
    lines.append("manifest: version %s, signature verified" % manifest.get("version"))

    try:
        index = json.loads(fetch(RELEASES_URL + RELEASES_FILE, 1024 * 1024).decode("utf-8"))
    except Exception as exc:
        return False, lines + ["could not fetch %s: %s" % (RELEASES_FILE, exc)]
    fulls = [a for a in index.get("Assets", []) if str(a.get("Type", "")).lower() == "full"]
    if not fulls:
        return False, lines + ["the feed lists no full package"]
    newest = max(fulls, key=lambda a: parse_version(a.get("Version")))
    ok, why = vouches(manifest, newest.get("Version"), newest.get("SHA256"), newest.get("Size"))
    lines.append("feed: newest full package %s, %s"
                 % (newest.get("FileName"), "vouched" if ok else "REFUSED: " + why))
    if not ok:
        return False, lines

    package_url = RELEASES_URL + newest.get("FileName", "")
    got = _head(package_url)
    if got != int(newest.get("Size") or -2):
        return False, lines + ["the package at %s is %d bytes, the feed says %s"
                               % (package_url, got, newest.get("Size"))]
    lines.append("package: present at the size the feed claims")

    setup_url = manifest.get("url", "")
    if setup_url:
        got = _head(setup_url)
        try:
            want = int(manifest.get("size") or -2)
        except (TypeError, ValueError):
            want = -2
        if got != want:
            return False, lines + ["the installer at %s is %d bytes, the manifest says %s"
                                   % (setup_url, got, manifest.get("size"))]
        lines.append("installer: present at the size the manifest claims")
    return True, lines
