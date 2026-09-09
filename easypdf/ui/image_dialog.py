"""Insert picture, and picture properties: the same dialog.

File, a preview that refuses focus, the description (required unless the
decorative box is ticked), an optional caption, the width and placement,
and a Describe button that hands the picture to Worker C's
DescribeImageDialog and puts the answer in the description field for
editing. The file goes through Worker A's docfile.embed_image, which
downscales it, and the dialog says what went in, in one sentence.

Controls are built directly on the dialog; the April version's OK button
sat under an inner panel and could not be clicked.
"""
import base64
import os

import wx

from .dialogs import QuietBitmap, add_row, name_field

WIDTHS = (("A quarter of the text width", "quarter"),
          ("Half the text width", "half"),
          ("Three quarters of the text width", "three-quarters"),
          ("The full text width", "full"))
PLACES = (("Left", "left"), ("Centre", "centre"), ("Right", "right"))
PICTURE_WILDCARD = ("Pictures (*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp)|"
                    "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp|All files (*.*)|*.*")


def data_uri_bytes(uri):
    """The bytes inside a data: URI, or b"" when it is not one."""
    if not uri or not uri.startswith("data:"):
        return b""
    head, _, payload = uri.partition(",")
    if ";base64" in head:
        try:
            return base64.b64decode(payload)
        except Exception:
            return b""
    from urllib.parse import unquote_to_bytes
    return unquote_to_bytes(payload)


def embed(path):
    """Worker A's embed_image, or a plain reading of the file until it exists.

    Returns (data_uri, sentence) where the sentence says what went in.
    """
    try:
        from .. import docfile
    except ImportError:
        docfile = None
    if docfile is not None and hasattr(docfile, "embed_image"):
        got = docfile.embed_image(path)
        sentence = "Picture: %s by %s pixels, %s KB" % (
            _n(got.width), _n(got.height), _n(round(got.kilobytes)))
        if (got.original_width, got.original_height) != (got.width, got.height):
            sentence += ", reduced from %s by %s" % (_n(got.original_width),
                                                     _n(got.original_height))
        sentence += "."
        if getattr(got, "note", ""):
            sentence += " " + got.note
        return got.data_uri, sentence
    with open(path, "rb") as fh:
        raw = fh.read()
    ext = os.path.splitext(path)[1].lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}.get(ext, "image/png")
    image = wx.Image(path)
    size = "%s by %s pixels, " % (_n(image.GetWidth()), _n(image.GetHeight())) if image.IsOk() else ""
    uri = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))
    return uri, ("Picture: %s%s KB, not reduced because the picture module is not "
                 "part of this build." % (size, _n(round(len(raw) / 1024.0))))


def _n(value):
    return "{:,}".format(int(value))


def _image_from_bytes(raw):
    """A wx.Image from picture bytes, or None. Phoenix takes a file-like
    object straight; wx.InputStream cannot be instantiated from Python."""
    if not raw:
        return None
    import io
    try:
        image = wx.Image(io.BytesIO(raw), wx.BITMAP_TYPE_ANY)
    except Exception:
        return None
    return image if image.IsOk() else None


