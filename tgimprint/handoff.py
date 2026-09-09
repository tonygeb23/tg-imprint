"""Handing a file from a second launch to the copy already running.

One copy at a time is a standing rule, and singleinstance.py reopens the
running copy when a second one starts. For a document editor that is not
enough: double clicking a document while the app is open, or dropping one on
the shortcut, arrives as a second launch WITH a file path, and a launch that
only raises the window has quietly thrown that path away. For somebody not
watching the screen, that is indistinguishable from the file failing to open.

So the second launch sends the path to the running copy's window with
WM_COPYDATA, the Windows message made for exactly this, and then raises the
window as before. The running copy opens the file, after its usual unsaved
changes prompt.

Kept out of singleinstance.py on purpose: that file is byte-identical across
every TG Studios app and this need is this app's own.

Everything here falls open. A failure to hand the path over must never stop
the app from starting, so the caller treats False as "start normally".
"""
import ctypes
import ctypes.wintypes
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_COPYDATA = 0x004A
GWLP_WNDPROC = -4

#: A tag in dwData so a message from anything else is ignored. Arbitrary,
#: stable, and not a secret.
OPEN_FILE = 0x45505046          # "EPPF"


class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [("dwData", ctypes.c_void_p),
                ("cbData", ctypes.wintypes.DWORD),
                ("lpData", ctypes.c_void_p)]


# 64 bit safe prototypes. Without these, ctypes truncates pointers.
user32.SendMessageTimeoutW.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM, ctypes.wintypes.UINT, ctypes.wintypes.UINT,
    ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.wintypes.LPARAM
user32.CallWindowProcW.argtypes = [
    ctypes.c_void_p, ctypes.wintypes.HWND, ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.CallWindowProcW.restype = ctypes.wintypes.LPARAM
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _set_long = user32.SetWindowLongPtrW
    _get_long = user32.GetWindowLongPtrW
else:                                   # pragma: no cover, a 32 bit Python
    _set_long = user32.SetWindowLongW
    _get_long = user32.GetWindowLongW
_set_long.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_set_long.restype = ctypes.c_void_p
_get_long.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_get_long.restype = ctypes.c_void_p

WNDPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.LPARAM, ctypes.wintypes.HWND,
                             ctypes.wintypes.UINT, ctypes.wintypes.WPARAM,
                             ctypes.wintypes.LPARAM)

SMTO_ABORTIFHUNG = 0x0002


def send_path(hwnd, path, timeout_ms=5000):
    """Ask the running copy at `hwnd` to open `path`. True if it took it.

    SendMessageTimeout rather than SendMessage, so a running copy that is
    hung (a modal dialog will still answer; a dead process will not) cannot
    hang the second launch with it.
    """
    if not hwnd or not path:
        return False
    try:
        data = str(path).encode("utf-16-le") + b"\x00\x00"
        buffer = ctypes.create_string_buffer(data, len(data))
        packet = COPYDATASTRUCT(OPEN_FILE, len(data),
                                ctypes.cast(buffer, ctypes.c_void_p))
        result = ctypes.c_size_t(0)
        ok = user32.SendMessageTimeoutW(
            hwnd, WM_COPYDATA, 0, ctypes.addressof(packet),
            SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result))
        return bool(ok) and result.value == 1
    except Exception:
        return False


class Receiver:
    """Subclasses a wx window's procedure to receive WM_COPYDATA.

    `callback(path)` is called on the window's own thread, which for a wx
    top-level window is the UI thread, so the callback may touch wx directly.
    Keep the Receiver alive for the life of the window: the window procedure
    it installs points into it.
    """

    def __init__(self, window, callback):
        self.callback = callback
        self.hwnd = None
        self.previous = None
        self._proc = None
        try:
            self.hwnd = int(window.GetHandle())
            self._proc = WNDPROC(self._handle)
            self.previous = _set_long(self.hwnd, GWLP_WNDPROC,
                                      ctypes.cast(self._proc, ctypes.c_void_p))
            if not self.previous:
                self.hwnd = None
        except Exception:
            self.hwnd = None

    @property
    def installed(self):
        return bool(self.hwnd and self.previous)

    def _handle(self, hwnd, message, wparam, lparam):
        if message == WM_COPYDATA:
            try:
                packet = COPYDATASTRUCT.from_address(lparam)
                if packet.dwData == OPEN_FILE and packet.cbData and packet.lpData:
                    raw = ctypes.string_at(packet.lpData, packet.cbData)
                    path = raw.decode("utf-16-le", "replace").rstrip("\x00")
                    if path:
                        try:
                            self.callback(path)
                        except Exception:
                            pass
                        return 1
            except Exception:
                pass
        return user32.CallWindowProcW(self.previous, hwnd, message, wparam, lparam)

    def remove(self):
        """Put the original procedure back. Call before the window is destroyed."""
        try:
            if self.installed:
                _set_long(self.hwnd, GWLP_WNDPROC, self.previous)
        except Exception:
            pass
        self.hwnd = None


def hand_over(instance, path):
    """Second launch: give `path` to the running copy found by `instance`.

    Returns True when the running copy accepted the file. The caller still
    raises the window either way.
    """
    try:
        hwnd = instance.find_existing()
    except Exception:
        return False
    return send_path(hwnd, path) if hwnd else False


if __name__ == "__main__":             # pragma: no cover, a manual probe
    print("send:", send_path(int(sys.argv[1]), sys.argv[2]))
