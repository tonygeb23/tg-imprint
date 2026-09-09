"""Asking a model that can see, on the user's own key, and nothing more.

TG Imprint's copy of TG Drop Deck's vision.py, which shipped on 8 September
2026 against all three services. The transport (`_request`, the three
provider functions and their readers), the error sentences in `_trouble`,
`list_models` and its diggers, `providers_with_keys` and `best_provider`
are kept with their shape, so a fix found in Drop Deck can be carried
across by copying the function. What is different is the job. Drop Deck
looks at a camera before a show and wants speed. TG Imprint writes the
alternative text for a picture that will sit in a distributed file for
ever, and describes a whole document to somebody who cannot see it, so it
wants accuracy: pictures go at 1,600 pixels wide rather than 1,024, a PNG
stays a PNG so chart labels and screenshot text survive, and one request
can carry the document's text plus many pictures. The prompts and the
consent rules live in describe.py.

Three rules hold this module up, and they are Drop Deck's rules.

Nothing here raises. Every failure comes back as a sentence somebody can
act on, because the person reading it cannot look at the screen to work
out what went wrong. A traceback in a status bar is not an answer.

Nothing here touches the window. Every call takes seconds and can fail, so
the dialogs put it on a thread of their own and come back with
wx.CallAfter. Nothing in this file imports wx.

Nothing leaves the machine without consent that names the provider. The
consent rules are in describe.py; this module only ever sends what it is
handed, and it can say how big that is first.

No new dependency. All three providers are plain HTTPS and JSON, so urllib
and the standard library cover it and the installer does not grow.
"""
from __future__ import annotations

import base64
import io as _io
import json
import urllib.error
import urllib.request

#: The three, in the order Tony named them.
PROVIDERS = ("anthropic", "openai", "google")

#: What each one is called out loud, so the settings page and the consent
#: question can say something better than "the API".
PROVIDER_NAMES = {
    "anthropic": "Claude, from Anthropic",
    "openai": "ChatGPT, from OpenAI",
    "google": "Gemini, from Google",
}

#: Sensible defaults that can be typed over. Model names change faster than
#: this app ships, so the model is a SETTING with a default rather than a
#: constant: a user whose provider has moved on can put the new name in
#: without waiting for a release, and `_trouble` tells them when that is what
#: has happened. Where a provider publishes a moving alias, that is the
#: default rather than a pinned version: measured in Drop Deck on 8 September
#: 2026, gemini-2.0-flash was already a 404 on a live key.
#:
#: **Accuracy is the choice here, not speed.** Drop Deck picks the quick
#: model because a presenter is stood waiting to go on air. An author writing
#: alternative text is writing something that will be read from a file for
#: years, and a chart's numbers have to come back right. Measured on this
#: machine on 9 September 2026 with Tony's Gemini key, on the circle fixture
#: and on a bar chart with six labelled values (the answers are in
#: docs/DESCRIBER.md): gemini-flash-lite-latest read all six chart values
#: right in 1.4 seconds, but called the circle fixture "the national flag
#: of Palau", an invention that would have gone into a file; gemini-pro-latest
#: was right on both and took 16.5 and 25.0 seconds; gemini-flash-latest was
#: right on both, all six values and the axis, in 7.2 and 5.9 seconds. So
#: the Google default is the flash alias: the accurate one at a usable speed.
#: There are no Anthropic or OpenAI keys on this machine, so those two are
#: not measured: each is its provider's current general model with vision,
#: named from the published lists in September 2026, and Get the list on the
#: settings page replaces them with whatever the account can really see.
DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-4.1",
    "google": "gemini-flash-latest",
}

#: Long enough for a considered answer even from a slow thinking model, which
#: a user may well type into the model box.
TIMEOUT = 90.0

#: A whole document, with a dozen pictures attached and a long answer to
#: write, is a different order of request. Measured: the flash model took
#: under half a minute for the sample document; a pro model can take longer.
DOCUMENT_TIMEOUT = 240.0

