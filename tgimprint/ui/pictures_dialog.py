"""Pictures (Ctrl+Shift+Alt+P): every picture, its description, and the two
buttons an imported PDF needs first: Edit and Describe.

Each row says what the description is and where it came from: "no
description", "described by AI" or "recovered from the PDF, please check",
from the img's data-alt-source and data-needs-alt.
"""
import wx

from .dialogs import name_field


def describe_row(index, picture):
    alt = (picture.get("alt") or "").strip()
    if picture.get("decorative"):
        text = "decorative, no description needed"
    elif not alt:
        text = "no description"
    else:
        text = alt if len(alt) <= 90 else alt[:87] + "..."
    source = picture.get("altSource") or ""
    if source.startswith("ai"):
        provider = source.partition(":")[2]
        text += ", described by AI%s" % (" (%s)" % provider if provider else "")
    elif source == "pdf":
        text += ", recovered from the PDF, please check"
    elif picture.get("needsAlt") and alt:
        text += ", please check"
    caption = (picture.get("caption") or "").strip()
    if caption:
        text += ", caption: %s" % caption
    return "Picture %d: %s" % (index + 1, text)


class PicturesDialog(wx.Dialog):
    def __init__(self, parent, frame, pictures):
        super().__init__(parent, title="Pictures",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.pictures = list(pictures or [])
        self.result = None
        outer = wx.BoxSizer(wx.VERTICAL)
        self.heading = wx.StaticText(self, label="")
        outer.Add(self.heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.list = wx.ListBox(self, size=self.FromDIP(wx.Size(600, 280)))
        name_field(self.list, "Pictures")
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.go = wx.Button(self, label="&Go to picture")
        self.edit = wx.Button(self, label="&Edit description...")
        self.describe = wx.Button(self, label="Describe with &AI...")
        close = wx.Button(self, wx.ID_CANCEL, "&Close")
        for button in (self.go, self.edit, self.describe, close):
            row.Add(button, 0, wx.RIGHT, 8)
        outer.Add(row, 0, wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(520, 300)))
        self.CentreOnParent()
        self.go.Bind(wx.EVT_BUTTON, lambda _e: self._act("go"))
        self.edit.Bind(wx.EVT_BUTTON, lambda _e: self._act("edit"))
        self.describe.Bind(wx.EVT_BUTTON, lambda _e: self._act("describe"))
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda _e: self._act("edit"))
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.edit.SetDefault()
        self.fill(self.pictures)
        self.list.SetFocus()

    def fill(self, pictures, select=0):
        self.pictures = list(pictures or [])
        self.list.Set([describe_row(i, p) for i, p in enumerate(self.pictures)]
                      or ["No pictures in the document."])
        missing = sum(1 for p in self.pictures
                      if not p.get("decorative") and not (p.get("alt") or "").strip())
        check = sum(1 for p in self.pictures
                    if (p.get("alt") or "").strip() and (p.get("altSource") or "") in ("pdf",))
        parts = ["%d picture%s" % (len(self.pictures), "" if len(self.pictures) == 1 else "s")]
        if missing:
            parts.append("%d without a description" % missing)
        if check:
            parts.append("%d recovered from a PDF and not yet checked" % check)
        self.heading.SetLabel("&Pictures: " + ", ".join(parts) + ".")
        for button in (self.go, self.edit, self.describe):
            button.Enable(bool(self.pictures))
        if self.pictures:
            self.list.SetSelection(min(select, len(self.pictures) - 1))

    def _on_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._act("edit")
            return
        event.Skip()

    def _act(self, what):
        index = self.list.GetSelection()
        if not self.pictures or index < 0:
            return
        self.result = (what, index)
        self.EndModal(wx.ID_OK)
