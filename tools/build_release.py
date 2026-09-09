"""Build the standalone Windows release: a folder, a zip and an installer.

    python tools/build_release.py

Produces, under %LOCALAPPDATA%\\TG Studios Build\\easy-pdf:
    dist\\Easy PDF\\                    the frozen program
    dist\\Easy-PDF-<version>-windows.zip
    installer\\EasyPDF-<version>-Setup.exe
and copies the zip and the installer back into dist/ here.

Everything is built OUTSIDE Dropbox and only the finished artefacts are
copied back. PyInstaller writes an exe and then reopens it to strip its
resources; inside Dropbox the sync client has a handle on it by then and the
build dies at "remove_all_resources". Same family of fault as every other
Dropbox-and-open-handles problem in this workspace.

The shape is TG Drop Deck's tools/build_release.py; only the payload differs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from easypdf import constants as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUILD_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", HERE),
                          "TG Studios Build", "easy-pdf")
WORK = os.path.join(BUILD_ROOT, "work")
DIST = os.path.join(BUILD_ROOT, "dist")
FINAL = os.path.join(HERE, "dist")
BUNDLE = os.path.join(DIST, C.APP_NAME)
ICON = os.path.join(HERE, "assets", "easypdf.ico")
INSTALLER_OUT = os.path.join(BUILD_ROOT, "installer")

ISCC_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                 "Inno Setup 6", "ISCC.exe"),
    os.path.join(os.path.expanduser("~"), "scoop", "apps", "inno-setup",
                 "current", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def installer_name(version=None):
    return "%s-%s-Setup.exe" % (C.INSTALLER_BASENAME, version or C.APP_VERSION)


def zip_name(version=None):
    return "%s-%s-windows.zip" % (C.ZIP_BASENAME, version or C.APP_VERSION)


def make_icon():
    """Regenerate assets/easypdf.ico from easypdf.appicon.

    Every build, so the .ico stamped into the exe and the installer can never
    drift from the mark the window and the About box draw at runtime.
    """
    import wx
    app = wx.App(redirect=False)          # noqa: F841  a colour needs one
    from easypdf import appicon
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    appicon.write_ico(ICON)
    if not wx.Icon(ICON, wx.BITMAP_TYPE_ICO).IsOk():
        raise SystemExit("wrote %s but Windows will not load it" % ICON)
    print(f"  icon: {ICON}")


def find_iscc():
    for path in ISCC_CANDIDATES:
        if path and os.path.exists(path):
            return path
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    raise SystemExit(
        "Could not find ISCC.exe (Inno Setup).\n"
        "Install it with:  winget install JRSoftware.InnoSetup")


def webview2_loader():
    """wxPython's WebView2Loader.dll, which PyInstaller does not collect.

    wxWidgets loads it by name from beside its own webview DLL, so it has to
    land in the same folder inside the bundle. Without it the editor is an
    empty grey panel and nothing raises: WebView.New simply returns a
    control that never loads. The selftest proves the editor renders for
    exactly this reason.
    """
    import wx
    folder = os.path.dirname(wx.__file__)
    path = os.path.join(folder, "WebView2Loader.dll")
    if not os.path.exists(path):
        raise SystemExit("WebView2Loader.dll not found beside wx at %s" % folder)
    return path


def make_installer():
    """The installer is the update path.

    appupdate.py downloads and runs this; a zip is not something it can
    install. The zip stays as well, for anyone who would rather have a folder.
    """
    iscc = find_iscc()
    # Cleared first, and the result is chosen by its expected name rather
    # than by whatever listdir happens to return. Leaving old builds here
    # meant a version bump picked up the PREVIOUS installer, a silent way to
    # publish the wrong thing under the right version number.
    shutil.rmtree(INSTALLER_OUT, ignore_errors=True)
    os.makedirs(INSTALLER_OUT, exist_ok=True)
    run([iscc,
         "/DAppVersion=%s" % C.APP_VERSION,
         "/DSourceDir=%s" % BUNDLE,
         "/DOutputDir=%s" % INSTALLER_OUT,
         "/DIconFile=%s" % ICON,
         os.path.join(HERE, "tools", "easypdf.iss")])
    expected = installer_name()
    path = os.path.join(INSTALLER_OUT, expected)
    if not os.path.exists(path):
        raise SystemExit(
            "Inno Setup did not produce %s. Found: %s"
            % (expected, os.listdir(INSTALLER_OUT)))
    return path


def run(command):
    print("  " + " ".join(command[:4]) + " ...")
    result = subprocess.run(command, cwd=HERE)
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
        # MuPDF; accessible_output2 carries the screen reader bridges.
        "--collect-all", "pikepdf",
        "--collect-all", "pymupdf",
        "--collect-all", "fitz",
        "--collect-all", "accessible_output2",
        # Pillow's native modules. It imports perfectly well without them
        # and then quietly answers None, which is how a sibling app shipped
        # a build that could not draw. The selftest opens and resizes a
        # real image so that cannot happen quietly here.
        "--collect-all", "PIL",
        # The two readers, imported lazily inside the functions that use
        # them, so named here rather than trusted to the import walk. The
        # selftest imports both so a build that lost one says so.
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
    # them and a person can find them without the app: what the describer
    # sends and when (the consent text names it), the keyboard map, and
    # what the PDF export guarantees.
    docs_out = os.path.join(BUNDLE, "docs")
    os.makedirs(docs_out, exist_ok=True)
    for name in ("DESCRIBER.md", "KEYBOARD.md", "PDF-UA.md"):
        source = os.path.join(HERE, "docs", name)
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(docs_out, name))
            print(f"  copied docs/{name}")


def make_zip():
    path = os.path.join(DIST, zip_name())
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for root, _dirs, files in os.walk(BUNDLE):
            for filename in files:
                full = os.path.join(root, filename)
                # Everything lives under one folder inside the zip, so
                # unzipping never scatters files across someone's Downloads.
                inside = os.path.join(C.APP_NAME,
                                      os.path.relpath(full, BUNDLE))
                archive.write(full, inside)
    return path


def main():
    print(f"Building {C.APP_NAME} {C.APP_VERSION}")
    print("Drawing the icon")
    make_icon()
    build_executable()
    print("Copying the licence and the readme")
    copy_payload()
    print("Zipping")
    path = make_zip()
    print("Inno Setup")
    installer = make_installer()

    print("Copying the finished artefacts back")
    os.makedirs(os.path.join(FINAL, "installer"), exist_ok=True)
    final_zip = os.path.join(FINAL, os.path.basename(path))
    final_setup = os.path.join(FINAL, "installer", os.path.basename(installer))
    shutil.copy2(path, final_zip)
    shutil.copy2(installer, final_setup)

    size = os.path.getsize(path) / 1024 / 1024
    folder = sum(os.path.getsize(os.path.join(r, f))
                 for r, _d, fs in os.walk(BUNDLE) for f in fs) / 1024 / 1024
    print(f"\n  folder: {BUNDLE}  ({folder:.1f} MB)")
    print(f"  zip:    {final_zip}  ({size:.1f} MB)")
    print(f"  setup:  {final_setup}  "
          f"({os.path.getsize(final_setup) / 1024 / 1024:.1f} MB)")
    print("\nSelftest the FROZEN build before you upload:")
    print(f'  "{os.path.join(BUNDLE, C.APP_NAME + ".exe")}" --selftest --selftest-out report.txt')
    return 0


if __name__ == "__main__":
    sys.exit(main())
