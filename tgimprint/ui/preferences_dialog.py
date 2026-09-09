"""Preferences (Ctrl+,): Speech, Document defaults, and Worker C's AI page.

The speech control is worded exactly as CONVENTIONS.md says, from
constants.SPEECH_LABELS. OK writes into the settings dict the window
passed in and calls the AI page's apply(); the window saves the file and
applies the level.
"""
import wx

from .. import constants as C
from .dialogs import add_row, name_field
from .doc_properties_dialog import LanguagePicker, PAGE_LABELS

FONTS = ("Arial, Helvetica, sans-serif", "Calibri, Carlito, sans-serif",
         "Segoe UI, sans-serif", "Verdana, sans-serif", "Georgia, serif",
         "Times New Roman, Times, serif", "Cambria, serif",
         "Consolas, Courier New, monospace")


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, frame, settings):
        super().__init__(parent, title="Preferences",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.settings = settings
        self.ai_page = None
        outer = wx.BoxSizer(wx.VERTICAL)
        self.tabs = wx.Notebook(self)
        self._build_speech()
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
        self.SetMinSize(self.FromDIP(wx.Size(560, 420)))
        self.CentreOnParent()
        self.speech.SetFocus()

    def _page(self, title):
        panel = wx.Panel(self.tabs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        self.tabs.AddPage(panel, title)
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
            self.tabs.AddPage(self.ai_page, "AI")
        except Exception as exc:
            panel, sizer = self._page("AI")
            note = wx.StaticText(panel, label="The AI settings page could not open. %s" % exc)
            note.Wrap(self.FromDIP(480))
            sizer.Add(note, 0, wx.ALL, 12)

    def _on_ok(self, _event):
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
