"""The describer's dialogs: one picture, or the whole document.

Both follow the shape every TG Studios dialog has: a multiline field with
focus in it, every control named, Enter and Escape handled, and never a
wx.MessageBox for anything somebody might want to re-read. The request
runs on a thread of its own and comes back through wx.CallAfter, so the
dialog stays responsive and Cancel works while the answer is in the air:
a cancelled dialog simply stops listening, and whatever arrives afterwards
is dropped.

The answer is never written into the document from here. The picture
dialog puts it in an editable field and hands back what the user accepts;
the document dialog puts it in a read-only field for reading and copying.
The editor, Worker B's, is the only thing that writes.

Consent follows describe.consent_needed: a picture from the user's own
disk asks once per session, a picture that came in with an imported
document asks every time, a whole document asks every time. The question
is a dialog with a read-only field whose default button is the one that
sends nothing.
"""
from __future__ import annotations

import io
import threading
import time

import wx

from .. import ai, describe

#: How big the preview is drawn, at most. It is a picture for a sighted
#: person glancing at the dialog; the model gets the full 1,600 wide copy.
PREVIEW_BOX = (360, 240)


def find_announcer(window, name="announce"):
    """The nearest ancestor with a callable `announce` (or another speech
    channel), or None. The frame owns speech; a dialog borrows it."""
    hops = 0
    while window is not None and hops < 24:
        found = getattr(window, name, None)
        if callable(found):
            return found
        try:
            window = window.GetParent()
        except Exception:
            return None
        hops += 1
    return None


def speech_channel(fn):
    """A speech channel that never raises, whether or not one was found."""
    def say(text):
        if fn is None:
            return
        try:
            fn(text)
        except Exception:
            pass
    return say


def show_wrapped(dialog, control, text):
    """Put a sentence in a static, wrapped to the dialog's width, and let
    the dialog grow when the sentence needs more lines than it has room
    for, rather than squeezing the field above it."""
    control.SetLabel(text)
    try:
        control.Wrap(max(200, dialog.GetClientSize().width - 20))
        dialog.Layout()
        sizer = dialog.GetSizer()
        if sizer is not None:
            need = sizer.GetMinSize()
            have = dialog.GetClientSize()
            if need.height > have.height:
                dialog.SetClientSize(wx.Size(have.width, need.height))
    except Exception:
        pass


class Preview(wx.StaticBitmap):
    """The picture, drawn for anybody who can see it. It refuses focus, so
    a screen reader user tabbing through the dialog never lands on a
    control that has nothing to say."""

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False


def preview_data(image_bytes, box=PREVIEW_BOX):
    """The picture decoded and scaled to fit `box`, as `(width, height, rgb)`
    with three bytes per pixel, or None.

    Pillow only, no wx: this is the slow half, and it runs on a thread. A
    4,000 by 3,000 photograph took 165 to 179 milliseconds to decode and
    scale here, measured 9 September 2026 over three runs, and that is a
    sixth of a second of dead window before the dialog appears at all if it
    is done in `__init__`.
    Transparency is laid on white, which is what a page is.
    """
    if not image_bytes:
        return None
    try:
        from PIL import Image, ImageOps
    except Exception:
        return None
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        if image.width <= 0 or image.height <= 0:
            return None
        scale = min(box[0] / float(image.width), box[1] / float(image.height),
                    1.0)
        if scale < 1.0:
            image = image.resize((max(1, int(image.width * scale)),
                                  max(1, int(image.height * scale))),
                                 Image.LANCZOS)
        if image.mode in ("RGBA", "LA", "P", "PA"):
            flat = Image.new("RGB", image.size, (255, 255, 255))
            rgba = image.convert("RGBA")
            flat.paste(rgba, mask=rgba.split()[-1])
            image = flat
        image = image.convert("RGB")
        return image.width, image.height, image.tobytes()
    except Exception:
        return None


