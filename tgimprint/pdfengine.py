"""The PDF engine: a Chromium browser printing headless to a tagged PDF.

Measured on this machine on 2026-09-09 (CLAUDE.md, CHALLENGE.md E1 to E3,
DECISIONS.md decision 2): msedge --headless=new --print-to-pdf writes a
genuinely tagged PDF, with H1 to H6, P, Strong, Em, Code, Link with OBJR,
L and LI with Lbl, BlockQuote, Figure with Alt, Caption, Table with TR, TH
and TD, MarkInfo, Lang, DisplayDocTitle, Tabs S and subset embedded fonts.
The Edge browser, the WebView2 runtime's own msedge.exe and Chrome all
produce byte identical output. Nothing else on this machine writes a
structure tree, so there is no fallback: with no engine, export refuses
and says so, because an accessibility product that quietly produces an
inaccessible file is worse than one that refuses.

    engines()      -> [Engine(name, path, version), ...] in search order
    find_browser() -> the first engine's path, or None
    available()    -> (ok, one plain sentence)
    render_pdf(html_text, out_path, timeout=90, engine=None) -> Engine used
    EngineError    -> a sentence somebody can act on

Nothing here touches wx, prints, or caches anything across runs; a browser
can be uninstalled between two exports.
"""

import os
import shutil
import subprocess
import tempfile
import time
from collections import namedtuple
from pathlib import Path

try:
    import winreg
except ImportError:  # not Windows; the finder then finds nothing
    winreg = None

Engine = namedtuple("Engine", "name path version")

EDGE_NAME = "Microsoft Edge"
RUNTIME_NAME = "Microsoft Edge WebView2 runtime"
CHROME_NAME = "Google Chrome"

