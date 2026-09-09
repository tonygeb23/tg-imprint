"""Small dialogs and the helpers every dialog here is built from.

The shape of everything, from CONVENTIONS.md and the standing rules:

- Anything somebody might want to re-read is a read-only multiline field
  with focus in it, never a wx.MessageBox. A screen reader reads a message
  box once and there is no way back over it.
- Every control has an accessible name: a static label in front of it, or
  a _Named accessible object where a static cannot go (SetName alone is not
  the accessible name on Windows; measured in Drop Deck).
- Controls are built directly on the dialog, never on an inner panel with
  CreateButtonSizer: the April image dialog's OK button was unclickable
  because of exactly that.
- Escape closes and never deletes.
"""
import wx

from .. import constants as C


class _Named(wx.Accessible):
    """An accessible object that answers one question: what is this."""

    def __init__(self, name):
        super().__init__()
        self._name = name

    def GetName(self, childId):
        if childId == 0:
            return (wx.ACC_OK, self._name)
        return (wx.ACC_NOT_IMPLEMENTED, "")


def name_field(control, name):
    """Make a control say what it is to a screen reader, not just to wx.

    The accessible is stored on the control on purpose: wx does not take
    ownership, and one left as a local is collected the moment the function
    returns, after which the control reports no name at all.
    """
    control.SetName(name)
    target = control
    for child in control.GetChildren():
        if isinstance(child, wx.TextCtrl):
            target = child
            break
    accessible = _Named(name)
    control._easypdf_accessible = accessible
    target.SetAccessible(accessible)
    return control


class QuietBitmap(wx.StaticBitmap):
    """A preview that refuses focus, so Tab never lands on a picture."""

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False


def labelled(parent, sizer, label, control, flag=wx.EXPAND, border=10, proportion=0):
    """A static label above a control, both added to `sizer`."""
    sizer.Add(wx.StaticText(parent, label=label), 0,
              wx.LEFT | wx.RIGHT | wx.TOP, border)
    sizer.Add(control, proportion, flag | wx.LEFT | wx.RIGHT | wx.TOP, border)
    return control


def add_row(parent, grid, label, control, name=None):
    """A label and a control in a two column FlexGridSizer.

    The caller has already made the control, so the static is made after
    it; it is then moved in front in the tab order, which on Windows is the
    window order, because a screen reader names an unnamed field from the
    static that comes BEFORE it in that order, not from where the sizer
    puts it on screen.
    """
    static = wx.StaticText(parent, label=label)
    static.MoveBeforeInTabOrder(control)
    grid.Add(static, 0, wx.ALIGN_CENTER_VERTICAL)
    grid.Add(control, 1, wx.EXPAND)
    if name:
        name_field(control, name)
    return control


def button_row(dialog, buttons):
    """Right aligned buttons. `buttons` is a list of (id, label, handler)."""
    sizer = wx.StdDialogButtonSizer()
    made = []
    for wid, label, handler in buttons:
        button = wx.Button(dialog, wid, label)
        if handler is not None:
            button.Bind(wx.EVT_BUTTON, handler)
        if wid in (wx.ID_OK, wx.ID_CANCEL, wx.ID_YES, wx.ID_NO, wx.ID_APPLY,
                   wx.ID_HELP, wx.ID_CLOSE, wx.ID_SAVE):
            sizer.AddButton(button)
        else:
            sizer.Add(button, 0, wx.LEFT, 6)
        made.append(button)
    sizer.Realize()
    return sizer, made


class TextDialog(wx.Dialog):
    """A message, or a report, in a read-only field with focus in it.

    `buttons` is a list of (label, result) pairs; the first is the default
    and Enter chooses it, Escape returns `escape_result` (the last button's
    result by default). `result` is what was chosen, or None.
    """

    def __init__(self, parent, title, text, buttons=(("&Close", "close"),),
                 field_label="&Message", size=(560, 260), escape_result=None):
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        self._buttons = list(buttons)
        self._escape_result = escape_result if escape_result is not None else self._buttons[-1][1]
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(wx.StaticText(self, label=field_label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.field = wx.TextCtrl(self, value=text,
                                 style=wx.TE_READONLY | wx.TE_MULTILINE,
                                 size=self.FromDIP(wx.Size(*size)))
        outer.Add(self.field, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        self.controls = []
        for index, (label, value) in enumerate(self._buttons):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, lambda _e, v=value: self._finish(v))
            row.Add(button, 0, wx.LEFT, 8)
            self.controls.append(button)
            if index == 0:
                button.SetDefault()
        outer.Add(row, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(360, 200)))
        self.CentreOnParent()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, lambda _e: self._finish(self._escape_result))
        self.field.SetFocus()
        self.field.SetInsertionPoint(0)

    def _finish(self, value):
        self.result = value
        if self.IsModal():
            self.EndModal(wx.ID_OK if value == self._buttons[0][1] else wx.ID_CANCEL)
        else:
            self.Show(False)

    def _on_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.ShiftDown():
            focus = wx.Window.FindFocus()
            if isinstance(focus, wx.Button) and focus in self.controls:
                event.Skip()
                return
            self._finish(self._buttons[0][1])
            return
        if code == wx.WXK_ESCAPE:
            self._finish(self._escape_result)
            return
        event.Skip()


