"""The provider layer: three envelopes, three readers, one set of sentences.

Everything else in TG Imprint is deterministic. This is the one layer that
can be slow, can cost money, can fail for reasons outside the machine, and
sends somebody's picture to a company. So these checks are about what it
must never do: never raise, never put a key in an address, never send a
picture bigger than it needs to, and never answer with a number where a
sentence is owed. No network: `urlopen` is a fake here.

    python tests/test_ai.py
"""

import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgimprint import ai  # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


def head(title):
    print(os.linesep + title + os.linesep)


from PIL import Image  # noqa: E402


def png_bytes(width, height, colour=(40, 90, 160), noisy=False):
    if noisy:
        image = Image.effect_noise((width, height), 80).convert("RGB")
    else:
        image = Image.new("RGB", (width, height), colour)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def jpeg_bytes(width, height, colour=(200, 120, 40), exif_orientation=None):
    image = Image.new("RGB", (width, height), colour)
    buffer = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        image.save(buffer, "JPEG", quality=85, exif=exif.tobytes())
    else:
        image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def size_of(data):
    return Image.open(io.BytesIO(data)).size


# ---------------------------------------------------------------------------
head("The three envelopes, one picture (Drop Deck's builders, verbatim)")

jpeg = jpeg_bytes(640, 360)
addresses = {}
for name, builder in (("anthropic", ai._anthropic), ("openai", ai._openai),
                      ("google", ai._google)):
    request, read = builder("m", "SECRETKEY", jpeg, "ask")
    addresses[name] = request.full_url
    check("%s posts" % name, request.method == "POST")
    check("%s sends the key in a HEADER, never in the address" % name,
          "SECRETKEY" not in request.full_url
          and "SECRETKEY" in str(request.headers), request.full_url[:52])
    check("%s says it is JSON" % name,
          "json" in str(request.headers).lower())
    body = json.loads(request.data.decode("utf-8"))
    if name == "anthropic":
        first = body["messages"][0]["content"][0]
        check("anthropic carries the picture as a base64 JPEG block",
              first["type"] == "image"
              and first["source"]["media_type"] == "image/jpeg")
    elif name == "openai":
        image = body["messages"][0]["content"][1]["image_url"]["url"]
        check("openai carries the picture as a data address",
              image.startswith("data:image/jpeg;base64,"))
    else:
        part = body["contents"][0]["parts"][1]["inline_data"]
        check("google carries the picture inline", part["mime_type"] == "image/jpeg")
        check("google's model is in the path, not the query",
              "/models/m:generateContent" in request.full_url
              and "?" not in request.full_url)

# ---------------------------------------------------------------------------
head("The three envelopes, text plus several pictures")

pictures = [("image/png", png_bytes(320, 200)),
            ("image/jpeg", jpeg),
            ("image/png", png_bytes(100, 100, (255, 255, 255)))]
