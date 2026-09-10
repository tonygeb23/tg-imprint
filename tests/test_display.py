"""The low vision settings: they stick, they apply, and they stay off the PDF.

    python tests/test_display.py

Four things this has to prove, because they are the four ways the feature
could look right and be wrong:

- **The screen theme never reaches the exported PDF.** Every theme is a CSS
  custom property on the page's html element; the export takes the body
  HTML, which is the same bytes whatever the theme is. Checked twice: the
  body of the built page is identical under all four themes, and no theme
  colour appears in the HTML the export builds.
- **The text size survives a restart.** The zoom keys write editor_zoom,
  the settings file round trips it, and a page built from the loaded file
  starts at that size.
- **The toolbar label choice is honoured.** Icons, icons with labels and
  labels only each build a bar whose tools carry the words that mode asks
  for, and the squeeze drops only the words, never a tool.
- **Windows high contrast wins.** The forced-colors block remaps every
  variable, so no theme can fight it.

The first half needs no window. The window half builds one frame and ends
with os._exit because it holds a WebView.
"""
import ctypes
import os
import re
import sys
import tempfile

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tgimprint-display-appdata-")
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="tgimprint-display-local-")

from tgimprint import editor_page  # noqa: E402
from tgimprint import settings as settings_mod  # noqa: E402
from tgimprint.settings import Settings  # noqa: E402
from tgimprint.ui import keymap  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" and not condition else ""))


BODY = ('<h1>The Ridgeway</h1><p>Chalk, and a <strong>forecast</strong> that '
        'changed.</p><ul><li>Water</li></ul>'
        '<figure class="width-half place-centre"><img src="data:image/png;base64,AA" '
        'alt="A gate"></figure>')


def page_with(theme=None, **rest):
    display = dict(rest)
    if theme:
        display["theme"] = theme
    return editor_page.build_page(keymap.page_bindings(), keymap.DENY_CHORDS,
                                  body_html=BODY, display=display, nonce="fixed")


def body_of(html):
    """What is between the editor element's tags: what getBody returns and
    what the export is built from."""
    match = re.search(r'<main id="editor"[^>]*>(.*)</main>', html, re.S)
    return match.group(1) if match else ""


print("\nThe settings file")
folder = tempfile.mkdtemp(prefix="tgimprint-display-")
path = os.path.join(folder, "settings.json")
s = Settings(path)
s.load()
check("every screen setting has a default",
      all(k in s for k in settings_mod.DISPLAY_KEYS), list(settings_mod.DISPLAY_KEYS))
check("the text size starts at 100 percent", s["editor_zoom"] == 100)
check("the caret starts at the ordinary two pixels", s["caret_width"] == 2)
check("the toolbar starts with icons and labels",
      s["toolbar_labels_mode"] == "icons_labels")
check("display() is the dict the page takes",
      set(s.display()) == {"zoom", "theme", "caret", "focus", "bold", "spacing"},
      s.display())

print("\nThe text size survives a restart")
s["editor_zoom"] = 175
s["page_theme"] = "yellow_on_black"
s["caret_width"] = 5
s["focus_ring_width"] = 6
s["bold_body"] = True
s["line_spacing"] = "double"
s["toolbar_labels_mode"] = "labels"
check("the file was written", s.save())
again = Settings(path)
check("and read back", again.load() == "loaded")
check("the text size came back", again["editor_zoom"] == 175, again["editor_zoom"])
check("so did the theme", again["page_theme"] == "yellow_on_black")
check("so did the caret, the ring, the weight and the spacing",
      (again["caret_width"], again["focus_ring_width"], again["bold_body"],
       again["line_spacing"]) == (5, 6, True, "double"))
check("so did the toolbar choice", again["toolbar_labels_mode"] == "labels")
built = editor_page.build_page(keymap.page_bindings(), keymap.DENY_CHORDS,
                               display=again.display())
check("and a page built from the loaded file starts at that size",
      '"zoom": 175' in built, built[built.find("var display"):][:120])

print("\nA hand edited settings file cannot hurt the page")
bad = Settings(os.path.join(folder, "bad.json"))
bad.load()
bad["editor_zoom"] = 100000
bad["caret_width"] = -4
bad["page_theme"] = "</script><script>alert(1)"
bad["line_spacing"] = "enormous"
bad._absorb_display({})
check("a silly text size is clamped to the range", bad["editor_zoom"] == 300)
check("a negative caret becomes the smallest one", bad["caret_width"] == 2)
check("a theme that is not a theme falls back", bad["page_theme"] == "normal")
check("a spacing that is not a spacing falls back", bad["line_spacing"] == "normal")
clean = editor_page.clean_display({"theme": "</script><script>", "zoom": "abc",
                                   "caret": None, "spacing": 7, "bold": "yes"})
