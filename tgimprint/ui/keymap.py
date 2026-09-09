"""The one list of keys, menus and what each key does.

Everything that mentions a key is derived from ENTRIES below, so nothing can
drift: the wx accelerator table (used only when focus is outside the editor),
the key map generated into the editor page's JavaScript (used whenever the
editor has focus, because with the WebView2 focused not one wx accelerator
fires, CHALLENGE.md W4), the menu labels, the F1 help text and
docs/KEYBOARD.md. tests/test_menus.py fails when any of them disagree.

Scopes, which say who handles the key when the editor has focus:

  page     the page's capture phase keydown handler does the work itself
           (formatting, undo, headings) and posts a "did" message so the
           window can confirm it in the status bar
  app      the page swallows the key and forwards its action name to Python
           over the message bridge; the window's handler runs once
  native   the page does not intercept the key: Chromium's own behaviour is
           the right one (Ctrl+V raises the paste event the page reads, the
           Applications key raises the contextmenu event the page forwards)

A key that is "conditional" is intercepted only when the caret is somewhere
it applies (Tab in a list or a table cell, Delete on a picture); otherwise the
page lets it through so ordinary typing is untouched.

Ctrl+Alt+digit is AltGr on German, French, Polish, Spanish and Portuguese
layouts and types a character there, so the page acts on it only when the
event's key is the digit itself. The Ctrl+Shift+digit aliases are gated on
the physical key code (event.code, "Digit1" and so on), which no layout
changes. Both are documented together in KEYBOARD.md.

    python tgimprint/ui/keymap.py docs/KEYBOARD.md      # regenerate the document
"""
import os
import sys

#: The browser keys the page swallows with nothing forwarded, on top of every
#: key in the map. F5 reloads the page, which is the document gone (W6);
#: Ctrl+F and Ctrl+P pulled focus into browser chrome; the rest open
#: DevTools, view source, history or downloads inside the editor.
DENY_CHORDS = (
    "f5", "ctrl+shift+r", "ctrl+g", "ctrl+shift+g", "f12",
    "ctrl+shift+j", "ctrl+shift+n", "ctrl+t",
    "ctrl+shift+delete", "ctrl+shift+o", "ctrl+shift+b", "ctrl+shift+m",
    "f7", "alt+left", "alt+right", "alt+home", "ctrl+shift+u",
    "browserback", "browserforward", "browserrefresh", "browserhome",
    "browsersearch", "browserfavorites",
)
# Ctrl+R (align right) and Ctrl+Shift+T (insert table) are app keys, so the
# map swallows them; they are not listed twice.


class Entry:
    """One thing the user can do, and the keys that do it."""

    __slots__ = ("action", "label", "keys", "scope", "help", "kind",
                 "conditional", "page_keys", "digit", "group")

    def __init__(self, action, label, keys=(), scope="app", help="",
                 kind="normal", conditional=False, page_keys=(),
                 digit=False, group=""):
        self.action = action            # names the handler: MainFrame.on_<action>
        self.label = label              # the menu label, with its mnemonic
        self.keys = tuple(keys)         # shown in the menu and in the wx table
        self.scope = scope              # page, app or native
        self.help = help                # one line for KEYBOARD.md and F1
        self.kind = kind                # normal, check or radio
        self.conditional = conditional  # the page intercepts only in context
        self.page_keys = tuple(page_keys)   # bound in the page only, never shown
        self.digit = digit              # the AltGr rule applies to keys
        self.group = group              # radio group name

    @property
    def primary(self):
        return self.keys[0] if self.keys else ""

    @property
    def plain_label(self):
        return self.label.replace("&", "")


E = Entry

