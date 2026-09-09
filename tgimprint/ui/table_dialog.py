"""Insert table (Ctrl+Shift+T): rows, columns, and a header row by default."""
import wx

from .dialogs import add_row


class TableDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Insert table", style=wx.DEFAULT_DIALOG_STYLE)
        self.result = None
        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.rows = wx.SpinCtrl(self, min=1, max=100, initial=3)
        add_row(self, grid, "&Rows:", self.rows, name="Rows")
        self.columns = wx.SpinCtrl(self, min=1, max=20, initial=3)
        add_row(self, grid, "&Columns:", self.columns, name="Columns")
        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        self.header = wx.CheckBox(self, label="The first row holds the column &headings")
        self.header.SetValue(True)
        self.header.SetToolTip("Header cells tell a screen reader what each column "
                               "is, in every row. Leave this on unless the table "
                               "really has no headings.")
        outer.Add(self.header, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        note = wx.StaticText(self, label="Tab and Shift+Tab move between cells, and "
                                         "Tab in the last cell adds a row.")
        note.Wrap(self.FromDIP(380))
        outer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        buttons = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK, "&Insert table")
        cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.AddButton(ok)
        buttons.AddButton(cancel)
        buttons.Realize()
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, self._on_ok)
        outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.rows.SetFocus()

    def _on_ok(self, _event):
        self.result = (int(self.rows.GetValue()), int(self.columns.GetValue()),
                       bool(self.header.GetValue()))
        self.EndModal(wx.ID_OK)
