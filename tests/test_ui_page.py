"""The editor page, driven through the asynchronous wrapper.

    python tests/test_ui_page.py

Every call goes through EditorView.call, which is RunScriptAsync with the
result event; a helper pumps the loop until the answer arrives, under a
timeout. Nothing here calls the synchronous RunScript (CLAUDE.md).

Checks: set HTML; every block style; a link; a picture with alt; the
selection state; find and replace preserving strong; a body holding an img
with an onerror that would set a marker never sets it (the Content
Security Policy); the real DOM after bold, italic, a list and centre
alignment passed to htmlclean.normalise comes back semantic (the drift
test); the handoff opens a document in the running window; a clean close
leaves no snapshot and a simulated crash leaves one that is offered.

The window is real and holds a WebView, so the process ends with os._exit.
"""
import ctypes
import os
import sys
import tempfile
import time

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-test-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-test-local-")

import wx  # noqa: E402

from tgimprint import constants as C  # noqa: E402
from tgimprint import paths  # noqa: E402
from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import main_window  # noqa: E402

CHECKS = []
DOT = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
       "DwAChwGA60e6kgAAAABJRU5ErkJggg==")


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)[:300]) if detail != "" and not condition else ""))


def pump(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        wx.Yield()
        wx.MilliSleep(5)


def wait_until(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        wx.Yield()
        wx.MilliSleep(5)
    return bool(condition())


def call(method, *args, timeout=5.0):
    """editor.<method>(*args) and wait for the answer. Never synchronous."""
    box = {}
    frame.editor.call(method, *args, callback=lambda v, e: box.update(value=v, error=e))
    if not wait_until(lambda: "value" in box, timeout):
        return None, "no answer within %.1f seconds" % timeout
    return box["value"], box["error"]


def run(expression, timeout=5.0):
    box = {}
    frame.editor.run(expression, callback=lambda v, e: box.update(value=v, error=e))
    if not wait_until(lambda: "value" in box, timeout):
        return None, "no answer within %.1f seconds" % timeout
    return box["value"], box["error"]


def body():
    value, error = call("getBody")
    return (value or "") if not error else "ERROR: " + error


def set_body(html):
    """Load through the sanitiser, then wait for the page to have it."""
    box = {}
    frame.editor.load_body(html, callback=lambda warnings: box.update(done=True))
    wait_until(lambda: box.get("done"), 5.0)
    pump(120)


def caret_end_of(selector):
    return run("(function(){ var n = document.querySelector(%r); var r = document.createRange(); "
               "r.selectNodeContents(n); r.collapse(false); var s = getSelection(); "
               "s.removeAllRanges(); s.addRange(r); return n.tagName; })()" % selector)


def caret_start_of(selector):
    return run("(function(){ var n = document.querySelector(%r); var r = document.createRange(); "
               "r.selectNodeContents(n); r.collapse(true); var s = getSelection(); "
               "s.removeAllRanges(); s.addRange(r); return n.tagName; })()" % selector)


def select_text(selector):
    return run("(function(){ var n = document.querySelector(%r); var r = document.createRange(); "
               "r.selectNodeContents(n); var s = getSelection(); s.removeAllRanges(); "
               "s.addRange(r); return s.toString(); })()" % selector)


app = wx.App(False)
# The frame exists before MainLoop starts, or the loop would end at once
# for want of a top level window. The checks run inside the loop, because
# WebView2 delivers its events only through a running loop.
app.SetExitOnFrameDelete(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
frame = main_window.MainFrame(settings=settings)
frame.Show()


def main():
    """Everything, inside the main loop so WebView2 delivers its events."""
    check("the page becomes ready", wait_until(lambda: frame.editor.ready, 15.0))
    pump(300)

    # ---------------------------------------------------------------------------
    print("\nLoading and reading back")
    set_body("<h1>Title</h1><p>Plain <b>bold</b> and <i>italic</i> words.</p>")
    html = body()
    check("the body loads and reads back", "Title" in html and "Plain" in html, html)
    check("the sanitiser turned b into strong on the way in", "<strong>" in html and "<b>" not in html, html)
    check("and i into em", "<em>" in html and "<i>" not in html, html)
    value, error = run("String(document.querySelector('meta[http-equiv]').content)")
    check("the page carries a Content Security Policy with a nonce",
          value and "script-src 'nonce-" in value and "img-src data:" in value, value)

    # ---------------------------------------------------------------------------
    print("\nThe hostile file: the marker is never set")
    # Straight into the page, past the sanitiser, so the policy alone is tested.
    box = {}
    frame.editor.load_clean_body('<p>doc</p><img src="x" onerror="window.__evil = 1">',
                                 callback=lambda v, e: box.update(done=True))
    wait_until(lambda: box.get("done"), 5.0)
    pump(800)
    value, error = run("String(window.__evil)")
    check("an onerror handler in a loaded body never runs", value == "undefined", value)
    value, error = run("(function(){ var s = document.createElement('script'); s.textContent = 'window.__evil2 = 1'; "
                       "document.body.appendChild(s); return String(window.__evil2); })()")
    check("an inline script without the nonce does not run", value == "undefined", value)

    # ---------------------------------------------------------------------------
    print("\nBlock styles")
    set_body("<p>One</p><p>Two</p><p>Three</p>")
    caret_end_of("p:nth-of-type(2)")
    for action, tag in (("heading1", "h1"), ("heading2", "h2"), ("heading3", "h3"),
                        ("heading4", "h4"), ("heading5", "h5"), ("heading6", "h6"),
                        ("normal", "p")):
        value, error = call("apply", action)
        html = body()
        check("%s makes %s" % (action, tag), ("<%s>Two</%s>" % (tag, tag)) in html, html)
    value, error = call("apply", "bullets")
    html = body()
    check("bullets makes a ul with the paragraph as an item, not nested in it",
          "<p>One</p><ul><li>Two</li></ul><p>Three</p>" == html.replace("\n", ""), html)
    value, error = call("apply", "bullets")
    html = body()
    check("bullets again takes the item out of the list", "<ul>" not in html and "<p>Two</p>" in html, html)
    value, error = call("apply", "numbers")
    html = body()
    check("numbers makes an ol, not nested in a paragraph",
          "<p>One</p><ol><li>Two</li></ol><p>Three</p>" == html.replace("\n", ""), html)
    value, error = call("apply", "heading2")
    html = body()
    check("a heading applied inside a list leaves the list first",
          "<h2>Two</h2>" in html and "<ol>" not in html, html)
    check("and leaves no style attribute behind", "style=" not in html, html)
    value, error = call("apply", "normal")
    value, error = call("apply", "quote")
    html = body()
    check("quote wraps the paragraph in a blockquote", "<blockquote>" in html and "Two" in html, html)
    value, error = call("apply", "quote")
    html = body()
    check("quote again removes it", "<blockquote>" not in html and "Two" in html, html)
    value, error = call("apply", "align_center")
    html = body()
    check("centre alignment marks the block", 'align-center' in html, html)
    state, error = call("state")
    check("the state reports the alignment", state and state.get("align") == "center", state)
    value, error = call("apply", "align_left")
    html = body()
    check("align left clears the class", "align-center" not in html, html)

    # ---------------------------------------------------------------------------
    print("\nInline styles and the state")
    set_body("<p>Some words here</p>")
    select_text("p")
    call("apply", "bold")
    call("apply", "italic")
    html = body()
    check("bold and italic wrap the selection", ("<b>" in html or "<strong>" in html)
          and ("<i>" in html or "<em>" in html), html)
    state, error = call("state")
    check("the state says bold and italic", state and state.get("bold") and state.get("italic"), state)
    call("apply", "bold")
    state, error = call("state")
    check("bold again turns it off in the state", state and not state.get("bold"), state)
    call("apply", "underline")
    call("apply", "strike")
    state, error = call("state")
    check("underline and strike show in the state",
          state and state.get("underline") and state.get("strike"), state)
    set_body("<p>make this code</p>")
    select_text("p")
    value, error = call("apply", "code")
    html = body()
    check("code wraps the selection in a code element", "<code>make this code</code>" in html, html)
    state, error = call("state")
    check("and the state says code", state and state.get("code"), state)

    # ---------------------------------------------------------------------------
    print("\nLinks and pictures")
    set_body("<p>Read the guide today</p>")
    caret_end_of("p")
    value, error = call("insertLink", "the guide", "https://tgstudios.app/guide")
    html = body()
    check("a link is inserted at the caret", '<a href="https://tgstudios.app/guide">the guide</a>' in html, html)
    caret_start_of("a")
    run("(function(){ var a = document.querySelector('a'); var r = document.createRange(); r.setStart(a.firstChild, 2); "
        "r.collapse(true); var s = getSelection(); s.removeAllRanges(); s.addRange(r); return 1; })()")
    value, error = call("linkAtCaret")
    check("linkAtCaret finds it with text and address",
          value and value.get("link") and value["link"]["href"] == "https://tgstudios.app/guide", value)
    state, error = call("state")
    check("the state carries the link", state and state.get("link"), state)
    value, error = call("insertLink", "the new guide", "https://tgstudios.app/new")
    html = body()
    check("editing replaces the whole link", html.count("<a ") == 1 and "the new guide" in html
          and "https://tgstudios.app/new" in html, html)

    set_body("<p>Before</p><p>After</p>")
    caret_end_of("p")
    spec = {"src": DOT, "alt": "A single dot", "caption": "Figure 1", "width": "half",
            "place": "centre", "altSource": ""}
    value, error = call("insertFigure", spec)
    html = body()
    check("a figure with alt and caption is inserted",
          '<figure class="width-half place-centre">' in html and 'alt="A single dot"' in html
          and "<figcaption>Figure 1</figcaption>" in html, html)
    value, error = call("pictures")
    check("pictures lists it with its description", value and value[0]["alt"] == "A single dot", value)
    value, error = call("goToPicture", 0)
    value, error = call("figureAtCaret")
    check("goToPicture puts the caret on it and figureAtCaret finds it",
          value and value.get("alt") == "A single dot", value)
    state, error = call("state")
    check("the state reports the picture", state and state.get("block") == "figure"
          and state.get("figure", {}).get("alt") == "A single dot", state)
    value, error = call("updateFigure", 0, dict(spec, alt="Two dots", width="full", place="right",
                                               altSource="ai:google"))
    html = body()
    check("updateFigure rewrites the figure", 'alt="Two dots"' in html and "width-full place-right" in html
          and 'data-alt-source="ai:google"' in html, html)
    value, error = call("apply", "undo")
    html = body()
    check("undo puts the previous figure back", 'alt="A single dot"' in html, html)
    value, error = call("removeObject", "figure", 0)
    html = body()
    check("removeObject removes it and keeps both paragraphs apart",
          "<figure" not in html and "<p>Before</p>" in html and "<p>After</p>" in html, html)
    value, error = call("apply", "undo")
    html = body()
    check("and undo brings it back", "<figure" in html, html)
    set_body("<figure><img src=\"" + DOT + "\" alt=\"First\"></figure><p>After</p>")
    value, error = call("removeObject", "figure", 0)
    html = body()
    check("a figure at the very top is removed too", "<figure" not in html and "<p>After</p>" in html, html)
    set_body("<p>Text</p><table><tbody><tr><td><br></td></tr></tbody></table><p>More</p>")
    value, error = call("removeObject", "table", 0)
    html = body()
    check("an empty table is removed the same way", "<table" not in html and "<p>More</p>" in html, html)
    spec2 = dict(spec, alt="", decorative=True)
    value, error = call("insertFigure", spec2)
    html = body()
    check("a decorative picture gets an empty alt and role presentation",
          'alt="" role="presentation"' in html, html)

    # ---------------------------------------------------------------------------
    print("\nUndo after programmatic edits (W7)")
    set_body("<p>abc</p>")
    caret_end_of("p")
    call("typeText", "TYPED")
    call("insertLink", "LINK", "https://x.example")
    html = body()
    check("the typing and the link are both there", "TYPED" in html and "LINK" in html, html)
    call("apply", "undo")
    html = body()
    check("one undo removes the link and keeps the typing", "LINK" not in html and "TYPED" in html, html)

    # ---------------------------------------------------------------------------
    print("\nTables")
    set_body("<p>Start</p>")
    caret_end_of("p")
    value, error = call("insertTable", 2, 3, True)
    html = body()
    check("a table with a header row and scope col is inserted",
          html.count('<th scope="col">') == 3 and html.count("<td>") == 3, html)
    state, error = call("state")
    check("the caret is in the first header cell", state and state.get("block") == "th", state)
    call("typeText", "H1")
    value, error = call("apply", "indent")           # Tab
    state, error = call("state")
    check("Tab moves to the next cell", value and value.get("moved") and state.get("block") == "th", (value, state))
    for _ in range(4):
        call("apply", "indent")
    value, error = call("apply", "indent")
    html = body()
    check("Tab in the last cell adds a row", value and value.get("added") and html.count("<tr>") == 3, (value, html))
    check("the header typed earlier survived the rebuild", "H1" in html, html)
    call("apply", "undo")
    html = body()
    check("undo removes the added row", html.count("<tr>") == 2, html)
    caret_start_of("td")
    value, error = call("tableAtCaret")
    check("tableAtCaret sees the table and knows it is not empty", value and value.get("empty") is False, value)

    # ---------------------------------------------------------------------------
    print("\nLists: Enter and Tab")
    set_body("<ul><li>One</li><li>Two</li></ul>")
    caret_end_of("li:nth-of-type(2)")
    value, error = call("apply", "indent")
    html = body()
    check("Tab nests the second item", html.count("<ul>") == 2, html)
    value, error = call("apply", "outdent")
    html = body()
    check("Shift+Tab unnests it", html.count("<ul>") == 1 and html.count("<li>") == 2, html)
    run("document.execCommand('insertParagraph')")
    run("document.execCommand('insertParagraph')")
    html = body()
    check("Enter twice at the end of a list leaves the list with a paragraph",
          html.count("<li>") == 2 and "<p>" in html, html)
    set_body("<h2>Heading</h2>")
    caret_end_of("h2")
    run("document.execCommand('insertParagraph')")
    call("typeText", "after")
    html = body()
    check("Enter at the end of a heading starts a paragraph", "<p>after</p>" in html and "<h2>Heading</h2>" in html, html)

    # ---------------------------------------------------------------------------
    print("\nHeadings and navigation")
    set_body("<h1>A</h1><p>x</p><h2>B</h2><p>y</p><h3>C</h3>")
    value, error = call("headings")
    check("headings lists three with levels", value and [h["level"] for h in value] == [1, 2, 3], value)
    call("caretToStart")
    value, error = call("apply", "next_heading")
    check("next heading from the very top lands on A", value and value.get("text") == "A", value)
    value, error = call("apply", "next_heading")
    check("then B", value and value.get("text") == "B", value)
    value, error = call("apply", "next_heading")
    check("then C", value and value.get("text") == "C", value)
    value, error = call("apply", "next_heading")
    check("then none", value and not value.get("found"), value)
    value, error = call("apply", "previous_heading")
    check("previous heading goes back to B", value and value.get("text") == "B", value)
    value, error = call("goToHeading", 0)
    state, error = call("state")
    check("goToHeading puts the caret in the h1", state and state.get("block") == "h1", state)

    # ---------------------------------------------------------------------------
    print("\nFind and replace")
    set_body("<h2>Cats</h2><p>The <strong>cat</strong> sat. Another cat.</p><ul><li>cat food</li></ul>")
    call("caretToStart")
    value, error = call("find", "cat", True, False)
    check("find finds the first match with its context", value and value.get("found") and "cat" in value.get("context", "").lower(), value)
    value, error = call("replaceSelection", "dog", "cat", False)
    html = body()
    check("replaceSelection swaps the selected match, keeping its capital", value and value.get("replaced") and "Dogs" in html, html)
    value, error = call("replaceAll", "cat", "dog", False)
    html = body()
    check("replaceAll counts the rest", value and value.get("count") == 3, value)
    check("and keeps the heading, the strong and the list, adapting the case",
          "<h2>Dogs</h2>" in html and "<strong>" in html and "<li>dog food</li>" in html, html)
    check("with no trace of cat left", "cat" not in html.lower(), html)
    value, error = call("apply", "undo")
    html = body()
    check("one undo puts every replacement back", html.lower().count("cat") >= 3, html)
    check("and says it was the replace all it restored", value and value.get("restored"), value)
    value, error = call("apply", "redo")
    html = body()
    check("redo applies it again", "cat" not in html.lower(), html)
    call("apply", "undo")

    # ---------------------------------------------------------------------------
    print("\nThe drift test: the real DOM through the normaliser")
    try:
        from tgimprint import htmlclean
    except ImportError:
        htmlclean = None
    set_body("<p>Alpha beta</p><p>Gamma</p>")
    select_text("p:first-of-type")
    call("apply", "bold")
    call("apply", "italic")
    caret_end_of("p:nth-of-type(2)")
    call("apply", "bullets")
    call("apply", "align_center")
    raw = body()
    if htmlclean is None:
        print("  skip htmlclean is not written yet; the drift test waits for it")
    else:
        clean, warnings = htmlclean.normalise(raw)
        check("bold comes back as strong", "<strong>" in clean and "<b>" not in clean, clean)
        check("italic comes back as em", "<em>" in clean and "<i>" not in clean, clean)
        check("the list survives", "<ul>" in clean and "<li" in clean, clean)
        check("centre alignment becomes the align-center class", "align-center" in clean, clean)
        check("no style attribute survives", "style=" not in clean, clean)

    # ---------------------------------------------------------------------------
    print("\nWord count and modified")
    set_body("<p>one two three four</p>")
    pump(700)
    check("the word count reaches the status bar", frame.status.GetStatusText(2) == "4 words",
          frame.status.GetStatusText(2))
    frame.modified = False
    call("typeText", " five")
    pump(100)
    check("typing marks the document modified", frame.modified)

    # ---------------------------------------------------------------------------
    print("\nThe handoff: a second launch's path opens here")
    from tgimprint import handoff  # noqa: E402
    doc = os.path.join(tempfile.mkdtemp(), "handed.imprint")
    with open(doc, "w", encoding="utf-8") as fh:
        fh.write("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Handed over</title>"
                 "</head><body><h1>Handed over</h1><p>From the second launch.</p></body></html>")
    frame.modified = True
    frame.receiver = handoff.Receiver(frame, lambda p: wx.CallAfter(frame.open_document, p))
    # Answer the save prompt from the test: Don't Save.
    answered = {}
    orig_prompt = main_window.dialogs.unsaved_changes
    main_window.dialogs.unsaved_changes = lambda parent, name: (answered.setdefault("asked", name), "discard")[1]
    started = time.monotonic()
    sent = handoff.send_path(int(frame.GetHandle()), doc)
    elapsed = time.monotonic() - started
    check("send_path returns True at once", sent is True and elapsed < 2.0, (sent, elapsed))
    wait_until(lambda: frame.path == doc, 8.0)
    pump(400)
    main_window.dialogs.unsaved_changes = orig_prompt
    check("the save prompt was asked and answered", answered.get("asked") is not None, answered)
    check("the document opened in the running window", frame.path == doc, frame.path)
    check("its title reached the document properties", frame.meta.get("title") == "Handed over", frame.meta)
    html = body()
    check("and its body is in the editor", "From the second launch" in html, html)
    frame.receiver.remove()

    # ---------------------------------------------------------------------------
    print("\nThe watchdog: a script after a keystroke answers")
    frame.editor.focus()
    pump(200)
    call("typeText", "k")
    pump(700)
    value, error = run("String(2 + 2)", timeout=5.0)
    check("a script issued 700 ms after input answers within five seconds", value == "4", (value, error))

    # ---------------------------------------------------------------------------
    print("\nThe update flow hands the token to the Velopack client, after the flush")
    from tgimprint import appupdate  # noqa: E402
    seen = {}
    orig_run = appupdate.run_installer
    orig_show = main_window.dialogs.show_text

    def fake_run_installer(token, before_restart=None):
        seen["token"] = token
        seen["before_restart"] = before_restart
        if before_restart is not None:
            before_restart()
        return False, "probe: the update was not started"

    appupdate.run_installer = fake_run_installer
    main_window.dialogs.show_text = lambda parent, title, text, **kw: seen.setdefault("shown", (title, text))
    set_body("<h1>Keep me</h1><p>Unsaved words</p>")
    frame.modified = True
    frame.meta["title"] = "Update flush"
    frame._download_done("9.9.9", "Downloaded 9.9.9.")
    wait_until(lambda: "token" in seen, 8.0)
    pump(300)
    appupdate.run_installer = orig_run
    main_window.dialogs.show_text = orig_show
    check("run_installer received the download token", seen.get("token") == "9.9.9", seen)
    check("with the window's flush as before_restart", seen.get("before_restart") == frame._flush_for_restart)
    check("the flush wrote the settings file", os.path.exists(settings.path), settings.path)
    snaps = frame._recoverable()
    check("and, the document being modified, an autosave snapshot of the current body",
          any("Keep me" in open(r[0], encoding="utf-8", errors="replace").read() for r in snaps), snaps)
    check("a refused start is shown in a dialog, not a message box",
          seen.get("shown") and seen["shown"][0] == "Update failed", seen.get("shown"))
    check("and the window carries on: autosave timer running, not closing",
          frame._autosave.IsRunning() and not frame._closing)
    for snapshot, _s, _w, _t in snaps:
        try:
            os.remove(snapshot)
        except OSError:
            pass
    frame.snapshot_path = None
    check("nothing in the window still names the old portable swap",
          not any(hasattr(frame, n) for n in ("_finish_portable_update", "_replace_this_copy")))
    check("About names the update channel",
          "Updates: " in main_window.S["about"] and "%s" in main_window.S["about"])
    frame.modified = False

    # ---------------------------------------------------------------------------
    print("\nSnapshots: a clean close leaves none, a crash leaves one")
    try:
        from tgimprint import docfile
    except ImportError:
        docfile = None
    frame.modified = True
    frame.meta["title"] = "Crash test"
    frame._on_autosave_tick(None)
    wait_until(lambda: frame.snapshot_path is not None, 8.0)
    check("autosave wrote a snapshot while modified", frame.snapshot_path and os.path.exists(frame.snapshot_path),
          frame.snapshot_path)
    snapshot = frame.snapshot_path
    # A simulated crash: the frame is torn down without EVT_CLOSE.
    paths.PREVIOUS_RUN_CRASHED = True
    recoverable = frame._recoverable()
    check("after a crash the snapshot is listed as recoverable",
          any(os.path.normcase(r[0]) == os.path.normcase(snapshot) for r in recoverable), recoverable)
    offered = {}
    orig_dialog = main_window.dialogs.RecoveryDialog


    class FakeRecovery:
        def __init__(self, parent, entries):
            offered["entries"] = entries
            self.result = "later"

        def ShowModal(self):
            return wx.ID_CANCEL

        def Destroy(self):
            pass


    main_window.dialogs.RecoveryDialog = FakeRecovery
    frame._offer_recovery()
    main_window.dialogs.RecoveryDialog = orig_dialog
    check("the recovery dialog is offered with the snapshot in it", offered.get("entries"), offered)
    paths.PREVIOUS_RUN_CRASHED = False
    # Now a clean close: the snapshot must go.
    frame.modified = False
    frame.Close()
    pump(500)
    check("a clean close removes the snapshot", not os.path.exists(snapshot), snapshot)

    print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
    sys.stdout.flush()
    os._exit(0 if all(CHECKS) else 1)


def guarded():
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("\n%d/%d checks passed, then the test itself raised" % (sum(CHECKS), len(CHECKS)))
        sys.stdout.flush()
        os._exit(1)


wx.CallLater(100, guarded)
wx.CallLater(240000, lambda: (print("TIMEOUT: the test did not finish in four minutes"), os._exit(2)))
app.MainLoop()
os._exit(1)