#: The list. Order inside each menu is the order here.
ENTRIES = [
    # ------------------------------------------------------------- File ----
    E("new", "&New", ("Ctrl+N",), "app", "Start a new, empty document."),
    E("open", "&Open...", ("Ctrl+O",), "app",
      "Open a document: .imprint, .html, .txt, .md, .docx or .pdf."),
    E("save", "&Save", ("Ctrl+S",), "app", "Save the document."),
    E("save_as", "Save &As...", ("Ctrl+Shift+S",), "app",
      "Save the document under a new name, as a TG Imprint document."),
    E("save_web_page", "Save as &web page...", (), "app",
      "Write the same document to a .html file any browser can open."),
    E("close_document", "&Close document", ("Ctrl+W",), "app",
      "Close the document and start an empty one."),
    E("export_pdf", "&Export PDF...", ("Ctrl+Shift+E",), "app",
      "Make the tagged PDF and check it."),
    E("print", "&Print...", ("Ctrl+P",), "app",
      "Make a PDF and send it to the printer."),
    E("properties", "&Document properties...", ("Alt+Enter",), "app",
      "Properties of the picture at the caret, or of the document: title, "
      "author, language, subject, page size and margins."),
    E("exit", "E&xit", ("Alt+F4",), "app", "Close TG Imprint."),

    # ------------------------------------------------------------- Edit ----
    E("undo", "&Undo", ("Ctrl+Z",), "page", "Undo the last change."),
    E("redo", "&Redo", ("Ctrl+Y",), "page", "Redo the change you undid."),
    E("cut", "Cu&t", ("Ctrl+X",), "page", "Cut the selection to the clipboard."),
    E("copy", "&Copy", ("Ctrl+C",), "page", "Copy the selection to the clipboard."),
    E("paste", "&Paste", ("Ctrl+V",), "native",
      "Paste. Text from Word or a web page is cleaned to headings, lists, "
      "links, bold and italic; a picture becomes a figure that needs a "
      "description."),
    E("select_all", "Select &all", ("Ctrl+A",), "page", "Select the whole document."),
    E("find", "&Find...", ("Ctrl+F",), "app", "Find text in the document."),
    E("replace", "Find and rep&lace...", ("Ctrl+H",), "app",
      "Find text and replace it, one at a time or all at once."),
    E("find_next", "Find &next", ("F3",), "app", "Find the next match."),
    E("find_previous", "Find pre&vious", ("Shift+F3",), "app",
      "Find the previous match."),
    E("rename", "Edit picture &description or document title", ("F2",), "app",
      "Edit the description of the picture at the caret, or rename the "
      "document when there is no picture."),
    E("delete_object", "Re&move picture or table", ("Delete",), "page",
      "Remove the picture at the caret, or an empty table, after a "
      "confirmation. Elsewhere Delete deletes text as usual.",
      conditional=True),

    # ----------------------------------------------------------- Format ----
    E("bold", "&Bold", ("Ctrl+B",), "page", "Bold on or off.", kind="check"),
    E("italic", "&Italic", ("Ctrl+I", "Ctrl+Shift+I"), "page",
      "Italic on or off. Ctrl+Shift+I is kept from the April build.",
      kind="check"),
    E("underline", "&Underline", ("Ctrl+U",), "page", "Underline on or off.",
      kind="check"),
    E("strike", "&Strikethrough", ("Ctrl+Shift+K",), "page",
      "Strikethrough on or off.", kind="check"),
    E("code", "&Code", ("Ctrl+Shift+C",), "page",
      "Code, in a fixed width font, on or off.", kind="check"),
    E("normal", "&Normal text", ("Ctrl+Alt+0", "Ctrl+Shift+0"), "page",
      "Make this an ordinary paragraph.", kind="radio", digit=True,
      group="style"),
    E("heading1", "Heading &1", ("Ctrl+Alt+1", "Ctrl+Shift+1"), "page",
      "Heading level 1.", kind="radio", digit=True, group="style"),
    E("heading2", "Heading &2", ("Ctrl+Alt+2", "Ctrl+Shift+2"), "page",
      "Heading level 2.", kind="radio", digit=True, group="style"),
    E("heading3", "Heading &3", ("Ctrl+Alt+3", "Ctrl+Shift+3"), "page",
      "Heading level 3.", kind="radio", digit=True, group="style"),
    E("heading4", "Heading &4", ("Ctrl+Alt+4", "Ctrl+Shift+4"), "page",
      "Heading level 4.", kind="radio", digit=True, group="style"),
    E("heading5", "Heading &5", ("Ctrl+Alt+5", "Ctrl+Shift+5"), "page",
      "Heading level 5.", kind="radio", digit=True, group="style"),
    E("heading6", "Heading &6", ("Ctrl+Alt+6", "Ctrl+Shift+6"), "page",
      "Heading level 6.", kind="radio", digit=True, group="style"),
    E("bullets", "&Bullet list", ("Ctrl+Alt+8", "Ctrl+Shift+8"), "page",
      "A bullet list, on or off.", kind="radio", digit=True, group="style"),
    E("numbers", "Nu&mbered list", ("Ctrl+Alt+9", "Ctrl+Shift+9"), "page",
      "A numbered list, on or off.", kind="radio", digit=True, group="style"),
    E("quote", "&Quote", ("Ctrl+Q",), "page", "A quotation block, on or off.",
      kind="radio", group="style"),
    E("align_left", "&Left", ("Ctrl+L",), "page", "Align left.",
      kind="radio", group="align"),
    E("align_center", "&Centre", ("Ctrl+E",), "page", "Centre.",
      kind="radio", group="align"),
    E("align_right", "&Right", ("Ctrl+R",), "page", "Align right.",
      kind="radio", group="align"),
    E("align_justify", "&Justify", ("Ctrl+J",), "page", "Justify.",
      kind="radio", group="align"),
    E("indent", "Increase list &level", (), "page",
      "In a list, Tab nests the item one level deeper.",
      conditional=True, page_keys=("Tab",)),
    E("outdent", "Decrease list le&vel", (), "page",
      "In a list, Shift+Tab moves the item out one level. In a table, Tab "
      "and Shift+Tab move between cells and Tab in the last cell adds a "
      "row.", conditional=True, page_keys=("Shift+Tab",)),

    # ----------------------------------------------------------- Insert ----
    E("insert_link", "&Link...", ("Ctrl+K",), "app",
      "Insert a link, or edit the link at the caret."),
    E("insert_picture", "&Picture...", ("Ctrl+Shift+P",), "app",
      "Insert a picture with a description."),
    E("insert_table", "&Table...", ("Ctrl+Shift+T",), "app",
      "Insert a table with a header row."),
    E("picture_properties", "Picture p&roperties...", (), "app",
      "Description, caption, width and placement of the picture at the "
      "caret. Alt+Enter opens this when the caret is on a picture."),

    # ------------------------------------------------------------ Tools ----
    E("describe_picture", "&Describe picture...", ("Ctrl+D",), "app",
      "Ask Claude, ChatGPT or Gemini to describe the picture at the caret."),
    E("describe_document", "Describe d&ocument...", ("Ctrl+Shift+D",), "app",
      "Ask an AI service to describe the whole document."),
    E("check_pdf", "&Check accessibility of a PDF...", ("Ctrl+Shift+A",), "app",
      "Run the accessibility checks on any PDF and read the report."),
    E("preferences", "&Preferences...", ("Ctrl+,",), "app",
      "Spoken feedback, document defaults and the AI services."),

    # ------------------------------------------------------------- View ----
    E("next_heading", "&Next heading", ("F6",), "page",
      "Move the caret to the next heading."),
    E("previous_heading", "&Previous heading", ("Shift+F6",), "page",
      "Move the caret to the previous heading."),
    E("structure", "&Structure navigator...", ("Alt+F6",), "app",
      "Every heading in a list; Enter jumps to it."),
    E("pictures", "Pi&ctures...", ("Ctrl+Shift+Alt+P",), "app",
      "Every picture with its description, or the ones still needing one."),
    E("zoom_in", "Zoom &in", ("Ctrl+=",), "page", "Make the page larger on screen."),
    E("zoom_out", "Zoom &out", ("Ctrl+-",), "page", "Make the page smaller on screen."),
    E("zoom_reset", "&Actual size", ("Ctrl+0",), "page",
      "Show the page at its normal size."),

    # ------------------------------------------------------------- Help ----
    E("keyboard_help", "&Keyboard shortcuts", ("F1",), "app",
      "This list, in a window you can read."),
    E("user_guide", "&User guide on the web", (), "app",
      "Open the user guide in your browser."),
    E("check_updates", "&Check for updates", (), "app",
      "Ask whether a newer version exists."),
    E("donate", "&Donate", (), "app", "Support TG Studios."),
    E("about", "&About TG Imprint", (), "app",
      "The version, the tagline and the PDF engine that was found."),

    # -------------------------------------------- the context menu keys ----
    E("context_menu", "Context menu", ("Applications", "Shift+F10"), "native",
      "The context menu, offering what the menu bar offers."),
]