for name, builder in (("anthropic", ai._anthropic_parts),
                      ("openai", ai._openai_parts),
                      ("google", ai._google_parts)):
    request, read = builder("m", "SECRETKEY", pictures, "the question", 1234)
    check("%s multi-part posts to the same address as the single builder"
          % name, request.full_url == addresses[name], request.full_url[:52])
    check("%s multi-part keeps the key out of the address" % name,
          "SECRETKEY" not in request.full_url
          and "SECRETKEY" in str(request.headers))
    body = json.loads(request.data.decode("utf-8"))
    if name == "anthropic":
        content = body["messages"][0]["content"]
        kinds = [c["type"] for c in content]
        check("anthropic: three image blocks then one text block",
              kinds == ["image", "image", "image", "text"], kinds)
        mimes = [c["source"]["media_type"] for c in content[:3]]
        check("anthropic: each picture keeps its own type, in order",
              mimes == ["image/png", "image/jpeg", "image/png"], mimes)
        check("anthropic: the question is the text block",
              content[3]["text"] == "the question")
        check("anthropic: the answer budget is the one asked for",
              body["max_tokens"] == 1234)
        check("anthropic: the version header matches the single builder",
              request.headers.get("Anthropic-version")
              == ai._anthropic("m", "k", jpeg, "q")[0].headers.get(
                  "Anthropic-version"))
    elif name == "openai":
        content = body["messages"][0]["content"]
        kinds = [c["type"] for c in content]
        check("openai: the text first, then three pictures",
              kinds == ["text", "image_url", "image_url", "image_url"], kinds)
        prefixes = [c["image_url"]["url"][:15] for c in content[1:]]
        check("openai: each picture keeps its own type, in order",
              prefixes == ["data:image/png;", "data:image/jpeg", "data:image/png;"],
              prefixes)
        check("openai: pictures are sent at high detail so labels can be read",
              all(c["image_url"].get("detail") == "high" for c in content[1:]))
        check("openai: the budget uses the name every current model takes",
              body.get("max_completion_tokens") == 1234
              and "max_tokens" not in body, sorted(body))
    else:
        parts = body["contents"][0]["parts"]
        check("google: the text first, then three inline pictures",
              "text" in parts[0] and all("inline_data" in p for p in parts[1:])
              and len(parts) == 4)
        mimes = [p["inline_data"]["mime_type"] for p in parts[1:]]
        check("google: each picture keeps its own type, in order",
              mimes == ["image/png", "image/jpeg", "image/png"], mimes)
        check("google: the answer budget is the one asked for",
              body["generationConfig"]["maxOutputTokens"] == 1234)

request, _read = ai._google_parts("m", "k", [], "text only", 50)
body = json.loads(request.data.decode("utf-8"))
check("a text only question is a single text part",
      body["contents"][0]["parts"] == [{"text": "text only"}])
request, _read = ai._anthropic_parts("m", "k", [], "text only", 50)
body = json.loads(request.data.decode("utf-8"))
check("and for anthropic a single text block",
      body["messages"][0]["content"] == [{"type": "text", "text": "text only"}])

# ---------------------------------------------------------------------------
head("The readers dig the text out of each provider's answer shape")

thoughtful = {"content": [{"type": "thinking", "thinking": ""},
                          {"type": "text", "text": "A yellow circle."}],
              "stop_reason": "end_turn"}
check("anthropic: a thinking block first does not hide the text",
      ai._read_anthropic(thoughtful) == "A yellow circle.")
plain = {"content": [{"type": "text", "text": "A yellow circle."}]}
check("anthropic: a plain answer reads the same",
      ai._read_anthropic(plain) == "A yellow circle.")
_r, single_read = ai._anthropic("m", "k", jpeg, "q")
try:
    single_read(thoughtful)
    single_fails = False
except (KeyError, IndexError, TypeError):
    single_fails = True
check("anthropic: Drop Deck's block-zero reader would fail on that shape, "
      "which is why the multi-part reader joins text blocks", single_fails)
check("openai: the message content",
      ai._openai_parts("m", "k", [], "q")[1](
          {"choices": [{"message": {"content": "A yellow circle."}}]})
      == "A yellow circle.")
gemini = {"candidates": [{"content": {"parts": [
    {"text": "let me think", "thought": True},
    {"text": "A yellow circle."}]}}]}
check("google: a thought part is skipped and the text part read",
      ai._read_google(gemini) == "A yellow circle.")
gemini_two = {"candidates": [{"content": {"parts": [
    {"text": "A yellow"}, {"text": " circle."}]}}]}
check("google: two text parts are joined",
      ai._read_google(gemini_two).replace("\n", "") == "A yellow circle.")

# ---------------------------------------------------------------------------
head("_trouble says it in words that name the provider, never a number")

