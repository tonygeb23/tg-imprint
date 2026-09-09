"""
Welcome dialog — shown at startup before the main window appears.

Two primary actions (keyboard-navigable, NVDA-friendly):
  New Document  — start blank
  Open Document — browse for an existing .rtf file

Closing the dialog (X / Escape / Exit button) exits the application.
"""
from __future__ import annotations

import wx


class WelcomeDialog(wx.Dialog):
    """
    Startup chooser dialog.

    Usage:
        with WelcomeDialog() as dlg:
            result = dlg.ShowModal()
            path   = dlg.get_path()   # only meaningful when result == wx.ID_OPEN
        # result: wx.ID_NEW | wx.ID_OPEN | wx.ID_EXIT
    """

    def __init__(self, parent: wx.Window | None = None) -> None:
        super().__init__(
            parent,
            title="Easy PDF",
            style=wx.DEFAULT_DIALOG_STYLE,
            size=(420, 310),
        )
        self._path: str = ""
        self._build_ui()
        self.Centre()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        # ---- App title ----
        title_lbl = wx.StaticText(panel, label="Easy PDF")
        tf = title_lbl.GetFont()
        tf.SetPointSize(24)
        tf.SetWeight(wx.FONTWEIGHT_BOLD)
        title_lbl.SetFont(tf)
        title_lbl.SetName("Easy PDF")

        sub_lbl = wx.StaticText(panel, label="Accessible PDF Authoring")
        sub_lbl.SetName("Application subtitle")

        outer.Add(title_lbl, 0, wx.ALIGN_CENTER | wx.TOP, 28)
        outer.Add(sub_lbl,   0, wx.ALIGN_CENTER | wx.TOP, 4)
        outer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 24)
        outer.AddSpacer(18)

        # ---- Action buttons ----
        new_btn  = wx.Button(panel, wx.ID_NEW,  "&New Document",     size=(-1, 48))
        open_btn = wx.Button(panel, wx.ID_OPEN, "&Open Document...", size=(-1, 48))

        new_btn.SetName("Create a new blank document")
        open_btn.SetName("Open an existing RTF document from disk")
        new_btn.SetToolTip("Start with an empty document (Ctrl+N)")
        open_btn.SetToolTip("Browse for an existing .rtf file to open (Ctrl+O)")
        new_btn.SetDefault()   # Enter key activates this by default

        btn_font = new_btn.GetFont()
        btn_font.SetPointSize(11)
        new_btn.SetFont(btn_font)
        open_btn.SetFont(btn_font)

        outer.Add(new_btn,  0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 24)
        outer.Add(open_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        outer.AddStretchSpacer()

        # ---- Exit link ----
        exit_btn = wx.Button(panel, wx.ID_EXIT, "E&xit", size=(-1, -1))
        exit_btn.SetName("Exit Easy PDF")
        outer.Add(exit_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 16)

        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # Keyboard accelerators on the dialog itself
        accel = wx.AcceleratorTable([
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("N"), wx.ID_NEW),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("O"), wx.ID_OPEN),
        ])
        self.SetAcceleratorTable(accel)

        # Bindings
        new_btn.Bind( wx.EVT_BUTTON, self._on_new)
        open_btn.Bind(wx.EVT_BUTTON, self._on_open)
        exit_btn.Bind(wx.EVT_BUTTON, self._on_exit)
        self.Bind(wx.EVT_CLOSE,      self._on_exit)

        new_btn.SetFocus()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_new(self, event=None) -> None:
        self.EndModal(wx.ID_NEW)

    def _on_open(self, event=None) -> None:
        with wx.FileDialog(
            self, "Open document",
            wildcard=("Documents (*.rtf;*.html;*.epdf)|*.rtf;*.html;*.epdf"
                      "|RTF files (*.rtf)|*.rtf"
                      "|HTML files (*.html;*.epdf)|*.html;*.epdf"
                      "|All files (*.*)|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._path = dlg.GetPath()
                self.EndModal(wx.ID_OPEN)
            # else: stay on welcome dialog so user can try again or pick New

    def _on_exit(self, event=None) -> None:
        self.EndModal(wx.ID_EXIT)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_path(self) -> str:
        """Return the chosen file path. Meaningful only when ShowModal() == wx.ID_OPEN."""
        return self._path