#: The menus, in order, naming entries by action. "-" is a separator, a tuple
#: is a submenu, and "recent" is the Recent documents submenu the window
#: fills in itself.
MENUS = [
    ("&File", ["new", "open", "recent", "-", "save", "save_as",
               "save_web_page", "close_document", "-", "export_pdf", "print",
               "-", "properties", "-", "exit"]),
    ("&Edit", ["undo", "redo", "-", "cut", "copy", "paste", "select_all", "-",
               "find", "replace", "find_next", "find_previous", "-",
               "rename", "delete_object"]),
    ("F&ormat", ["bold", "italic", "underline", "strike", "code", "-",
                 ("&Paragraph style", ["normal", "heading1", "heading2",
                                       "heading3", "heading4", "heading5",
                                       "heading6", "bullets", "numbers",
                                       "quote"]),
                 ("Ali&gnment", ["align_left", "align_center", "align_right",
                                 "align_justify"]),
                 "-", "indent", "outdent"]),
    ("&Insert", ["insert_link", "insert_picture", "insert_table", "-",
                 "picture_properties"]),
    ("&Tools", ["describe_picture", "describe_document", "check_pdf", "-",
                "preferences"]),
    ("&View", ["next_heading", "previous_heading", "structure", "pictures",
               "-", "zoom_in", "zoom_out", "zoom_reset"]),
    ("&Help", ["keyboard_help", "user_guide", "-", "check_updates", "donate",
               "-", "about"]),
]

