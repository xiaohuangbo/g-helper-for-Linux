from __future__ import annotations

from pathlib import Path

from ghelper.hw.sysfs import read_text
from ghelper.peripherals.catalog import ASUS, identify
from ghelper.peripherals.mouse import AsusMouse


def _scan_hidraw() -> list[dict]:
    root = Path("/sys/class/hidraw")
    found = []
    if not root.is_dir():
        return found
    seen = set()
    for node in sorted(root.glob("hidraw*")):
        uevent = read_text(node / "device" / "uevent") or ""
        fields = {}
        for line in uevent.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value
        hid_id = fields.get("HID_ID", "")
        parts = hid_id.split(":")
        if len(parts) < 3:
            continue
        try:
            vid = int(parts[1], 16)
            pid = int(parts[2], 16)
        except ValueError:
            continue
        if vid != ASUS:
            continue
        phys = fields.get("HID_PHYS", "")
        key = (pid, phys)
        if key in seen:
            continue
        seen.add(key)
        meta = identify(pid)
        found.append({
            "path": "/dev/" + node.name,
            "node": node.name,
            "vid": vid,
            "pid": pid,
            "phys": phys,
            "hid_name": fields.get("HID_NAME", ""),
            **meta,
        })
    return found


class PeripheralManager:
    def discover(self) -> list[dict]:
        devices = _scan_hidraw()
        # Collapse multiple HID collections of one USB device to the preferred iface.
        grouped: dict[int, dict] = {}
        for item in devices:
            current = grouped.get(item["pid"])
            iface = item.get("iface", 0)
            preferred = ("input%d" % iface) in item.get("phys", "")
            if current is None or preferred:
                grouped[item["pid"]] = item
        return list(grouped.values())

    def mouse(self, pid: int) -> AsusMouse | None:
        for item in self.discover():
            if item["pid"] == pid and item["kind"] == "mouse":
                return AsusMouse(pid, item)
        meta = identify(pid)
        if meta["kind"] != "mouse":
            return None
        return AsusMouse(pid, meta)