#: Room for the answer. A ceiling and not a target: nothing is billed for
#: tokens that are not written. It is high because on the current Claude
#: models thinking happens inside this budget before the answer does, and a
#: Gemini model does the same; Drop Deck measured one Gemini answer stopping
#: after eighteen characters under a low ceiling.
IMAGE_TOKENS = 4000
DOCUMENT_TOKENS = 16000

#: The picture is scaled down before it goes. 1,600 wide, not Drop Deck's
#: 1,024: the demanding case here is a chart's axis labels or the small text
#: in a screenshot, which have to be read back exactly, and 1,600 keeps them
#: legible while staying well inside every provider's limits.
SEND_WIDTH = 1600

#: A JPEG source goes as JPEG at this quality. A photograph survives it.
SEND_QUALITY = 85

#: A PNG source stays PNG, because a chart or a screenshot is ruined by JPEG
#: ringing around its text. But a photograph saved as PNG makes a huge PNG,
#: and Anthropic refuses a single picture over five megabytes. Over this
#: size a PNG is a photograph in PNG clothing and goes as JPEG instead.
PNG_CEILING = 2 * 1024 * 1024


#: Offered in the model box before anybody asks the service. Short on
#: purpose: the box is editable and the Get the list button replaces these
#: with whatever the account can really see, which is the only list that
#: cannot go stale.
KNOWN_MODELS = {
    "anthropic": ("claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"),
    "openai": ("gpt-4.1", "gpt-4o", "gpt-4.1-mini"),
    "google": ("gemini-flash-latest", "gemini-pro-latest",
               "gemini-flash-lite-latest"),
}

#: Where each provider will say what it has, and how to dig the names out.
_MODEL_LISTS = {
    "anthropic": ("https://api.anthropic.com/v1/models",
                  lambda got: [m["id"] for m in got.get("data", [])]),
    "openai": ("https://api.openai.com/v1/models",
               lambda got: [m["id"] for m in got.get("data", [])]),
    "google": ("https://generativelanguage.googleapis.com/v1beta/models",
               lambda got: [m["name"].split("/")[-1]
                            for m in got.get("models", [])
                            if "generateContent"
                            in m.get("supportedGenerationMethods", [])]),
}


def list_models(provider, key, timeout=30.0):
    """What this account can really use. Returns `(ok, names or message)`.

    Model names change faster than this app ships, which is not a guess:
    on 8 September 2026 two of the names Drop Deck had as defaults were
    already gone on a live key. A list typed into the source is a list that
    goes wrong quietly, so the app can ask instead.
    """
    provider = (provider or "").strip().lower()
    where = _MODEL_LISTS.get(provider)
    if where is None:
        return False, "That is not a service this app knows."
    if not key:
        return False, "Put a key in first, then ask for the list."
    url, dig = where
    headers = {"accept": "application/json"}
    if provider == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    elif provider == "openai":
        headers["authorization"] = "Bearer " + key
    else:
        headers["x-goog-api-key"] = key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            got = json.loads(answer.read().decode("utf-8", "replace"))
    except Exception as error:
        return False, _trouble(error, provider)
    try:
        names = [n for n in dig(got) if n]
    except Exception:
        return False, "The list came back in a shape this app did not expect."
    if not names:
        return False, "That account has no models that can look at pictures."
    return True, sorted(set(names))


def providers_with_keys():
    """Which of the three have actually been set up on this machine."""
    from . import secrets
    out = []
    for name in PROVIDERS:
        try:
            if secrets.fetch(name, secrets.VISION_PREFIX):
                out.append(name)
        except Exception:
            pass
    return out


def best_provider(fallback):
    """Who to ask when nobody has chosen yet.

    The one whose key is actually present, rather than the alphabetically
    first. A window that says "Claude is asked" on a machine where the only
    key is a Gemini one is not a default, it is a wrong answer nobody typed.
    """
    have = providers_with_keys()
    if fallback in have:
        return fallback
    return have[0] if have else fallback


