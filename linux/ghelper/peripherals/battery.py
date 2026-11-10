"""Peripheral battery reads and a background cache.

Mouse packets match AsusMouse.ReadBattery (percent at byte 5). Headsets use
the same 0x12 0x07 report with the percent at byte 6, then 0x12 0x08 for
charging. The UI only reads the cache, so a slow HID transaction cannot
freeze the window.
"""

from __future__ import annotations

import threading

from ghelper.peripherals.mouse import AsusMouse
from ghelper.priv import hid_exchange


def format_battery(info: dict | None) -> str:
    if not info:
        return "读取中"
    if info.get("wired"):
        return "有线"
    percent = info.get("percent")
    if percent is None:
        return _human_error(info.get("message") or "") or "无电量"
    charging = " 充电中" if info.get("charging") else ""
    return "%d%%%s" % (int(percent), charging)


def _human_error(message: str) -> str:
    low = message.lower()
    if not message:
        return ""
    if "permission" in low or "denied" in low or "errno 13" in low:
        return "需要授权后才能读电量"
    if "refused" in low or "not running" in low or "111" in low:
        return "助手未运行"
    if "not found" in low:
        return "设备未找到"
    if "timed out" in low:
        return "电量读取超时"
    return message


def read_device_battery(device: dict) -> dict:
    kind = device.get("kind")
    wireless = bool(device.get("wireless"))
    if kind not in {"mouse", "headset", "keyboard"}:
        return {"wired": not wireless, "percent": None, "message": "无电池"}
    if not wireless and kind != "mouse":
        return {"wired": True, "percent": None}
    if kind == "mouse":
        result = AsusMouse(int(device["pid"]), device).read_battery()
        if not result.ok or not result.data:
            return {"percent": None, "message": result.message or "电量不可读", "charging": False}
        return {
            "percent": int(result.data.get("percent") or 0),
            "charging": bool(result.data.get("charging")),
            "message": "",
        }
    return _hid_percent(device, headset=kind == "headset")


def _hid_percent(device: dict, headset: bool) -> dict:
    iface = int(device.get("iface") or 0)
    packet = bytes([0x00, 0x12, 0x07])
    result = hid_exchange(0x0B05, int(device["pid"]), packet, iface=iface, size=65)
    raw = (result.data or {}).get("response") if result.ok else None
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 8 or raw[1] != 0x12:
        return {"percent": None, "message": result.message or "无电量报告", "charging": False}
    percent = int(raw[6] if headset else raw[5])
    if percent > 100:
        return {"percent": None, "message": "电量报文无效", "charging": False}
    charging = False
    if headset:
        charge = hid_exchange(0x0B05, int(device["pid"]), bytes([0x00, 0x12, 0x08]), iface=iface, size=65)
        charge_raw = (charge.data or {}).get("response") if charge.ok else None
        if isinstance(charge_raw, (bytes, bytearray)) and len(charge_raw) > 5:
            charging = charge_raw[5] == 1
    return {"percent": percent, "charging": charging, "message": ""}


class BatteryMonitor:
    def __init__(self, manager, interval: float = 15.0):
        self.manager = manager
        self.interval = interval
        self._cache: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ghelper-battery", daemon=False)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.5)
        self._thread = None

    def refresh_now(self) -> None:
        self._wake.set()

    def snapshot(self) -> dict[int, dict]:
        with self._lock:
            return dict(self._cache)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._poll()
            self._wake.wait(self.interval)
            self._wake.clear()

    def _poll(self) -> None:
        found: dict[int, dict] = {}
        try:
            devices = self.manager.discover()
        except Exception as exc:
            with self._lock:
                self._cache = {0: {"percent": None, "message": str(exc)}}
            return
        for device in devices:
            if self._stop.is_set():
                break
            try:
                found[int(device["pid"])] = read_device_battery(device)
            except Exception as exc:
                found[int(device["pid"])] = {"percent": None, "message": str(exc)}
        with self._lock:
            self._cache = found
