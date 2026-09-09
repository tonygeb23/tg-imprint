"""Find and replace: modeless, window.find in the page, undoable replacements.

Ctrl+F opens it with focus in Find, Ctrl+H with focus in Replace with. F3
and Shift+F3 in the document find the next and previous match of the last
search without the dialog. Replace runs through insertText and Replace All
through the undoable route (DECISIONS.md, risk 4): the page computes the
new body on a clone by walking text nodes, keeping headings, lists and
bold, and applies it with select all plus insertHTML, so one Ctrl+Z puts
everything back.
"""
import wx

from .dialogs import add_row


class FindDialog(wx.Dialog):
    def __init__(self, parent, frame):
        super().__init__(parent, title="Find and replace",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        self.find = add_row(self, grid, "&Find:", wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER))
        self.replace = add_row(self, grid, "Re&place with:",
                               wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER))
        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        self.match_case = wx.CheckBox(self, label="&Match case")
        outer.Add(self.match_case, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.next = wx.Button(self, label="Find &next")
        self.previous = wx.Button(self, label="Find pre&vious")
        self.replace_one = wx.Button(self, label="&Replace")
        self.replace_all = wx.Button(self, label="Replace &all")
        self.close = wx.Button(self, wx.ID_CANCEL, "&Close")
        for button in (self.next, self.previous, self.replace_one, self.replace_all, self.close):
            row.Add(button, 0, wx.RIGHT, 8)
        outer.Add(row, 0, wx.ALL, 12)
        self.note = wx.StaticText(self, label="")
        outer.Add(self.note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(520, self.GetSize().height)))
        self.next.SetDefault()
        self.next.Bind(wx.EVT_BUTTON, lambda _e: self.find_next())
        self.previous.Bind(wx.EVT_BUTTON, lambda _e: self.find_previous())
        self.replace_one.Bind(wx.EVT_BUTTON, lambda _e: self.replace_current())
        self.replace_all.Bind(wx.EVT_BUTTON, lambda _e: self.replace_everything())
        self.close.Bind(wx.EVT_BUTTON, lambda _e: self.Hide())
        self.find.Bind(wx.EVT_TEXT_ENTER, lambda _e: self.find_next())
        self.replace.Bind(wx.EVT_TEXT_ENTER, lambda _e: self.replace_current())
        self.Bind(wx.EVT_CLOSE, lambda _e: self.Hide())
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.find.SetValue(getattr(frame, "find_text", "") or "")
        self.match_case.SetValue(bool(getattr(frame, "find_match_case", False)))

    def _on_key(self, event):
        code = event.GetKeyCode()
        if code == wx.WXK_ESCAPE:
            self.Hide()
            return
        if code == wx.WXK_F3:
            if event.ShiftDown():
                self.find_previous()
            else:
                self.find_next()
            return
        event.Skip()

    def open(self, replacing=False):
        self.Show()
        self.Raise()
        (self.replace if replacing else self.find).SetFocus()
        self.find.SelectAll()

    # --------------------------------------------------------- actions --
    def _terms(self):
        text = self.find.GetValue()
        self.frame.find_text = text
        self.frame.find_match_case = bool(self.match_case.GetValue())
        return text, self.frame.find_match_case

    def _say(self, text):
        self.note.SetLabel(text)
        self.frame.announce(text)

    def find_next(self):
        text, case = self._terms()
        if not text:
            self._say("Type something to find.")
            self.find.SetFocus()
            return
        self.frame.find_in_document(text, True, case, self._found)

    def find_previous(self):
        text, case = self._terms()
        if not text:
            self._say("Type something to find.")
            self.find.SetFocus()
            return
        self.frame.find_in_document(text, False, case, self._found)

    def _found(self, result):
        if result and result.get("found"):
            self._say("Found. %s" % (result.get("context") or ""))
        else:
            self._say("Not found.")

    def replace_current(self):
        text, case = self._terms()
        replacement = self.replace.GetValue()

        def done(value, _error):
            if value and value.get("replaced"):
                self.frame.find_in_document(text, True, case, self._after_replace)
            else:
                self.frame.find_in_document(text, True, case, self._found)

        self.frame.editor.call("replaceSelection", replacement, text, case, callback=done)

    def _after_replace(self, result):
        if result and result.get("found"):
            self._say("Replaced. Next: %s" % (result.get("context") or ""))
        else:
            self._say("Replaced. No more matches.")

    def replace_everything(self):
        text, case = self._terms()
        if not text:
            self._say("Type something to find.")
            self.find.SetFocus()
            return
        replacement = self.replace.GetValue()

        def done(value, error):
            count = int((value or {}).get("count") or 0)
            if error:
                self._say("Replace all failed. %s" % error)
            elif count == 0:
                self._say("Nothing to replace.")
            else:
                self._say("Replaced %d. Press Ctrl+Z in the document to put them back." % count)
                self.frame.mark_modified()

        self.frame.editor.call("replaceAll", text, replacement, case, callback=done)
