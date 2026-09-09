import os
import sys

import wx
from ui.main_window import MainWindow
from ui.welcome_dialog import WelcomeDialog


def _use_web_editor() -> bool:
    """
    The WebView editor (NVDA-announces headings, lists, links via DOM/UIA)
    is enabled when EITHER:
      - --web is passed on the command line, OR
      - the EASY_PDF_WEB_EDITOR environment variable is set to a truthy value.

    Default for now is the legacy RICHEDIT editor so the change is opt-in
    until the WebView path is fully validated.
    """
    if "--web" in sys.argv:
        return True
    if "--classic" in sys.argv:
        return False
    return os.environ.get("EASY_PDF_WEB_EDITOR", "").lower() in ("1", "true", "yes")


def main():
    app = wx.App(False)

    with WelcomeDialog() as dlg:
        result    = dlg.ShowModal()
        open_path = dlg.get_path() if result == wx.ID_OPEN else ""

    if result == wx.ID_EXIT:
        return

    frame = MainWindow(None, use_web_editor=_use_web_editor())
    frame.Show()

    if open_path:
        frame._load_file(open_path)

    app.MainLoop()


if __name__ == "__main__":
    main()
