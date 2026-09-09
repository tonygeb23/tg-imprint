"""The AI page of Preferences: who to ask, their key, and which model.

A panel Worker B mounts inside the Preferences notebook. `apply()` writes
the provider and the model into the settings dict and the key into Windows
Credential Manager; the key never goes into settings.

**The key is shown masked and only ever revealed on purpose.** The box
holds the stored key, so what you see is what is kept, and clearing it and
choosing OK forgets it; the Show box reveals it for checking a paste. It
is never spoken, never put in a status line and never written to a file:
`secrets.redact` gives the last four characters and nothing else.

Every button that touches the network runs on a thread and reports back
in the status line and through the frame's speech, so the page never
freezes and Preferences can be closed while an answer is on its way.

Every sentence on the page is wrapped to the page's real width, and
wrapped again when the page is resized, because a wx.StaticText never
wraps on its own and a Preferences dialog is not a fixed size.
"""
from __future__ import annotations

import io
import threading
import time

import wx

from .. import ai, describe, secrets
from .describe_dialog import ConsentDialog, find_announcer, speech_channel

#: What the Test button asks, over a picture Easy PDF draws itself, so the
#: test sends nothing of the user's.
TEST_PROMPT = ("In at most ten words, say what shape and colour is in this "
               "picture.")
TEST_PROMPT_NO_PICTURE = "Reply with the single word: ready."

#: The Credential Manager entry, as somebody looking for it will see it.
_ENTRY_NAME = secrets.VISION_PREFIX.strip().rstrip(":")

#: Windows' own message to an edit control: a character to mask with, or
#: zero to show the text. Zero also clears the password style, so a screen
#: reader reads the revealed text plainly.
_EM_SETPASSWORDCHAR = 0x00CC
_MASK_CHAR = 0x25CF

#: The wrap width before the page has a real size, and the least it will
#: ever wrap at.
_FIRST_WIDTH = 620
_LEAST_WIDTH = 300


def test_picture():
    """A tiny picture drawn here: a red circle on white, 96 by 64 pixels,
    about a kilobyte. Returns prepared `(mime, data)` or None."""
    try:
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (96, 64), (255, 255, 255))
        ImageDraw.Draw(image).ellipse((24, 8, 72, 56), fill=(220, 30, 30))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        return "image/png", buffer.getvalue()
    except Exception:
        return None


