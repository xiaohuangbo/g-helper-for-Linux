"""Laptop Fn-key listener.

Reads the Asus WMI hotkeys evdev node. Access needs the udev uaccess rule
(or membership of group input). Global desktop shortcuts stay with the
compositor; this module only handles events the EC already emits.
"""

from __future__ import annotations

import os
import select
import struct
import threading
from pathlib import Path

from ghelper.hw.sysfs import read_text
from ghelper.logutil import get_logger

log = get_logger("ghelper.hotkeys")

# linux/input-event-codes.h, the ones ASUS WMI commonly emits.
KEY_NAMES = {
    113: "MUTE",
    114: "VOLUMEDOWN",
    115: "VOLUMEUP",
    148: "PROG1",
    149: "PROG2",
    202: "PROG3",
    203: "PROG4",
    224: "BRIGHTNESSDOWN",
    225: "BRIGHTNESSUP",
    229: "KBDILLUMDOWN",
    230: "KBDILLUMUP",
    237: "DISPLAYTOGGLE",
    431: "F13",
    432: "F14",
    433: "F15",
    434: "F16",
    435: "F17",
    436: "F18",
    437: "F19",
    438: "F20",
    439: "F21",
    440: "F22",
    441: "F23",
    442: "F24",
}

EVENT_SIZE = 24
EVENT_FORMAT = "llHHi"


def asus_event_node() -> str | None:
    root = Path("/sys/class/input")
    if not root.is_dir():
        return None
    for node in root.glob("event*"):
        name = read_text(node / "device" / "name")
        if name == "Asus WMI hotkeys":
            return "/dev/input/" + node.name
    return None


class HotkeyListener:
    def __init__(self, callback):
        self.callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error = ""

    def start(self) -> bool:
        path = asus_event_node()
        if not path:
            self.last_error = "Asus WMI hotkeys input node not found"
            return False
        if not os.access(path, os.R_OK):
            self.last_error = "cannot read %s (install udev rule or add user to input)" % path
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(path,), daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None

    def _loop(self, path: str) -> None:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            self.last_error = str(exc)
            log.warning("hotkey open failed: %s", exc)
            return
        try:
            while not self._stop.is_set():
                ready, _, _ = select.select([fd], [], [], 0.5)
                if not ready:
                    continue
                data = os.read(fd, EVENT_SIZE * 16)
                for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _sec, _usec, ev_type, code, value = struct.unpack_from(EVENT_FORMAT, data, offset)
                    if ev_type != 1 or value != 1:
                        continue
                    name = KEY_NAMES.get(code, "KEY_%d" % code)
                    try:
                        self.callback(code, name)
                    except Exception as exc:
                        log.warning("hotkey callback: %s", exc)
        finally:
            os.close(fd)
