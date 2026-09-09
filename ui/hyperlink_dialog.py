"""
Insert Hyperlink dialog — opened by Ctrl+K.

WebAIM guidance embedded here:
  - The "Display text" field should contain meaningful, descriptive text
    (not "click here" or a raw URL) so screen-reader users understand the
    link purpose from the link text alone (WCAG 2.4.4).
  - The URL field accepts any valid absolute URL or mailto: address.

NVDA behaviour in the editor:
  - Link text is read as ordinary text when the caret moves through it.
  - In the exported PDF, Adobe Reader / NVDA announces "link" before the
    display text when the user tabs through interactive elements.

Tab order: Display text field → URL field → OK → Cancel.
"""
from __future__ import annotations

import wx


class HyperlinkDialog(wx.Dialog):
    """
    Modal dialog for inserting or editing a hyperlink.

    Usage:
        with HyperlinkDialog(parent, selected_text) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                text, url = dlg.get_result()
    """

    def __init__(self, parent: wx.Window, selected_text: str = "") -> None:
        super().__init__(
            parent,
            title="Insert Hyperlink",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self._selected_text = selected_text
        self._build_ui()
        self.Fit()
        self.SetMinSize((420, self.GetSize().height))
        self.Centre()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Build directly on the dialog — no inner panel — so the
        # OK/Cancel buttons (which are dialog children) live in the same
        # parent as the rest of the layout.  Using an inner wx.Panel
        # silently breaks button hit-testing because the buttons render
        # underneath the panel.
        outer = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=2, cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        text_lbl = wx.StaticText(self, label="&Display text:")
        self._text_ctrl = wx.TextCtrl(self)
        self._text_ctrl.SetName("Link display text field")
        self._text_ctrl.SetToolTip(
            "The text readers will see and NVDA will announce. "
            "Use a meaningful description, not the URL itself (WCAG 2.4.4)."
        )
        self._text_ctrl.SetValue(self._selected_text)
        grid.Add(text_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._text_ctrl, 1, wx.EXPAND)

        url_lbl = wx.StaticText(self, label="&URL:")
        self._url_ctrl = wx.TextCtrl(self)
        self._url_ctrl.SetName("URL field")
        self._url_ctrl.SetToolTip(
            "Full web address (e.g. https://webaim.org) or email address "
            "(e.g. mailto:name@example.com)."
        )
        grid.Add(url_lbl,        0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._url_ctrl, 1, wx.EXPAND)

        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)

        hint = wx.StaticText(
            self,
            label=(
                "Tip: Use descriptive link text so screen-reader users\n"
                "understand the destination without context (WCAG 2.4.4)."
            ),
        )
        hint.SetForegroundColour(wx.Colour(80, 80, 80))
        outer.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        outer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 12)

        self.SetSizerAndFit(outer)

        ok_btn = self.FindWindowById(wx.ID_OK,    self)
        if ok_btn:
            ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        ok_btn.SetDefault()

        if self._selected_text:
            self._url_ctrl.SetFocus()
        else:
            self._text_ctrl.SetFocus()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_ok(self, event: wx.CommandEvent) -> None:
        text = self._text_ctrl.GetValue().strip()
        url  = self._url_ctrl.GetValue().strip()

        if not text:
            wx.MessageBox("Please enter display text for the link.",
                          "Display text required", wx.OK | wx.ICON_WARNING, self)
            self._text_ctrl.SetFocus()
            return

        if not url:
            wx.MessageBox("Please enter a URL for the link.",
                          "URL required", wx.OK | wx.ICON_WARNING, self)
            self._url_ctrl.SetFocus()
            return

        # Auto-prefix bare URLs so they work in PDF
        if not (url.startswith("http") or url.startswith("mailto:")
                or url.startswith("ftp:")):
            url = "https://" + url
            self._url_ctrl.SetValue(url)

        self.EndModal(wx.ID_OK)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_result(self) -> tuple[str, str]:
        """Call after ShowModal() == wx.ID_OK. Returns (display_text, url)."""
        return (
            self._text_ctrl.GetValue().strip(),
            self._url_ctrl.GetValue().strip(),
        )
