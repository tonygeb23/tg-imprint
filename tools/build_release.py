"""Build the Windows release: the frozen folder, then Velopack's packages.

    python tools/build_release.py

Produces, under %LOCALAPPDATA%\\TG Studios Build\\easy-pdf:
    dist\\Easy PDF\\              the frozen program (PyInstaller, one folder)
    releases\\                    Velopack's output: the Setup, the portable zip,
                                 the full and delta packages, releases.win.json
and copies back into dist/ here:
    dist\\installer\\EasyPDF-<version>-Setup.exe
    dist\\Easy-PDF-<version>-windows.zip
    dist\\releases\\              the feed files the release tool uploads

Velopack (vpk) replaces Inno Setup for this program and every TG Studios
program after it (Tony, 2026-09-09). It gives delta updates and an update
that is applied in place with no installer window; what it does not give
is a signature, which is why tools/release_app.py still signs a manifest
and easypdf/appupdate.py still checks it before letting Velopack apply
anything.

Everything is built OUTSIDE Dropbox and only the finished artefacts are
copied back. PyInstaller writes an exe and then reopens it to strip its
resources; inside Dropbox the sync client has a handle on it by then and
the build dies at "remove_all_resources".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from easypdf import constants as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUILD_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", HERE),
                          "TG Studios Build", "easy-pdf")
WORK = os.path.join(BUILD_ROOT, "work")
DIST = os.path.join(BUILD_ROOT, "dist")
RELEASES = os.path.join(BUILD_ROOT, "releases")
FINAL = os.path.join(HERE, "dist")
BUNDLE = os.path.join(DIST, C.APP_NAME)
ICON = os.path.join(HERE, "assets", "easypdf.ico")
MAIN_EXE = C.APP_NAME + ".exe"
CHANNEL = "win"

#: The per-user .NET SDK, installed 2026-09-09 with dotnet-install.ps1 so no
#: administrator prompt was needed. vpk is a .NET global tool and lives in
#: %USERPROFILE%\.dotnet\tools.
DOTNET_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "dotnet")
VPK_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), ".dotnet", "tools", "vpk.exe"),
]


def installer_name(version=None):
    return "%s-%s-Setup.exe" % (C.INSTALLER_BASENAME, version or C.APP_VERSION)


def zip_name(version=None):
    return "%s-%s-windows.zip" % (C.ZIP_BASENAME, version or C.APP_VERSION)


def velopack_setup_name():
    return "%s-%s-Setup.exe" % (C.PACK_ID, CHANNEL)


def velopack_portable_name():
    return "%s-%s-Portable.zip" % (C.PACK_ID, CHANNEL)


def package_name(version=None, kind="full"):
    return "%s-%s-%s.nupkg" % (C.PACK_ID, version or C.APP_VERSION, kind)


def make_icon():
    """Regenerate assets/easypdf.ico from easypdf.appicon, every build, so the
    icon stamped into the exe and the Setup can never drift from the mark the
    window draws at runtime."""
    import wx
    app = wx.App(redirect=False)          # noqa: F841  a colour needs one
    from easypdf import appicon
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    appicon.write_ico(ICON)
    if not wx.Icon(ICON, wx.BITMAP_TYPE_ICO).IsOk():
        raise SystemExit("wrote %s but Windows will not load it" % ICON)
    print(f"  icon: {ICON}")


def find_vpk():
    found = shutil.which("vpk")
    if found:
        return found
    for path in VPK_CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit(
        "Could not find vpk (Velopack).\n"
        "Install the .NET SDK per user with dotnet-install.ps1, then:\n"
        "  dotnet tool install -g vpk")


def vpk_env():
    env = dict(os.environ)
    if os.path.isdir(DOTNET_ROOT):
        env["DOTNET_ROOT"] = DOTNET_ROOT
        env["PATH"] = DOTNET_ROOT + os.pathsep + env.get("PATH", "")
    return env


def webview2_loader():
    """wxPython's WebView2Loader.dll, which PyInstaller does not collect.

    wxWidgets loads it by name from beside its own webview DLL, so it has to
    land in the same folder inside the bundle. Without it the editor is an
    empty grey panel and nothing raises. The selftest proves the editor
    renders for exactly this reason.
    """
    import wx
    folder = os.path.dirname(wx.__file__)
    path = os.path.join(folder, "WebView2Loader.dll")
    if not os.path.exists(path):
        raise SystemExit("WebView2Loader.dll not found beside wx at %s" % folder)
    return path


def run(command, env=None):
    print("  " + " ".join(command[:4]) + " ...")
    result = subprocess.run(command, cwd=HERE, env=env)
    if result.returncode != 0:
        raise SystemExit(f"failed: {' '.join(command)}")


def build_executable():
    loader = webview2_loader()
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", C.APP_NAME,
        "--windowed",                     # no console window behind the app
        "--icon", ICON,
        "--distpath", DIST,
        "--workpath", WORK,
        "--specpath", WORK,
        # The WebView2 loader, next to wx's own DLLs. See webview2_loader.
        "--add-binary", loader + os.pathsep + "wx",
        # Native code beside these packages that PyInstaller will not find by
        # walking imports alone. pikepdf carries qpdf; PyMuPDF carries
        # MuPDF; accessible_output2 carries the screen reader bridges;
        # velopack is one Rust extension module.
        "--collect-all", "pikepdf",
        "--collect-all", "pymupdf",
        "--collect-all", "fitz",
        "--collect-all", "accessible_output2",
        "--collect-all", "velopack",
        # Pillow's native modules. It imports perfectly well without them
        # and then quietly answers None. The selftest resizes a real image.
        "--collect-all", "PIL",
        # The two readers, imported lazily inside the functions that use
        # them, so named here rather than trusted to the import walk.
        "--hidden-import", "docx",
        "--hidden-import", "markdown_it",
        "--collect-all", "docx",
        "--collect-all", "markdown_it",
        # Nothing here needs any of these, and an editable install elsewhere
        # on this machine once dragged torch and friends into a build through
        # a .pth file: 1.1 GB instead of 170 MB. The excludes are load bearing.
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pytest",
        "--exclude-module", "torch",
        "--exclude-module", "transformers",
        "--exclude-module", "yt_dlp",
        "--exclude-module", "tkinter",
        "--exclude-module", "numpy",
        "--exclude-module", "cv2",
        "--exclude-module", "av",
        "--exclude-module", "google",
        "main.py",
    ]
    run(command)


def copy_payload():
    """Everything that sits beside the executable."""
    for name, target in (("LICENSE", "LICENSE.txt"),
                         ("README.md", "README.txt")):
        source = os.path.join(HERE, name)
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(BUNDLE, target))
            print(f"  copied {target}")
    # The user-facing documents, beside the program where Help can open
    # them and a person can find them without the app.
    docs_out = os.path.join(BUNDLE, "docs")
    os.makedirs(docs_out, exist_ok=True)
    for name in ("DESCRIBER.md", "KEYBOARD.md", "PDF-UA.md"):
        source = os.path.join(HERE, "docs", name)
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(docs_out, name))
            print(f"  copied docs/{name}")


def fetch_previous_releases(vpk, env):
    """Pull the published feed into the output folder so vpk can make a delta.

    A delta needs the previous full package beside the new one. The first
    release has nothing to fetch, and a machine offline has nothing to fetch
    either; both are a warning, not a failure, because a full package still
    updates everybody, only more slowly.
    """
    print("  fetching the published releases for the delta")
    result = subprocess.run([vpk, "download", "http", "--url", C.RELEASES_URL,
                             "--outputDir", RELEASES, "--channel", CHANNEL,
                             "--yes"], cwd=HERE, env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
        print("  no previous release fetched (first release, or offline):")
        for line in tail:
            print("     " + line)
        return False
    return True


def release_notes_file():
    """The notes for this version, from the release tool, as Velopack markdown."""
    sys.path.insert(0, os.path.join(HERE, "tools"))
    try:
        import release_app
        note = (release_app.NOTES.get(C.APP_VERSION) or "").strip()
    except Exception:
        note = ""
    path = os.path.join(BUILD_ROOT, "notes-%s.md" % C.APP_VERSION)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(note + "\n")
    return path


def pack():
    """Velopack's packages from the frozen folder."""
    vpk = find_vpk()
    env = vpk_env()
    shutil.rmtree(RELEASES, ignore_errors=True)
    os.makedirs(RELEASES, exist_ok=True)
    fetch_previous_releases(vpk, env)
    run([vpk, "pack",
         "--packId", C.PACK_ID,
         "--packVersion", C.APP_VERSION,
         "--packDir", BUNDLE,
         "--mainExe", MAIN_EXE,
         "--packTitle", C.APP_NAME,
         "--packAuthors", C.VENDOR,
         "--icon", ICON,
         "--channel", CHANNEL,
         "--outputDir", RELEASES,
         "--releaseNotes", release_notes_file(),
         "--yes"], env=env)
    for name in (velopack_setup_name(), velopack_portable_name(),
                 package_name(), "releases.%s.json" % CHANNEL):
        if not os.path.exists(os.path.join(RELEASES, name)):
            raise SystemExit("vpk did not produce %s. Found: %s"
                             % (name, sorted(os.listdir(RELEASES))))