#: The WebView2 runtime's registration, measured (DECISIONS.md, edit A3).
WEBVIEW2_CLIENT_KEY = (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
                       r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
CREATE_NO_WINDOW = 0x08000000

#: Always on. --no-pdf-header-footer: the defaults print the date, the
#: title, the temp file path and page numbers on every page (E2).
#: --generate-pdf-document-outline: headings become bookmarks (E2).
FLAGS = (
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--no-pdf-header-footer",
    "--generate-pdf-document-outline",
    "--disable-extensions",
    "--disable-sync",
    "--disable-background-networking",
    "--disable-component-update",
)

# docs/STRINGS.md, Worker A.
MSG_NO_ENGINE = ("No PDF engine was found. TG Imprint makes its PDF with Microsoft Edge, "
                 "the Microsoft Edge WebView2 runtime or Google Chrome, and none of "
                 "them is installed. Install one of them, then export again. Until "
                 "then, Save as web page keeps everything.")
MSG_TIMEOUT = ("The PDF engine did not finish in %d seconds and was stopped. Try "
               "again; if it happens every time, the document may be too large "
               "for one PDF.")
MSG_NO_OUTPUT = ("The PDF engine ran but wrote no file. %s reported: %s")
MSG_NOT_PDF = "The PDF engine wrote a file that is not a PDF. Try the export again."
MSG_CANNOT_START = "The PDF engine could not be started: %s"
MSG_BAD_FOLDER = "The PDF cannot be written to %s because that folder does not exist."


class EngineError(Exception):
    """The message is a sentence a user can act on."""


# --------------------------------------------------------------- finding ---


def _read_registry(root, key, value=""):
    if winreg is None:
        return None
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(root, key, 0, winreg.KEY_READ | view) as handle:
                data, _kind = winreg.QueryValueEx(handle, value)
                return str(data)
        except OSError:
            continue
    return None


def _app_path(exe):
    key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\%s" % exe
    for root in ((winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER) if winreg else ()):
        path = _read_registry(root, key)
        if path:
            path = path.strip().strip('"')
            if os.path.isfile(path):
                return path
    return None


def _program_folders():
    seen = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        value = os.environ.get(var)
        if value and value not in seen:
            seen.append(value)
    return seen


def _standard(exe, *tails):
    for base in _program_folders():
        for tail in tails:
            path = os.path.join(base, tail, exe)
            if os.path.isfile(path):
                return path
    return None


def _looks_like_version(name):
    parts = name.split(".")
    return len(parts) >= 3 and all(p.isdigit() for p in parts)


def _version_from_folders(path):
    """The version from the folder the exe sits in (the runtime's shape,
    EdgeCore\\152.0.4191.66\\msedge.exe) or from a version shaped folder
    beside it (the browsers' shape, Application\\152.0.4191.66\\)."""
    folder = os.path.dirname(path)
    name = os.path.basename(folder)
    if _looks_like_version(name):
        return name
    try:
        candidates = [n for n in os.listdir(folder)
                      if _looks_like_version(n) and os.path.isdir(os.path.join(folder, n))]
    except OSError:
        candidates = []
    if candidates:
        candidates.sort(key=lambda n: [int(p) for p in n.split(".")])
        return candidates[-1]
    return None


def _version_from_file(path):
    """The file version resource, through the Windows API, as a last resort."""
    try:
        import ctypes
        from ctypes import wintypes
        version = ctypes.windll.version
        size = version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        data = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(path, 0, size, data):
            return None
        pointer = ctypes.c_void_p()
        length = wintypes.UINT()
        if not version.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return None

        class FixedFileInfo(ctypes.Structure):
            _fields_ = [("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
                        ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
                        ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
                        ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
                        ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
                        ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
                        ("dwFileDateLS", wintypes.DWORD)]
        info = ctypes.cast(pointer, ctypes.POINTER(FixedFileInfo)).contents
        ms, ls = info.dwFileVersionMS, info.dwFileVersionLS
        return "%d.%d.%d.%d" % (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)
    except Exception:
        return None


def version_of(path):
    return _version_from_folders(path) or _version_from_file(path) or "unknown"


def _find_edge():
    return (_app_path("msedge.exe")
            or _standard("msedge.exe", os.path.join("Microsoft", "Edge", "Application")))


def _find_runtime():
    """The WebView2 runtime's own msedge.exe. The registry location points
    at EdgeWebView\\Application, which holds no msedge.exe on this machine,
    while EdgeCore\\<pv> does (measured); both are tried."""
    if winreg is None:
        return None
    pv = _read_registry(winreg.HKEY_LOCAL_MACHINE, WEBVIEW2_CLIENT_KEY, "pv")
    if not pv:
        pv = _read_registry(winreg.HKEY_CURRENT_USER, WEBVIEW2_CLIENT_KEY, "pv")
    if not pv:
        return None
    pv = pv.strip()
    for base in _program_folders():
        for tail in (os.path.join("Microsoft", "EdgeCore", pv),
                     os.path.join("Microsoft", "EdgeWebView", "Application", pv)):
            path = os.path.join(base, tail, "msedge.exe")
            if os.path.isfile(path):
                return path
    return None


def _find_chrome():
    return (_app_path("chrome.exe")
            or _standard("chrome.exe", os.path.join("Google", "Chrome", "Application")))


def engines():
    """Every candidate found, in the order export uses them: the Edge
    browser, the WebView2 runtime, Chrome. Never cached."""
    found = []
    for name, finder in ((EDGE_NAME, _find_edge), (RUNTIME_NAME, _find_runtime),
                         (CHROME_NAME, _find_chrome)):
        try:
            path = finder()
        except Exception:
            path = None
        if path:
            found.append(Engine(name, path, version_of(path)))
    return found


def find_browser():
    found = engines()
    return found[0].path if found else None


def available():
    """(ok, sentence). The sentence names what will be used, or what to
    install."""
    found = engines()
    if not found:
        return False, MSG_NO_ENGINE
    engine = found[0]
    return True, "%s %s will make the PDF." % (engine.name, engine.version)


# ------------------------------------------------------------- rendering ---


def _kill_tree(process):
    """Stop the browser and every child it started. subprocess's own
    timeout kills msedge.exe alone; its renderer, GPU and crashpad
    children can outlive it holding the profile folder and the CPU
    (Overseer round 2, defect 7), so on Windows the whole tree goes
    through taskkill /T."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.communicate(timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def _remove_tree(folder, tries=8):
    """The browser can hold its profile folder for a moment after it exits."""
    for attempt in range(tries):
        shutil.rmtree(folder, ignore_errors=True)
        if not os.path.exists(folder):
            return
        time.sleep(0.25 * (attempt + 1))
    shutil.rmtree(folder, ignore_errors=True)


def render_pdf(html_text, out_path, timeout=90, engine=None):
    """Print html_text to a tagged PDF at out_path with the first engine
    found (or the one given). Returns the Engine used. Raises EngineError
    with a sentence when there is no engine, when it times out, or when it
    writes nothing.

    The page is written to a temp file and opened as a file URI, so paths
    with spaces and non-ASCII characters work (measured). A fresh
    --user-data-dir per render means it works while the user's own browser
    is open (E3), and the folder is removed afterwards.
    """
    if engine is None:
        found = engines()
        if not found:
            raise EngineError(MSG_NO_ENGINE)
        engine = found[0]
    out_path = os.path.abspath(out_path)
    out_folder = os.path.dirname(out_path)
    if not os.path.isdir(out_folder):
        raise EngineError(MSG_BAD_FOLDER % out_folder)
    work = tempfile.mkdtemp(prefix="tgimprint-render-")
    try:
        html_path = os.path.join(work, "document.html")
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html_text)
        profile = os.path.join(work, "profile")
        target = os.path.join(work, "output.pdf")
        command = [engine.path] + list(FLAGS) + [
            "--user-data-dir=" + profile,
            "--print-to-pdf=" + target,
            Path(html_path).as_uri(),
        ]
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        except OSError as exc:
            raise EngineError(MSG_CANNOT_START % exc)
        try:
            _out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            raise EngineError(MSG_TIMEOUT % int(timeout))
        if not os.path.isfile(target) or os.path.getsize(target) == 0:
            tail = (err or b"").decode("utf-8", "replace").strip().splitlines()
            tail = " ".join(tail[-3:]) if tail else "nothing"
            raise EngineError(MSG_NO_OUTPUT % (engine.name, tail[:300]))
        with open(target, "rb") as handle:
            head = handle.read(5)
        if head != b"%PDF-":
            raise EngineError(MSG_NOT_PDF)
        if os.path.exists(out_path):
            os.remove(out_path)
        shutil.move(target, out_path)
        return engine
    finally:
        _remove_tree(work)