# ---------------------------------------------------------------------------
# Getting a picture into something that can be posted
# ---------------------------------------------------------------------------

def prepare_picture(image_bytes, width=SEND_WIDTH, quality=SEND_QUALITY):
    """The bytes of a picture file as `(mime_type, data)` ready to send, or
    None when it cannot be done.

    Scaled to at most `width` across, never scaled up. A JPEG source comes
    back as JPEG; anything else comes back as PNG, unless the PNG would be
    bigger than `PNG_CEILING`, in which case it is a photograph in PNG
    clothing and comes back as JPEG. A phone photo's orientation tag is
    honoured, so a picture taken sideways is not described sideways.

    Guarded end to end, because Drop Deck's build once shipped with Pillow
    present and its native modules missing and NOTHING said so.
    """
    try:
        from PIL import Image, ImageOps
    except Exception:
        return None
    try:
        image = Image.open(_io.BytesIO(image_bytes))
        image.load()
        source = (image.format or "").upper()
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        if width and image.width > width:
            height = max(1, int(round(image.height * width / float(image.width))))
            image = image.resize((width, height), Image.LANCZOS)
        if source != "JPEG":
            if image.mode not in ("RGB", "RGBA", "L", "LA"):
                has_alpha = "transparency" in image.info or image.mode in ("P", "PA")
                image = image.convert("RGBA" if has_alpha else "RGB")
            buffer = _io.BytesIO()
            image.save(buffer, "PNG")
            data = buffer.getvalue()
            if len(data) <= PNG_CEILING:
                return "image/png", data
        if image.mode in ("RGBA", "LA", "P", "PA"):
            # JPEG has no transparency: lay the picture on white, which is
            # what a page is.
            flat = Image.new("RGB", image.size, (255, 255, 255))
            rgba = image.convert("RGBA")
            flat.paste(rgba, mask=rgba.split()[-1])
            image = flat
        buffer = _io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True)
        return "image/jpeg", buffer.getvalue()
    except Exception:
        return None


def sent_kilobytes(pictures, text=""):
    """How much really leaves, so a dialog can say so rather than guess.

    `pictures` is a list of prepared `(mime_type, data)` pairs. The number is
    the picture and text bytes; the base64 wrapping on the wire adds about a
    third on top, which docs/DESCRIBER.md says.
    """
    total = sum(len(data) for _mime, data in (pictures or []) if data)
    total += len((text or "").encode("utf-8"))
    return total / 1024.0


# ---------------------------------------------------------------------------
# The three providers. Same question, three shapes of envelope.
#
# The single picture functions are Drop Deck's, verbatim, so a fix there can
# be pasted here. The `_parts` function beside each is the same envelope
# generalised to one text part plus any number of pictures of either type,
# which is what this app sends; when one of a pair changes, change both.
# tests/test_ai.py checks that each pair agrees on its address and headers.
# ---------------------------------------------------------------------------

def _request(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers,
                                  method="POST")


def _anthropic(model, key, jpeg, prompt):
    body = {"model": model, "max_tokens": 700,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.b64encode(jpeg).decode("ascii")}},
                {"type": "text", "text": prompt}]}]}
    request = _request("https://api.anthropic.com/v1/messages",
                       {"content-type": "application/json",
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01"}, body)
    return request, lambda got: got["content"][0]["text"]


def _anthropic_parts(model, key, pictures, prompt, max_tokens=IMAGE_TOKENS):
    content = []
    for mime, data in pictures:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": mime,
            "data": base64.b64encode(data).decode("ascii")}})
    content.append({"type": "text", "text": prompt})
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}]}
    request = _request("https://api.anthropic.com/v1/messages",
                       {"content-type": "application/json",
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01"}, body)
    return request, _read_anthropic


def _read_anthropic(got):
    # The text blocks, joined. On the current Claude models thinking is on
    # unless it is switched off, and a thinking block comes FIRST in the
    # answer, so taking block zero would hand back an empty thought. This
    # is the one place the `_parts` reader knowingly differs from the
    # single picture reader above, and it is a fix worth carrying back.
    texts = [block.get("text", "") for block in got["content"]
             if block.get("type") == "text"]
    return "\n".join(t for t in texts if t)


def _openai(model, key, jpeg, prompt):
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    body = {"model": model, "max_tokens": 700,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}}]}]}
    request = _request("https://api.openai.com/v1/chat/completions",
                       {"content-type": "application/json",
                        "authorization": "Bearer " + key}, body)
    return request, lambda got: got["choices"][0]["message"]["content"]