for provider in ai.PROVIDERS:
    who = ai.PROVIDER_NAMES[provider]
    for code, word in ((401, "key"), (403, "key"), (404, "model"),
                       (429, "credit"), (400, "refused"), (413, "too big"),
                       (500, "their end"), (503, "their end")):
        error = urllib.error.HTTPError("u", code, "m", {}, None)
        said = ai._trouble(error, provider)
        check("%s, HTTP %d: names the provider and says '%s'"
              % (provider, code, word),
              who in said and word in said.lower() and str(code) not in said,
              said[:60])
said = ai._trouble(urllib.error.URLError("offline"), "google")
check("offline: says to check the machine is online, and the document is "
      "unaffected", "online" in said and "document" in said, said[:70])
said = ai._trouble(TimeoutError("timed out"), "openai")
check("a timeout says so and names the provider",
      "in time" in said and "ChatGPT" in said, said[:60])
said = ai._trouble(ValueError("something odd"), "anthropic")
check("anything else is still a sentence with the cause in it",
      "could not be done" in said and "something odd" in said, said[:60])
check("404 points at the Model box on the AI page",
      "AI page" in ai._trouble(urllib.error.HTTPError("u", 404, "m", {}, None),
                               "google"))

# ---------------------------------------------------------------------------
head("The model list digger handles each provider's shape")

url, dig = ai._MODEL_LISTS["anthropic"]
check("anthropic: ids from data", dig({"data": [{"id": "claude-x"}, {"id": "claude-y"}]})
      == ["claude-x", "claude-y"])
