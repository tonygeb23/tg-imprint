"""Document properties: title, author, language, subject, page size, margins.

Alt+Enter with no picture at the caret. Writes nothing until OK; the window
applies `result`. The title is required before an export, so the window
opens this with focus in the title field when it is blank, and there is no
"Untitled" written into any PDF.
"""
import wx

from .. import constants as C
from .dialogs import add_row, name_field

#: Common BCP-47 tags, offered in the picker. Anything else goes in the
#: custom field.
LANGUAGES = [
    ("en-US", "English (United States)"),
    ("en-GB", "English (United Kingdom)"),
    ("en-AU", "English (Australia)"),
    ("en-CA", "English (Canada)"),
    ("es-ES", "Spanish (Spain)"),
    ("es-MX", "Spanish (Mexico)"),
    ("fr-FR", "French (France)"),
    ("fr-CA", "French (Canada)"),
    ("de-DE", "German"),
    ("it-IT", "Italian"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("nl-NL", "Dutch"),
    ("sv-SE", "Swedish"),
    ("pl-PL", "Polish"),
    ("zh-CN", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"),
    ("ja-JP", "Japanese"),
    ("ko-KR", "Korean"),
    ("hi-IN", "Hindi"),
]
LANG_CODES = [c for c, _ in LANGUAGES]
LANG_LABELS = ["%s, %s" % (label, code) for code, label in LANGUAGES]
PAGE_LABELS = {"letter": "Letter, 8.5 by 11 inches", "A4": "A4",
               "legal": "Legal, 8.5 by 14 inches"}


class LanguagePicker:
    """A choice of common languages plus a custom BCP-47 field.

    Two controls, added to a grid by `add_to`. `value` reads and writes the
    code. Shared by the properties dialog and Preferences.
    """

    def __init__(self, parent):
        self.choice = wx.Choice(parent, choices=LANG_LABELS + ["Other, typed below"])
        name_field(self.choice, "Language")
        self.choice.SetToolTip("The language of the document, which the PDF "
                               "carries so a screen reader pronounces it right.")
        self.custom = wx.TextCtrl(parent)
        name_field(self.custom, "Custom language code")
        self.custom.SetToolTip("A BCP-47 code when your language is not in the "
                               "list, such as en-NZ or fr-CH.")
        self.choice.Bind(wx.EVT_CHOICE, self._on_choice)

    def add_to(self, parent, grid):
        add_row(parent, grid, "&Language:", self.choice)
        add_row(parent, grid, "&Other language code:", self.custom)

    def _on_choice(self, _event):
        index = self.choice.GetSelection()
        if 0 <= index < len(LANG_CODES):
            self.custom.SetValue("")

    @property
    def value(self):
        custom = self.custom.GetValue().strip()
        if custom:
            return custom
        index = self.choice.GetSelection()
        return LANG_CODES[index] if 0 <= index < len(LANG_CODES) else "en-US"

    @value.setter
    def value(self, code):
        code = (code or "en-US").strip()
        if code in LANG_CODES:
            self.choice.SetSelection(LANG_CODES.index(code))
            self.custom.SetValue("")
        else:
            self.choice.SetSelection(len(LANG_CODES))
            self.custom.SetValue(code)


class DocPropertiesDialog(wx.Dialog):
    def __init__(self, parent, meta, focus="title"):
        super().__init__(parent, title="Document properties",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        meta = dict(meta or {})
        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)

        self.title = add_row(self, grid, "&Title:", wx.TextCtrl(self))
        self.title.SetToolTip("Required before the PDF is made. A screen reader "
                              "says this when the PDF opens.")
        self.author = add_row(self, grid, "&Author:", wx.TextCtrl(self))
        self.language = LanguagePicker(self)
        self.language.add_to(self, grid)
        self.subject = add_row(self, grid, "&Subject:", wx.TextCtrl(self))
        self.page_size = add_row(self, grid, "&Page size:",
                                 wx.Choice(self, choices=[PAGE_LABELS[s] for s in C.PAGE_SIZES]))
        name_field(self.page_size, "Page size")
        self.margins = wx.SpinCtrlDouble(self, min=0.25, max=3.0, inc=0.25,
                                         initial=float(meta.get("margin_inches", C.DEFAULT_MARGIN_INCHES)))
        self.margins.SetDigits(2)
        add_row(self, grid, "&Margins, in inches:", self.margins, name="Margins in inches")
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 12)

        note = wx.StaticText(self, label="Title and language go into the PDF, where a "
                                         "screen reader reads them before anything else.")
        note.Wrap(self.FromDIP(440))
        outer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        buttons = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK, "OK")
        cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.AddButton(ok)
        buttons.AddButton(cancel)
        buttons.Realize()
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, self._on_ok)
        outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(460, self.GetSize().height)))
        self.CentreOnParent()

        self.title.SetValue(meta.get("title", "") or "")
        self.author.SetValue(meta.get("author", "") or "")
        self.language.value = meta.get("lang", "en-US")
        self.subject.SetValue(meta.get("subject", "") or "")
        size = meta.get("page_size", C.DEFAULT_PAGE_SIZE)
        self.page_size.SetSelection(C.PAGE_SIZES.index(size) if size in C.PAGE_SIZES else 0)
        (self.title if focus == "title" else self.author).SetFocus()
        if focus == "title":
            self.title.SelectAll()

    def _on_ok(self, _event):
        self.result = {
            "title": self.title.GetValue().strip(),
            "author": self.author.GetValue().strip(),
            "lang": self.language.value,
            "subject": self.subject.GetValue().strip(),
            "page_size": C.PAGE_SIZES[max(0, self.page_size.GetSelection())],
            "margin_inches": round(float(self.margins.GetValue()), 2),
        }
        self.EndModal(wx.ID_OK)
