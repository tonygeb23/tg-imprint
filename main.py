"""Easy PDF: accessible documents and tagged PDFs. A TG Studios program.

    python main.py                       open a blank document
    python main.py <file>                open that file (html, txt, md, rtf, pdf)
    python main.py --selftest --selftest-out report.txt
"""

import ctypes
import os
import sys


def _make_dpi_aware():
    """Tell Windows this app draws its own pixels. Must run before wx loads.

    Without it Windows treats the app as a 96-DPI program, renders it into a
    small bitmap and stretches that bitmap up to the display scale. Everything
    still works and every glyph in the window is blurry. A display scale above
    100 percent is itself an accessibility setting, so the people most likely
    to be running at 150 or 200 percent are exactly the people who can least
    afford softened text.

    Two things about the calls, both of which fail quietly if got wrong:
    SetProcessDpiAwarenessContext takes a pointer-sized handle, so the bare
    int -4 marshals as 32 bits and the call returns 0; wrap it in c_void_p.
    And shcore.SetProcessDpiAwareness returns S_OK, which is 0, so test it
    against 0 rather than for truth.
    """
    u32 = ctypes.windll.user32
    try:
        u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        u32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        # -4 is DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2.
        if u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:   # S_OK
            return
    except Exception:
        pass
    try:
        u32.SetProcessDPIAware()
    except Exception:
        pass


def _set_taskbar_identity():
    """Give Windows an explicit AppUserModelID.

    The taskbar groups windows by it, and it defaults to the host executable,
    so running from source showed the Python icon on the taskbar however good
    the window icon was.
    """
    try:
        from easypdf import constants
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            constants.APP_USER_MODEL_ID)
    except Exception:
        pass


if sys.platform == "win32":
    _make_dpi_aware()
    _set_taskbar_identity()

import wx  # noqa: E402

from easypdf import constants as C                    # noqa: E402
from easypdf.singleinstance import SingleInstance     # noqa: E402


def file_argument(argv):
    """The document named on the command line, if any.

    The first argument that is not a flag and names a file that exists. A
    shortcut, a drag onto the exe, or "Open with" all arrive this way.
    """
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        if os.path.isfile(arg):
            return os.path.abspath(arg)
    return None


def build_main_window(open_path=None):
    """The main window. One place, so the app and the selftest agree.

    The UI package exports `create_frame(open_path)`; until it does, the
    April prototype's MainWindow is used so the scaffold runs on day one.
    """
    from easypdf.ui import main_window
    factory = getattr(main_window, "create_frame", None)
    if factory is not None:
        return factory(open_path)
    frame = main_window.MainWindow(None, use_web_editor=True)
    from easypdf import appicon
    frame.SetIcons(appicon.bundle())
    if open_path and hasattr(frame, "_load_file"):
        frame._load_file(open_path)
    return frame


