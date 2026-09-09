import os
import wx


class ImageDialog(wx.Dialog):
    """
    Dialog for inserting an image with mandatory alternative text.

    Usage:
        with ImageDialog(parent) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path, alt_text = dlg.get_result()
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Insert Image",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._path = ""
        self._build_ui()
        self.Fit()
        self.SetMinSize((420, 360))
        self.Centre()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Image file chooser ---
        file_label = wx.StaticText(panel, label="Image file:")
        file_label.SetName("Image file label")
        vbox.Add(file_label, 0, wx.LEFT | wx.TOP, 12)

        file_row = wx.BoxSizer(wx.HORIZONTAL)
        self._file_display = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self._file_display.SetName("Selected image file path")
        file_row.Add(self._file_display, 1, wx.EXPAND | wx.RIGHT, 8)

        browse_btn = wx.Button(panel, label="Browse…")
        browse_btn.SetName("Browse for image file")
        browse_btn.SetToolTip("Open a file chooser to select an image")
        file_row.Add(browse_btn, 0)
        vbox.Add(file_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)

        # --- Preview ---
        self._preview = wx.StaticBitmap(panel, size=(160, 120))
        self._preview.SetName("Image preview")
        vbox.Add(self._preview, 0, wx.ALIGN_CENTER | wx.TOP, 10)

        # --- Alt text ---
        alt_label = wx.StaticText(panel, label="Alternative text (required):")
        alt_label.SetName("Alternative text label")
        vbox.Add(alt_label, 0, wx.LEFT | wx.TOP, 12)

        self._alt_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60))
        self._alt_ctrl.SetName("Alternative text field")
        self._alt_ctrl.SetToolTip(
            "Describe the image for screen reader users. "
            "Leave blank only if the image is purely decorative."
        )
        vbox.Add(self._alt_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)

        # Decorative checkbox (disables alt text field)
        self._decorative_cb = wx.CheckBox(panel, label="Decorative image (no alt text needed)")
        self._decorative_cb.SetName("Mark image as decorative")
        self._decorative_cb.SetToolTip(
            "Check this only for purely decorative images that add no information. "
            "Alt text will be set to empty so screen readers skip this image."
        )
        vbox.Add(self._decorative_cb, 0, wx.LEFT | wx.TOP, 12)

        # --- Buttons ---
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)

        panel.SetSizer(vbox)

        # Outer sizer to hold panel
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)

        # Start with OK disabled
        self.FindWindowById(wx.ID_OK).Disable()
        self.FindWindowById(wx.ID_OK).SetName("Insert image")

        # Bindings
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        self._alt_ctrl.Bind(wx.EVT_TEXT, self._on_alt_changed)
        self._decorative_cb.Bind(wx.EVT_CHECKBOX, self._on_decorative_toggled)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_browse(self, event):
        wildcard = (
            "Image files (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tiff)|"
            "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tiff|"
            "All files (*.*)|*.*"
        )
        with wx.FileDialog(
            self, "Choose an image",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._path = dlg.GetPath()
                self._file_display.SetValue(os.path.basename(self._path))
                self._load_preview(self._path)
                self._update_ok()

    def _on_alt_changed(self, event):
        self._update_ok()

    def _on_decorative_toggled(self, event):
        is_decorative = self._decorative_cb.IsChecked()
        self._alt_ctrl.Enable(not is_decorative)
        if is_decorative:
            self._alt_ctrl.SetValue("")
        self._update_ok()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_preview(self, path: str):
        try:
            img = wx.Image(path)
            if img.IsOk():
                # Scale to fit preview box
                w, h = img.GetWidth(), img.GetHeight()
                max_w, max_h = 160, 120
                scale = min(max_w / w, max_h / h)
                img = img.Scale(int(w * scale), int(h * scale), wx.IMAGE_QUALITY_HIGH)
                self._preview.SetBitmap(wx.Bitmap(img))
        except Exception:
            pass

    def _update_ok(self):
        has_file = bool(self._path)
        has_alt  = bool(self._alt_ctrl.GetValue().strip()) or self._decorative_cb.IsChecked()
        self.FindWindowById(wx.ID_OK).Enable(has_file and has_alt)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def get_result(self) -> tuple[str, str]:
        """Return (image_path, alt_text). Call after ShowModal() == wx.ID_OK."""
        alt = "" if self._decorative_cb.IsChecked() else self._alt_ctrl.GetValue().strip()
        return self._path, alt
