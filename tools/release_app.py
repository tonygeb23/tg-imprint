#!/usr/bin/env python3
"""Sign and publish the app-update manifest, so installed copies see a release.

    python tools/release_app.py stage     # sign locally, upload nothing
    python tools/release_app.py rehearse  # run the client against the staged files
    python tools/release_app.py publish   # stage, then upload installer + zip + manifest
    python tools/release_app.py verify    # behave like a client against the live feed

TG Drop Deck's tools/release_app.py with the app-specific block changed and
nothing else. It is signed with the TG Studios *update* key, because a key
that can only publish text is a much smaller thing to lose than one that can
run code.

Every stage verifies before anything is uploaded. A manifest whose signature
fails is a silent outage: clients simply stop seeing updates and nothing
anywhere reports an error.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from easypdf import constants as C            # noqa: E402
from easypdf import appupdate                 # noqa: E402

PRIVATE_KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".tgstudios", "update-private-key.pem")

INSTALLER_DIR = os.path.join(HERE, "dist", "installer")
OUT_DIR = os.path.join(HERE, "dist", "manifests")

SERVER = "tony@server.tonygebhard.me"
REMOTE_DOWNLOADS = "/home/tony/tgstudios/downloads"
REMOTE_UPDATES = "/home/tony/tgstudios/updates"
DOWNLOAD_BASE = "https://tgstudios.app/downloads"
MANIFEST_NAME = "%s-app.json" % C.FEED_SLUG

# What the release adds, shown in the update prompt. Keep it to a couple of
# lines: it is read aloud as part of a dialog. Every entry is a string in
# Tony's voice and is listed in docs/STRINGS.md for his approval before it
# ships.
NOTES = {
    "1.0.0": ("The first release. Write a document with headings, lists, "
              "links and pictures, and export a tagged PDF that screen "
              "readers can read. Open a PDF somebody sent you and make it "
              "accessible. Describe pictures with Claude, ChatGPT or Gemini "
              "on your own key."),
}


def canonical(obj):
    """The exact bytes that get signed. Client and server must agree exactly."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload):
    from cryptography.hazmat.primitives import serialization
    if not os.path.exists(PRIVATE_KEY_PATH):
        raise SystemExit("No update signing key at %s" % PRIVATE_KEY_PATH)
    with open(PRIVATE_KEY_PATH, "rb") as fh:
        private = serialization.load_pem_private_key(fh.read(), password=None)
    return base64.b64encode(private.sign(payload)).decode("ascii")


def installer_path():
    name = "%s-%s-Setup.exe" % (C.INSTALLER_BASENAME, C.APP_VERSION)
    path = os.path.join(INSTALLER_DIR, name)
    if not os.path.exists(path):
        raise SystemExit(
            "No installer at %s.\nRun: python tools/build_release.py" % path)
    return path


def zip_path():
    """The portable download, which is a different lifecycle from the installer.

    A copy running from the zip has to be offered a zip. Handed an installer,
    it installs a SECOND copy elsewhere and leaves the running one on the old
    version, which looks, from where the user is sitting, like the update
    quietly doing nothing.
    """
    name = "%s-%s-windows.zip" % (C.ZIP_BASENAME, C.APP_VERSION)
    path = os.path.join(HERE, "dist", name)
    if not os.path.exists(path):
        raise SystemExit("No portable zip at %s.\n"
                         "Run: python tools/build_release.py" % path)
    return path


def require_notes():
    """Refuse to publish a version with nothing to say about it.

    NOTES defaults to an empty string when a version is missing from it, and
    an empty string is a perfectly valid manifest, so nothing anywhere fails.
    A rule that has to be remembered every release is a rule that gets missed
    every few releases, so it is checked here instead.
    """
    note = (NOTES.get(C.APP_VERSION) or "").strip()
    if len(note) < 40:
        raise SystemExit(
            "\nNothing to tell people about %s.\n\n"
            "Add a line to NOTES in tools/release_app.py saying what was\n"
            "added or fixed. It is read aloud in the update dialog, so a\n"
            "couple of plain sentences, no markdown.\n\n"
            "%s"
            % (C.APP_VERSION,
               "It is empty." if not note
               else "It is only %d characters: %r" % (len(note), note)))
    return note


