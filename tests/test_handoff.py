"""A second launch with a document hands it to the running copy.

The Challenger's finding, 2026-09-09: "reopen the running copy" is not enough
for a document editor. Double clicking a file while the app is open must
open THAT file in the copy that is running, or a blind user gets a window
raised and no idea what became of the document.

This starts a real wx frame in this process, tags it exactly as main.py
does, then runs a SECOND Python process that finds the window the way a
second launch would and sends it a path. The frame's callback must receive
that path, on the UI thread, with its non-ASCII characters intact.

    python tests/test_handoff.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# The test prints a path with an accent and a CJK character, and a Windows
# console is cp1252 by default, which cannot encode them and raises.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import wx   # noqa: E402

from tgimprint import constants as C          # noqa: E402
from tgimprint import handoff                 # noqa: E402
from tgimprint.singleinstance import SingleInstance   # noqa: E402

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + label
          + (("  " + str(detail)) if detail != "" else ""))


# A path with a space, an accent and a CJK character, because a file name is
# where encoding bugs live.
DOC = os.path.join(tempfile.gettempdir(), "café 文書 sample.html")

SECOND_LAUNCH = r"""
import sys
sys.path.insert(0, %r)
from tgimprint import handoff
from tgimprint.singleinstance import SingleInstance
from tgimprint import constants as C
si = SingleInstance(C.INSTANCE_SLUG)
found = si.find_existing()
print("found", bool(found))
print("sent", handoff.hand_over(si, %r))
si.release()
""" % (HERE, DOC)

print("\nThe running copy receives a path from a second launch")

app = wx.App(False)
instance = SingleInstance(C.INSTANCE_SLUG)
check("this process holds the single instance", not instance.already_running,
      "another TG Imprint is running; close it and rerun" if instance.already_running else "")
frame = wx.Frame(None, title="handoff test")
instance.tag_window(frame)
received = []
receiver = handoff.Receiver(frame, lambda path: received.append(
    (path, wx.IsMainThread())))
check("the receiver installed itself on the window", receiver.installed)
frame.Show()

outcome = {}


def run_second_launch():
    # On a thread of its own. The first version ran the child from a timer
    # callback, which parked the UI thread inside subprocess.run while the
    # child was sending it a message; the message needs that thread to pump,
    # so the send timed out and the test reported the hand-over broken when
    # it was the test that was deadlocked. A real second launch never has
    # this problem because the running copy is in its main loop.
    result = subprocess.run([sys.executable, "-c", SECOND_LAUNCH],
                            capture_output=True, text=True, encoding="utf-8",
                            cwd=HERE, timeout=30)
    outcome["out"] = result.stdout + result.stderr
    # Give the message a moment to be dispatched, then stop the loop.
    wx.CallAfter(wx.CallLater, 300, app.ExitMainLoop)


import threading   # noqa: E402
wx.CallLater(200, lambda: threading.Thread(target=run_second_launch,
                                           daemon=True).start())
wx.CallLater(15000, app.ExitMainLoop)
app.MainLoop()

out = outcome.get("out", "")
check("the second launch found the tagged window", "found True" in out, out.strip()[:80])
check("and reports that the path was accepted", "sent True" in out)
check("the running copy received exactly one path", len(received) == 1, received)
if received:
    path, on_main = received[0]
    check("with every character intact", path == DOC, path)
    check("on the UI thread", on_main)

print("\nNoise is ignored and nothing raises")
check("a message from something else is refused",
      handoff.send_path(int(frame.GetHandle()), "") is False)
check("sending to no window is refused", handoff.send_path(0, DOC) is False)
receiver.remove()
check("the original procedure is restored", not receiver.installed)

print("\nA slow opener does not hold the second launch")
# The Overseer's K5: open_document may put up the unsaved-changes prompt.
# Run inside the message, that prompt would hold the SENDING process in its
# SendMessageTimeout until it was answered (or the five second timeout),
# which reads as a failed hand-over. main.py therefore installs the opener
# behind wx.CallAfter; this is that arrangement, with a two second sleep
# standing in for the prompt. The child must still be told "sent True" and
# finish well inside two seconds.
import time   # noqa: E402
slow_got = []


def slow_opener(path):
    time.sleep(2.0)
    slow_got.append(path)


deferred = handoff.Receiver(frame, lambda path: wx.CallAfter(slow_opener, path))
timing = {}


def run_second_launch_timed():
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-c", SECOND_LAUNCH],
                            capture_output=True, text=True, encoding="utf-8",
                            cwd=HERE, timeout=30)
    timing["seconds"] = time.monotonic() - started
    timing["out"] = result.stdout + result.stderr
    wx.CallAfter(wx.CallLater, 2600, app.ExitMainLoop)


wx.CallLater(100, lambda: threading.Thread(target=run_second_launch_timed,
                                           daemon=True).start())
wx.CallLater(15000, app.ExitMainLoop)
app.MainLoop()
child_seconds = timing.get("seconds", 99.0)
# The child process itself takes about a second to start Python and import
# wx, so the budget is the startup cost plus a little, well under the two
# second sleep plus the five second timeout that a blocking callback costs.
check("the second launch was told the path was taken", "sent True" in timing.get("out", ""))
check("and returned before the opener finished", child_seconds < 1.9, "%.2fs" % child_seconds)
check("while the opener still ran, on the UI thread, afterwards", slow_got == [DOC])
deferred.remove()
frame.Destroy()
instance.release()

print("\n%d/%d checks passed" % (sum(CHECKS), len(CHECKS)))
sys.stdout.flush()
os._exit(0 if all(CHECKS) else 1)