url, dig = ai._MODEL_LISTS["openai"]
check("openai: ids from data", dig({"data": [{"id": "gpt-x"}]}) == ["gpt-x"])
url, dig = ai._MODEL_LISTS["google"]
got = dig({"models": [
    {"name": "models/gemini-x", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/embed-1", "supportedGenerationMethods": ["embedContent"]},
    {"name": "models/gemini-y", "supportedGenerationMethods": ["generateContent",
                                                               "countTokens"]}]})
check("google: only models that generate content, without the models/ prefix",
      got == ["gemini-x", "gemini-y"], got)
ok, said = ai.list_models("nobody", "k")
check("an unknown provider is a sentence", not ok and "not a service" in said)
ok, said = ai.list_models("google", "")
check("no key is a sentence", not ok and "key" in said.lower())


class _Answer:
    """What urlopen hands back: a context manager with read()."""

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _Fake:
    """A stand-in for urlopen that records the request and answers as told."""

    def __init__(self, answer=None, error=None):
        self.answer = answer
        self.error = error
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        payload = self.answer(request) if callable(self.answer) else self.answer
        return _Answer(payload)


real_urlopen = urllib.request.urlopen

fake = _Fake({"models": [{"name": "models/gemini-live",
                          "supportedGenerationMethods": ["generateContent"]}]})
urllib.request.urlopen = fake
try:
    ok, got = ai.list_models("google", "SECRETKEY")
finally:
    urllib.request.urlopen = real_urlopen
check("list_models end to end against a fake server", ok and got == ["gemini-live"], got)
check("and it asked with the key in a header",
      "SECRETKEY" in str(fake.requests[0][0].headers)
      and "SECRETKEY" not in fake.requests[0][0].full_url)
fake = _Fake({"models": []})
urllib.request.urlopen = fake
try:
    ok, got = ai.list_models("google", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("an empty list is a sentence, not an empty list",
      not ok and "no models" in got, got)

# ---------------------------------------------------------------------------
head("A picture is scaled before it goes, JPEG for JPEG and PNG for PNG")

check("the sending width is 1,600, for chart labels", ai.SEND_WIDTH == 1600)
big_jpeg = jpeg_bytes(4000, 3000)
prepared = ai.prepare_picture(big_jpeg)
check("a 4000 wide JPEG comes back as JPEG", prepared is not None
      and prepared[0] == "image/jpeg")
check("and 1,600 wide", prepared is not None and size_of(prepared[1]) == (1600, 1200),
      size_of(prepared[1]) if prepared else None)
check("and well under a megabyte", prepared is not None and len(prepared[1]) < 1048576,
      "%d bytes" % (len(prepared[1]) if prepared else 0))
check("and it really is JPEG data", prepared is not None and prepared[1][:2] == b"\xff\xd8")
flat_png = png_bytes(3000, 2000)
prepared = ai.prepare_picture(flat_png)
check("a 3000 wide PNG stays PNG", prepared is not None and prepared[0] == "image/png")
check("and is 1,600 wide", prepared is not None and size_of(prepared[1]) == (1600, 1067),
      size_of(prepared[1]) if prepared else None)
check("and it really is PNG data", prepared is not None and prepared[1][:8] == b"\x89PNG\r\n\x1a\n")
noisy_png = png_bytes(2400, 1800, noisy=True)
prepared = ai.prepare_picture(noisy_png)
check("a photograph in PNG clothing goes as JPEG instead (the PNG would be over %d MB)"
      % (ai.PNG_CEILING // 1048576),
      prepared is not None and prepared[0] == "image/jpeg", prepared[0] if prepared else None)
small = png_bytes(320, 200)
prepared = ai.prepare_picture(small)
check("a small picture is not scaled UP", prepared is not None
      and size_of(prepared[1]) == (320, 200))
sideways = jpeg_bytes(400, 200, exif_orientation=6)
prepared = ai.prepare_picture(sideways)
check("a phone photo's orientation tag is honoured (400 by 200 tagged as "
      "rotated becomes 200 by 400)", prepared is not None
      and size_of(prepared[1]) == (200, 400), size_of(prepared[1]) if prepared else None)
rgba = Image.new("RGBA", (300, 300), (255, 0, 0, 0))
buffer = io.BytesIO()
rgba.save(buffer, "PNG")
prepared = ai.prepare_picture(buffer.getvalue())
check("a transparent PNG stays PNG with its transparency", prepared is not None
      and prepared[0] == "image/png"
      and Image.open(io.BytesIO(prepared[1])).mode == "RGBA")
check("garbage bytes are None, not an exception", ai.prepare_picture(b"not a picture") is None)
check("no bytes are None too", ai.prepare_picture(b"") is None
      and ai.prepare_picture(None) is None)
check("sent_kilobytes adds up the pictures and the text",
      abs(ai.sent_kilobytes([("image/png", b"x" * 1024), ("image/jpeg", b"y" * 1024)],
                            "z" * 1024) - 3.0) < 0.001)

# ---------------------------------------------------------------------------
head("Nothing raises, whatever is wrong")

good = [("image/png", png_bytes(320, 200))]
ok, said = ai.ask(good, "q", "google", "")
check("no key is a sentence pointing at Preferences", not ok and "Preferences" in said)
ok, said = ai.ask(good, "q", "notaprovider", "k")
check("an unknown provider is a sentence", not ok and "provider" in said)
ok, said = ai.ask(good, "   ", "google", "k")
check("an empty question is a sentence", not ok and "nothing to ask" in said)
ok, said = ai.ask([None], "q", "google", "k")
check("a picture that could not be prepared is a sentence and nothing leaves",
      not ok and "nothing has left" in said)
ok, said = ai.ask([("image/png", b"")], "q", "google", "k")
check("and so is an empty one", not ok and "nothing has left" in said)

# ---------------------------------------------------------------------------
head("A fake urlopen, end to end, for each provider")


def answer_for(request):
    url = request.full_url
    if "anthropic" in url:
        return {"content": [{"type": "thinking", "thinking": ""},
                            {"type": "text", "text": "  A yellow circle.  "}],
                "stop_reason": "end_turn"}
    if "openai" in url:
        return {"choices": [{"message": {"content": "A yellow circle."},
                             "finish_reason": "stop"}]}
    return {"candidates": [{"content": {"parts": [{"text": "A yellow circle."}]},
                            "finishReason": "STOP"}]}


for provider in ai.PROVIDERS:
    fake = _Fake(answer_for)
    urllib.request.urlopen = fake
    try:
        ok, text = ai.ask(good, "what is this", provider, "SECRETKEY", "",
                          timeout=12.5, max_tokens=321)
    finally:
        urllib.request.urlopen = real_urlopen
    check("%s: the answer comes back stripped" % provider,
          ok and text == "A yellow circle.", text)
    request, timeout = fake.requests[0]
    check("%s: the key travelled in a header only" % provider,
          "SECRETKEY" in str(request.headers) and "SECRETKEY" not in request.full_url)
    check("%s: the timeout asked for is the one used" % provider, timeout == 12.5)
    body = json.loads(request.data.decode("utf-8"))
    if provider == "google":
        check("google: an empty model name means the default, in the path",
              "/models/%s:" % ai.DEFAULT_MODELS["google"] in request.full_url)
        check("google: the budget travelled",
              body["generationConfig"]["maxOutputTokens"] == 321)
    else:
        check("%s: an empty model name means the default" % provider,
              body["model"] == ai.DEFAULT_MODELS[provider])

fake = _Fake(error=urllib.error.HTTPError("u", 401, "m", {}, None))
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "openai", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("a 401 from the server becomes the key sentence", not ok and "key" in said.lower())

fake = _Fake({"candidates": [{"finishReason": "SAFETY"}],
              "promptFeedback": {"blockReason": "SAFETY"}})
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "google", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("a content filter is named as such, not as a broken key",
      not ok and "content filter" in said and "key" in said, said[:60])

fake = _Fake({"content": [{"type": "text", "text": "no"}], "stop_reason": "refusal"})
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "anthropic", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("anthropic's refusal stop reason is the same sentence",
      not ok and "content filter" in said)

fake = _Fake({"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]})
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "openai", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("an empty answer says nothing came back", not ok and "nothing back" in said)

fake = _Fake({"unexpected": True})
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "google", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("a strange shape is a sentence", not ok and "shape" in said)

fake = _Fake(error=urllib.error.URLError("no route"))
urllib.request.urlopen = fake
try:
    ok, said = ai.ask(good, "q", "google", "k")
finally:
    urllib.request.urlopen = real_urlopen
check("being offline is a sentence", not ok and "online" in said)

# ---------------------------------------------------------------------------
head("Who to ask, and the defaults")

check("every provider has a name that can be read out",
      all(p in ai.PROVIDER_NAMES for p in ai.PROVIDERS))
check("and a default model", all(ai.DEFAULT_MODELS.get(p) for p in ai.PROVIDERS))
check("and its default is among the known names",
      all(ai.DEFAULT_MODELS[p] in ai.KNOWN_MODELS[p] for p in ai.PROVIDERS))
check("the Google default is a moving alias, not a pinned version",
      "latest" in ai.DEFAULT_MODELS["google"], ai.DEFAULT_MODELS["google"])
check("the Google default is the accurate flash alias, not the lite one",
      ai.DEFAULT_MODELS["google"] == "gemini-flash-latest")
check("the document timeout is longer than the picture timeout",
      ai.DOCUMENT_TIMEOUT > ai.TIMEOUT >= 60)
check("the document answer budget is bigger than the picture one",
      ai.DOCUMENT_TOKENS > ai.IMAGE_TOKENS >= 1500)
have = ai.providers_with_keys()
if have:
    check("the default follows a key that is really on this machine",
          ai.best_provider("anthropic") in have, ai.best_provider("anthropic"))
else:
    check("with no keys at all it falls back rather than failing",
          ai.best_provider("anthropic") == "anthropic")
source = open(ai.__file__, encoding="utf-8").read()
check("nothing of the camera or the screen prompts survived the copy",
      "_CAMERA" not in source and "_SCREEN" not in source
      and "needs_consent" not in source and "converse" not in source)
check("and nothing in this file imports wx", "import wx" not in source)

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
