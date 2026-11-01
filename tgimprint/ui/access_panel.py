"""The Accessibility panel: what is left to do in this document.

A side panel beside the editor, native all the way through: a summary line, a
wx.ListCtrl of doccheck issues, the whole of the chosen issue in words, and a
button for anybody on a mouse. The window owns the timing (main_window.py); this
file only shows what it is given.

Rules it keeps:

- **It never moves focus and never speaks on its own.** A refresh keeps the
  same issue selected, by what it is rather than by row number.
- **The accessible name of the list never changes.** The count goes in the
  accessible description, which is only read when somebody lands on the list,
  so a refresh cannot restart an announcement.
- **Every row starts with a word, Fix or Review.** The mark beside it repeats
  that word.
- **Fix comes first**, in the order doccheck found them, then Review.

Enter, or a double click, calls `on_go(issue)`. Escape calls `on_leave()`.
"""
import wx

from . import icons
from . import theme
from .dialogs import _Named, focus_ring

#: docs/STRINGS.md, 0.3.0.
S = {
    "title": "Accessibility",
    "list_name": "Accessibility issues",
    "summary": "%d to fix, %d to review",
    "summary_none": "Nothing to fix or review",
    "summary_waiting": "Checking the document",
    "row_fix": "Fix: %s",
    "row_review": "Review: %s",
    "row_none": "Nothing left to do.",
    "detail_none": ("Every check this panel can make has passed. It cannot judge what "
                    "the words mean."),
    "go": "Go to this issue",
    "hide": "Hide this panel",
}


class _IssueList(_Named):
    """The list's accessible object. The count is the description, which a
    screen reader reads once, on arrival."""

    def __init__(self, name, panel):
        super().__init__(name)
        self.panel = panel

    def GetDescription(self, childId):
        if childId == 0:
            return (wx.ACC_OK, self.panel.summary_text())
        return (wx.ACC_NOT_IMPLEMENTED, "")