def selftest():  # noqa: C901
    """Prove the packaged build actually works. Run with --selftest.

    Every check here is something that fails SILENTLY when frozen: a missing
    cryptography reports every update unavailable forever, a missing
    accessible_output2 means the app never speaks, a missing WebView2Loader
    leaves an empty grey editor, Pillow without its native modules answers
    None to every image, and an engine that cannot be found exports nothing.
    None of those raise, so none of them show up in a build log.
    """
    import tempfile
    problems, notes = [], []

    notes.append("version: %s" % C.APP_VERSION)

    # ---- the update channel ------------------------------------------------
    try:
        from easypdf import appupdate
        if "REPLACE" in appupdate.PUBLIC_KEY_B64:
            problems.append("no app-update key baked into this build")
        else:
            import base64
            appupdate._verify(b"probe", base64.b64encode(bytes(64)).decode())
            notes.append("app updates: verification working, key %s..."
                         % appupdate.PUBLIC_KEY_B64[:12])
        notes.append("app update channel: %s"
                     % ("live" if appupdate.is_frozen() else
                        "source build, correctly disabled"))
        notes.append("update feed: %s" % appupdate.MANIFEST_URL)
    except RuntimeError as exc:
        problems.append("app update verification broken: %s" % exc)
    except Exception as exc:
        problems.append("app update check raised: %r" % exc)

    # ---- speech --------------------------------------------------------------
    try:
        from easypdf import speech
        notes.append("speech: %s" % ("available" if speech.Speaker().available
                                     else "not available (app still runs)"))
    except Exception as exc:
        problems.append("speech module raised: %r" % exc)

    # ---- the libraries that carry native code --------------------------------
    try:
        import pikepdf
        notes.append("pikepdf: %s" % pikepdf.__version__)
    except Exception as exc:
        problems.append("pikepdf is unusable, so no PDF can be checked or "
                        "patched: %r" % exc)
    try:
        import fitz
        notes.append("PyMuPDF: %s (PDF import)" % fitz.VersionBind)
    except Exception as exc:
        problems.append("PyMuPDF is unusable, so no PDF can be opened: %r" % exc)
    try:
        # Actually resize an image. Pillow imports with none of its native
        # modules present and then quietly answers nothing.
        from PIL import Image
        import io as _io
        picture = Image.new("RGB", (64, 48), (30, 60, 120))
        picture = picture.resize((32, 24))
        buffer = _io.BytesIO()
        picture.save(buffer, "JPEG", quality=80)
        if buffer.getvalue()[:2] != bytes((0xFF, 0xD8)):
            problems.append("Pillow cannot write a JPEG in this build, so no "
                            "picture could ever be sent to a describer")
        else:
            notes.append("Pillow: resize and JPEG working")
    except Exception as exc:
        problems.append("Pillow raised in this build: %r" % exc)

    # ---- the PDF engine ------------------------------------------------------
    engine_ok = False
    try:
        from easypdf import pdfengine
        ok, detail = pdfengine.available()
        engine_ok = bool(ok)
        (notes if ok else problems).append("pdf engine: %s" % detail)
    except ImportError:
        notes.append("pdf engine: module not written yet")
    except Exception as exc:
        problems.append("pdf engine raised: %r" % exc)

    if engine_ok:
        try:
            from easypdf import pdfexport
            out = os.path.join(tempfile.mkdtemp(prefix="easypdf-selftest-"),
                               "selftest.pdf")
            body = ("<h1>Selftest</h1><p>A paragraph with <strong>bold</strong> "
                    "and <a href=\"https://tgstudios.app\">a link</a>.</p>"
                    "<ul><li>One</li><li>Two</li></ul>")
            meta = {"title": "Easy PDF selftest", "author": C.VENDOR,
                    "lang": "en-US", "subject": ""}
            pdfexport.export_html(body, out, meta)
            import pikepdf as _pk
            with _pk.open(out) as pdf:
                root = pdf.Root
                tagged = "/StructTreeRoot" in root
                marked = bool(root.get("/MarkInfo", {}).get("/Marked", False))
                lang = str(root.get("/Lang", ""))
            if not (tagged and marked):
                problems.append("the exported PDF has no structure tree, so it "
                                "is not accessible; the engine ran but did not "
                                "tag the output")
            else:
                notes.append("export: tagged PDF written, lang %s" % lang)
            try:
                from easypdf import pdfcheck
                report = pdfcheck.check(out)
                ok_count, total = report.score
                if not report.passed:
                    problems.append("the accessibility checker fails the "
                                    "app's own export: %d of %d"
                                    % (ok_count, total))
                else:
                    notes.append("checker: %d of %d checks pass on the "
                                 "app's own export" % (ok_count, total))
            except ImportError:
                notes.append("checker: module not written yet")
        except ImportError:
            notes.append("export: module not written yet")
        except Exception as exc:
            problems.append("export raised: %r" % exc)

    # ---- the editor surface --------------------------------------------------
    # WebView2Loader.dll is not something PyInstaller collects on its own,
    # and without it the editor is an empty grey panel that never loads and
    # never raises. Load a real page and read the DOM back.
    app = wx.App(redirect=False)
    try:
        import wx.html2 as webview
        if not webview.WebView.IsBackendAvailable(webview.WebViewBackendEdge):
            problems.append("the WebView2 (Edge) backend is not available, so "
                            "the editor cannot load. Is the WebView2 runtime "
                            "installed, and is WebView2Loader.dll in the build?")
        else:
            probe = wx.Frame(None, title="Easy PDF selftest probe")
            view = webview.WebView.New(probe, backend=webview.WebViewBackendEdge)
            outcome = {}

            def loaded(_event):
                ok, text = view.RunScript(
                    "document.getElementById('ed').textContent")
                outcome["text"] = text if ok else None
                app.ExitMainLoop()

            def timed_out():
                if "text" not in outcome:
                    outcome["text"] = None
                    app.ExitMainLoop()

            view.Bind(webview.EVT_WEBVIEW_LOADED, loaded)
            view.SetPage('<html><body><div id="ed" contenteditable="true">'
                         'editor probe</div></body></html>', "about:blank")
            probe.Show()
            wx.CallLater(8000, timed_out)
            app.MainLoop()
            probe.Destroy()
            if outcome.get("text") == "editor probe":
                notes.append("editor: WebView2 loads and answers")
            else:
                problems.append("the editor page never loaded, or the DOM "
                                "could not be read back")
    except Exception as exc:
        problems.append("the editor probe raised: %r" % exc)

    # ---- the window ----------------------------------------------------------
    try:
        frame = build_main_window()
        notes.append("window: %s" % frame.GetTitle())
        if not frame.GetIcons().GetIconCount():
            problems.append("the window has no icon")
        else:
            notes.append("window icon sizes: %d" % frame.GetIcons().GetIconCount())
        frame.Destroy()
    except Exception as exc:
        problems.append("the main window could not be built: %r" % exc)

    report = ["  " + line for line in notes] + [""]
    report += ["PROBLEM: %s" % p for p in problems]
    report.append("SELFTEST FAILED" if problems else "SELFTEST PASSED")
    text = "\n".join(report)

    # A windowed build has nowhere to print to, so always write the report to
    # a file as well. Without this the packaged app can only be tested by
    # looking at it, which defeats the point.
    out = None
    for i, arg in enumerate(sys.argv):
        if arg == "--selftest-out" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
    if out is None:
        out = os.path.join(tempfile.gettempdir(), "easypdf-selftest.txt")
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        pass
    print(text)
    return 1 if problems else 0


