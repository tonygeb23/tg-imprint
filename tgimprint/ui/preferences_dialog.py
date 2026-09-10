"""Preferences (Ctrl+,): Speech, Display, Document defaults, Worker C's AI.

The speech control is worded exactly as CONVENTIONS.md says, from
constants.SPEECH_LABELS. OK writes into the settings dict the window
passed in and calls the AI page's apply(); the window saves the file and
applies the level.

The Display page is different in one way: it applies as you change it,
because somebody who cannot read the current text size has no way to
choose a better one from a preview they cannot see. The window keeps a copy
of what was there and puts it back if you press Cancel.
"""
import wx

from .. import constants as C
from .. import settings as settings_mod
from .dialogs import add_row, focus_ring, name_field
from .doc_properties_dialog import LanguagePicker, PAGE_LABELS

def _index(names, value, fallback):
    """Where `value` sits in `names`, or where the default does."""
    if value in names:
        return names.index(value)
    return names.index(fallback)


FONTS = ("Arial, Helvetica, sans-serif", "Calibri, Carlito, sans-serif",
         "Segoe UI, sans-serif", "Verdana, sans-serif", "Georgia, serif",
         "Times New Roman, Times, serif", "Cambria, serif",
         "Consolas, Courier New, monospace")


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, frame, settings, page=None):
        super().__init__(parent, title="Preferences",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.settings = settings
        self.ai_page = None
        self._page_titles = []
        outer = wx.BoxSizer(wx.VERTICAL)
        self.tabs = wx.Notebook(self)
        # The tab strip and each page carry a name. Measured through the
        # accessibility tree on 2026-09-09, after HarmonicaPlayer wrote in:
        # the tab items were named, but the tab control answered with no
        # name at all and every page answered "panel", so arrowing along
        # the tabs said nothing useful and the page you landed on said
        # less. tests/test_ui_names.py reads the tree back and asserts it.
        name_field(self.tabs, "Preferences pages")
        self._build_speech()
        self._build_display()
        self._build_document()
        self._build_ai()
        outer.Add(self.tabs, 1, wx.EXPAND | wx.ALL, 10)
        buttons = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK, "OK")
        cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.AddButton(ok)
        buttons.AddButton(cancel)
        buttons.Realize()
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, self._on_ok)
        outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(560, 460)))
        self.CentreOnParent()
        first = self.speech
        if page and page in self._page_titles:
            index = self._page_titles.index(page)
            self.tabs.SetSelection(index)
            if page == "Display":
                first = self.zoom
        first.SetFocus()

    def _page(self, title):
        panel = wx.Panel(self.tabs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        name_field(panel, title)
        self.tabs.AddPage(panel, title)
        self._page_titles.append(title)
        return panel, sizer

    def _build_speech(self):
        panel, sizer = self._page("Speech")
        sizer.Add(wx.StaticText(panel, label="Spo&ken feedback from the app"), 0,
                  wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.speech = wx.Choice(panel, choices=list(C.SPEECH_LABELS))
        name_field(self.speech, "Spoken feedback from the app")
        level = self.settings.get("speech_level", C.DEFAULT_SPEECH_LEVEL)
        self.speech.SetSelection(C.SPEECH_LEVELS.index(level) if level in C.SPEECH_LEVELS else 0)
        self.speech.SetToolTip(
            "Everything is the default. The middle setting drops confirmations "
            "and hints and keeps anything you could not otherwise know. Nothing "
            "leaves the commentary to your screen reader and the status bar, and "
            "still answers a key you press to ask a question.")
        sizer.Add(self.speech, 0, wx.EXPAND | wx.ALL, 12)
        note = wx.StaticText(panel, label=(
            "Whatever you choose, everything the app says is also written to the "
            "status bar, so nothing is only spoken."))
        note.Wrap(self.FromDIP(480))
        sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

    def _build_display(self):
        """Everything about the screen, and nothing about the PDF.

        Tony, 2026-09-09: "make sure it has low vision options as well." The
        app had almost none: one zoom that was forgotten at the next launch,
        no page colours, a one pixel caret and no way to turn the toolbar
        words on. Every control here applies at once and is written to the
        settings file, so it is still there tomorrow.
        """
        panel, sizer = self._page("Display")
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.zoom = wx.SpinCtrl(panel, min=settings_mod.MIN_ZOOM, max=settings_mod.MAX_ZOOM,
                                initial=int(self.settings.get("editor_zoom",
                                                              settings_mod.DEFAULT_ZOOM)))
        add_row(panel, grid, "Editor &text size, in percent:", self.zoom,
                name="Editor text size in percent")
        self.zoom.SetToolTip("70 to 300 percent. Ctrl+equals and Ctrl+minus step "
                             "through the sizes while you are typing, Ctrl+0 goes "
                             "back to 100, and whatever you land on is remembered.")
        self.theme = wx.Choice(panel, choices=list(settings_mod.PAGE_THEME_LABELS))
        self.theme.SetSelection(_index(settings_mod.PAGE_THEMES,
                                       self.settings.get("page_theme"),
                                       settings_mod.DEFAULT_PAGE_THEME))
        add_row(panel, grid, "&Page colours on screen:", self.theme,
                name="Page colours on screen")
        self.theme.SetToolTip("The colours of the page you are writing on. High "
                              "contrast follows the colours you chose in Windows. "
                              "None of them change the PDF.")
        self.caret = wx.SpinCtrl(panel, min=settings_mod.MIN_CARET_WIDTH,
                                 max=settings_mod.MAX_CARET_WIDTH,
                                 initial=int(self.settings.get("caret_width",
                                                               settings_mod.DEFAULT_CARET_WIDTH)))
        add_row(panel, grid, "&Cursor width, in pixels:", self.caret,
                name="Cursor width in pixels")
        self.caret.SetToolTip("The blinking text cursor. Two is the ordinary one; "
                              "anything more draws a wider bar, because a one pixel "
                              "cursor is invisible at 200 percent.")
        self.focus = wx.SpinCtrl(panel, min=settings_mod.MIN_FOCUS_RING,
                                 max=settings_mod.MAX_FOCUS_RING,
                                 initial=int(self.settings.get("focus_ring_width",
                                                               settings_mod.DEFAULT_FOCUS_RING)))
        add_row(panel, grid, "&Focus ring thickness, in pixels:", self.focus,
                name="Focus ring thickness in pixels")
        self.focus.SetToolTip("The ring round whatever the keyboard is on: the page "
                              "you are writing in, and the lists in this program's "
                              "own windows.")
        self.spacing = wx.Choice(panel, choices=list(settings_mod.LINE_SPACING_LABELS))
        self.spacing.SetSelection(_index(settings_mod.LINE_SPACINGS,
                                         self.settings.get("line_spacing"),
                                         settings_mod.DEFAULT_LINE_SPACING))
        add_row(panel, grid, "&Line spacing on screen:", self.spacing,
                name="Line spacing on screen")
        self.toolbar_labels = wx.Choice(panel, choices=list(settings_mod.TOOLBAR_LABEL_LABELS))
        self.toolbar_labels.SetSelection(_index(settings_mod.TOOLBAR_LABEL_MODES,
                                                self.settings.get("toolbar_labels_mode"),
                                                settings_mod.DEFAULT_TOOLBAR_LABELS))
        add_row(panel, grid, "T&oolbar:", self.toolbar_labels, name="Toolbar")
        self.toolbar_labels.SetToolTip("Icons, icons with a word under each one, or "
                                       "words alone. Every tool answers to a screen "
                                       "reader by name whichever you pick.")
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        self.bold_body = wx.CheckBox(panel, label="&Bold body text on screen")
        self.bold_body.SetValue(bool(self.settings.get("bold_body")))
        sizer.Add(self.bold_body, 0, wx.LEFT | wx.RIGHT, 12)
        self.bold_body.SetToolTip("For anyone who needs weight rather than size. "
                                  "Headings are bold already.")
        note = wx.StaticText(panel, label=(
            "Everything on this page changes the screen only. Every PDF you export "
            "is black text on a white page at the page size in Document properties."))
        note.Wrap(self.FromDIP(500))
        sizer.Add(note, 0, wx.ALL, 12)
        self.reset = wx.Button(panel, label="&Reset the screen settings")
        sizer.Add(self.reset, 0, wx.LEFT | wx.BOTTOM, 12)
        self.reset.Bind(wx.EVT_BUTTON, self._on_reset)
        # A thicker ring round whichever of these has the keyboard, drawn at
        # the thickness the person just chose, so the setting shows itself.
        self._ring = focus_ring(panel, [self.zoom, self.theme, self.caret, self.focus,
                                        self.spacing, self.toolbar_labels,
                                        self.bold_body, self.reset],
                                int(self.settings.get("focus_ring_width",
                                                      settings_mod.DEFAULT_FOCUS_RING)))
        for control, event in ((self.zoom, wx.EVT_SPINCTRL), (self.caret, wx.EVT_SPINCTRL),
                               (self.focus, wx.EVT_SPINCTRL), (self.theme, wx.EVT_CHOICE),
                               (self.spacing, wx.EVT_CHOICE),
                               (self.toolbar_labels, wx.EVT_CHOICE),
                               (self.bold_body, wx.EVT_CHECKBOX)):
            control.Bind(event, self._on_display_change)
        self.zoom.Bind(wx.EVT_TEXT, self._on_display_change)

    def _on_reset(self, _event):
        self.zoom.SetValue(settings_mod.DEFAULT_ZOOM)
        self.theme.SetSelection(settings_mod.PAGE_THEMES.index(settings_mod.DEFAULT_PAGE_THEME))
        self.caret.SetValue(settings_mod.DEFAULT_CARET_WIDTH)
        self.focus.SetValue(settings_mod.DEFAULT_FOCUS_RING)
        self.spacing.SetSelection(settings_mod.LINE_SPACINGS.index(
            settings_mod.DEFAULT_LINE_SPACING))
        self.toolbar_labels.SetSelection(settings_mod.TOOLBAR_LABEL_MODES.index(
            settings_mod.DEFAULT_TOOLBAR_LABELS))
        self.bold_body.SetValue(False)
        self._on_display_change(None)

    def display_values(self):
        """What the Display page says, as the settings keys."""
        return {
            "editor_zoom": int(self.zoom.GetValue()),
            "page_theme": settings_mod.PAGE_THEMES[max(0, self.theme.GetSelection())],
            "caret_width": int(self.caret.GetValue()),
            "focus_ring_width": int(self.focus.GetValue()),
            "line_spacing": settings_mod.LINE_SPACINGS[max(0, self.spacing.GetSelection())],
            "bold_body": bool(self.bold_body.GetValue()),
            "toolbar_labels_mode": settings_mod.TOOLBAR_LABEL_MODES[
                max(0, self.toolbar_labels.GetSelection())],
        }

    def _on_display_change(self, _event=None):
        """Applied at once, so the effect is on the screen before you commit."""
        values = self.display_values()
        values["toolbar_labels"] = values["toolbar_labels_mode"] != "icons"
        self.settings.update(values)
        if self._ring is not None:
            self._ring.set_width(values["focus_ring_width"])
        applier = getattr(self.frame, "apply_display", None)
        if applier is not None:
            try:
                applier()
            except Exception:
                pass

    def _build_document(self):
        panel, sizer = self._page("Document defaults")
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.page_size = add_row(panel, grid, "&Page size:",
                                 wx.Choice(panel, choices=[PAGE_LABELS[s] for s in C.PAGE_SIZES]))
        name_field(self.page_size, "Page size")
        size = self.settings.get("page_size", C.DEFAULT_PAGE_SIZE)
        self.page_size.SetSelection(C.PAGE_SIZES.index(size) if size in C.PAGE_SIZES else 0)
        self.margins = wx.SpinCtrlDouble(panel, min=0.25, max=3.0, inc=0.25,
                                         initial=float(self.settings.get("margin_inches", C.DEFAULT_MARGIN_INCHES)))
        self.margins.SetDigits(2)
        add_row(panel, grid, "&Margins, in inches:", self.margins, name="Margins in inches")
        self.font = wx.ComboBox(panel, value=self.settings.get("font_family", C.DEFAULT_FONT_FAMILY),
                                choices=list(FONTS))
        add_row(panel, grid, "&Font:", self.font, name="Font")
        self.font.SetToolTip("A font family list as a web page would write it. The "
                             "first one that is installed is used.")
        self.points = wx.SpinCtrl(panel, min=6, max=36,
                                  initial=int(self.settings.get("font_points", C.DEFAULT_FONT_POINTS)))
        add_row(panel, grid, "Font &size, in points:", self.points, name="Font size in points")
        self.language = LanguagePicker(panel)
        self.language.add_to(panel, grid)
        self.language.value = self.settings.get("lang", "en-US")
        self.author = add_row(panel, grid, "&Author for new documents:",
                              wx.TextCtrl(panel, value=self.settings.get("author", "")))
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        note = wx.StaticText(panel, label=(
            "These apply to new documents. Alt+Enter changes the open document."))
        note.Wrap(self.FromDIP(480))
        sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

    def _build_ai(self):
        try:
            from .ai_settings_page import AISettingsPage
        except ImportError:
            AISettingsPage = None
        if AISettingsPage is None:
            panel, sizer = self._page("AI")
            note = wx.StaticText(panel, label=(
                "The AI settings page is not part of this build yet. Describing "
                "pictures needs it."))
            note.Wrap(self.FromDIP(480))
            sizer.Add(note, 0, wx.ALL, 12)
            return
        try:
            self.ai_page = AISettingsPage(self.tabs, self.settings)
            name_field(self.ai_page, "AI")
            self.tabs.AddPage(self.ai_page, "AI")
        except Exception as exc:
            panel, sizer = self._page("AI")
            note = wx.StaticText(panel, label="The AI settings page could not open. %s" % exc)
            note.Wrap(self.FromDIP(480))
            sizer.Add(note, 0, wx.ALL, 12)

    def _on_ok(self, _event):
        self._on_display_change(None)
        self.settings["speech_level"] = C.SPEECH_LEVELS[max(0, self.speech.GetSelection())]
        self.settings["page_size"] = C.PAGE_SIZES[max(0, self.page_size.GetSelection())]
        self.settings["margin_inches"] = round(float(self.margins.GetValue()), 2)
        self.settings["font_family"] = self.font.GetValue().strip() or C.DEFAULT_FONT_FAMILY
        self.settings["font_points"] = int(self.points.GetValue())
        self.settings["lang"] = self.language.value
        self.settings["author"] = self.author.GetValue().strip()
        if self.ai_page is not None:
            try:
                self.ai_page.apply()
            except Exception as exc:
                speaker = getattr(self.frame, "announce", None)
                if speaker:
                    speaker("The AI settings could not be saved. %s" % exc)
        self.EndModal(wx.ID_OK)