#: What the context menu offers: the editing and formatting items, plus the
#: picture items when a picture is at the caret (the window adds those).
CONTEXT_MENU = ["undo", "redo", "-", "cut", "copy", "paste", "select_all", "-",
                "bold", "italic", "underline", "strike",
                ("&Paragraph style", ["normal", "heading1", "heading2",
                                      "heading3", "heading4", "heading5",
                                      "heading6", "bullets", "numbers",
                                      "quote"]),
                ("Ali&gnment", ["align_left", "align_center", "align_right",
                                "align_justify"]),
                "-", "insert_link", "insert_picture", "insert_table", "-",
                "properties"]

#: The keys CONVENTIONS.md promises in every TG Studios program, and the
#: entry that honours each one here.
CONTRACT = {
    "F1": "keyboard_help", "F2": "rename", "Alt+Enter": "properties",
    "Ctrl+F": "find", "Delete": "delete_object", "Applications": "context_menu",
    "Ctrl+S": "save", "Ctrl+O": "open", "Ctrl+N": "new", "Alt+F4": "exit",
}

BY_ACTION = {e.action: e for e in ENTRIES}


def entry(action):
    return BY_ACTION[action]


# ------------------------------------------------------------------ chords --

_NAMED = {"enter": "enter", "return": "enter", "delete": "delete",
          "del": "delete", "tab": "tab", "escape": "escape", "esc": "escape",
          "applications": "contextmenu", "apps": "contextmenu",
          "space": " ", "backspace": "backspace", "=": "=", "-": "-",
          ",": ",", "plus": "=", "minus": "-"}


