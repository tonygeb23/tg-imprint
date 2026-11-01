"""The start screen: what shows when nothing is open.

A native panel, not an empty editor. Plain wx.Buttons, then the recent
documents in a plain list. Focus starts on the first button. A button names a
keymap action and the window runs it, so a button and its menu item can never
do different things.

Two columns, and Tab walks them in the order the eye does: New, Open, the
recent list, then the four PDF jobs.

The mark at the top is decoration and refuses focus. Each button has a real
accessible name, and the line under it is also its accessible description, so
nothing a sighted person reads here is out of reach.
"""
import os

import wx

from .. import appicon
from .. import constants as C
from . import icons
from . import theme
from .dialogs import QuietBitmap, name_field

#: docs/STRINGS.md, 0.3.0. (action, button, what it is for). "new" is first
#: because focus starts on it.
WRITE = (("new", "New document", "Start with a blank page."),
         ("open", "Open a document", "TG Imprint, Word, Markdown, a web page or a PDF."))
PDFS = (("make_accessible", "Make a PDF accessible",
         "Bring it in, fix what is left, export a tagged copy."),
        ("check_pdf", "Analyse a PDF", "Find out what a screen reader will make of it."),
        ("repair_pdf", "Repair a PDF", "Keep the pages as they are and fix what can be fixed."),
        ("fill_form", "Fill in a PDF form", "One field at a time, from a list."))
HEADINGS = {"write": "Write", "pdf": "A PDF you already have", "recent": "Recent documents"}
NO_RECENT = "Documents you open will be listed here."

COLUMN_DIP = 320
GAP_DIP = 40