class AISettingsPage(wx.Panel):
    """Provider, key, model, and the buttons that prove them."""

    def __init__(self, parent, settings, prefix=None, announce=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else {}
        self._prefix = prefix or secrets.VISION_PREFIX
        self._pending = {}
        self._generation = 0
        self._say = speech_channel(announce or find_announcer(parent, "announce"))
        #: The unwrapped text of every static that wraps, so a resize can
        #: wrap it again from the original.
        self._raw = {}
        self._wrapped_at = 0

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        self.note = self._wrapped(
            sizer,
            "Describe pictures and whole documents with Claude, ChatGPT or "
            "Gemini on your own account; you pay them directly and nothing "
            "goes through TG Studios. Nothing leaves this machine until you "
            "say so in a dialog that names the provider, and no answer is "
            "written into your document unread.")

        self._label(sizer, "&Who to ask")
        self.provider = wx.Choice(
            self, choices=[ai.PROVIDER_NAMES[p] for p in ai.PROVIDERS])
        self.provider.SetName("Who to ask")
        current = self._setting("ai_provider", "")
        if current not in ai.PROVIDERS:
            current = ai.best_provider(ai.PROVIDERS[0])
        self.provider.SetSelection(ai.PROVIDERS.index(current))
        self.provider.Bind(wx.EVT_CHOICE, self._on_provider)
        sizer.Add(self.provider, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self._shown_for = current

        self._label(sizer, "Their &key")
        key_row = wx.BoxSizer(wx.HORIZONTAL)
        self.key = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.key.SetName("Their key")
        key_row.Add(self.key, 1, wx.RIGHT, 8)
        self.show = wx.CheckBox(self, label="&Show the key")
        self.show.SetName("Show the key")
        self.show.Bind(wx.EVT_CHECKBOX, self._on_show)
        key_row.Add(self.show, 0, wx.ALIGN_CENTRE_VERTICAL)
        sizer.Add(key_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self.key_state = self._wrapped(sizer, "")

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.forget_button = wx.Button(self, label="&Forget this key")
        self.forget_button.Bind(wx.EVT_BUTTON, self._on_forget)
        row.Add(self.forget_button, 0, wx.RIGHT, 8)
        self.drop_deck_button = wx.Button(
            self, label="Use the key I gave TG &Drop Deck")
        self.drop_deck_button.Bind(wx.EVT_BUTTON, self._on_drop_deck)
        row.Add(self.drop_deck_button, 0)
        sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._label(sizer, "&Model, if you want a particular one")
        model_row = wx.BoxSizer(wx.HORIZONTAL)
        self.model = wx.ComboBox(self, style=wx.CB_DROPDOWN,
                                 choices=list(ai.KNOWN_MODELS.get(current, ())))
        self.model.SetName("Model")
        self.model.SetValue(self._setting("ai_model", "") or "")
        model_row.Add(self.model, 1, wx.RIGHT, 8)
        self.list_button = wx.Button(self, label="&Get the list")
        self.list_button.Bind(wx.EVT_BUTTON, self._on_list)
        model_row.Add(self.list_button, 0, wx.RIGHT, 8)
        self.test_button = wx.Button(self, label="&Test the key and model")
        self.test_button.Bind(wx.EVT_BUTTON, self._on_test)
        model_row.Add(self.test_button, 0)
        sizer.Add(model_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self.model_note = self._wrapped(sizer, "")

        self.status = self._wrapped(sizer, "")
        self.status.SetName("Status")

        self.Bind(wx.EVT_SIZE, self._on_size)
        self._load_key(current)
        self._refresh()

    # -- layout helpers ---------------------------------------------------
    def _label(self, sizer, text):
        sizer.Add(wx.StaticText(self, label=text), 0, wx.LEFT | wx.TOP, 10)

    def _wrapped(self, sizer, text):
        """A static that wraps to the page's width, now and on resize."""
        control = wx.StaticText(self, label=text)
        self._raw[control] = text
        control.Wrap(_FIRST_WIDTH)
        sizer.Add(control, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        return control

    def _wrap_width(self):
        try:
            return max(_LEAST_WIDTH, self.GetClientSize().width - 20)
        except Exception:
            return _FIRST_WIDTH

    def _set_text(self, control, text):
        """Change a wrapping static's text. The raw text is kept, so a
        later resize wraps it again from the original."""
        self._raw[control] = text
        control.SetLabel(text)
        try:
            control.Wrap(self._wrap_width())
            self.Layout()
        except Exception:
            pass

    def _on_size(self, event):
        event.Skip()
        width = self._wrap_width()
        if width == self._wrapped_at:
            return
        self._wrapped_at = width
        for control, text in list(self._raw.items()):
            try:
                control.SetLabel(text)
                control.Wrap(width)
            except Exception:
                pass
        self.Layout()

    def _setting(self, name, default):
        try:
            value = self.settings.get(name, default)
        except AttributeError:
            try:
                value = self.settings[name]
            except Exception:
                value = default
        return value if value is not None else default

    # -- provider and key --------------------------------------------------
    def chosen_provider(self):
        at = self.provider.GetSelection()
        return ai.PROVIDERS[at] if 0 <= at < len(ai.PROVIDERS) \
            else ai.PROVIDERS[0]

    def _stored(self, provider):
        try:
            return secrets.fetch(provider, self._prefix) or ""
        except Exception:
            return ""

    def _load_key(self, provider):
        """The box shows what would be kept: an edit not yet applied, else
        the stored key."""
        if provider in self._pending:
            self.key.ChangeValue(self._pending[provider])
        else:
            self.key.ChangeValue(self._stored(provider))
        self._shown_for = provider

    def _on_provider(self, _event=None):
        self._pending[self._shown_for] = self.key.GetValue()
        self._load_key(self.chosen_provider())
        self._refresh()

    def _refresh(self):
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES[provider]
        held = self._stored(provider)
        if held:
            self._set_text(self.key_state,
                           "A key for %s is kept in Windows Credential "
                           "Manager, %s. Clear the box and choose OK to "
                           "forget it." % (who, secrets.redact(held)))
        else:
            self._set_text(self.key_state,
                           "No key for %s is kept yet. Paste one in the box; "
                           "it goes into Windows Credential Manager as %s, "
                           "never into a document or your settings."
                           % (who, _ENTRY_NAME))
        self.forget_button.Enable(bool(held))
        self._set_text(self.model_note,
                       "Empty means %s, chosen for accuracy. Get the list "
                       "asks %s what it really has. Test sends a tiny "
                       "picture Easy PDF draws itself, nothing of yours."
                       % (ai.DEFAULT_MODELS.get(provider, "the usual model"),
                          who))
        keeping = self.model.GetValue()
        self.model.Set(list(ai.KNOWN_MODELS.get(provider, ())))
        self.model.SetValue(keeping)
        self.Layout()

    def _on_show(self, _event=None):
        self._set_masked(not self.show.GetValue())

    def _set_masked(self, masked):
        """Mask or reveal the key box in place. On Windows the edit control
        takes a message for it; anywhere else the box stays masked."""
        try:
            import ctypes
            handle = self.key.GetHandle()
            ctypes.windll.user32.SendMessageW(
                handle, _EM_SETPASSWORDCHAR, _MASK_CHAR if masked else 0, 0)
            self.key.Refresh()
        except Exception:
            pass

    def _on_forget(self, _event=None):
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES[provider]
        try:
            secrets.forget(provider, self._prefix)
        except Exception:
            pass
        self._pending[provider] = ""
        self.key.ChangeValue("")
        self._refresh()
        gone = not self._stored(provider)
        text = ("The key for %s has been forgotten." % who if gone else
                "Windows Credential Manager would not remove the key for "
                "%s. Remove it there yourself, listed as %s."
                % (who, _ENTRY_NAME))
        self._show_status(text)
        self._say(text)

    def _on_drop_deck(self, _event=None):
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES[provider]
        question = ("Easy PDF will read the key for %s that TG Drop Deck "
                    "keeps in Windows Credential Manager, and keep its own "
                    "copy under Easy PDF's name. Nothing is sent anywhere. "
                    "Copy the key?" % who)
        if not self.ask_yes(question, "Use the key from TG Drop Deck?",
                            "&Copy the key", "&Don't copy"):
            self._show_status("Nothing was copied.")
            self._say("Nothing was copied.")
            return
        ok, text = describe.copy_drop_deck_key(provider,
                                               target_prefix=self._prefix)
        if ok:
            self._pending.pop(provider, None)
            self._load_key(provider)
        self._refresh()
        self._show_status(text)
        self._say(text)

    def ask_yes(self, question, title, yes_label, no_label):
        """A question in a read-only field. A test replaces this."""
        with ConsentDialog(self, title, question, yes_label, no_label) as box:
            box.ShowModal()
            return box.result

    # -- the two buttons that go online --------------------------------------
    def _key_in_use(self, provider):
        typed = self.key.GetValue().strip()
        return typed or self._stored(provider)

    def _on_list(self, _event=None):
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES[provider]
        key = self._key_in_use(provider)
        if not key:
            self._show_status("Put a key in first, then ask for the list.")
            self._say(self._raw.get(self.status, ""))
            return
        self.list_button.Enable(False)
        self._show_status("Asking %s what it has." % who)
        generation = self._generation

        def work():
            ok, got = ai.list_models(provider, key)
            wx.CallAfter(self._listed, generation, provider, ok, got)

        threading.Thread(target=work, name="easypdf-model-list",
                         daemon=True).start()

    def _listed(self, generation, provider, ok, got):
        if not self or generation != self._generation:
            return
        self.list_button.Enable(True)
        if not ok:
            self._show_status(got)
            self._say(got)
            return
        keeping = self.model.GetValue().strip()
        self.model.Set(list(got))
        self.model.SetValue(keeping)
        text = ("%d models. Arrow through the list, or leave the box empty "
                "for %s." % (len(got), ai.DEFAULT_MODELS.get(provider,
                                                             "the usual one")))
        self._show_status(text)
        self._say(text)

    def _on_test(self, _event=None):
        provider = self.chosen_provider()
        who = ai.PROVIDER_NAMES[provider]
        key = self._key_in_use(provider)
        if not key:
            self._show_status("Put a key in first, then test it.")
            self._say(self._raw.get(self.status, ""))
            return
        model = self.model.GetValue().strip()
        picture = test_picture()
        pictures = [picture] if picture else []
        prompt = TEST_PROMPT if picture else TEST_PROMPT_NO_PICTURE
        self.test_button.Enable(False)
        self._show_status("Testing with %s." % who)
        generation = self._generation
        started = time.monotonic()

        def work():
            ok, text = ai.ask(pictures, prompt, provider, key, model,
                              timeout=60.0, max_tokens=ai.IMAGE_TOKENS)
            wx.CallAfter(self._tested, generation, who, ok, text,
                         time.monotonic() - started)

        threading.Thread(target=work, name="easypdf-key-test",
                         daemon=True).start()

    def _tested(self, generation, who, ok, text, took):
        if not self or generation != self._generation:
            return
        self.test_button.Enable(True)
        if ok:
            text = "%s answered in %d seconds: %s" % (who, int(round(took)),
                                                     " ".join(text.split()))
        self._show_status(text)
        self._say(text)

    def _show_status(self, text):
        self._set_text(self.status, text)

    # -- writing it back ----------------------------------------------------
    def apply(self):
        """Provider and model into settings; the key into Credential
        Manager. A box left empty for a provider that had a key forgets it;
        a provider never visited on this page is left alone."""
        provider = self.chosen_provider()
        self._pending[provider] = self.key.GetValue()
        self.settings["ai_provider"] = provider
        self.settings["ai_model"] = self.model.GetValue().strip()[:80]
        for name, text in list(self._pending.items()):
            if name not in ai.PROVIDERS:
                continue
            text = (text or "").strip()
            stored = self._stored(name)
            try:
                if text and text != stored:
                    secrets.store(name, text, self._prefix)
                elif not text and stored:
                    secrets.forget(name, self._prefix)
            except Exception:
                pass
        self._pending = {}
        self._generation += 1
