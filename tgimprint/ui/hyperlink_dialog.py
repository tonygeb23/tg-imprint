"""Insert link (Ctrl+K), and edit the link at the caret with the same dialog."""
import wx

from .dialogs import add_row


class LinkDialog(wx.Dialog):
    def __init__(self, parent, text="", href="", editing=False):
        super().__init__(parent, title="Edit link" if editing else "Insert link",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.text = add_row(self, grid, "Link &text:", wx.TextCtrl(self))
        self.text.SetToolTip("The words people read and hear. Say where the link "
                             "goes, not \"click here\".")
        self.href = add_row(self, grid, "&Address:", wx.TextCtrl(self))
        self.href.SetToolTip("A web address, an email address with mailto:, or a "
                             "phone number with tel:.")
        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        hint = wx.StaticText(self, label=(
            "Link text should make sense on its own, because a screen reader "
            "can list every link in a document out of context (WCAG 2.4.4). "
            "\"The 2026 timetable\" is better than \"click here\"."))
        hint.Wrap(self.FromDIP(440))
        outer.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        self.note = wx.StaticText(self, label="")
        outer.Add(self.note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
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
        self.text.SetValue(text or "")
        self.href.SetValue(href or "")
        (self.href if text else self.text).SetFocus()

    def _on_ok(self, _event):
        text = self.text.GetValue().strip()
        href = self.href.GetValue().strip()
        if not text:
            self.note.SetLabel("The link needs some text.")
            self.text.SetFocus()
            return
        if not href:
            self.note.SetLabel("The link needs an address.")
            self.href.SetFocus()
            return
        href = normalise_href(href)
        if href is None:
            self.note.SetLabel("The address must start with http, https, mailto or tel.")
            self.href.SetFocus()
            return
        self.result = (text, href)
        self.EndModal(wx.ID_OK)


def normalise_href(href):
    """Accept web, mail and phone addresses; add https:// to a bare domain."""
    low = href.lower()
    if low.startswith(("http://", "https://", "mailto:", "tel:")):
        return href
    if "@" in href and " " not in href and "/" not in href:
        return "mailto:" + href
    if low.startswith(("javascript:", "file:", "data:", "vbscript:")):
        return None
    if " " in href:
        return None
    return "https://" + href
