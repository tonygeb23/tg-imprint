"""
Document Properties dialog.

Collects the metadata embedded in the PDF/UA-1 output:
  - Title     (required for PDF/UA — DisplayDocTitle)
  - Author
  - Language  (BCP-47 tag; required for PDF/UA /Lang entry)

All fields are properly labelled so NVDA announces them on focus.
"""
from __future__ import annotations

import wx


# Common BCP-47 language tags offered in the picker
_LANGUAGES = [
    ("en-US", "English (United States)"),
    ("en-GB", "English (United Kingdom)"),
    ("en-AU", "English (Australia)"),
    ("es-ES", "Spanish (Spain)"),
    ("es-MX", "Spanish (Mexico)"),
    ("fr-FR", "French (France)"),
    ("de-DE", "German (Germany)"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("zh-CN", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"),
    ("ja-JP", "Japanese"),
    ("ko-KR", "Korean"),
    ("ar-SA", "Arabic (Saudi Arabia)"),
]
_LANG_CODES   = [c for c, _ in _LANGUAGES]
_LANG_LABELS  = [f"{label} [{code}]" for code, label in _LANGUAGES]


class DocPropertiesDialog(wx.Dialog):
    """
    Modal dialog for document metadata.

    Usage:
        with DocPropertiesDialog(parent, props) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                props = dlg.get_result()   # dict with title/author/lang
    """

    def __init__(
        self,
        parent: wx.Window,
        props: dict | None = None,
    ) -> None:
        super().__init__(
            parent,
            title="Document Properties",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self._props = props or {}
        self._build_ui()
        self._populate(self._props)
        self.Fit()
        self.SetMinSize((420, self.GetSize().height))
        self.Centre()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Build directly on the dialog so the OK/Cancel buttons (which
        # CreateStdDialogButtonSizer parents to the dialog) live in the
        # same parent as the rest of the controls — otherwise the
        # buttons render under the inner panel and become unclickable.
        vbox = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=4, cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        title_lbl = wx.StaticText(self, label="Document &title:")
        self._title_ctrl = wx.TextCtrl(self)
        self._title_ctrl.SetName("Document title field")
        self._title_ctrl.SetToolTip(
            "Required for PDF/UA compliance. "
            "Screen readers announce this as the document name."
        )
        grid.Add(title_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._title_ctrl, 1, wx.EXPAND)

        author_lbl = wx.StaticText(self, label="&Author:")
        self._author_ctrl = wx.TextCtrl(self)
        self._author_ctrl.SetName("Author field")
        grid.Add(author_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._author_ctrl, 1, wx.EXPAND)

        lang_lbl = wx.StaticText(self, label="&Language:")
        self._lang_choice = wx.Choice(self, choices=_LANG_LABELS)
        self._lang_choice.SetName("Document language picker")
        self._lang_choice.SetToolTip(
            "Required for PDF/UA. Sets the /Lang entry so screen readers "
            "use the correct pronunciation rules."
        )
        grid.Add(lang_lbl,          0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._lang_choice, 1, wx.EXPAND)

        custom_lbl = wx.StaticText(self, label="Custom &code (BCP-47):")
        self._lang_custom = wx.TextCtrl(self)
        self._lang_custom.SetName("Custom language code")
        self._lang_custom.SetToolTip(
            "Type a BCP-47 code directly if your language isn't in the list "
            "(e.g. en-CA, fr-CH)."
        )
        grid.Add(custom_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._lang_custom, 1, wx.EXPAND)

        vbox.Add(grid, 0, wx.EXPAND | wx.ALL, 12)

        note = wx.StaticText(
            self,
            label="Title and Language are required for PDF/UA-1 compliance.",
        )
        note.SetForegroundColour(wx.Colour(80, 80, 80))
        vbox.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 12)

        self.SetSizerAndFit(vbox)
        ok_btn = self.FindWindowById(wx.ID_OK, self)
        if ok_btn:
            ok_btn.SetDefault()

        self._lang_choice.Bind(wx.EVT_CHOICE, self._on_lang_choice)

    # ------------------------------------------------------------------
    # Populate / read
    # ------------------------------------------------------------------

    def _populate(self, props: dict) -> None:
        self._title_ctrl.SetValue(props.get("title", ""))
        self._author_ctrl.SetValue(props.get("author", ""))

        lang = props.get("lang", "en-US")
        if lang in _LANG_CODES:
            self._lang_choice.SetSelection(_LANG_CODES.index(lang))
            self._lang_custom.SetValue("")
        else:
            self._lang_choice.SetSelection(wx.NOT_FOUND)
            self._lang_custom.SetValue(lang)

    def _on_lang_choice(self, event: wx.CommandEvent) -> None:
        # Clear custom field when a standard language is picked
        self._lang_custom.SetValue("")

    def get_result(self) -> dict:
        """Call after ShowModal() == wx.ID_OK."""
        custom = self._lang_custom.GetValue().strip()
        if custom:
            lang = custom
        else:
            idx = self._lang_choice.GetSelection()
            lang = _LANG_CODES[idx] if idx != wx.NOT_FOUND else "en-US"

        return {
            "title":  self._title_ctrl.GetValue().strip() or "Untitled",
            "author": self._author_ctrl.GetValue().strip(),
            "lang":   lang,
        }