def _openai_parts(model, key, pictures, prompt, max_tokens=IMAGE_TOKENS):
    content = [{"type": "text", "text": prompt}]
    for mime, data in pictures:
        url = "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
        # "high" detail, so the model looks at the picture in tiles rather
        # than one 512 pixel thumbnail. Chart labels need it.
        content.append({"type": "image_url",
                        "image_url": {"url": url, "detail": "high"}})
    # max_completion_tokens rather than max_tokens: the older name is
    # refused by OpenAI's reasoning models, and a user can type any model
    # name into the box. Every current OpenAI model takes the newer name.
    body = {"model": model, "max_completion_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}]}
    request = _request("https://api.openai.com/v1/chat/completions",
                       {"content-type": "application/json",
                        "authorization": "Bearer " + key}, body)
    return request, lambda got: got["choices"][0]["message"]["content"]


def _google(model, key, jpeg, prompt):
    body = {"contents": [{"parts": [
        {"text": prompt},
        {"inline_data": {"mime_type": "image/jpeg",
                         "data": base64.b64encode(jpeg).decode("ascii")}}]}],
        # A ceiling, because a thinking model spends this budget on thinking
        # FIRST and then has nothing left to answer with. Measured: without
        # it, one model returned the eighteen characters "There is no camera"
        # and stopped mid sentence.
        "generationConfig": {"maxOutputTokens": 1500}}
    # The key goes in a header rather than the query string, so it cannot end
    # up in a proxy log or a crash report.
    request = _request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "%s:generateContent" % model,
        {"content-type": "application/json", "x-goog-api-key": key}, body)
    return request, lambda got: (
        got["candidates"][0]["content"]["parts"][0]["text"])


