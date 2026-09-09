#!/usr/bin/env python3
"""Sign and publish a release, so installed copies see it.

    python tools/release_app.py stage     # sign locally, upload nothing
    python tools/release_app.py rehearse  # run the client against the staged files
    python tools/release_app.py publish   # rehearse, then upload feed + files + manifest
    python tools/release_app.py verify    # read the live feed the way a client does

The Velopack shape of the TG Studios release tool. Velopack's feed
(releases.win.json and the packages) is not signed, so the TG Studios
manifest still is: ed25519 with the update key, naming the version, the
SHA256 and the size of the Velopack package, and the Setup on the site.
The app refuses anything Velopack offers that the manifest does not vouch
for. Every stage verifies before anything is uploaded, because a manifest
whose signature fails is a silent outage: every installed copy quietly
stops seeing updates and nothing anywhere reports an error.

Order on the server, load bearing: the feed and the site files go up
first, the signed manifest last. The manifest is what makes installed
copies look, so publishing it first would offer a package that is not
there yet.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from tgimprint import constants as C            # noqa: E402
from tgimprint import appupdate                 # noqa: E402

PRIVATE_KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".tgstudios", "update-private-key.pem")

DIST = os.path.join(HERE, "dist")
INSTALLER_DIR = os.path.join(DIST, "installer")
FEED_DIR = os.path.join(DIST, "releases")
OUT_DIR = os.path.join(DIST, "manifests")

SERVER = "tony@server.tonygebhard.me"
REMOTE_DOWNLOADS = "/home/tony/tgstudios/downloads"
REMOTE_FEED = "%s/%s" % (REMOTE_DOWNLOADS, C.FEED_SLUG)
REMOTE_UPDATES = "/home/tony/tgstudios/updates"
DOWNLOAD_BASE = "https://tgstudios.app/downloads"
MANIFEST_NAME = "%s-app.json" % C.FEED_SLUG
CHANNEL = "win"

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


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    name = "%s-%s-windows.zip" % (C.ZIP_BASENAME, C.APP_VERSION)
    path = os.path.join(DIST, name)
    if not os.path.exists(path):
        raise SystemExit("No portable zip at %s.\n"
                         "Run: python tools/build_release.py" % path)
    return path


def feed_index():
    path = os.path.join(FEED_DIR, "releases.%s.json" % CHANNEL)
    if not os.path.exists(path):
        raise SystemExit("No feed index at %s.\nRun: python tools/build_release.py" % path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def full_package():
    """The full package for this version, checked against the feed index.

    The index's SHA256 is what Velopack will verify a download against, so
    it is what the manifest signs; but the file is hashed here as well, and
    the two must agree, or the feed on disk is not the feed that was built.
    """
    index = feed_index()
    wanted = None
    for asset in index.get("Assets", []):
        if (str(asset.get("Type", "")).lower() == "full"
                and str(asset.get("Version")) == C.APP_VERSION):
            wanted = asset
    if wanted is None:
        raise SystemExit("The feed index lists no full package for %s" % C.APP_VERSION)
    path = os.path.join(FEED_DIR, wanted["FileName"])
    if not os.path.exists(path):
        raise SystemExit("The feed index names %s but it is not in %s"
                         % (wanted["FileName"], FEED_DIR))
    digest = sha256_of(path)
    if digest.lower() != str(wanted.get("SHA256", "")).lower():
        raise SystemExit("The package on disk does not match the feed index: "
                         "%s versus %s" % (digest, wanted.get("SHA256")))
    if os.path.getsize(path) != int(wanted.get("Size") or -1):
        raise SystemExit("The package size on disk does not match the feed index")
    return path, wanted


def require_notes():
    """Refuse to publish a version with nothing to say about it. The floor is
    about a sentence; a one-word note is silence in a different shape."""
    note = (NOTES.get(C.APP_VERSION) or "").strip()
    if len(note) < 40:
        raise SystemExit(
            "\nNothing to tell people about %s.\n\n"
            "Add a line to NOTES in tools/release_app.py saying what was\n"
            "added or fixed. It is read aloud in the update dialog, so a\n"
            "couple of plain sentences, no markdown.\n\n%s"
            % (C.APP_VERSION, "It is empty." if not note
               else "It is only %d characters: %r" % (len(note), note)))
    return note


def stage():
    require_notes()
    setup = installer_path()
    portable = zip_path()
    package, asset = full_package()

    manifest = {
        "product": C.APP_NAME,
        "version": C.APP_VERSION,
        # The Setup on the site, for people and for the release checker.
        "url": "%s/%s" % (DOWNLOAD_BASE, os.path.basename(setup)),
        "sha256": sha256_of(setup),
        "size": os.path.getsize(setup),
        "notes": NOTES.get(C.APP_VERSION, ""),
        "zip_url": "%s/%s" % (DOWNLOAD_BASE, os.path.basename(portable)),
        "zip_sha256": sha256_of(portable),
        "zip_size": os.path.getsize(portable),
        # The Velopack package this manifest vouches for. The app compares
        # what Velopack offers against these three before it downloads.
        "package": asset["FileName"],
        "package_sha256": str(asset["SHA256"]).lower(),
        "package_size": int(asset["Size"]),
        "releases_url": C.RELEASES_URL,
    }
    envelope = {"manifest": manifest, "signature": sign(appupdate.canonical(manifest))}

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, MANIFEST_NAME)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2)

    # Verify with the client's own code, against the key baked into the build
    # that is about to ship. Signing with a key the app does not carry is the
    # exact failure that produces a silent outage.
    with open(out, "rb") as fh:
        parsed, message = appupdate.read_envelope(fh.read())
    if parsed is None:
        raise SystemExit("FAILED: the app cannot verify its own manifest: %s\n"
                         "tgimprint/appupdate.py has a different public key from\n%s"
                         % (message, PRIVATE_KEY_PATH))

    print("Staged %s" % out)
    print("  version : %s" % manifest["version"])
    print("  setup   : %s (%.1f MB)" % (os.path.basename(setup), manifest["size"] / 1048576.0))
    print("  package : %s (%.1f MB)" % (asset["FileName"], manifest["package_size"] / 1048576.0))
    print("  sha256  : %s" % manifest["package_sha256"])
    print("  verified against the key baked into this build")
    return setup, portable, package, out


def run(cmd):
    print("  $ %s" % " ".join(cmd[:3]) + (" ..." if len(cmd) > 3 else ""))
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("FAILED: %s" % cmd[0])


class _FakeManager:
    """A stand-in for Velopack's UpdateManager built from the staged index,
    so the client can be rehearsed on a machine where nothing is installed."""

    def __init__(self, asset, downgrade=False):
        import velopack
        self.asset = velopack.VelopackAsset(
            asset["PackageId"], asset["Version"], asset["Type"], asset["FileName"],
            asset.get("SHA1", ""), asset["SHA256"], int(asset["Size"]),
            asset.get("NotesMarkdown", ""), asset.get("NotesHtml", ""))
        self.info = velopack.UpdateInfo(self.asset, [], downgrade)

    def check_for_updates(self):
        return self.info

    def download_updates(self, info, callback=None):
        for step in (0, 50, 100):
            if callback:
                callback(step)

    def get_is_portable(self):
        return False

    def get_current_version(self):
        return "0.0.0"


def rehearse():
    """Run the client against the staged manifest before anything is uploaded.

    The two cases the design exists for are both here: a package swapped
    underneath a valid signature (the feed's SHA256 differs from the signed
    one), and a manifest edited after signing. A signature does not cover the
    feed, and the feed's hash is worthless when whoever rewrites the feed
    rewrites the hash; the signed copy of that hash is what closes the loop.
    """
    setup, portable, package, manifest_path = stage()
    envelope = json.load(open(manifest_path, encoding="utf-8"))
    _package_path, asset = full_package()
    real_fetch, real_maker = appupdate._fetch, appupdate._make_manager
    fails = []
    print()

    def serve(manifest=None, feed_asset=None):
        def fetch(url, limit=None, **kw):
            if url == appupdate.MANIFEST_URL:
                return json.dumps(manifest or envelope).encode()
            raise RuntimeError("unexpected fetch of %s" % url)
        appupdate._fetch = fetch
        appupdate._make_manager = lambda: _FakeManager(feed_asset or asset)

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

        seen = []
        token, message = appupdate.download(info, progress=lambda d, t: seen.append((d, t)))
        print("  the download reports progress    : %s" % (bool(token) and len(seen) >= 2))
        if not token:
            fails.append("the download failed in rehearsal: %s" % message)
        if seen and seen[-1][0] != seen[-1][1]:
            fails.append("progress did not end at the full size: %r" % (seen[-1],))

        # A different package behind a perfectly valid signature.
        swapped = dict(asset)
        swapped["SHA256"] = "0" * 64
        serve(feed_asset=swapped)
        avail, _i, why = appupdate.check("0.0.0")
        print("  a swapped package is refused     : %s" % (not avail))
        if avail:
            fails.append("a package whose hash the manifest did not sign was ACCEPTED")

        # The manifest edited after it was signed.
        tampered = json.loads(json.dumps(envelope))
        tampered["manifest"]["version"] = "99.0.0"
        serve(manifest=tampered)
        avail, _i, _m = appupdate.check("0.0.0")
        print("  an edited manifest is refused    : %s" % (not avail))
        if avail:
            fails.append("a manifest edited after signing was ACCEPTED")

        # The feed on disk, read the way verify reads the live one.
        def local_fetch(url, limit=None, **kw):
            if url == appupdate.MANIFEST_URL:
                return json.dumps(envelope).encode()
            if url == appupdate.RELEASES_URL + appupdate.RELEASES_FILE:
                return open(os.path.join(FEED_DIR, appupdate.RELEASES_FILE), "rb").read()
            raise RuntimeError("unexpected fetch of %s" % url)

        real_head = appupdate._head

        def local_head(url):
            name = url.rsplit("/", 1)[-1]
            for folder in (FEED_DIR, INSTALLER_DIR, DIST):
                path = os.path.join(folder, name)
                if os.path.exists(path):
                    return os.path.getsize(path)
            return -1

        appupdate._head = local_head
        try:
            ok, lines = appupdate.inspect_feed(fetch=local_fetch)
        finally:
            appupdate._head = real_head
        print("  the staged feed inspects clean   : %s" % ok)
        if not ok:
            fails.append("the staged feed failed inspection: %s" % " / ".join(lines))
    finally:
        appupdate._fetch, appupdate._make_manager = real_fetch, real_maker

    if fails:
        for f in fails:
            print("\nFAILED: %s" % f)
        raise SystemExit("\nRehearsal failed. Nothing uploaded.")
    print("\nRehearsal passed.")
    return setup, portable, manifest_path


def publish():
    setup, portable, manifest = rehearse()
    feed_files = sorted(os.path.join(FEED_DIR, n) for n in os.listdir(FEED_DIR))

    print("\nUploading the feed (the index and the packages)")
    run(["ssh", SERVER, "mkdir -p %s" % REMOTE_FEED])
    run(["scp"] + feed_files + ["%s:%s/" % (SERVER, REMOTE_FEED)])
    print("Uploading the installer and the portable zip")
    run(["scp", setup, portable, "%s:%s/" % (SERVER, REMOTE_DOWNLOADS)])
    print("Uploading the manifest")
    # Manifest last, always. It is what makes installed copies look.
    run(["scp", manifest, "%s:%s/" % (SERVER, REMOTE_UPDATES)])
    run(["ssh", SERVER,
         "chmod 755 %s && chmod 644 %s/* %s/%s %s/%s %s/%s"
         % (REMOTE_FEED, REMOTE_FEED,
            REMOTE_DOWNLOADS, os.path.basename(setup),
            REMOTE_DOWNLOADS, os.path.basename(portable),
            REMOTE_UPDATES, MANIFEST_NAME)])
    print("\nPublished. Verifying live...")
    verify()


def verify():
    """Read the live feed the way a client would, from here."""
    print("Reading %s and %s" % (appupdate.MANIFEST_URL, appupdate.RELEASES_URL))
    ok, lines = appupdate.inspect_feed()
    for line in lines:
        print("  " + line)
    if not ok:
        raise SystemExit("FAILED: the live feed is not what the manifest vouches for.")
    print("\nLive feed verified.")


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