def show_text(parent, title, text, field_label="&Message"):
    """A message that can be re-read, modal, one Close button."""
    dialog = TextDialog(parent, title, text, field_label=field_label)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()


def ask(parent, title, text, yes="&Yes", no="&No", field_label="&Question"):
    """A yes or no question with a re-readable field. True for yes."""
    dialog = TextDialog(parent, title, text, buttons=((yes, True), (no, False)),
                        field_label=field_label, size=(520, 180), escape_result=False)
    try:
        dialog.ShowModal()
        return dialog.result is True
    finally:
        dialog.Destroy()


def unsaved_changes(parent, name):
    """Save, Don't Save or Cancel. Returns "save", "discard" or "cancel"."""
    with wx.MessageDialog(
            parent, "Save the changes to %s?" % name, "Unsaved changes",
            wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_WARNING) as dialog:
        dialog.SetYesNoCancelLabels("&Save", "&Don't Save", "&Cancel")
        answer = dialog.ShowModal()
    if answer == wx.ID_YES:
        return "save"
    if answer == wx.ID_NO:
        return "discard"
    return "cancel"


class RecoveryDialog(TextDialog):
    """Offer a snapshot left by a run that did not close cleanly."""

    def __init__(self, parent, entries):
        lines = ["%s did not close properly last time, and %d unsaved "
                 "document%s can be recovered:" % (C.APP_NAME, len(entries),
                                                   "" if len(entries) == 1 else "s"), ""]
        for _snapshot, source, saved_at, title in entries:
            lines.append("%s, saved %s" % (title or source or "Untitled", saved_at))
        lines.append("")
        lines.append("Recover opens the most recent one. Delete throws them all "
                     "away. Not now leaves them for next time.")
        super().__init__(parent, "Recover unsaved work", "\n".join(lines),
                         buttons=(("&Recover", "recover"), ("&Delete them", "delete"),
                                  ("&Not now", "later")),
                         field_label="&Recovered documents", escape_result="later")


class KeyboardHelpDialog(TextDialog):
    """F1: the keys, as readable text, modeless so it can stay open."""

    def __init__(self, parent, text):
        super().__init__(parent, "Keyboard shortcuts", text,
                         field_label="&Shortcuts", size=(680, 460))
        self.SetMinSize(self.FromDIP(wx.Size(480, 300)))


class BusyDialog(wx.Dialog):
    """A step by step progress window that speaks its steps.

    `frame.announce_help` gets every step, so a screen reader user hears
    the export or the import move; the gauge pulses for anyone watching.
    """

    def __init__(self, parent, frame, title, first_line):
        super().__init__(parent, title=title,
                         style=wx.CAPTION | wx.SYSTEM_MENU)
        self.frame = frame
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(wx.StaticText(self, label="&Progress"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.log = wx.TextCtrl(self, value=first_line, style=wx.TE_READONLY | wx.TE_MULTILINE,
                               size=self.FromDIP(wx.Size(440, 140)))
        outer.Add(self.log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        self.bar = wx.Gauge(self, range=100, size=self.FromDIP(wx.Size(440, 22)))
        name_field(self.bar, "Progress")
        outer.Add(self.bar, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.log.SetFocus()
        self.log.SetInsertionPointEnd()
        self._pulse = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda _e: self.bar.Pulse(), self._pulse)
        self._pulse.Start(120)
        self.Bind(wx.EVT_CLOSE, lambda e: None)     # closes when the work says so

    def step(self, text):
        """Called from any thread."""
        wx.CallAfter(self._step, text)

    def _step(self, text):
        if not self:
            return
        self.log.AppendText("\n" + text)
        speaker = getattr(self.frame, "announce_help", None)
        if speaker is not None:
            try:
                speaker(text)
            except Exception:
                pass

    def finish(self):
        try:
            self._pulse.Stop()
        except Exception:
            pass
        self.Destroy()
