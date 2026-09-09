"""The update client: Velopack does the work, the TG Studios key decides.

Every check here is about the gate. Velopack's feed is not signed, so the
signed manifest has to vouch for exactly the package Velopack offers, and
anything else has to be refused with a sentence that says why. The
Velopack manager is replaced by a stand-in, because nothing is installed on
the machine running this test; the UpdateInfo and VelopackAsset objects are
the real classes from the SDK.

    python tests/test_update.py
"""

import base64
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cryptography.hazmat.primitives import serialization   # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey   # noqa: E402
import velopack   # noqa: E402

from tgimprint import appupdate   # noqa: E402
from tgimprint import constants as C   # noqa: E402
from tgimprint import paths   # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


# A key of this test's own. The real public key stays untouched in the
# module; it is swapped in and restored around the checks that sign.
private = Ed25519PrivateKey.generate()
public_b64 = base64.b64encode(private.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
REAL_KEY = appupdate.PUBLIC_KEY_B64
appupdate.PUBLIC_KEY_B64 = public_b64

PACKAGE_SHA = "ab" * 32
MANIFEST = {"product": C.APP_NAME, "version": "9.9.9",
            "url": "https://example.invalid/TGImprint-9.9.9-Setup.exe",
            "sha256": "cd" * 32, "size": 100, "notes": "A note for the dialog.",
            "package": "%s-9.9.9-full.nupkg" % C.PACK_ID,
            "package_sha256": PACKAGE_SHA, "package_size": 5000,
            "releases_url": C.RELEASES_URL}


def envelope(manifest):
    # A copy, so a test that edits the envelope after signing cannot edit
    # the shared MANIFEST underneath every later check. The first version
    # of this test did exactly that and reported the gate broken.
    manifest = json.loads(json.dumps(manifest))
    payload = appupdate.canonical(manifest)
    return {"manifest": manifest,
            "signature": base64.b64encode(private.sign(payload)).decode()}


def asset(version="9.9.9", sha=PACKAGE_SHA, size=5000):
    return velopack.VelopackAsset(C.PACK_ID, version, "Full",
                                  "%s-%s-full.nupkg" % (C.PACK_ID, version),
                                  "", sha.upper(), size, "", "")


class FakeManager:
    def __init__(self, info="offered", portable=False, fail_download=None):
        self.kind = info
        self.portable = portable
        self.fail_download = fail_download
        self.applied = None
        self.downloaded = None

    def check_for_updates(self):
        if self.kind == "none":
            return None
        if self.kind == "swapped":
            return velopack.UpdateInfo(asset(sha="00" * 32), [], False)
        if self.kind == "wrong-size":
            return velopack.UpdateInfo(asset(size=4999), [], False)
        if self.kind == "other-version":
            return velopack.UpdateInfo(asset(version="9.9.8"), [], False)
        return velopack.UpdateInfo(asset(), [], False)

    def download_updates(self, info, callback=None):
        self.downloaded = info
        for step in (0, 25, 50, 75, 100):
            if self.fail_download == "midway" and step == 50:
                raise RuntimeError("the wire dropped")
            if callback:
                callback(step)

    def apply_updates_and_restart(self, info):
        self.applied = info

    def get_is_portable(self):
        return self.portable

    def get_current_version(self):
        return "1.0.0"


def serve(manifest_envelope=None, manager=None, manifest_error=None):
    def fetch(url, limit=None, **kw):
        if manifest_error:
            raise manifest_error
        if url == appupdate.MANIFEST_URL:
            return json.dumps(manifest_envelope or envelope(MANIFEST)).encode()
        raise RuntimeError("unexpected fetch of %s" % url)
    appupdate._fetch = fetch
    appupdate._make_manager = (lambda: manager) if manager is not None else None


real_fetch, real_maker = appupdate._fetch, appupdate._make_manager
try:
    print("\nVersions compare as numbers")
    check("0.10.0 is newer than 0.9.0",
          appupdate.parse_version("0.10.0") > appupdate.parse_version("0.9.0"))
    check("junk sorts as zero", appupdate.parse_version("x.y") == (0, 0, 0))

    print("\nThe signed manifest")
    parsed, message = appupdate.read_envelope(json.dumps(envelope(MANIFEST)).encode())
    check("a manifest signed with the key is read", parsed == MANIFEST, message)
    edited = envelope(MANIFEST)
    edited["manifest"]["version"] = "99.0.0"
    parsed, message = appupdate.read_envelope(json.dumps(edited).encode())
    check("one edited after signing is refused", parsed is None and "wrong key" in message, message)
    parsed, message = appupdate.read_envelope(b"not json at all")
    check("garbage is refused with a sentence", parsed is None and message, message)
    other = Ed25519PrivateKey.generate()
    forged = {"manifest": MANIFEST, "signature": base64.b64encode(
        other.sign(appupdate.canonical(MANIFEST))).decode()}
    parsed, message = appupdate.read_envelope(json.dumps(forged).encode())
    check("one signed by another key is refused", parsed is None)

    print("\nThe gate: what the manifest vouches for")
    ok, why = appupdate.vouches(MANIFEST, "9.9.9", PACKAGE_SHA.upper(), 5000)
    check("the right version, hash and size pass", ok, why)
    ok, why = appupdate.vouches(MANIFEST, "9.9.8", PACKAGE_SHA, 5000)
    check("another version is refused and named", not ok and "9.9.8" in why, why)
    ok, why = appupdate.vouches(MANIFEST, "9.9.9", "00" * 32, 5000)
    check("another hash is refused", not ok and "checksum" in why, why)
    ok, why = appupdate.vouches(MANIFEST, "9.9.9", PACKAGE_SHA, 4999)
    check("another size is refused", not ok and "bytes" in why, why)
    ok, why = appupdate.vouches({}, "9.9.9", PACKAGE_SHA, 5000)
    check("no manifest vouches for nothing", not ok)

    print("\ncheck(): the client asks Velopack and believes only the manifest")
    serve(manager=FakeManager())
    available, info, message = appupdate.check("1.0.0")
    check("an old client is offered the vouched package", available, message)
    check("with the version, the notes and the Velopack update inside",
          info["version"] == "9.9.9" and info["notes"] == "A note for the dialog."
          and info.get("velopack") is not None)
    available, info, message = appupdate.check("9.9.9")
    check("a client on the newest version is told so",
          not available and "newest" in message, message)
    available, info, message = appupdate.check("10.0.0")
    check("and so is one ahead of the feed", not available and "newest" in message)

    serve(manager=FakeManager("swapped"))
    available, info, message = appupdate.check("1.0.0")
    check("a package with a hash the manifest did not sign is refused",
          not available and "not vouched" in message, message)
    check("and nothing is handed to the window", info is None)

    serve(manager=FakeManager("wrong-size"))
    available, _i, message = appupdate.check("1.0.0")
    check("a package of another size is refused", not available and "not vouched" in message)

    serve(manager=FakeManager("other-version"))
    available, _i, message = appupdate.check("1.0.0")
    check("a package of another version is refused", not available and "not vouched" in message)

    serve(manager=FakeManager("none"))
    available, _i, message = appupdate.check("1.0.0")
    check("a manifest ahead of the feed says the download is not there yet",
          not available and "not there yet" in message, message)

    serve(manifest_envelope=edited, manager=FakeManager())
    available, _i, message = appupdate.check("1.0.0")
    check("an edited manifest stops everything before Velopack is asked",
          not available and "wrong key" in message)

    serve(manifest_error=OSError("no route"), manager=FakeManager())
    available, _i, message = appupdate.check("1.0.0")
    check("an unreachable server is a sentence", not available and "Could not reach" in message)

    def raising():
        raise RuntimeError("This application is not properly installed")
    serve(manager=None)
    appupdate._make_manager = raising
    available, info, message = appupdate.check("1.0.0")
    check("a copy Velopack did not install is told to fetch it by hand",
          not available and "cannot update itself" in message, message)
    check("but still learns the version", info and info["version"] == "9.9.9")

    print("\ndownload(): progress in bytes, Stop honoured, failure a sentence")
    manager = FakeManager()
    serve(manager=manager)
    available, info, _m = appupdate.check("1.0.0")
    seen = []
    token, message = appupdate.download(info, progress=lambda d, t: seen.append((d, t)))
    check("the download returns a token", token == "9.9.9", message)
    check("progress arrives as bytes of the package",
          seen and seen[0] == (0, 5000) and seen[-1] == (5000, 5000), seen)
    check("Velopack was asked to download the vouched update", manager.downloaded is not None)

    def stop(done, total):
        if done >= 2500:
            raise appupdate.Stopped()
    token, message = appupdate.download(info, progress=stop)
    check("Stop from the progress bar stops it", token is None and "stopped" in message, message)

    serve(manager=FakeManager(fail_download="midway"))
    available, info, _m = appupdate.check("1.0.0")
    token, message = appupdate.download(info)
    check("a failed download is a sentence", token is None and "Download failed" in message, message)
    token, message = appupdate.download({})
    check("downloading before checking is refused", token is None and "Check for updates" in message)

    print("\nrun_installer(): flush, clear the marker, hand over to Velopack")
    manager = FakeManager()
    serve(manager=manager)
    _a, info, _m = appupdate.check("1.0.0")
    token, _m = appupdate.download(info)
    scratch = tempfile.mkdtemp()
    real_local = paths.local_dir
    paths.local_dir = lambda: scratch
    flushed = []
    try:
        paths.mark_started()
        ok, message = appupdate.run_installer(token, before_restart=lambda: flushed.append(1))
        check("apply reports what will happen", ok and "close and reopen" in message, message)
        check("the window's flush ran first", flushed == [1])
        check("the clean exit marker was cleared, so the next start does not "
              "offer a recovery", not paths.last_run_crashed())
        check("Velopack was handed the downloaded update", manager.applied is not None)
    finally:
        paths.local_dir = real_local
    ok, message = appupdate.run_installer("0.0.0")
    check("applying what was never downloaded is refused", not ok)

    print("\nauto_check(): quiet unless installed, and throttled")
    appupdate._make_manager = raising
    config = tempfile.mkdtemp()
    check("a source run never checks on its own",
          appupdate.auto_check(config) == (False, None, None))
    serve(manager=FakeManager())
    available, info, message = appupdate.auto_check(config)
    check("an installed copy checks and is offered the update", available and info["version"] == "9.9.9")
    available, info, message = appupdate.auto_check(config)
    check("and not again within a day", (available, message) == (False, None))
    available, info, message = appupdate.auto_check(config, force=True)
    check("unless asked", available)

    print("\ninspect_feed(): a release verified from any machine")
    index = {"Assets": [
        {"PackageId": C.PACK_ID, "Version": "9.9.8", "Type": "Full",
         "FileName": "%s-9.9.8-full.nupkg" % C.PACK_ID, "SHA256": "11" * 32, "Size": 4000},
        {"PackageId": C.PACK_ID, "Version": "9.9.9", "Type": "Delta",
         "FileName": "%s-9.9.9-delta.nupkg" % C.PACK_ID, "SHA256": "22" * 32, "Size": 100},
        {"PackageId": C.PACK_ID, "Version": "9.9.9", "Type": "Full",
         "FileName": "%s-9.9.9-full.nupkg" % C.PACK_ID, "SHA256": PACKAGE_SHA.upper(), "Size": 5000},
    ]}
    sizes = {"%s-9.9.9-full.nupkg" % C.PACK_ID: 5000, "TGImprint-9.9.9-Setup.exe": 100}

    def fetch(url, limit=None, **kw):
        if url == appupdate.MANIFEST_URL:
            return json.dumps(envelope(MANIFEST)).encode()
        if url == appupdate.RELEASES_URL + appupdate.RELEASES_FILE:
            return json.dumps(index).encode()
        raise RuntimeError(url)
    real_head = appupdate._head
    appupdate._head = lambda url: sizes.get(url.rsplit("/", 1)[-1], -1)
    try:
        ok, lines = appupdate.inspect_feed(fetch=fetch)
        check("a feed whose newest full package is the vouched one passes", ok, lines)
        sizes["%s-9.9.9-full.nupkg" % C.PACK_ID] = 4999
        ok, lines = appupdate.inspect_feed(fetch=fetch)
        check("a package missing or truncated on the server fails", not ok, lines[-1])
        sizes["%s-9.9.9-full.nupkg" % C.PACK_ID] = 5000
        index["Assets"][2]["SHA256"] = "33" * 32
        ok, lines = appupdate.inspect_feed(fetch=fetch)
        check("a feed the manifest does not vouch for fails", not ok and "REFUSED" in lines[-1], lines[-1])
    finally:
        appupdate._head = real_head

    print("\nFrom source")
    appupdate._make_manager = raising
    check("not installed", not appupdate.is_installed())
    check("not portable", not appupdate.is_portable())
    check("the channel state says so", "source" in appupdate.channel_state(), appupdate.channel_state())
    check("the feed URL is the constant", appupdate.RELEASES_URL == C.RELEASES_URL)
    check("the manifest URL is unchanged for the release checker",
          appupdate.MANIFEST_URL == "https://tgstudios.app/updates/tg-imprint-app.json")
finally:
    appupdate._fetch, appupdate._make_manager = real_fetch, real_maker
    appupdate.PUBLIC_KEY_B64 = REAL_KEY

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.exit(0 if all(CHECKS) else 1)