def bitmap_from(data):
    """`preview_data`'s answer as a wx.Bitmap, or None. Cheap, and it builds
    window objects, so it runs on the window thread."""
    if not data:
        return None
    try:
        width, height, rgb = data
        quiet = wx.LogNull()
        try:
            image = wx.Image(width, height, rgb)
        finally:
            del quiet
        if not image.IsOk():
            return None
        return wx.Bitmap(image)
    except Exception:
        return None


def bitmap_for(image_bytes, box=PREVIEW_BOX):
    """A wx.Bitmap of the picture scaled to fit `box`, or None. Both halves
    at once, for a caller that is already on the window thread and has a
    small picture."""
    return bitmap_from(preview_data(image_bytes, box))


class ConsentDialog(wx.Dialog):
    """The question before anything leaves, in a field that can be read
    twice. The default button sends nothing: Enter from the field does not
    send, and Escape never does."""

    def __init__(self, parent, title, question, send_label="&Send",
                 keep_label="&Don't send"):
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = False
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(wx.StaticText(self, label="&Question"), 0,
                  wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.question = wx.TextCtrl(
            self, value=question, style=wx.TE_READONLY | wx.TE_MULTILINE,
            size=(560, 270))
        self.question.SetName("Question")
        outer.Add(self.question, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.StdDialogButtonSizer()
        self.send = wx.Button(self, wx.ID_OK, send_label)
        self.keep = wx.Button(self, wx.ID_CANCEL, keep_label)
        buttons.AddButton(self.send)
        buttons.AddButton(self.keep)
        buttons.Realize()
        self.keep.SetDefault()
        outer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.SetEscapeId(wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_send, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_keep, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._on_keep)
        self.question.SetFocus()
        self.question.SetInsertionPoint(0)

    def _finish(self, code):
        if self.IsModal():
            self.EndModal(code)
        else:
            self.Show(False)

    def _on_send(self, _event):
        self.result = True
        self._finish(wx.ID_OK)

    def _on_keep(self, _event):
        self.result = False
        self._finish(wx.ID_CANCEL)


class _Threaded:
    """What both dialogs share: a generation counter so a cancelled dialog
    ignores an answer that arrives late, and a hop back to the window."""

    _generation = 0

    def _later(self, generation, fn, *args):
        wx.CallAfter(self._maybe, generation, fn, *args)

    def _maybe(self, generation, fn, *args):
        if not self or generation != self._generation:
            return
        try:
            fn(*args)
        except RuntimeError:
            # The window went away between the check and the call.
            pass

    def _start(self, name, work):
        threading.Thread(target=work, name=name, daemon=True).start()


class DescribeImageDialog(wx.Dialog, _Threaded):
    """Describe one picture, edit the answer, accept it or not.

    `result` is the text the user accepted, edited or not, or None.
    `provider_used` is "anthropic", "openai" or "google" when the accepted
    text came from a provider in this dialog (edited afterwards or not),
    and "" when the user typed it all themselves; Worker B writes it into
    `data-alt-source`.

    `provider` and `model` are the user's settings; the model only applies
    when the provider chosen in the dialog is the one it was set for.
    `imported` says the picture arrived inside an imported document, which
    makes consent ask every time.
    """

    def __init__(self, parent, image_bytes, current_alt="", context="",
                 imported=False, provider="", model="", announce=None):
        wx.Dialog.__init__(self, parent, title="Describe this picture",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        self.provider_used = ""
        self._image_bytes = image_bytes or b""
        self._context = context or ""
        self._imported = bool(imported)
        self._settings_provider = (provider or "").strip().lower()
        self._settings_model = (model or "").strip()
        self._busy = False
        self._generation = 0
        self._came_from = ""
        self._say = speech_channel(announce or find_announcer(parent, "announce"))
        self._help = speech_channel(find_announcer(parent, "announce_help"))

        outer = wx.BoxSizer(wx.VERTICAL)

        # The slot is made empty and filled when the decode lands. Decoding
        # here would hold the dialog shut for a quarter of a second on a
        # photograph, and a dialog that is slow to open is a dialog whose
        # first keystroke is lost.
        self.preview = Preview(self)
        self.preview.SetName("The picture")
        self.preview.SetMinSize(wx.Size(*PREVIEW_BOX))
        outer.Add(self.preview, 0, wx.ALIGN_CENTRE | wx.ALL, 10)
        self.preview_note = wx.StaticText(self, label="")
        outer.Add(self.preview_note, 0, wx.LEFT | wx.RIGHT, 10)
        self.preview_note.Hide()

        outer.Add(wx.StaticText(self, label="&Who to ask"), 0,
                  wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.provider = wx.Choice(
            self, choices=[ai.PROVIDER_NAMES[p] for p in ai.PROVIDERS])
        self.provider.SetName("Who to ask")
        chosen = ai.best_provider(self._settings_provider or ai.PROVIDERS[0])
        self.provider.SetSelection(
            ai.PROVIDERS.index(chosen) if chosen in ai.PROVIDERS else 0)
        outer.Add(self.provider, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.describe_button = wx.Button(self, label="&Describe")
        self.detail_button = wx.Button(self, label="Describe in d&etail")
        row.Add(self.describe_button, 0, wx.RIGHT, 8)
        row.Add(self.detail_button, 0)
        outer.Add(row, 0, wx.LEFT | wx.RIGHT, 10)

        self.status = wx.StaticText(self, label="Nothing has been asked yet.")
        self.status.SetName("Status")
        outer.Add(self.status, 0, wx.ALL, 10)

        outer.Add(wx.StaticText(self, label="Descri&ption"), 0,
                  wx.LEFT | wx.RIGHT, 10)
        self.answer = wx.TextCtrl(self, value=current_alt or "",
                                  style=wx.TE_MULTILINE, size=(560, 140))
        self.answer.SetName("Description")
        outer.Add(self.answer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        buttons = wx.StdDialogButtonSizer()
        self.use_button = wx.Button(self, wx.ID_OK, "&Use this description")
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "&Cancel")
        buttons.AddButton(self.use_button)
        buttons.AddButton(self.cancel_button)
        buttons.Realize()
        outer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.SetEscapeId(wx.ID_CANCEL)
        self.describe_button.Bind(wx.EVT_BUTTON,
                                  lambda _e: self._on_describe(False))
        self.detail_button.Bind(wx.EVT_BUTTON,
                                lambda _e: self._on_describe(True))
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._on_cancel)
        # Enter in the description accepts it. Alternative text has no line
        # breaks, so there is nothing else Enter could usefully mean there.
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.describe_button.SetFocus()
        self._start_preview()

    # -- the preview, which nobody reading this can see ------------------
    def _start_preview(self):
        """Decode the picture on a thread and hand the bitmap back through
        wx.CallAfter. Nothing here is spoken: the preview is for a sighted
        person glancing at the dialog, and a screen reader user does not want
        to be told a picture they cannot see has finished loading."""
        if not self._image_bytes:
            self._no_preview()
            return
        generation = self._generation
        image_bytes = self._image_bytes

        def work():
            data = preview_data(image_bytes)
            self._later(generation, self._preview_ready, data)

        self._start("tgimprint-describe-preview", work)

    def _preview_ready(self, data):
        bitmap = bitmap_from(data)
        if bitmap is None:
            self._no_preview()
            return
        self.preview.SetBitmap(bitmap)
        self.preview.SetMinSize(wx.Size(bitmap.GetWidth(),
                                        bitmap.GetHeight()))
        self.Layout()

    def _no_preview(self):
        self.preview.Hide()
        self.preview_note.SetLabel("The picture could not be shown here.")
        self.preview_note.Show()
        self.Layout()

    # -- what the user chose -------------------------------------------
    def chosen_provider(self):
        at = self.provider.GetSelection()
        return ai.PROVIDERS[at] if 0 <= at < len(ai.PROVIDERS) \
            else ai.PROVIDERS[0]

    def _model_for(self, provider):
        if provider == self._settings_provider:
            return self._settings_model
        return ""

    # -- asking ----------------------------------------------------------
    def _on_describe(self, long):
        if self._busy:
            return
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES.get(provider, provider)
        if not describe.key_for(provider):
            self._show_status("No key has been set up for %s yet. Put one "
                              "in on the AI page of Preferences, then try "
                              "again." % who)
            self._say(self.status.GetLabel())
            return
        if not self._image_bytes:
            self._show_status("There is no picture to describe.")
            self._say(self.status.GetLabel())
            return
        if describe.consent_needed("image", self._imported, 1):
            self._set_busy(True, "Measuring the picture.")
            generation = self._generation
            image_bytes = self._image_bytes

            def measure():
                _w, _p, kilobytes = describe.payload_estimate("", [image_bytes])
                self._later(generation, self._consent_then_send, provider,
                            long, kilobytes)

            self._start("tgimprint-describe-measure", measure)
            return
        self._send(provider, long)

    def _consent_then_send(self, provider, long, kilobytes):
        self._set_busy(False, "")
        question = describe.consent_question("image", provider, 1, 0,
                                             kilobytes, self._imported)
        if not self.ask_consent(question):
            self._show_status("Nothing was sent.")
            self._help("Nothing was sent.")
            return
        if not self._imported:
            describe.record_consent("image")
        self._send(provider, long)

    def ask_consent(self, question):
        """Put the question up and return whether they said send. A test
        replaces this so the flow runs without a modal loop."""
        with ConsentDialog(self, "Send the picture?", question) as box:
            box.ShowModal()
            return box.result

    def _send(self, provider, long):
        who = ai.PROVIDER_NAMES.get(provider, provider)
        self._set_busy(True, "Asking %s. This usually takes a few seconds."
                       % who)
        generation = self._generation
        image_bytes, context = self._image_bytes, self._context
        model = self._model_for(provider)
        started = time.monotonic()

        def work():
            ok, text = describe.describe_image(image_bytes, provider, model,
                                               context, long)
            self._later(generation, self._done, ok, text, provider,
                        time.monotonic() - started)

        self._start("tgimprint-describe-image", work)

    def _done(self, ok, text, provider, took):
        who = ai.PROVIDER_NAMES.get(provider, provider)
        self._set_busy(False, "")
        if not ok:
            self._show_status(text)
            self._say(text)
            return
        self._came_from = provider
        self.answer.SetValue(text)
        self.answer.SetFocus()
        self.answer.SetInsertionPoint(0)
        self._show_status("Described by %s in %d seconds. Read it, change "
                          "it if you like, then choose Use this "
                          "description." % (who, int(round(took))))
        self._say("Described by %s: %s" % (who, text))

    # -- the window ------------------------------------------------------
    def _set_busy(self, busy, status):
        self._busy = busy
        for button in (self.describe_button, self.detail_button,
                       self.use_button):
            button.Enable(not busy)
        self.provider.Enable(not busy)
        if status:
            self._show_status(status)
            if busy:
                # A static's label is not spoken; say the wait out loud.
                self._help(status)

    def _show_status(self, text):
        show_wrapped(self, self.status, text)

    def _finish(self, code):
        if self.IsModal():
            self.EndModal(code)
        else:
            self.Show(False)

    def _on_ok(self, _event=None):
        if self._busy:
            return
        text = self.answer.GetValue().strip()
        if not text:
            self._show_status("Type or ask for a description first.")
            self._say("Type or ask for a description first.")
            self.answer.SetFocus()
            return
        self.result = text
        self.provider_used = self._came_from if text else ""
        self._generation += 1
        self._finish(wx.ID_OK)

    def _on_cancel(self, _event=None):
        self.result = None
        self.provider_used = ""
        # Anything still in the air is dropped when it lands.
        self._generation += 1
        self._finish(wx.ID_CANCEL)

    def _on_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and \
                self.FindFocus() is self.answer and not event.ShiftDown():
            self._on_ok()
            return
        event.Skip()


class DescribeDocumentDialog(wx.Dialog, _Threaded):
    """Describe the whole document: consent, then progress, then the answer
    in a read-only field with focus, and Copy and Close.

    `result` is the description, or None. `images` is one entry of bytes
    per picture in `body_html` in document order, or None to let
    describe.py use the document's own embedded pictures. `document_name`
    is named in the consent question when given.
    """

    def __init__(self, parent, body_html, images=None, provider="", model="",
                 announce=None, announce_help=None, document_name=""):
        wx.Dialog.__init__(self, parent, title="Describe this document",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        self.provider_used = ""
        self._body_html = body_html or ""
        self._images = images
        self._settings_provider = (provider or "").strip().lower()
        self._settings_model = (model or "").strip()
        self._document_name = document_name or ""
        self._generation = 0
        self._stage = "measuring"
        self._estimate = None
        self._say = speech_channel(announce or find_announcer(parent, "announce"))
        self._help = speech_channel(announce_help
                            or find_announcer(parent, "announce_help"))

        outer = wx.BoxSizer(wx.VERTICAL)

        outer.Add(wx.StaticText(self, label="&Who to ask"), 0,
                  wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.provider = wx.Choice(
            self, choices=[ai.PROVIDER_NAMES[p] for p in ai.PROVIDERS])
        self.provider.SetName("Who to ask")
        chosen = ai.best_provider(self._settings_provider or ai.PROVIDERS[0])
        self.provider.SetSelection(
            ai.PROVIDERS.index(chosen) if chosen in ai.PROVIDERS else 0)
        self.provider.Bind(wx.EVT_CHOICE, self._on_provider)
        outer.Add(self.provider, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        outer.Add(wx.StaticText(self, label="&Message"), 0,
                  wx.LEFT | wx.RIGHT, 10)
        self.message = wx.TextCtrl(
            self, value="Measuring what would be sent.",
            style=wx.TE_READONLY | wx.TE_MULTILINE, size=(600, 320))
        self.message.SetName("Message")
        outer.Add(self.message, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.status = wx.StaticText(self, label="")
        self.status.SetName("Status")
        outer.Add(self.status, 0, wx.ALL, 10)

        buttons = wx.StdDialogButtonSizer()
        self.send_button = wx.Button(self, wx.ID_OK, "&Send the document")
        self.copy_button = wx.Button(self, wx.ID_ANY, "Cop&y")
        self.close_button = wx.Button(self, wx.ID_CANCEL, "&Close")
        buttons.AddButton(self.send_button)
        buttons.SetAffirmativeButton(self.send_button)
        buttons.AddButton(self.close_button)
        buttons.SetCancelButton(self.close_button)
        buttons.Realize()
        buttons.Insert(1, self.copy_button, 0, wx.RIGHT, 6)
        outer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.send_button.Enable(False)
        self.copy_button.Enable(False)
        self.close_button.SetDefault()

        self.SetSizerAndFit(outer)
        self.CentreOnParent()
        self.SetEscapeId(wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_send, id=wx.ID_OK)
        self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy)
        self.Bind(wx.EVT_BUTTON, self._on_close, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.message.SetFocus()
        self.message.SetInsertionPoint(0)
        self._measure()

    # -- what the user chose -------------------------------------------
    def chosen_provider(self):
        at = self.provider.GetSelection()
        return ai.PROVIDERS[at] if 0 <= at < len(ai.PROVIDERS) \
            else ai.PROVIDERS[0]

    def _model_for(self, provider):
        if provider == self._settings_provider:
            return self._settings_model
        return ""

    # -- measuring, then the question ------------------------------------
    def _measure(self):
        generation = self._generation
        body, images = self._body_html, self._images

        def work():
            # payload_plan, not payload_estimate: the fourth number is how
            # many pictures will REALLY be attached, which the picture cap,
            # the byte budget and a picture that cannot be read can each cut
            # below the number in the document. The question says that one.
            got = describe.payload_plan(body, images)
            self._later(generation, self._measured, *got)

        self._start("tgimprint-describe-measure", work)

    def _measured(self, words, pictures, attached, kilobytes):
        self._estimate = (words, pictures, attached, kilobytes)
        self._stage = "asking"
        self._show_question()
        self.send_button.Enable(True)
        self.message.SetFocus()
        self.message.SetInsertionPoint(0)

    def _show_question(self):
        words, pictures, attached, kilobytes = self._estimate
        provider = self.chosen_provider()
        self.message.SetValue(describe.consent_question(
            "document", provider, pictures, words, kilobytes, False,
            self._document_name, attached=attached))
        self.message.SetInsertionPoint(0)

    def _on_provider(self, _event=None):
        if self._stage == "asking" and self._estimate is not None:
            self._show_question()

    # -- sending -----------------------------------------------------------
    def _on_send(self, _event=None):
        if self._stage != "asking":
            return
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES.get(provider, provider)
        if not describe.key_for(provider):
            text = ("No key has been set up for %s yet. Put one in on the "
                    "AI page of Preferences, then try again." % who)
            self._show_status(text)
            self._say(text)
            return
        self._stage = "sending"
        self.send_button.Enable(False)
        self.provider.Enable(False)
        self.message.SetValue("Sending the document to %s." % who)
        self.message.SetInsertionPoint(0)
        generation = self._generation
        body, images = self._body_html, self._images
        model = self._model_for(provider)
        started = time.monotonic()

        def progress(text):
            self._later(generation, self._progress, text)

        def work():
            ok, text = describe.describe_document(body, images, provider,
                                                  model, progress=progress)
            self._later(generation, self._done, ok, text, provider,
                        time.monotonic() - started)

        self._start("tgimprint-describe-document", work)

    def _progress(self, text):
        self._show_status(text)
        self._help(text)

    def _done(self, ok, text, provider, took):
        who = ai.PROVIDER_NAMES.get(provider, provider)
        self.message.SetFocus()
        if ok:
            self.message.SetValue(text)
            self.message.SetInsertionPoint(0)
            self._stage = "answered"
            self.result = text
            self.provider_used = provider
            self.copy_button.Enable(True)
            self._show_status("Described by %s in %d seconds."
                              % (who, int(round(took))))
            self._say("Described by %s in %d seconds. The description is "
                      "in the Message field; arrow through it, or choose "
                      "Copy." % (who, int(round(took))))
        else:
            self._stage = "asking"
            self.send_button.Enable(True)
            self.provider.Enable(True)
            self._show_status(text)
            self._say(text)
            # The question goes back so Send can be re-read before it is pressed again.
            self._show_question()

    # -- the window ------------------------------------------------------
    def _show_status(self, text):
        show_wrapped(self, self.status, text)

    def _on_copy(self, _event=None):
        text = self.message.GetValue()
        if not text or self._stage != "answered":
            return
        copied = False
        try:
            if wx.TheClipboard.Open():
                try:
                    copied = wx.TheClipboard.SetData(wx.TextDataObject(text))
                finally:
                    wx.TheClipboard.Close()
        except Exception:
            copied = False
        said = ("The description has been copied to the clipboard." if copied
                else "The clipboard would not take the text. Select it in "
                     "the Message field and press Control C.")
        self._show_status(said)
        self._help(said)

    def _finish(self, code):
        if self.IsModal():
            self.EndModal(code)
        else:
            self.Show(False)

    def _on_close(self, _event=None):
        # Whatever is still in the air is dropped when it lands. `result`
        # keeps an answer that already arrived.
        self._generation += 1
        self._finish(wx.ID_CANCEL)
