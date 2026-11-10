"""Shared ASUS mouse HID family.

Packets match app/Peripherals/Mouse/AsusMouse.cs. Transport is hidraw
(direct or via the privileged helper). Report size is 65, report id 0.
"""

from __future__ import annotations

from ghelper.peripherals.catalog import POLLING
from ghelper.priv import hid_exchange
from ghelper.result import Result

PACKET = 65


def _pkt(*data: int) -> bytes:
    return bytes(data)


class AsusMouse:
    def __init__(self, pid: int, meta: dict):
        self.pid = pid
        self.meta = meta
        self.iface = int(meta.get("iface") or 0)
        self.step = int(meta.get("step") or 100)
        self.max_dpi = int(meta.get("max_dpi") or 12000)
        self.profiles = 4

    def exchange(self, packet: bytes) -> Result:
        return hid_exchange(0x0B05, self.pid, packet, iface=self.iface, size=PACKET)

    def _response(self, result: Result) -> bytes | None:
        if not result.ok or not result.data:
            return None
        raw = result.data.get("response")
        return raw if isinstance(raw, (bytes, bytearray)) else None

    def read_battery(self) -> Result:
        result = self.exchange(_pkt(0x00, 0x12, 0x07))
        raw = self._response(result)
        if not raw or len(raw) < 11 or raw[1] != 0x12:
            return Result(False, result.message or "no battery report", {"raw": raw.hex() if raw else ""})
        return Result(True, "", {
            "percent": raw[5],
            "charging": raw[10] > 0,
            "power_off": raw[6],
            "low_warning": raw[7],
        })

    def read_dpi(self) -> Result:
        result = self.exchange(_pkt(0x00, 0x12, 0x04, 0x02 if self.meta.get("xy") else 0x00))
        raw = self._response(result)
        if not raw or len(raw) < 7 or raw[1] != 0x12:
            return Result(False, result.message or "no DPI report")
        values = []
        stride = 4 if self.meta.get("xy") else 2
        for index in range(self.profiles):
            offset = 5 + index * stride
            if offset + 1 >= len(raw):
                break
            encoded = raw[offset] | (raw[offset + 1] << 8)
            values.append(encoded * self.step + self.step)
        return Result(True, "", {"dpi": values})

    def set_dpi(self, dpi: int, profile: int = 1) -> Result:
        dpi = max(self.step, min(self.max_dpi, int(dpi)))
        dpi -= dpi % self.step
        encoded = max(0, (dpi - self.step) // self.step)
        packet = _pkt(0x00, 0x51, 0x31, max(0, profile - 1), 0x00, encoded & 0xFF, (encoded >> 8) & 0xFF)
        result = self.exchange(packet)
        if not result.ok:
            return result
        return Result(True, "dpi set", {"dpi": dpi, "profile": profile})

    def read_polling(self) -> Result:
        result = self.exchange(_pkt(0x00, 0x12, 0x04, 0x00))
        raw = self._response(result)
        if not raw or len(raw) < 14 or not (raw[1] == 0x12 and raw[2] == 0x04):
            return Result(False, result.message or "no polling report")
        code = raw[13] & 0x07
        hz = POLLING[code] if code < len(POLLING) else None
        return Result(True, "", {"code": code, "hz": hz})

    def set_polling(self, hz: int) -> Result:
        if hz not in POLLING:
            return Result(False, "unsupported polling rate")
        code = POLLING.index(hz)
        result = self.exchange(_pkt(0x00, 0x51, 0x31, 0x04, 0x00, code))
        if not result.ok:
            return result
        return Result(True, "polling set", {"hz": hz})

    def set_angle_snapping(self, enabled: bool) -> Result:
        return self.exchange(_pkt(0x00, 0x51, 0x31, 0x06, 0x00, 1 if enabled else 0))

    def set_lighting(self, mode: int, r: int, g: int, b: int, brightness: int = 25) -> Result:
        # Feature-style static lighting used by RGB Aura mice in this family.
        # Non-RGB models return FF AA, which the UI surfaces as unsupported.
        packet = _pkt(0x00, 0x51, 0x31, 0x0C, 0x00, mode & 0xFF, r & 0xFF, g & 0xFF, b & 0xFF, brightness & 0xFF)
        return self.exchange(packet)