check("clean_display refuses anything not in the lists",
      clean["theme"] == "normal" and clean["zoom"] == 100 and clean["spacing"] == "normal")
made = editor_page.build_page(keymap.page_bindings(), keymap.DENY_CHORDS,
                              display={"theme": "</script><script>alert(1)</script>"})
check("and nothing from a settings file can close the script tag",
      "alert(1)" not in made)

print("\nThe older settings file still opens")
older = os.path.join(folder, "old.json")
with open(older, "w", encoding="utf-8") as fh:
    fh.write('{"speech_level": "all", "toolbar_labels": false, "page_size": "A4"}')
migrated = Settings(older)
migrated.load()
check("a file with the old toolbar_labels switch off means icons only",
      migrated["toolbar_labels_mode"] == "icons", migrated["toolbar_labels_mode"])
with open(older, "w", encoding="utf-8") as fh:
    fh.write('{"toolbar_labels": true}')
migrated = Settings(older)
migrated.load()
check("and with it on means icons with labels",
      migrated["toolbar_labels_mode"] == "icons_labels")

print("\nThe screen theme does not reach the exported PDF")
bodies = {theme: body_of(page_with(theme)) for theme in settings_mod.PAGE_THEMES}
check("the four themes build four different pages",
      len({page_with(t) for t in settings_mod.PAGE_THEMES}) == 4)
check("and the body of the document is the same in every one",
      len(set(bodies.values())) == 1, {k: v[:60] for k, v in bodies.items()})
check("the body is the document, not a themed copy of it",
      "The Ridgeway" in bodies["dark"] and "<strong>" in bodies["dark"])
yellow = page_with("yellow_on_black")
check("the yellow theme is in the stylesheet",
      "#ffff00" in yellow and 'data-theme="yellow_on_black"' in yellow)
check("and no theme colour is anywhere in the body",
      "#ffff00" not in bodies["yellow_on_black"]
      and "color" not in bodies["yellow_on_black"].lower())
loud = body_of(page_with("dark", zoom=300, caret=6, focus=6, bold=True, spacing="double"))
check("nor is the text size, the caret, the ring, the weight or the spacing",
      loud == bodies["normal"], loud[:80])

print("\nThe export builds the PDF from that body, in black on white")
try:
    from tgimprint import pdfexport
    # pdfexport.build_page is what the engine is handed. It is given the
    # body the editor returns, which is the same body under every theme, so
    # this is the page that becomes the PDF.
    printed = pdfexport.build_page(
        bodies["yellow_on_black"],
        pdfexport.settings_from({"title": "The Ridgeway", "lang": "en-US"}))
    check("the page the PDF is made from carries the document",
          "The Ridgeway" in printed and "<strong>" in printed)
    check("and no theme colour, and no theme at all",
          "#ffff00" not in printed and "data-theme" not in printed
          and "--paper" not in printed, printed[:300])
    check("its text is black, whatever colour the screen was",
          "color: #000000" in printed, printed[printed.find("html {"):][:120])
    check("and the export's stylesheet knows nothing about the screen themes",
          not any(t in pdfexport.STYLESHEET for t in ("#ffff00", "data-theme", "--paper")))
    for theme in settings_mod.PAGE_THEMES:
        same = pdfexport.build_page(
            bodies[theme], pdfexport.settings_from({"title": "The Ridgeway",
                                                    "lang": "en-US"}))
        check("the PDF page is byte for byte the same under the %s theme" % theme,
              same == printed)
except ImportError:
    print("  skip pdfexport is not part of this build yet")

print("\nWindows high contrast is never fought")
normal = page_with("normal")
forced = normal[normal.find("@media (forced-colors: active)"):]
forced = forced[:forced.find("}\n}") + 3]
check("the forced colours block remaps every variable",
      all(name in forced for name in ("--paper", "--ink", "--link", "--focus",
                                      "--caret", "--sel")), forced[:200])
check("it uses the system colour keywords",
      "Canvas" in forced and "CanvasText" in forced and "Highlight" in forced)
check("it applies to every theme, not only the default",
      "html[data-theme]" in forced, forced[:120])
check("the page never forces its own colours over the system ones",
      "forced-color-adjust: none" not in normal)