class StartPanel(wx.ScrolledWindow):
    """`frame.perform(action)` is what a button does."""

    def __init__(self, parent, frame):
        super().__init__(parent, style=wx.TAB_TRAVERSAL | wx.VSCROLL, name="Start")
        self.frame = frame
        self.pal = None
        self.SetScrollRate(0, self.FromDIP(16))
        self.buttons = {}
        self.notes = []
        self.section_labels = []
        self.recent_paths = []

        self.mark = QuietBitmap(self, bitmap=appicon.bitmap(self.FromDIP(52)))
        self.name_text = wx.StaticText(self, label=C.APP_NAME)
        self.name_text.SetFont(self.GetFont().Scaled(2.2).Bold())
        self.tagline = wx.StaticText(self, label=C.TAGLINE)
        self.tagline.SetFont(self.GetFont().Scaled(1.1))

        # Built in Tab order: the window order is the tab order on Windows.
        left = wx.BoxSizer(wx.VERTICAL)
        self._section(left, HEADINGS["write"], WRITE)
        left.AddSpacer(self.FromDIP(10))
        self.recent_label = self._heading(HEADINGS["recent"])
        left.Add(self.recent_label, 0, wx.BOTTOM, self.FromDIP(6))
        self.recent = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL,
                                  size=self.FromDIP(wx.Size(COLUMN_DIP, 112)))
        self.recent.InsertColumn(0, HEADINGS["recent"], width=self.FromDIP(COLUMN_DIP - 24))
        name_field(self.recent, HEADINGS["recent"])
        self.recent.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _e: self._open_selected())
        self.recent.Bind(wx.EVT_SET_FOCUS, self._on_recent_focus)
        self.recent.Bind(wx.EVT_SIZE, self._on_recent_size)
        left.Add(self.recent, 0)
        self.no_recent = wx.StaticText(self, label=NO_RECENT)
        self.no_recent.Wrap(self.FromDIP(COLUMN_DIP))
        left.Add(self.no_recent, 0)

        right = wx.BoxSizer(wx.VERTICAL)
        self._section(right, HEADINGS["pdf"], PDFS)

        hero = wx.BoxSizer(wx.HORIZONTAL)
        hero.Add(self.mark, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(14))
        words = wx.BoxSizer(wx.VERTICAL)
        words.Add(self.name_text, 0)
        words.Add(self.tagline, 0, wx.TOP, self.FromDIP(1))
        hero.Add(words, 0, wx.ALIGN_CENTER_VERTICAL)

        columns = wx.BoxSizer(wx.HORIZONTAL)
        columns.Add(left, 0)
        columns.AddSpacer(self.FromDIP(GAP_DIP))
        columns.Add(right, 0)

        column = wx.BoxSizer(wx.VERTICAL)
        column.Add(hero, 0, wx.BOTTOM, self.FromDIP(22))
        column.Add(columns, 0)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer(1)
        row.Add(column, 0, wx.TOP | wx.BOTTOM, self.FromDIP(18))
        row.AddStretchSpacer(1)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddStretchSpacer(1)
        outer.Add(row, 0, wx.EXPAND)
        outer.AddStretchSpacer(2)
        self.SetSizer(outer)
        self.refresh_recent()

    def _heading(self, text):
        label = wx.StaticText(self, label=text)
        label.SetFont(self.GetFont().Scaled(1.1).Bold())
        self.section_labels.append(label)
        return label

    def _section(self, sizer, title, items):
        sizer.Add(self._heading(title), 0, wx.BOTTOM, self.FromDIP(6))
        for action, label, note in items:
            button = wx.Button(self, label=label, style=wx.BU_LEFT,
                               size=wx.Size(self.FromDIP(COLUMN_DIP), self.FromDIP(34)))
            name_field(button, label, description=note)
            button.Bind(wx.EVT_BUTTON, lambda _e, a=action: self.frame.perform(a))
            button.SetToolTip(note)
            sizer.Add(button, 0, wx.BOTTOM, self.FromDIP(2))
            text = wx.StaticText(self, label=note)
            text.Wrap(self.FromDIP(COLUMN_DIP - 8))
            sizer.Add(text, 0, wx.LEFT | wx.BOTTOM, self.FromDIP(4))
            sizer.AddSpacer(self.FromDIP(4))
            self.buttons[action] = button
            self.notes.append(text)

    # ------------------------------------------------------------- colours --
    def set_palette(self, pal):
        self.pal = pal
        theme.paint(self, pal)
        theme.paint(self.name_text, pal)
        theme.paint(self.tagline, pal, foreground=pal.muted)
        for label in self.section_labels:
            theme.paint(label, pal)
        for note in self.notes:
            theme.paint(note, pal, foreground=pal.muted)
        theme.paint(self.no_recent, pal, foreground=pal.muted)
        theme.paint_list(self.recent, pal, background=pal.raised)
        theme.scrollbars_follow(self.recent, pal)
        theme.scrollbars_follow(self, pal)
        size = self.FromDIP(20)
        for action, button in self.buttons.items():
            theme.paint_button(button, pal)
            button.SetBitmap(icons.draw(action, size, pal), wx.LEFT)
            button.SetBitmapMargins(self.FromDIP(8), 0)
        self.Refresh()

    # -------------------------------------------------------------- recent --
    def refresh_recent(self):
        self.recent_paths = list(self.frame.settings.recent_existing()[:C.RECENT_FILES])
        self.recent.DeleteAllItems()
        for index, path in enumerate(self.recent_paths):
            self.recent.InsertItem(index, os.path.basename(path))
        have = bool(self.recent_paths)
        self.recent.Show(have)
        self.no_recent.Show(not have)
        self.Layout()
        self.FitInside()
        wx.CallAfter(self._fit_column)

    def _on_recent_size(self, event):
        event.Skip()
        wx.CallAfter(self._fit_column)

    def _fit_column(self):
        if self and self.recent.GetClientSize().width > 0:
            self.recent.SetColumnWidth(0, self.recent.GetClientSize().width)

    def _on_recent_focus(self, event):
        event.Skip()
        if self.recent.GetItemCount() and self.recent.GetFirstSelected() < 0:
            self.recent.Focus(0)
            self.recent.Select(0)

    def _open_selected(self):
        index = self.recent.GetFirstSelected()
        if 0 <= index < len(self.recent_paths):
            self.frame.open_document(self.recent_paths[index])

    def focus_first(self):
        self.Scroll(0, 0)
        self.buttons["new"].SetFocus()
