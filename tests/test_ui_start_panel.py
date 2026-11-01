"""The 0.3.0 window: the start screen, the Accessibility panel, passwords.

    python tests/test_ui_start_panel.py

Everything runs in the real window inside the main loop, because WebView2
delivers its events only through a running loop. File dialogs are not opened:
the parts behind them are called directly, and dialogs.ask_password and
dialogs.TextDialog are replaced so nothing waits for a person.

What is proved:

- the start screen shows when nothing is open, every button has a real
  accessible name, a description and a handler, and they fire; recovery, a
  file on the command line and a second launch all land in the editor;
- commands that need a document are greyed and refused on the start screen;
- the panel lists doccheck's issues in order, says Fix or Review in words,
  refreshes after an edit without moving focus or speaking, and keeps the
  selection; Enter jumps to the right heading, picture, link and table and
  opens Document properties for a title;
- Ctrl+F6, dispatched inside the page, reaches Python;
- the page is read with checkBody, no RunScript, and with no picture data;
- a protected PDF asks for its password, retries on a wrong one, and Cancel
  leaves everything alone;
- Analyse, Repair and Export as do what their menu items say.

The window holds a WebView, so the process ends with os._exit.
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

import fitz  # noqa: E402
import wx  # noqa: E402

from tgimprint import constants as C  # noqa: E402
from tgimprint import doccheck, docfile  # noqa: E402
from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import dialogs, keymap, main_window  # noqa: E402
from tgimprint.ui import access_panel, start_panel  # noqa: E402

CHECKS = []
DOT = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
       "DwAChwGA60e6kgAAAABJRU5ErkJggg==")
ISSUES_BODY = ('<h1>One</h1><p>Text.</p><h3>Skipped</h3><p>A <a href="https://example.com">'
               'here</a> and <a href="https://example.com/b">the walking map</a>.</p>'
               '<figure class="width-half place-centre"><img src="%s" alt="" '
               'data-needs-alt="1"></figure>'
               '<table><tbody><tr><td>a</td><td>b</td></tr></tbody></table>' % DOT)


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)[:300]) if detail != "" and not condition else ""), flush=True)


def pump(ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        wx.Yield()
        wx.MilliSleep(5)


def wait_until(condition, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        wx.Yield()
        wx.MilliSleep(5)
    return bool(condition())


def call(method, *args, timeout=5.0):
    box = {}
    frame.editor.call(method, *args, callback=lambda v, e: box.update(value=v, error=e))
    if not wait_until(lambda: "value" in box, timeout):
        return None
    return box["value"]


def run(expression):
    box = {}
    frame.editor.run(expression, callback=lambda v, e: box.update(value=v, error=e))
    wait_until(lambda: "value" in box)
    return box.get("value")


def load(html):
    box = {}
    frame.show_editor()
    frame.editor.load_body(html, callback=lambda _w: box.update(done=True))
    wait_until(lambda: box.get("done"))
    frame._panel_dirty(0)
    pump(200)


def wait_for_issues(condition, timeout=6.0):
    return wait_until(lambda: condition(frame.panel.issues), timeout)


def spoken_guard():
    """Every word the window tries to say, for the silent refresh check."""
    said = []
    frame.speaker.say = lambda text, *a, **k: said.append(text)
    return said


def make_pdf(path, password=""):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "A protected page of plain text.", fontsize=14)
    if password:
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=password, user_pw=password)
    else:
        doc.save(path)
    doc.close()


def names_in_tree():
    """(control type, name) of everything UI Automation can see in the frame."""
    import comtypes.client as cc
    cc.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as U
    auto = cc.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}", interface=U.IUIAutomation)
    walker = auto.ControlViewWalker
    found = []

    def walk(element, depth):
        child = walker.GetFirstChildElement(element)
        while child:
            try:
                if child.CurrentClassName.startswith("Chrome"):
                    child = walker.GetNextSiblingElement(child)
                    continue
                found.append((child.CurrentLocalizedControlType, child.CurrentName or ""))
            except Exception:
                pass
            if depth < 7:
                walk(child, depth + 1)
            child = walker.GetNextSiblingElement(child)

    walk(auto.ElementFromHandle(int(frame.GetHandle())), 0)
    return found


app = wx.App(False)
app.SetExitOnFrameDelete(False)
settings = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
settings["first_run_done"] = True
folder = tempfile.mkdtemp(prefix="tgimprint-test-docs-")
remembered = os.path.join(folder, "Letter.imprint")
docfile.save(remembered, "<h1>Letter</h1><p>Dear reader.</p>", {"title": "Letter", "lang": "en-US"})
settings.remember(remembered)
frame = main_window.MainFrame(settings=settings, start_screen=True)
frame.SetSize(frame.FromDIP(wx.Size(1180, 760)))
frame.Show()


def start_screen():
    print("\nThe start screen")
    check("the frame comes up on the start screen", frame.start_showing())
    check("the editor is hidden and the start panel is not",
          frame.start.IsShown() and not frame.splitter.IsShown())
    check("the toolbar is hidden", not frame.toolbar.IsShown())
    check("the title is the program's name alone", frame.GetTitle() == C.APP_NAME, frame.GetTitle())
    check("the page still comes up behind it, so a document can land at once",
          wait_until(lambda: frame.editor.ready, 15.0))
    wanted = [a for a, _l, _n in start_panel.WRITE + start_panel.PDFS]
    check("six buttons", list(frame.start.buttons) == wanted, list(frame.start.buttons))
    for action, label, note in start_panel.WRITE + start_panel.PDFS:
        button = frame.start.buttons[action]
        accessible = getattr(button, "_tgimprint_accessible", None)
        check("%s is a real button named for what it does" % label,
              type(button) is wx.Button and button.GetLabel() == label
              and accessible is not None and accessible.GetName(0)[1] == label)
        check("%s says what it is for to a screen reader as well" % label,
              accessible is not None and accessible.GetDescription(0)[1] == note)
    check("the mark refuses focus", not frame.start.mark.AcceptsFocus()
          and not frame.start.mark.AcceptsFocusFromKeyboard())
    frame._refocus()
    pump(100)
    check("focus starts on New document",
          wx.Window.FindFocus() is frame.start.buttons["new"], wx.Window.FindFocus())
    order = [c for c in frame.start.GetChildren() if c.AcceptsFocusFromKeyboard()]
    check("Tab goes New, Open, the recent list, then the PDF jobs",
          order == [frame.start.buttons["new"], frame.start.buttons["open"], frame.start.recent]
          + [frame.start.buttons[a] for a, _l, _n in start_panel.PDFS], order)
    check("the recent list shows what was remembered",
          frame.start.recent.GetItemCount() == 1
          and frame.start.recent.GetItemText(0) == "Letter.imprint")
    check("and is named", frame.start.recent._tgimprint_accessible.GetName(0)[1]
          == start_panel.HEADINGS["recent"])

    fired = []
    saved = {}
    for action in wanted:
        saved[action] = getattr(frame, "on_" + action)
        setattr(frame, "on_" + action, lambda _e=None, a=action: fired.append(a))
    for action in wanted:
        button = frame.start.buttons[action]
        event = wx.CommandEvent(wx.wxEVT_BUTTON, button.GetId())
        event.SetEventObject(button)
        button.GetEventHandler().ProcessEvent(event)
    check("every button fires its action, in order", fired == wanted, fired)
    for action, handler in saved.items():
        setattr(frame, "on_" + action, handler)

    print("\nWith nothing open")
    menus = frame._menu_items
    check("Save is greyed", not menus["save"][0].IsEnabled())
    check("Bold is greyed", not menus["bold"][0].IsEnabled())
    check("Export is greyed", not menus["export_word"][0].IsEnabled())
    check("New, Open, Analyse and Repair are not",
          all(menus[a][0].IsEnabled() for a in ("new", "open", "check_pdf", "repair_pdf")))
    said = spoken_guard()
    frame.perform("save")
    check("a key that needs a document is refused in words",
          said and said[-1] == main_window.S["nothing_open"], said)
    check("and no document appeared", frame.start_showing())

    print("\nChoosing New")
    frame.perform("new")
    pump(200)
    check("New shows the editor", not frame.start_showing() and frame.splitter.IsShown())
    check("and the toolbar", frame.toolbar.IsShown())
    check("Save is back", menus["save"][0].IsEnabled())
    check("the title names the document", "Untitled" in frame.GetTitle(), frame.GetTitle())

    print("\nClosing the document")
    frame.modified = False
    frame.on_close_document()
    pump(150)
    check("Ctrl+W goes back to the start screen", frame.start_showing())
    check("the status fields have nothing to report",
          all(frame.status.GetStatusText(i) == "" or i == 0 for i in range(4)))

    print("\nA recent document, and a second launch")
    frame.start.recent.Select(0)
    frame.start._open_selected()
    check("a recent document opens in the editor",
          wait_until(lambda: not frame.start_showing() and frame.path == remembered))
    frame.modified = False
    frame.on_close_document()
    pump(100)
    frame.open_document(remembered)
    check("a document handed over by a second launch lands in the editor",
          wait_until(lambda: not frame.start_showing() and frame.path == remembered))

    print("\nRecovery")
    frame.modified = False
    frame.on_close_document()
    pump(100)
    frame._recovered("snap.imprint", "", "Lost", "<p>Back again.</p>", {"title": "Lost"}, [])
    pump(200)
    check("recovered work lands in the editor, modified",
          not frame.start_showing() and frame.modified)
    frame.snapshot_path = None
    frame.modified = False


def panel():
    print("\nThe Accessibility panel")
    check("it is on by default", frame.panel_visible())
    wide = frame.splitter.GetClientSize().width - frame.splitter.GetSashPosition()
    check("at a sensible width", frame.FromDIP(250) <= wide <= frame.FromDIP(360), wide)
    frame.meta["title"] = "A document"
    load(ISSUES_BODY)
    check("the issues arrive", wait_for_issues(bool))
    expected = doccheck.check(call("checkBody"), frame.meta)
    fixes = [i for i in expected if i.severity == "fix"]
    reviews = [i for i in expected if i.severity != "fix"]
    check("every issue doccheck found is listed", len(frame.panel.issues) == len(expected),
          frame.panel.issues)
    check("Fix comes first", [i.severity for i in frame.panel.issues]
          == ["fix"] * len(fixes) + ["review"] * len(reviews))
    check("the summary line counts them",
          frame.panel.summary.GetLabel() == "%d to fix, %d to review" % (len(fixes), len(reviews)),
          frame.panel.summary.GetLabel())
    rows = [frame.panel.list.GetItemText(i) for i in range(frame.panel.list.GetItemCount())]
    check("every row starts with the word", all(r.startswith(("Fix: ", "Review: ")) for r in rows),
          rows)
    accessible = frame.panel.list._tgimprint_accessible
    check("the list has a real accessible name", accessible.GetName(0)[1] == "Accessibility issues")
    check("and the count is its description, not its name",
          accessible.GetDescription(0)[1] == frame.panel.summary_text()
          and "to fix" in accessible.GetDescription(0)[1])
    check("the Go button is a real button with its label",
          frame.panel.go.GetLabel() == access_panel.S["go"])

    print("\nIt reads the document without the pictures")
    light = call("checkBody")
    check("checkBody carries the attributes doccheck wants", "data-needs-alt" in light, light[:200])
    check("and none of the picture data", DOT not in light)
    check("getBody is untouched", DOT in (call("getBody") or ""))

    print("\nA refresh moves nothing and says nothing")
    frame.editor.focus()
    pump(150)
    frame.panel.list.Select(2)
    frame.panel.list.Focus(2)
    pump(50)
    kept = frame.panel.selected_issue()
    said = spoken_guard()
    frame.panel.list.SetFocus()
    pump(100)
    # Not insertHTML: that focuses the page, which nobody can do while they
    # are in the list. What arrives here is the page changing on its own.
    run("document.getElementById('editor').insertAdjacentHTML('beforeend', "
        "'<p>Another <a href=' + JSON.stringify('https://example.com/c') + '>click here</a>.</p>')")
    frame.mark_modified()
    check("typing brings a new issue in", wait_for_issues(
        lambda issues: any(i.message.startswith('The link "click here"') for i in issues)))
    check("focus stayed in the list", wx.Window.FindFocus() is frame.panel.list,
          wx.Window.FindFocus())
    check("the same issue is still selected",
          frame.panel.selected_issue().message == kept.message,
          frame.panel.selected_issue())
    check("nothing was spoken", not said, said)
    timer_before = frame._check_timer.IsRunning()
    check("the refresh runs from a one shot timer", not timer_before)

    print("\nEnter jumps")
    for kind, ordinal, tag in (("heading", 2, "H3"), ("link", 2, "A"), ("table", 1, "TD"),
                               ("picture", 1, "FIGURE")):
        issue = doccheck.Issue("x", "fix", "m", kind, ordinal)
        frame._go_to_issue(issue)
        pump(200)
        where = run("(function(){ var n = getSelection().anchorNode; if (n.nodeType !== 1) "
                    "{ n = n.parentElement; } return n.tagName; })()")
        check("to %s %d" % (kind, ordinal), where == tag, where)
    frame._go_to_issue(doccheck.Issue("x", "fix", "m", "link", 99))
    pump(200)
    check("to something that has gone: it says so",
          frame.status.GetStatusText(0) == main_window.S["panel_gone"],
          frame.status.GetStatusText(0))
    opened = []
    real = frame._edit_properties
    frame._edit_properties = lambda focus="title": opened.append(focus)
    frame._go_to_issue(doccheck.Issue("title", "fix", "m"))
    frame._go_to_issue(doccheck.Issue("lang", "fix", "m"))
    frame._edit_properties = real
    check("a title or language issue opens Document properties there",
          opened == ["title", "lang"], opened)
    frame._go_to_issue(doccheck.Issue("no_headings", "review", "m"))
    pump(50)
    check("a whole document issue says there is nowhere to go",
          frame.status.GetStatusText(0) == main_window.S["panel_whole_document"])
    jumped = []
    real_go = frame.panel.on_go
    frame.panel.on_go = jumped.append
    frame.panel.list.Select(0)
    event = wx.ListEvent(wx.wxEVT_LIST_ITEM_ACTIVATED, frame.panel.list.GetId())
    event.SetEventObject(frame.panel.list)
    frame.panel.list.GetEventHandler().ProcessEvent(event)
    frame.panel.on_go = real_go
    check("Enter on a row is what fires it", len(jumped) == 1, jumped)

    print("\nThe keys")
    posted = []
    real_next = frame.on_next_pane
    frame.on_next_pane = lambda _e=None: posted.append("next")
    run("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'F6', ctrlKey: true, "
        "bubbles: true, cancelable: true}))")
    check("Ctrl+F6 pressed inside the page reaches Python", wait_until(lambda: posted))
    frame.on_next_pane = real_next
    frame.panel.focus_list()
    pump(100)
    check("the list takes focus", wx.Window.FindFocus() is frame.panel.list)
    frame.on_next_pane()
    pump(100)
    check("the next pane after the panel is the toolbar",
          wx.Window.FindFocus() is frame.toolbar.style, wx.Window.FindFocus())
    frame.on_previous_pane()
    pump(100)
    check("the one before is the panel again", wx.Window.FindFocus() is frame.panel.list)
    run("window.editor.caretToStart()")
    frame.perform("next_heading")
    pump(200)
    check("F6 in the panel does not move the caret, it goes to the document",
          not frame._focus_is_in(frame.panel), wx.Window.FindFocus())

    print("\nShowing and hiding")
    frame.on_toggle_panel()
    check("the key hides it", not frame.panel_visible())
    check("and the View item says so", not frame._menu_items["toggle_panel"][0].IsChecked())
    check("and it is remembered", frame.settings["window"]["panel"] is False)
    frame.on_toggle_panel()
    check("and shows it again", frame.panel_visible())
    check("the tick follows", frame._menu_items["toggle_panel"][0].IsChecked())
    size = frame.GetSize()
    frame.SetSize(frame.FromDIP(wx.Size(700, 600)))
    pump(450)
    check("a narrow window hides it", not frame.panel_visible())
    check("without turning the setting off", frame._panel_wanted)
    frame.on_toggle_panel()
    check("the key can still ask for it in a narrow window", frame.panel_visible())
    pump(300)
    check("and it stays", frame.panel_visible())
    frame.on_toggle_panel()
    frame._panel_wanted = True
    frame.SetSize(size)
    pump(450)
    check("a wide window brings it back", frame.panel_visible())
    event = wx.SplitterEvent(wx.wxEVT_SPLITTER_SASH_POS_CHANGED, frame.splitter)
    event.SetSashPosition(frame.splitter.GetClientSize().width - frame.FromDIP(340))
    frame._on_sash_moved(event)
    frame._save_geometry()
    check("the sash position is remembered, in pixels that survive a scale change",
          abs(frame.settings["window"]["panel_width"] - 340) <= 1,
          frame.settings["window"]["panel_width"])
    check("and survives a settings file round trip", frame.settings.save()
          and _reload()["window"].get("panel_width") == frame.settings["window"]["panel_width"])


def _reload():
    again = Settings(settings.path)
    again.load()
    return again


def passwords():
    print("\nA password prompt")
    locked = os.path.join(folder, "Locked.pdf")
    make_pdf(locked, password="right")
    asked = []
    answers = ["wrong", "right"]

    def fake(_parent, name, reason):
        asked.append((name, reason))
        return answers.pop(0) if answers else None

    real = dialogs.ask_password
    dialogs.ask_password = fake
    shown = []
    real_text = dialogs.show_text
    dialogs.show_text = lambda *a, **k: shown.append(a)
    frame.modified = False
    frame.path = None
    frame._load_path(locked)
    check("opening asks, then tells you it was wrong, then opens",
          wait_until(lambda: frame.source_path == locked, 20.0), asked)
    check("the first question says it needs a password",
          asked and "protected by a password" in asked[0][1], asked)
    check("the second says that one did not open it",
          len(asked) > 1 and "did not open" in asked[1][1], asked)
    check("the document is there", "protected page" in (call("getBody") or ""))

    print("\nCancel leaves everything alone")
    load("<p>Keep this.</p>")
    frame.modified = False
    source_before = frame.source_path
    asked.clear()
    answers.clear()
    frame._load_path(locked)
    check("it asks", wait_until(lambda: asked, 20.0))
    pump(400)
    check("the document is untouched", "Keep this." in (call("getBody") or ""))
    check("and nothing about it changed", frame.source_path == source_before)
    check("nothing was shown as a failure", not shown, shown)

    print("\nThe prompt itself")
    named = {}

    def press_cancel():
        dialog = wx.GetActiveWindow()
        for child in dialog.GetChildren() if dialog else ():
            if isinstance(child, wx.TextCtrl):
                accessible = getattr(child, "_tgimprint_accessible", None)
                named["name"] = accessible.GetName(0)[1] if accessible else ""
                named["password"] = bool(child.GetWindowStyle() & wx.TE_PASSWORD)
        if dialog:
            dialog.EndModal(wx.ID_CANCEL)

    dialogs.ask_password = real
    wx.CallLater(400, press_cancel)
    answer = dialogs.ask_password(frame, "Locked.pdf", "This PDF is protected by a password.")
    check("Cancel returns nothing", answer is None, answer)
    check("the field has a real accessible name", named.get("name") == dialogs.PASSWORD_FIELD, named)
    check("and hides what is typed", named.get("password") is True, named)
    dialogs.ask_password = fake

    print("\nAnalyse asks too")
    reports = []

    class Report:
        def __init__(self, parent, title, text, **kw):
            self.result = "close"
            reports.append((title, text, kw))

        def ShowModal(self):
            return 0

        def Destroy(self):
            pass

    real_dialog = dialogs.TextDialog
    dialogs.TextDialog = Report
    asked.clear()
    answers[:] = ["right"]
    frame.analyse_path(locked)
    check("the report arrives after the password", wait_until(lambda: reports, 20.0), asked)
    check("it was asked for", len(asked) == 1, asked)
    title, text, options = reports[0]
    check("the report is the analysis, in the read only dialog",
          "Locked.pdf" in title and "Locked.pdf" in text, text[:120])
    buttons = [b[1] for b in options["buttons"]]
    check("with Open it here, Repair it and Close", buttons == ["open", "repair", "close"], buttons)
    check("and Enter means Close, so reading never opens anything", options["default"] == 2)

    print("\nRepair asks too")
    reports.clear()
    asked.clear()
    answers[:] = ["wrong", "right"]
    target = os.path.join(folder, "Locked repaired.pdf")
    frame.repair_path(locked, target=target)
    check("the copy is written after the password retry",
          wait_until(lambda: reports, 20.0) and os.path.exists(target), asked)
    check("the wrong password was refused first", len(asked) == 2, asked)
    check("the changes and the remaining report are shown",
          "What changed:" in reports[0][1] and "Locked repaired.pdf" in reports[0][1],
          reports[0][1][:200])
    reports.clear()
    plain = os.path.join(folder, "Plain.pdf")
    make_pdf(plain)
    frame._ask_repair_target = lambda _source: None
    frame.repair_path(plain)
    pump(200)
    check("no target chosen, nothing done", not reports)
    del frame._ask_repair_target
    dialogs.TextDialog = real_dialog
    dialogs.ask_password = real
    dialogs.show_text = real_text


def exports():
    print("\nHigh contrast: the lists go back to the system")
    from tgimprint.ui import theme
    real_high = theme.high_contrast
    theme.high_contrast = lambda: True
    frame.apply_display()
    system = wx.SystemSettings.GetColour
    check("the panel's list is the system's list colour, never black by accident",
          frame.panel.list.GetBackgroundColour() == system(wx.SYS_COLOUR_LISTBOX)
          and frame.panel.list.GetTextColour() == system(wx.SYS_COLOUR_LISTBOXTEXT))
    check("the recent list too",
          frame.start.recent.GetBackgroundColour() == system(wx.SYS_COLOUR_LISTBOX))
    check("the status bar's skin steps aside for the native bar", not frame.status.skin.IsShown())
    check("the toolbar uses real labels again", not frame.toolbar.drawn)
    theme.high_contrast = real_high
    frame.apply_display()
    check("and it all comes back", frame.status.skin.IsShown())

    print("\nWhat UI Automation sees")
    frame.show_start()
    frame._refocus()
    pump(300)
    start = names_in_tree()
    for _action, label, _note in start_panel.WRITE + start_panel.PDFS:
        check("the start screen shows a button named %s" % label, ("button", label) in start, start)
    frame.show_editor()
    frame.panel.focus_list()
    pump(300)
    tree = names_in_tree()
    check("the panel's list has its name", ("list", "Accessibility issues") in tree, tree)
    check("and its rows read as words",
          any(kind == "list item" and name.startswith(("Fix: ", "Review: "))
              for kind, name in tree), tree)
    check("nothing in the window answers with wx's default name",
          not any(name.lower() == "panel" for _k, name in tree), tree)

    print("\nExport as")
    load("<h1>Notes</h1><p>Two <strong>bold</strong> words.</p>")
    frame.meta["title"] = "Notes"
    for writer, name, proof in (("export_docx", "Notes.docx", b"PK"),
                                ("export_markdown", "Notes.md", b"# Notes"),
                                ("export_text", "Notes.txt", b"Notes")):
        out = os.path.join(folder, name)
        frame.export_body_to(out, writer)
        check("%s is written" % name, wait_until(lambda: os.path.exists(out), 10.0))
        with open(out, "rb") as fh:
            check("and holds the document", proof in fh.read(4000))
    check("and the status bar says so", "Written" in frame.status.GetStatusText(0),
          frame.status.GetStatusText(0))
    print("\nThe menus have them")
    labels = {a: keymap.entry(a).plain_label for a in ("export_pdf", "export_word",
                                                       "export_markdown", "export_text")}
    check("Export as has PDF, Word, Markdown and Plain text",
          list(labels.values()) == ["PDF...", "Word...", "Markdown...", "Plain text..."], labels)
    menu = keymap.MENUS[0][1]
    sub = [i for i in menu if isinstance(i, tuple)]
    check("under File", sub and sub[0][0] == "&Export as" and list(sub[0][1]) == list(labels), sub)
    check("the context menu has them too",
          any(isinstance(i, tuple) and i[0] == "&Export as" for i in keymap.CONTEXT_MENU))


def main():
    try:
        start_screen()
        panel()
        passwords()
        exports()
    except Exception:
        import traceback
        traceback.print_exc()
        CHECKS.append(False)
    print("\nThe proof that a check can fail")
    check("(deliberate) the panel lists a thousand issues", len(frame.panel.issues) == 1000)
    last = CHECKS.pop()
    print("  the line above is the deliberate failure; it is not counted")
    check("the deliberate failure was recorded as a failure", last is False)
    print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)), flush=True)
    os._exit(0 if all(CHECKS) else 1)


wx.CallLater(800, main)
wx.CallLater(150000, lambda: (print("  FAIL timed out", flush=True), os._exit(1)))
app.MainLoop()
os._exit(1)