print("\nThe page applies each setting to itself and to nothing else")
big = page_with("dark", zoom=200, caret=5, focus=6, bold=True, spacing="one_and_a_half")
check("the settings reach the page as JSON",
      '"caret": 5' in big and '"focus": 6' in big and '"bold": true' in big)
check("setDisplay writes custom properties on the html element",
      "root.style.setProperty('--caret-width'" in big
      and "root.style.setProperty('--line-height'" in big)
check("and never on the editor or on the text",
      "ed.style.setProperty" not in big and "ed.style.color" not in big)
check("the caret box lives outside the editor",
      "document.body.appendChild(caretBox)" in big)
check("the zoom steps come from settings.py",
      str(list(settings_mod.ZOOM_STEPS)) in big.replace(", ", ", "))

print("\nThe zoom steps")
stepper = Settings(os.path.join(folder, "steps.json"))
stepper.load()
stepper["editor_zoom"] = 100
check("up from 100 is 115", stepper.zoom_step(1) == 115)
check("down from 100 is 85", stepper.zoom_step(-1) == 85)
stepper["editor_zoom"] = 210
check("up from a number in between lands on the next step", stepper.zoom_step(1) == 250)
check("and down lands on the one below", stepper.zoom_step(-1) == 200)
stepper["editor_zoom"] = 300
check("up from the top stays at the top", stepper.zoom_step(1) == 300)
stepper["editor_zoom"] = 70
check("down from the bottom stays at the bottom", stepper.zoom_step(-1) == 70)
check("zero goes back to 100", stepper.zoom_step(0) == 100)

# ---------------------------------------------------------------- the window
print("\nThe window applies them")
import wx  # noqa: E402

from tgimprint.ui import main_window, toolbar as toolbar_mod  # noqa: E402

app = wx.App(False)
live = Settings(os.path.join(tempfile.mkdtemp(), "settings.json"))
live["first_run_done"] = True
live["editor_zoom"] = 150
live["page_theme"] = "dark"
live["toolbar_labels_mode"] = "labels"
frame = main_window.MainFrame(settings=live)
frame.Show()
wx.Yield()
check("the editor page was built with the settings' text size",
      frame.editor.display()["zoom"] == 150, frame.editor.display())
check("and with the theme", frame.editor.display()["theme"] == "dark")

print("\nThe toolbar honours the choice")
check("labels only was asked for and built", frame.toolbar.mode == "labels",
      frame.toolbar.mode)
words = {a: frame.toolbar.label_for(a) for a in ("new", "bold", "align_right", "export_pdf")}
check("every tool carries its word", all(words.values()), words)
frame.settings["toolbar_labels_mode"] = "icons"
frame._fit_toolbar()
check("icons only builds a bar with no words",
      frame.toolbar.mode == "icons" and not frame.toolbar.label_for("bold"))
frame.settings["toolbar_labels_mode"] = "icons_labels"
frame._fit_toolbar()
check("icons with labels builds a bar with words",
      frame.toolbar.mode == "icons_labels" and frame.toolbar.label_for("bold") == "Bold")
tools = ("new", "open", "save", "bold", "italic", "underline", "strike", "bullets",
         "numbers", "quote", "align_left", "align_center", "align_right",
         "align_justify", "insert_link", "insert_picture", "insert_table", "export_pdf")
check("no mode ever drops a tool",
      all(frame.toolbar.FindById(frame.id_of(a)) is not None for a in tools))
squeezed = toolbar_mod.EditorToolBar(frame, frame.id_of, mode="icons_labels", squeeze=1)
check("the squeeze drops words, not tools",
      all(squeezed.FindById(frame.id_of(a)) is not None for a in tools)
      and squeezed.label_for("new") == "New" and squeezed.label_for("align_right") == "")
check("and it is narrower than the bar with every word",
      squeezed.needed_width() < frame.toolbar.needed_width(),
      (squeezed.needed_width(), frame.toolbar.needed_width()))
check("every tool keeps its tooltip whatever is drawn",
      all((squeezed.FindById(frame.id_of(a)).GetShortHelp() or "").strip() for a in tools))
squeezed.Destroy()

print("\nThe zoom keys write the setting")
frame._on_did("zoom_in", {"percent": 130})
check("a zoom the page reports is written to the settings",
      frame.settings["editor_zoom"] == 130, frame.settings["editor_zoom"])
check("and the editor is told about it", frame.editor.display()["zoom"] == 130)
check("and it says the new size",
      "130" in frame.status.GetStatusText(0), frame.status.GetStatusText(0))