class EasyPdfApp(wx.App):
    def __init__(self, instance, open_path=None, **kw):
        self.instance = instance
        self.open_path = open_path
        super().__init__(**kw)

    def OnInit(self):
        self.SetAppName(C.APP_NAME)
        self.SetVendorName(C.VENDOR)
        frame = build_main_window(self.open_path)
        # Mark this window as the one a second launch should reopen.
        self.instance.tag_window(frame)
        frame.Show()
        self.SetTopWindow(frame)
        return True


def finish_update():
    """Replace the copy that asked us to, then start it and get out of the way.

    This runs in the NEWLY unpacked copy, started by the old one with
    --finish-update, and it is the only way a portable copy can replace
    itself: Windows will not let a running executable be overwritten, so the
    new one does the writing while the old one is closing.

    No window, no wx, and no single instance mutex: the app that starts
    afterwards needs both of those and this must not be holding either.
    """
    from easypdf import appupdate

    at = sys.argv.index(appupdate.FINISH_FLAG)
    target, pid = sys.argv[at + 1], sys.argv[at + 2]
    ok, message = appupdate.finish_update(target, pid)
    if not ok:
        try:
            note = os.path.join(target, "update-did-not-finish.txt")
            with open(note, "w", encoding="utf-8") as handle:
                handle.write(message + "\n")
        except OSError:
            pass
    appupdate.relaunch(target)
    return 0 if ok else 1


def main():
    from easypdf import appupdate
    if appupdate.FINISH_FLAG in sys.argv:
        os._exit(finish_update())
    if "--selftest" in sys.argv:
        try:
            code = selftest()
        except Exception:
            import traceback
            traceback.print_exc()
            code = 1
        sys.stdout.flush()
        # Hard exit, on purpose. The selftest builds real windows but never
        # finishes a MainLoop cleanly, so wx.App is still alive when the
        # interpreter starts unwinding, and that teardown can crash after
        # passing, with the report already written. Closing the app normally
        # is clean (measured); this path has nothing left to do.
        os._exit(code)

    # One copy at a time. A second launch reopens the running copy: a launch
    # that silently does nothing is indistinguishable from the program
    # failing to start, for somebody not watching the screen.
    instance = SingleInstance(C.INSTANCE_SLUG)
    if instance.already_running:
        if instance.raise_existing():
            return 0
        wx.MessageBox(
            "%s is already running.\n\nPress Alt+Tab to switch to it."
            % C.APP_NAME, C.APP_NAME, wx.OK | wx.ICON_INFORMATION)
        return 0

    app = EasyPdfApp(instance, open_path=file_argument(sys.argv), redirect=False)
    app.MainLoop()
    instance.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