def _google_parts(model, key, pictures, prompt, max_tokens=IMAGE_TOKENS):
    parts = [{"text": prompt}]
    for mime, data in pictures:
        parts.append({"inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("ascii")}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    request = _request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "%s:generateContent" % model,
        {"content-type": "application/json", "x-goog-api-key": key}, body)
    return request, _read_google


def _read_google(got):
    # Every text part joined, skipping parts marked as thoughts, which a
    # thinking model can put first.
    parts = got["candidates"][0]["content"]["parts"]
    texts = [p.get("text", "") for p in parts if not p.get("thought")]
    return "\n".join(t for t in texts if t)


_BUILDERS = {"anthropic": _anthropic, "openai": _openai, "google": _google}
_PART_BUILDERS = {"anthropic": _anthropic_parts, "openai": _openai_parts,
                  "google": _google_parts}


# ---------------------------------------------------------------------------

def _trouble(error, provider):
    """A failure said in words somebody can act on.

    The person reading this cannot look at the screen to work out what went
    wrong, so "HTTP 401" is not an answer. Each of these names the thing to
    go and change. Drop Deck's sentences, with "the show" replaced by "the
    document", because that is what is unaffected here.
    """
    who = PROVIDER_NAMES.get(provider, provider)
    code = getattr(error, "code", None)
    if code == 401 or code == 403:
        return ("%s would not accept that key. Check it has been pasted in "
                "full, and that it is a key for %s rather than another "
                "service." % (who, who))
    if code == 404:
        return ("%s does not know that model name. Model names change; put "
                "the current one in the Model box on the AI page of "
                "Preferences, or use Get the list there." % who)
    if code == 429:
        return ("%s is rate limiting, or the account has run out of credit. "
                "Wait a moment and try again, or check the billing on your "
                "account." % who)
    if code == 400:
        return ("%s refused the request. The most likely cause is a model "
                "name that cannot look at pictures; the other is a document "
                "too big for it. Try the default model again, or describe "
                "fewer pictures." % who)
    if code == 413:
        return ("%s said the request was too big. Describe fewer pictures "
                "at a time." % who)
    if code is not None and 500 <= int(code) < 600:
        return ("%s is having trouble at their end. Nothing is wrong here, "
                "so try again in a minute." % who)
    if isinstance(error, urllib.error.URLError):
        return ("Could not reach %s. Check this machine is online. Nothing "
                "in your document has changed." % who)
    if isinstance(error, TimeoutError) or "timed out" in str(error).lower():
        return ("%s did not answer in time. Try again, or try a quicker "
                "model. Nothing in your document has changed." % who)
    return ("The description could not be done: %s. Nothing in your "
            "document has changed." % error)


def _declined(got, provider):
    """A sentence when the service answered but would not describe, or an
    empty string when it did describe. A content filter is not a fault in
    the key or the model, and saying "nothing came back" would send somebody
    off to check things that are fine."""
    who = PROVIDER_NAMES.get(provider, provider)
    said = ("%s declined to describe this. Its content filter stopped the "
            "answer, which happens with some pictures of people and some "
            "documents. Nothing is wrong with your key." % who)
    try:
        if provider == "google":
            if got.get("promptFeedback", {}).get("blockReason"):
                return said
            candidates = got.get("candidates") or []
            if candidates and candidates[0].get("finishReason") in (
                    "SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
                return said
        elif provider == "anthropic":
            if got.get("stop_reason") == "refusal":
                return said
        elif provider == "openai":
            choices = got.get("choices") or []
            if choices and choices[0].get("finish_reason") == "content_filter":
                return said
    except Exception:
        pass
    return ""


def ask(pictures, prompt, provider, key, model="", timeout=TIMEOUT,
        max_tokens=IMAGE_TOKENS):
    """One question, any number of prepared pictures, one answer.

    `pictures` is a list of `(mime_type, data)` pairs from `prepare_picture`,
    and may be empty for a text only question. Returns `(ok, text)`.
    **Never raises**, and never runs on the window thread: the caller puts
    it on one of its own.
    """
    if not key:
        return False, ("No key has been set up yet. Put one in on the AI "
                       "page of Preferences, then try again.")
    provider = (provider or "").strip().lower()
    build = _PART_BUILDERS.get(provider)
    if build is None:
        return False, ("That provider is not one this app knows. Choose "
                       "Claude, ChatGPT or Gemini on the AI page of "
                       "Preferences.")
    if not (prompt or "").strip():
        return False, "There is nothing to ask."
    pictures = list(pictures or [])
    for pair in pictures:
        try:
            mime, data = pair
        except Exception:
            mime, data = None, None
        if not mime or not data:
            return False, ("One of the pictures could not be prepared for "
                           "sending, so nothing has left this machine.")
    model = (model or "").strip() or DEFAULT_MODELS.get(provider, "")
    request, read = build(model, key, pictures, prompt, max_tokens)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            got = json.loads(answer.read().decode("utf-8", "replace"))
    except Exception as error:
        return False, _trouble(error, provider)
    declined = _declined(got, provider)
    if declined:
        return False, declined
    try:
        text = (read(got) or "").strip()
    except Exception:
        return False, ("%s answered in a shape this app did not expect, so "
                       "there is nothing to read out."
                       % PROVIDER_NAMES.get(provider, provider))
    if not text:
        return False, ("%s looked at the picture and said nothing back."
                       % PROVIDER_NAMES.get(provider, provider))
    return True, text