frame._on_did("zoom_reset", {"percent": 100})
check("actual size goes back to 100", frame.settings["editor_zoom"] == 100)
saved = Settings(frame.settings.path)
check("and the file on disk holds it, so it survives a restart",
      saved.load() == "loaded" and saved["editor_zoom"] == 100, saved.get("editor_zoom"))

print("\nThe Display page")
from tgimprint.ui.preferences_dialog import PreferencesDialog  # noqa: E402

prefs = PreferencesDialog(frame, frame, frame.settings, page="Display")
titles = [prefs.tabs.GetPageText(i) for i in range(prefs.tabs.GetPageCount())]
check("Preferences has a Display page", "Display" in titles, titles)
check("and it opens on it when asked",
      prefs.tabs.GetPageText(prefs.tabs.GetSelection()) == "Display")
check("the text size runs from 70 to 300",
      (prefs.zoom.GetMin(), prefs.zoom.GetMax()) == (70, 300))
check("the caret runs from 2 to 6",
      (prefs.caret.GetMin(), prefs.caret.GetMax()) == (2, 6))
check("the focus ring runs from 2 to 6",
      (prefs.focus.GetMin(), prefs.focus.GetMax()) == (2, 6))
check("the four themes are offered in the person's words",
      [prefs.theme.GetString(i) for i in range(prefs.theme.GetCount())]
      == list(settings_mod.PAGE_THEME_LABELS))
check("three line spacings", prefs.spacing.GetCount() == 3)
check("three toolbar shapes", prefs.toolbar_labels.GetCount() == 3)
check("bold body text is a tick box", isinstance(prefs.bold_body, wx.CheckBox))
# Wrap() puts real newlines in the label, so the words are compared with
# the spacing taken out.
sentence = [" ".join(w.GetLabel().split())
            for w in prefs.tabs.GetPage(titles.index("Display")).GetChildren()
            if isinstance(w, wx.StaticText) and "PDF" in w.GetLabel()]
check("the page says in one sentence that none of it changes the PDF",
      sentence and "screen only" in sentence[0] and "black text on a white page" in sentence[0],
      sentence)
prefs.zoom.SetValue(220)
prefs.theme.SetSelection(settings_mod.PAGE_THEMES.index("yellow_on_black"))
prefs.caret.SetValue(5)
prefs.bold_body.SetValue(True)
prefs._on_display_change(None)
check("changing a control applies it at once",
      frame.editor.display()["zoom"] == 220
      and frame.editor.display()["theme"] == "yellow_on_black"
      and frame.editor.display()["caret"] == 5
      and frame.editor.display()["bold"] is True, frame.editor.display())
check("and writes it into the settings", frame.settings["editor_zoom"] == 220)
prefs._on_reset(None)
check("Reset puts the ordinary screen back",
      frame.settings["editor_zoom"] == 100 and frame.settings["page_theme"] == "normal"
      and frame.settings["caret_width"] == 2 and not frame.settings["bold_body"])
prefs.Destroy()

print("\nView has the toolbar choice and a way to the Display page")
labels = []
bar = frame.GetMenuBar()
view = bar.GetMenu(bar.FindMenu("View"))
for item in view.GetMenuItems():
    sub = item.GetSubMenu()
    if sub is not None:
        labels.extend([(item.GetItemLabelText(), i.GetItemLabelText(), i.IsCheckable())
                       for i in sub.GetMenuItems()])
    else:
        labels.append(("", item.GetItemLabelText(), item.IsCheckable()))
names = [b for _a, b, _c in labels]
check("Toolbar labels offers the three shapes",
      [b for a, b, _c in labels if a == "Toolbar labels"]
      == ["Icons only", "Icons with labels", "Labels only"], labels)
check("they are check or radio items", all(c for a, _b, c in labels if a == "Toolbar labels"))
check("and Display options is there", "Display options..." in names, names)
frame.on_toolbar_icons(None)
check("choosing icons only from the menu changes the bar and the setting",
      frame.toolbar.mode == "icons" and frame.settings["toolbar_labels_mode"] == "icons")
check("and it says so", "icons only" in frame.status.GetStatusText(0).lower(),
      frame.status.GetStatusText(0))
frame.on_toolbar_labels(None)
check("choosing labels only does too", frame.toolbar.mode == "labels")

print("\nThe proof that a check can fail")
check("(deliberate) the text size is 999 percent", frame.settings["editor_zoom"] == 999)
last = CHECKS.pop()
print("  the line above is the deliberate failure; it is not counted")
check("the deliberate failure was recorded as a failure", last is False)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.stdout.flush()
os._exit(0 if all(CHECKS) else 1)