def chord(text):
    """"Ctrl+Shift+E" -> "ctrl+shift+e", the form the page's map is keyed on.

    Modifiers are always written in the order ctrl, alt, shift, whatever
    order the entry spelt them in, so a lookup built from a keydown event
    lands on the same string.
    """
    parts = [p.strip() for p in text.split("+") if p.strip()]
    mods = set()
    key = ""
    for part in parts:
        low = part.lower()
        if low in ("ctrl", "control"):
            mods.add("ctrl")
        elif low == "alt":
            mods.add("alt")
        elif low == "shift":
            mods.add("shift")
        elif low in _NAMED:
            key = _NAMED[low]
        else:
            key = low
    out = [m for m in ("ctrl", "alt", "shift") if m in mods]
    out.append(key)
    return "+".join(out)


def page_bindings():
    """What the editor page binds, as a list of plain dicts for JSON.

    Every key of every page and app entry, and every page-only key, each
    with its action, its scope, whether it is conditional, and how it is
    gated: "key" (the event's key must be the digit, the AltGr rule) or
    "code" (the physical key, for the Ctrl+Shift+digit aliases). Native
    entries are listed with scope "native" so the page knows not to touch
    them, and so a test can see that every entry is present.
    """
    out = []
    for e in ENTRIES:
        for text in e.keys + e.page_keys:
            c = chord(text)
            binding = {"chord": c, "action": e.action, "scope": e.scope,
                       "conditional": e.conditional}
            key = c.rsplit("+", 1)[-1]
            if e.digit and key.isdigit():
                if "shift" in c:
                    binding["code"] = "Digit" + key
                else:
                    binding["gate"] = "key"
            out.append(binding)
    return out


# --------------------------------------------------------------- wx table --

def wx_accelerators(id_of):
    """The wx accelerator entries, one per key, all pointing at the entry's id.

    `id_of(action)` returns the wx id the window bound the action to. Keys
    that wx cannot express (the Applications key is expressible, "Ctrl+,"
    is) are all here; anything unparseable raises so it is noticed. Native
    entries are left out: the frame must not act on Ctrl+V itself.
    """
    import wx
    entries = []
    for e in ENTRIES:
        if e.scope == "native":
            continue
        for text in e.keys:
            flags, code = wx_key(text)
            entries.append(wx.AcceleratorEntry(flags, code, id_of(e.action)))
    return entries


def wx_key(text):
    """"Ctrl+Shift+E" -> (flags, keycode) for a wx.AcceleratorEntry."""
    import wx
    named = {"enter": wx.WXK_RETURN, "delete": wx.WXK_DELETE, "tab": wx.WXK_TAB,
             "escape": wx.WXK_ESCAPE, "applications": wx.WXK_WINDOWS_MENU,
             "space": wx.WXK_SPACE, "backspace": wx.WXK_BACK}
    for n in range(1, 25):
        named["f%d" % n] = getattr(wx, "WXK_F%d" % n)
    flags = 0
    code = None
    for part in text.split("+"):
        low = part.strip().lower()
        if low == "ctrl":
            flags |= wx.ACCEL_CTRL
        elif low == "alt":
            flags |= wx.ACCEL_ALT
        elif low == "shift":
            flags |= wx.ACCEL_SHIFT
        elif low in named:
            code = named[low]
        elif len(low) == 1:
            code = ord(low.upper())
        else:
            raise ValueError("cannot express %r as a wx accelerator" % text)
    if code is None:
        raise ValueError("no key in %r" % text)
    return flags, code


def menu_label(e):
    """The label wx gets: the mnemonic label, a tab, the primary key.

    Only keys wx can parse back go after the tab; the Applications key is
    described in the help text instead.
    """
    if not e.keys:
        return e.label
    key = e.primary
    try:
        wx_key(key)
    except ValueError:
        return e.label
    return "%s\t%s" % (e.label, key)