def stage():
    require_notes()
    path = installer_path()
    blob = open(path, "rb").read()
    digest = hashlib.sha256(blob).hexdigest()

    portable = zip_path()
    zip_blob = open(portable, "rb").read()
    zip_url = "%s/%s" % (DOWNLOAD_BASE, os.path.basename(portable))
    zip_hash = hashlib.sha256(zip_blob).hexdigest()
    zip_size = len(zip_blob)

    manifest = {
        "product": C.APP_NAME,
        "version": C.APP_VERSION,
        "url": "%s/%s" % (DOWNLOAD_BASE, os.path.basename(path)),
        "sha256": digest,
        "size": len(blob),
        "notes": NOTES.get(C.APP_VERSION, ""),
        # The portable download, so a copy running from the zip can update
        # itself with a zip instead of being handed an installer.
        "zip_url": zip_url,
        "zip_sha256": zip_hash,
        "zip_size": zip_size,
    }
    envelope = {"manifest": manifest, "signature": sign(canonical(manifest))}

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, MANIFEST_NAME)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2)

    # Verify with the client's own code, against the key baked into the build
    # that is about to ship. Signing with a key the app does not carry is the
    # exact failure that produces a silent outage.
    payload = canonical(envelope["manifest"])
    if not appupdate._verify(payload, envelope["signature"]):
        raise SystemExit(
            "FAILED: the app cannot verify its own manifest.\n"
            "easypdf/appupdate.py has a different public key from\n"
            "%s" % PRIVATE_KEY_PATH)

    print("Staged %s" % out)
    print("  version : %s" % manifest["version"])
    print("  file    : %s (%.1f MB)" % (os.path.basename(path),
                                        len(blob) / (1024.0 * 1024.0)))
    print("  sha256  : %s" % digest)
    print("  verified against the key baked into this build")
    return path, out


def run(cmd):
    print("  $ %s" % " ".join(cmd[:3]) + (" ..." if len(cmd) > 3 else ""))
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("FAILED: %s" % cmd[0])


def publish():
    # Rehearse first, always. A manifest whose signature fails is a silent
    # outage: every installed copy stops seeing updates and nothing reports it.
    installer, manifest = rehearse()

    print("\nUploading the installer")
    run(["scp", installer, "%s:%s/" % (SERVER, REMOTE_DOWNLOADS)])
    # And the zip, which the manifest names for portable copies. A manifest
    # pointing at a download that does not exist gives every portable copy a
    # 404 and tells them the file was thrown away.
    portable = zip_path()
    print("Uploading the portable zip")
    run(["scp", portable, "%s:%s/" % (SERVER, REMOTE_DOWNLOADS)])
    print("Uploading the manifest")
    # Manifest last, always. It is what points clients at the installer, so
    # publishing it first would offer a download that is not there yet.
    run(["scp", manifest, "%s:%s/" % (SERVER, REMOTE_UPDATES)])
    run(["ssh", SERVER,
         "chmod 644 %s/%s %s/%s %s/%s" % (REMOTE_DOWNLOADS,
                                          os.path.basename(installer),
                                          REMOTE_DOWNLOADS,
                                          os.path.basename(portable),
                                          REMOTE_UPDATES, MANIFEST_NAME)])
    print("\nPublished. Verifying live...")
    verify()