class AccessPanel(wx.Panel):
    def __init__(self, parent, on_go, on_leave, on_hide, ring=3):
        super().__init__(parent, name="Accessibility panel")
        self.on_go = on_go
        self.on_leave = on_leave
        self.on_hide = on_hide
        self.issues = []
        self.pal = None
        self._summary = S["summary_waiting"]
        self._signature = None
        self._size = self.FromDIP(16)

        self.heading = wx.StaticText(self, label=S["title"])
        self.heading.SetFont(self.GetFont().Scaled(1.25).Bold())
        self.summary = wx.StaticText(self, label=self._summary)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL
                                | wx.BORDER_NONE)
        self.list.InsertColumn(0, S["list_name"])
        accessible = _IssueList(S["list_name"], self)
        self.list._tgimprint_accessible = accessible
        self.list.SetAccessible(accessible)
        self.list.SetName(S["list_name"])
        self.rule = theme.Hairline(self)
        self.detail = wx.StaticText(self, label="")
        self.go = wx.Button(self, label=S["go"])

        outer = wx.BoxSizer(wx.VERTICAL)
        pad = self.FromDIP(14)
        outer.AddSpacer(self.FromDIP(14))
        outer.Add(self.heading, 0, wx.LEFT | wx.RIGHT, pad)
        outer.AddSpacer(self.FromDIP(3))
        outer.Add(self.summary, 0, wx.LEFT | wx.RIGHT, pad)
        outer.AddSpacer(self.FromDIP(10))
        # The list's rows have an inset of their own, so 10 lines their
        # marks up with the heading's 14.
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, self.FromDIP(10))
        outer.Add(self.rule, 0, wx.EXPAND)
        outer.AddSpacer(self.FromDIP(10))
        outer.Add(self.detail, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, pad)
        outer.AddSpacer(self.FromDIP(10))
        outer.Add(self.go, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, pad)
        self.SetSizer(outer)
        # The list draws no ring of its own that low vision can find. This
        # one is the width the Display page says, like the editor's.
        self.ring = focus_ring(self, [self.list], ring)

        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_activate)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selected)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self._on_context)
        self.list.Bind(wx.EVT_SET_FOCUS, self._on_list_focus)
        self.list.Bind(wx.EVT_SIZE, self._on_list_size)
        self.go.Bind(wx.EVT_BUTTON, lambda _e: self.go_to_selected())
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._rebuild()

    # ------------------------------------------------------------ colours --
    def set_palette(self, pal):
        self.pal = pal
        self.SetBackgroundColour(wx.NullColour)
        theme.paint(self, pal)
        theme.paint(self.heading, pal)
        theme.paint(self.summary, pal, foreground=pal.muted)
        theme.paint(self.detail, pal)
        theme.paint_list(self.list, pal)
        if not pal.native:
            self.rule.SetBackgroundColour(pal.rule)
        else:
            self.rule.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW))
        if self.ring is not None:
            self.ring.colour = None if pal.native else pal.second
        theme.paint_button(self.go, pal)
        theme.scrollbars_follow(self.list, pal)
        keep = self._identity(self.selected_issue())
        self._load_images()
        self._rebuild(keep)
        self.Refresh()

    def _load_images(self):
        pal = self.pal if self.pal is not None else theme.palette("high_contrast")
        images = wx.ImageList(self._size, self._size)
        images.Add(icons.draw("fix", self._size, pal))
        images.Add(icons.draw("review", self._size, pal))
        self.list.AssignImageList(images, wx.IMAGE_LIST_SMALL)

    # ------------------------------------------------------------- issues --
    def summary_text(self):
        return self._summary

    def set_issues(self, issues):
        """Show these issues. Never takes focus, never speaks."""
        ordered = ([i for i in issues if i.severity == "fix"]
                   + [i for i in issues if i.severity != "fix"])
        fixes = sum(1 for i in ordered if i.severity == "fix")
        reviews = len(ordered) - fixes
        self._summary = (S["summary"] % (fixes, reviews) if ordered else S["summary_none"])
        self.summary.SetLabel(self._summary)
        signature = [(i.key, i.severity, i.message, i.kind, i.ordinal) for i in ordered]
        keep = self._identity(self.selected_issue())
        self.issues = ordered
        if signature != self._signature:
            self._signature = signature
            self._rebuild(keep)

    @staticmethod
    def _identity(issue):
        return (issue.key, issue.kind, issue.ordinal, issue.message) if issue else None

    def _rebuild(self, keep=None):
        if self.pal is None:
            return
        self.list.Freeze()
        try:
            self.list.DeleteAllItems()
            if not self.issues and self._summary != S["summary_waiting"]:
                self.list.InsertItem(0, S["row_none"], -1)
            for index, issue in enumerate(self.issues):
                fix = issue.severity == "fix"
                text = (S["row_fix"] if fix else S["row_review"]) % issue.message
                self.list.InsertItem(index, text, 0 if fix else 1)
        finally:
            self.list.Thaw()
        target = 0
        for index, issue in enumerate(self.issues):
            if self._identity(issue) == keep:
                target = index
                break
        if self.list.GetItemCount():
            self.list.Focus(target)
            self.list.Select(target)
        self._show_detail()
        self._fit_column()

    def selected_issue(self):
        index = self.list.GetFirstSelected()
        if 0 <= index < len(self.issues):
            return self.issues[index]
        return None

    def _show_detail(self):
        issue = self.selected_issue()
        text = issue.message if issue else (S["detail_none"] if self._signature == [] else "")
        self.detail.SetLabel(text)
        self.detail.Wrap(max(self.FromDIP(120), self.GetClientSize().width - self.FromDIP(28)))
        self.go.Enable(issue is not None)
        self.Layout()

    def go_to_selected(self):
        issue = self.selected_issue()
        if issue is not None:
            self.on_go(issue)

    def focus_list(self):
        self.list.SetFocus()

    # ------------------------------------------------------------- events --
    def _on_activate(self, _event):
        self.go_to_selected()

    def _on_selected(self, event):
        event.Skip()
        self._show_detail()

    def _on_list_focus(self, event):
        event.Skip()
        if self.list.GetItemCount() and self.list.GetFirstSelected() < 0:
            self.list.Focus(0)
            self.list.Select(0)

    def _on_context(self, _event):
        menu = wx.Menu()
        go = menu.Append(wx.ID_ANY, "&" + S["go"])
        go.Enable(self.selected_issue() is not None)
        hide = menu.Append(wx.ID_ANY, "&" + S["hide"])
        self.Bind(wx.EVT_MENU, lambda _e: self.go_to_selected(), go)
        self.Bind(wx.EVT_MENU, lambda _e: self.on_hide(), hide)
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_key(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.on_leave()
            return
        event.Skip()

    def _fit_column(self):
        width = self.list.GetClientSize().width
        if width > 0:
            self.list.SetColumnWidth(0, width)

    def _on_list_size(self, event):
        event.Skip()
        wx.CallAfter(self._fit_if_alive)

    def _fit_if_alive(self):
        if self:
            self._fit_column()

    def _on_size(self, event):
        event.Skip()
        wx.CallAfter(self._wrap_if_alive)

    def _wrap_if_alive(self):
        if self:
            self._show_detail()