# ------------------------------------------------------------ documents --

def _rows():
    """(menu, label, keys, help) for every entry, in menu order."""
    rows = []
    seen = set()

    def visit(menu, items):
        for item in items:
            if item == "-" or item == "recent":
                continue
            if isinstance(item, tuple):
                visit(menu + ", " + item[0].replace("&", ""), item[1])
                continue
            e = BY_ACTION[item]
            seen.add(item)
            rows.append((menu, e.plain_label, e.keys + e.page_keys, e.help))

    for title, items in MENUS:
        visit(title.replace("&", ""), items)
    for e in ENTRIES:
        if e.action not in seen:
            rows.append(("Everywhere", e.plain_label, e.keys + e.page_keys, e.help))
    return rows


def render_markdown():
    """docs/KEYBOARD.md, generated. Never edit the file by hand."""
    lines = [
        "# TG Imprint keyboard reference",
        "",
        "Generated from `tgimprint/ui/keymap.py` by `python tgimprint/ui/keymap.py "
        "docs/KEYBOARD.md`. `tests/test_menus.py` fails if this file and the "
        "code disagree, so edit the code and regenerate.",
        "",
        "Every key works while you are typing in the document. The same keys "
        "are in the menus, and the Applications key (or Shift+F10) opens a "
        "context menu offering the editing and formatting items.",
        "",
        "## The headings and the AltGr rule",
        "",
        "Ctrl+Alt+1 to Ctrl+Alt+6 set heading levels 1 to 6, Ctrl+Alt+0 makes "
        "normal text, Ctrl+Alt+8 a bullet list and Ctrl+Alt+9 a numbered list. "
        "On German, French, Polish, Spanish and Portuguese keyboards Ctrl+Alt "
        "is AltGr and some of those chords type a character instead, so Easy "
        "PDF acts on them only when the key really was the digit. The same "
        "commands are also on Ctrl+Shift+0 to Ctrl+Shift+9, which work on "
        "every layout.",
        "",
        "## Inside lists and tables",
        "",
        "Enter at the end of a heading starts a normal paragraph. Enter on an "
        "empty list item leaves the list. Backspace at the start of a list "
        "item takes it out of the list. Tab and Shift+Tab nest and unnest a "
        "list item; in a table they move between cells, and Tab in the last "
        "cell adds a row. Outside a list or table, Tab leaves the document "
        "for the toolbar, and Shift+Tab comes back.",
        "",
        "## Every key",
        "",
        "| Menu | Command | Keys | What it does |",
        "|---|---|---|---|",
    ]
    for menu, label, keys, help_text in _rows():
        lines.append("| %s | %s | %s | %s |" % (
            menu, label, ", ".join(keys) if keys else "", help_text))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_text():
    """The F1 window: the same list as plain text a screen reader reads well."""
    lines = ["TG Imprint keyboard shortcuts", ""]
    current = None
    for menu, label, keys, help_text in _rows():
        if menu != current:
            current = menu
            lines.append("")
            lines.append(menu)
        if keys:
            lines.append("%s: %s. %s" % (", ".join(keys), label, help_text))
        else:
            lines.append("%s (menu only). %s" % (label, help_text))
    lines.append("")
    lines.append("Ctrl+Alt+digit is AltGr on some European keyboards, so those "
                 "chords act only when the key really was the digit. Ctrl+Shift+0 "
                 "to Ctrl+Shift+9 do the same on every layout.")
    lines.append("In a list, Tab and Shift+Tab nest and unnest the item. In a "
                 "table they move between cells, and Tab in the last cell adds a "
                 "row. Enter on an empty list item leaves the list; Backspace at "
                 "the start of a list item takes it out of the list.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "KEYBOARD.md")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_markdown())
    print("wrote", target)
