"""The structure navigator (Alt+F6): every heading, Enter jumps to it."""
import wx

from .dialogs import name_field


class StructureDialog(wx.Dialog):
    def __init__(self, parent, frame, headings):
        super().__init__(parent, title="Structure navigator",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.headings = list(headings or [])
        outer = wx.BoxSizer(wx.VERTICAL)
        count = len(self.headings)
        outer.Add(wx.StaticText(self, label="&Headings, %d in the document:" % count),
                  0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        items = ["%sHeading %d: %s" % ("    " * (h["level"] - 1), h["level"],
                                        h["text"] or "(empty heading)")
                 for h in self.headings] or ["No headings yet. Ctrl+Alt+1 makes one."]
        self.list = wx.ListBox(self, choices=items, size=self.FromDIP(wx.Size(520, 300)))
        name_field(self.list, "Headings")
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        go = wx.Button(self, wx.ID_OK, "&Go to heading")
        close = wx.Button(self, wx.ID_CANCEL, "&Close")
        row.Add(go, 0, wx.RIGHT, 8)
        row.Add(close, 0)
        outer.Add(row, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        go.SetDefault()
        go.Bind(wx.EVT_BUTTON, self._on_go)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_go)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        if self.headings:
            self.list.SetSelection(0)
        self.list.SetFocus()

    def _on_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_go(None)
            return
        event.Skip()

    def _on_go(self, _event):
        index = self.list.GetSelection()
        if not self.headings or index < 0:
            self.EndModal(wx.ID_CANCEL)
            return
        self.result = index
        self.EndModal(wx.ID_OK)