def rehearse():
    """Run the client against the staged manifest before anything is uploaded.

    `verify` tests the live feed, which is too late to learn the signature is
    wrong: by then every installed copy has already seen it. This runs the same
    client code against the staged files, including the two cases the design
    exists for: an installer swapped underneath a valid signature, and a
    manifest edited after signing. Neither check is redundant. A signature does
    not cover the payload, and a hash is worthless when whoever rewrites the
    manifest rewrites the hash.
    """
    installer, manifest_path = stage()
    envelope = json.load(open(manifest_path, encoding="utf-8"))
    blob = open(installer, "rb").read()
    real = appupdate._fetch
    fails = []
    print()

    def serve(manifest=None, payload=None):
        # **kw: _fetch takes a progress argument for the download bar, and a
        # stand-in with a fixed signature reports "the real installer failed
        # its own hash", which reads like a corrupt build.
        def fetch(url, limit=None, **kw):
            if url == appupdate.MANIFEST_URL:
                return json.dumps(manifest or envelope).encode()
            return payload if payload is not None else blob
        appupdate._fetch = fetch

    try:
        serve()
        available, info, message = appupdate.check("0.0.0")
        print("  an old client is offered it      : %s" % available)
        if not available:
            fails.append("an old client is not offered the update: %s" % message)

        again, _i, _m = appupdate.check(C.APP_VERSION)
        print("  a current client is not          : %s" % (not again))
        if again:
            fails.append("a client already on %s is offered it again" % C.APP_VERSION)

        path, message = appupdate.download(info)
        print("  the real installer passes        : %s" % bool(path))
        if not path:
            fails.append("the real installer failed its own hash: %s" % message)
        else:
            os.remove(path)

        # A different executable behind a perfectly valid signature.
        serve(payload=b"a different executable entirely")
        bad, message = appupdate.download(info)
        print("  a swapped installer is rejected  : %s" % (bad is None))
        if bad is not None:
            fails.append("a swapped installer was ACCEPTED")
            os.remove(bad)

        # The manifest edited after it was signed.
        tampered = json.loads(json.dumps(envelope))
        tampered["manifest"]["version"] = "99.0.0"
        serve(manifest=tampered)
        avail, _i, _m = appupdate.check("0.0.0")
        print("  an edited manifest is rejected   : %s" % (not avail))
        if avail:
            fails.append("a manifest edited after signing was ACCEPTED")
    finally:
        appupdate._fetch = real

    if fails:
        for f in fails:
            print("\nFAILED: %s" % f)
        raise SystemExit("\nRehearsal failed. Nothing uploaded.")
    print("\nRehearsal passed.")
    return installer, manifest_path


def verify():
    """Behave exactly like an installed client would."""
    print("Fetching %s" % appupdate.MANIFEST_URL)
    available, info, message = appupdate.check(current_version="0.0.0")
    print("  a client on 0.0.0 : %s  (%s)" % (available, message))
    if not available:
        raise SystemExit("FAILED: an old client is not offered the update.")

    available_now, _info, message_now = appupdate.check(current_version=C.APP_VERSION)
    print("  a client on %-5s : %s  (%s)" % (C.APP_VERSION, available_now, message_now))
    if available_now:
        raise SystemExit("FAILED: a client already on %s is offered it again."
                         % C.APP_VERSION)

    print("Downloading the installer it names and checking the hash")
    path, message = appupdate.download(info)
    if not path:
        raise SystemExit("FAILED: %s" % message)
    size = os.path.getsize(path)
    os.remove(path)
    print("  %s  (%.1f MB, hash matched)" % (message, size / (1024.0 * 1024.0)))

    # The same again as a PORTABLE copy, which is offered the zip instead.
    if not appupdate.zip_for(info):
        raise SystemExit("FAILED: the manifest names no portable download, "
                         "so a copy running from the zip would be handed an "
                         "installer.")
    print("Downloading the portable zip it names and checking the hash")
    path, message = appupdate.download(info, portable=True)
    if not path:
        raise SystemExit("FAILED, for every portable copy: %s" % message)
    size = os.path.getsize(path)
    os.remove(path)
    print("  %s  (%.1f MB, hash matched)" % (message, size / (1024.0 * 1024.0)))
    print("\nLive feed verified, for both kinds of copy.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "stage":
        stage()
    elif cmd == "rehearse":
        rehearse()
    elif cmd == "publish":
        publish()
    elif cmd == "verify":
        verify()
    else:
        raise SystemExit(__doc__)