def copy_back():
    """The site's copies under the names the site and TG Stats know, and the
    feed files under dist/releases for the release tool."""
    os.makedirs(os.path.join(FINAL, "installer"), exist_ok=True)
    os.makedirs(os.path.join(FINAL, "releases"), exist_ok=True)
    setup = os.path.join(FINAL, "installer", installer_name())
    portable = os.path.join(FINAL, zip_name())
    shutil.copy2(os.path.join(RELEASES, velopack_setup_name()), setup)
    shutil.copy2(os.path.join(RELEASES, velopack_portable_name()), portable)
    # The feed: the index and every package, but not the Setup and the
    # portable zip, which the site serves under their own names above.
    for name in os.listdir(os.path.join(FINAL, "releases")):
        os.remove(os.path.join(FINAL, "releases", name))
    for name in sorted(os.listdir(RELEASES)):
        if name in (velopack_setup_name(), velopack_portable_name()):
            continue
        shutil.copy2(os.path.join(RELEASES, name), os.path.join(FINAL, "releases", name))
    return setup, portable


def main():
    print(f"Building {C.APP_NAME} {C.APP_VERSION}")
    print("Drawing the icon")
    make_icon()
    build_executable()
    print("Copying the licence, the readme and the documents")
    copy_payload()
    print("Velopack")
    pack()
    print("Copying the finished artefacts back")
    setup, portable = copy_back()

    folder = sum(os.path.getsize(os.path.join(r, f))
                 for r, _d, fs in os.walk(BUNDLE) for f in fs) / 1024 / 1024
    print(f"\n  folder:   {BUNDLE}  ({folder:.1f} MB)")
    print(f"  setup:    {setup}  ({os.path.getsize(setup) / 1024 / 1024:.1f} MB)")
    print(f"  portable: {portable}  ({os.path.getsize(portable) / 1024 / 1024:.1f} MB)")
    print(f"  feed:     {os.path.join(FINAL, 'releases')}  "
          f"({', '.join(sorted(os.listdir(os.path.join(FINAL, 'releases'))))})")
    print("\nSelftest the FROZEN build before you upload:")
    print(f'  "{os.path.join(BUNDLE, MAIN_EXE)}" --selftest --selftest-out report.txt')
    return 0


if __name__ == "__main__":
    sys.exit(main())