class PictureDialog(wx.Dialog):
    """`spec` is None to insert, or the figure's spec to edit."""

    def __init__(self, parent, frame, spec=None, imported=False, context=""):
        editing = spec is not None
        super().__init__(parent, title="Picture properties" if editing else "Insert picture",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = frame
        self.result = None
        self.imported = imported
        self.context = context
        spec = dict(spec or {})
        self._src = spec.get("src", "")
        self._alt_source = spec.get("altSource", "")
        self._accepted_alt = None

        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.file = wx.TextCtrl(self, style=wx.TE_READONLY)
        name_field(self.file, "Picture file")
        row.Add(self.file, 1, wx.EXPAND | wx.RIGHT, 8)
        self.browse = wx.Button(self, label="&Browse...")
        self.browse.Bind(wx.EVT_BUTTON, self._on_browse)
        row.Add(self.browse, 0)
        grid.Add(wx.StaticText(self, label="&File:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(row, 1, wx.EXPAND)

        self.preview = QuietBitmap(self, size=self.FromDIP(wx.Size(240, 160)))
        self.preview.SetName("Preview")
        grid.Add(wx.StaticText(self, label="Preview:"), 0)
        grid.Add(self.preview, 0)

        self.size_note = wx.StaticText(self, label="No picture chosen yet.")
        grid.Add(wx.StaticText(self, label="Size:"), 0)
        grid.Add(self.size_note, 1, wx.EXPAND)

        self.alt = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=self.FromDIP(wx.Size(360, 70)))
        add_row(self, grid, "&Description:", self.alt)
        self.alt.SetToolTip("What the picture shows and why it is here, for "
                            "somebody who cannot see it. Required unless the "
                            "picture is decorative.")
        self.alt.Bind(wx.EVT_TEXT, self._on_alt_edited)

        self.decorative = wx.CheckBox(self, label="This picture is &decorative and needs no description")
        grid.AddSpacer(1)
        grid.Add(self.decorative, 0)
        self.decorative.Bind(wx.EVT_CHECKBOX, self._on_decorative)

        self.describe = wx.Button(self, label="Describe with &AI...")
        self.describe.SetToolTip("Ask Claude, ChatGPT or Gemini for a description "
                                 "you can edit before accepting it.")
        self.describe.Bind(wx.EVT_BUTTON, self._on_describe)
        grid.AddSpacer(1)
        grid.Add(self.describe, 0)

        self.caption = add_row(self, grid, "&Caption, optional:", wx.TextCtrl(self))
        self.width = add_row(self, grid, "&Width:",
                             wx.Choice(self, choices=[w[0] for w in WIDTHS]))
        name_field(self.width, "Width")
        self.place = add_row(self, grid, "&Placement:",
                             wx.Choice(self, choices=[p[0] for p in PLACES]))
        name_field(self.place, "Placement")
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 12)

        self.note = wx.StaticText(self, label="")
        self.note.Wrap(self.FromDIP(520))
        outer.Add(self.note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        buttons = wx.StdDialogButtonSizer()
        self.ok = wx.Button(self, wx.ID_OK, "&Insert picture" if not editing else "OK")
        cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.AddButton(self.ok)
        buttons.AddButton(cancel)
        buttons.Realize()
        self.ok.SetDefault()
        self.ok.Bind(wx.EVT_BUTTON, self._on_ok)
        outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.FromDIP(wx.Size(520, 420)))
        self.CentreOnParent()

        widths = [w[1] for w in WIDTHS]
        places = [p[1] for p in PLACES]
        self.width.SetSelection(widths.index(spec.get("width", "half")) if spec.get("width", "half") in widths else 1)
        self.place.SetSelection(places.index(spec.get("place", "centre")) if spec.get("place", "centre") in places else 1)
        self.caption.SetValue(spec.get("caption", "") or "")
        if editing:
            self.file.SetValue("The picture already in the document")
            self.alt.SetValue(spec.get("alt", "") or "")
            self.decorative.SetValue(bool(spec.get("decorative")))
            self._show_preview(data_uri_bytes(self._src))
            self.size_note.SetLabel(self._describe_bytes(data_uri_bytes(self._src)))
            self._accepted_alt = self.alt.GetValue() if self._alt_source else None
            self.alt.SetFocus()
        else:
            self.file.SetFocus()
        self._on_decorative(None)

    # ------------------------------------------------------------ file --
    def _on_browse(self, _event):
        start = getattr(self.frame, "last_folder", "") or ""
        with wx.FileDialog(self, "Choose a picture", defaultDir=start,
                           wildcard=PICTURE_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self.load_file(path)

    def load_file(self, path):
        try:
            self._src, sentence = embed(path)
        except Exception as exc:
            self.note.SetLabel("That picture could not be read. %s" % exc)
            self.note.Wrap(self.FromDIP(520))
            return False
        self.file.SetValue(path)
        try:
            self.frame.last_folder = os.path.dirname(path)
        except Exception:
            pass
        self.size_note.SetLabel(sentence)
        self._show_preview(data_uri_bytes(self._src))
        self.Layout()
        if not self.alt.GetValue().strip():
            self.alt.SetFocus()
        return True

    def _describe_bytes(self, raw):
        if not raw:
            return "No picture."
        image = _image_from_bytes(raw)
        if image is not None and image.IsOk():
            return "Picture: %s by %s pixels, %s KB." % (
                _n(image.GetWidth()), _n(image.GetHeight()), _n(round(len(raw) / 1024.0)))
        return "Picture: %s KB." % _n(round(len(raw) / 1024.0))

    def _show_preview(self, raw):
        if not raw:
            return
        image = _image_from_bytes(raw)
        if image is None or not image.IsOk():
            return
        box = self.preview.GetSize()
        w, h = image.GetWidth(), image.GetHeight()
        scale = min(box.width / float(w), box.height / float(h), 1.0)
        image = image.Scale(max(1, int(w * scale)), max(1, int(h * scale)),
                            wx.IMAGE_QUALITY_HIGH)
        self.preview.SetBitmap(wx.Bitmap(image))

    # ------------------------------------------------------ description --
    def _on_decorative(self, _event):
        decorative = self.decorative.GetValue()
        self.alt.Enable(not decorative)
        self.describe.Enable(not decorative)

    def _on_alt_edited(self, _event):
        # Hand editing clears the AI provenance; the words are the user's now.
        if self._accepted_alt is not None and self.alt.GetValue() != self._accepted_alt:
            self._alt_source = ""
            self._accepted_alt = None

    def _on_describe(self, _event):
        raw = data_uri_bytes(self._src)
        if not raw:
            self.note.SetLabel("Choose a picture first.")
            self.note.Wrap(self.FromDIP(520))
            self.browse.SetFocus()
            return
        try:
            from .describe_dialog import DescribeImageDialog
        except ImportError:
            self.note.SetLabel("The describer is not part of this build yet.")
            self.note.Wrap(self.FromDIP(520))
            speaker = getattr(self.frame, "announce", None)
            if speaker:
                speaker("The describer is not part of this build yet.")
            return
        dialog = DescribeImageDialog(self, raw, current_alt=self.alt.GetValue(),
                                     context=self.context, imported=self.imported)
        try:
            dialog.ShowModal()
            text = getattr(dialog, "result", None)
            provider = getattr(dialog, "provider_used", "") or ""
        finally:
            dialog.Destroy()
        if text:
            self.alt.SetValue(text.strip())
            self._alt_source = "ai:%s" % provider if provider else "ai"
            self._accepted_alt = self.alt.GetValue()
            self.alt.SetFocus()
            self.alt.SetInsertionPointEnd()

    # -------------------------------------------------------------- ok --
    def _on_ok(self, _event):
        if not self._src:
            self.note.SetLabel("Choose a picture file first.")
            self.note.Wrap(self.FromDIP(520))
            self.browse.SetFocus()
            return
        decorative = self.decorative.GetValue()
        alt = self.alt.GetValue().strip()
        if not decorative and not alt:
            self.note.SetLabel("A description is required, or tick the decorative box "
                               "if the picture carries no information.")
            self.note.Wrap(self.FromDIP(520))
            self.alt.SetFocus()
            return
        self.result = {
            "src": self._src,
            "alt": "" if decorative else alt,
            "decorative": decorative,
            "caption": self.caption.GetValue().strip(),
            "width": WIDTHS[max(0, self.width.GetSelection())][1],
            "place": PLACES[max(0, self.place.GetSelection())][1],
            "altSource": "" if decorative else self._alt_source,
        }
        self.EndModal(wx.ID_OK)
