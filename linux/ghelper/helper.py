"""Privileged helper.

Started by systemd or pkexec. Speaks one JSON object per line over a Unix
socket. Every write is checked against ghelper.hw.whitelist. HID access is
limited to ASUS vendor 0x0b05.
"""

from __future__ import annotations

import json
import os
import select
import socket
import stat
import struct
import threading
import time
from pathlib import Path

from ghelper.hidframe import is_command_response, to_windows_layout
from ghelper.hw.sysfs import read_text
from ghelper.hw.whitelist import is_allowed, validate_value
from ghelper.logutil import get_logger
from ghelper.paths import helper_socket

log = get_logger("ghelper.helper")
ASUS_VID = 0x0B05
MAX_HID = 256
STOP = threading.Event()
_HANDLERS: list[threading.Thread] = []


def _lockdown() -> str:
    text = read_text(Path("/sys/kernel/security/lockdown")) or ""
    start = text.find("[")
    end = text.find("]", start + 1)
    return text[start + 1:end] if start >= 0 and end > start else "none"


def _debug_root() -> Path | None:
    for candidate in (Path("/sys/kernel/debug/asus-nb-wmi"), Path("/sys/kernel/debug/asus-wmi")):
        if (candidate / "dev_id").exists() or candidate.is_dir():
            return candidate
    return None


def _write_allowed(path: str, value: str) -> str:
    if not is_allowed(path, write=True):
        raise PermissionError("path not allowed")
    cleaned = validate_value(path, value)
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(path)
    target.write_text(cleaned + "\n", encoding="utf-8")
    return cleaned


def _parse_debug_value(text: str) -> int:
    token = ""
    if "=" in text:
        token = text.split("=", 1)[1].strip().split()[0]
    else:
        parts = text.strip().split()
        token = parts[-1] if parts else ""
    if not token:
        raise ValueError("empty debugfs reply: " + text)
    return int(token, 0)


def acpi_get(device_id: int) -> dict:
    root = _debug_root()
    if root is None:
        return {"ok": False, "message": "debugfs asus-nb-wmi is not available (root and debugfs required)"}
    if _lockdown() not in {"none", "unknown"}:
        return {"ok": False, "message": "kernel lockdown blocks debugfs; ACPI scalar access is unavailable"}
    try:
        (root / "dev_id").write_text(format(int(device_id) & 0xFFFFFFFF, "#x") + "\n", encoding="utf-8")
        raw = (root / "dsts").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise OSError("debugfs access failed: %s" % exc)
    value = _parse_debug_value(raw)
    stripped = value - 0x10000 if value >= 0x10000 else value
    return {"ok": True, "data": {"raw": value, "value": stripped, "supported": value >= 0x10000, "text": raw.strip()}}


def acpi_set(device_id: int, value: int) -> dict:
    root = _debug_root()
    if root is None:
        return {"ok": False, "message": "debugfs asus-nb-wmi is not available"}
    if _lockdown() not in {"none", "unknown"}:
        return {"ok": False, "message": "kernel lockdown blocks debugfs; ACPI scalar access is unavailable"}
    device_id = int(device_id) & 0xFFFFFFFF
    value = int(value) & 0xFFFFFFFF
    (root / "dev_id").write_text(format(device_id, "#x") + "\n", encoding="utf-8")
    (root / "ctrl_param").write_text(format(value, "#x") + "\n", encoding="utf-8")
    (root / "devs").write_text("1\n", encoding="utf-8")
    return {"ok": True, "data": {"device": device_id, "value": value}, "message": "DEVS submitted"}


def _hidraw_nodes() -> list[dict]:
    found = []
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return found
    for node in root.glob("hidraw*"):
        uevent = read_text(node / "device" / "uevent") or ""
        fields = {}
        for line in uevent.splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                fields[key] = val
        hid_id = fields.get("HID_ID", "")
        parts = hid_id.split(":")
        vid = int(parts[1], 16) if len(parts) >= 3 else 0
        pid = int(parts[2], 16) if len(parts) >= 3 else 0
        found.append({
            "name": node.name,
            "path": "/dev/" + node.name,
            "vid": vid,
            "pid": pid,
            "hid_name": fields.get("HID_NAME", ""),
            "phys": fields.get("HID_PHYS", ""),
            "hid_id": hid_id,
        })
    return found


def _match_hid(vid: int, pid: int, iface: int | None) -> str | None:
    matches = [item for item in _hidraw_nodes() if item["vid"] == vid and (pid == 0 or item["pid"] == pid)]
    if vid != ASUS_VID:
        return None
    if not matches:
        return None
    if iface is None:
        for item in matches:
            if item["phys"].endswith("input0"):
                return item["path"]
        return matches[0]["path"]
    for item in matches:
        if item["phys"].endswith("input%d" % iface):
            return item["path"]
    return matches[0]["path"]


def hid_exchange(vid: int, pid: int, packet_hex: str, iface: int | None = None, size: int = 65, timeout: float = 0.45) -> dict:
    if int(vid) != ASUS_VID:
        return {"ok": False, "message": "HID helper only opens ASUS devices"}
    path = _match_hid(int(vid), int(pid), iface)
    if not path:
        return {"ok": False, "message": "ASUS HID device not found"}
    raw = bytes.fromhex(packet_hex)
    if len(raw) > MAX_HID:
        return {"ok": False, "message": "packet too large"}
    length = max(len(raw), min(int(size), MAX_HID))
    buf = bytearray(length)
    buf[: len(raw)] = raw
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        try:
            while True:
                os.read(fd, 512)
        except BlockingIOError:
            pass
        os.write(fd, buf)
        deadline = time.monotonic() + max(timeout, 1.2)
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                break
            data = os.read(fd, max(length, 64))
            if is_command_response(raw, data):
                normalized = to_windows_layout(raw, data)
                return {"ok": True, "data": {"path": path, "hex": normalized.hex(), "len": len(normalized)}}
        return {"ok": False, "message": "HID read timed out", "data": {"path": path}}
    finally:
        os.close(fd)


def dispatch(req: dict) -> dict:
    op = req.get("op")
    try:
        if op == "ping":
            return {"ok": True, "data": {"uid": os.geteuid(), "debugfs": _debug_root() is not None}}
        if op == "shutdown":
            STOP.set()
            return {"ok": True, "message": "stopping"}
        if op == "write":
            cleaned = _write_allowed(str(req["path"]), str(req["value"]))
            return {"ok": True, "data": {"value": cleaned}}
        if op == "acpi_get":
            return acpi_get(int(req["device"]))
        if op == "acpi_set":
            return acpi_set(int(req["device"]), int(req["value"]))
        if op == "hid_list":
            return {"ok": True, "data": [item for item in _hidraw_nodes() if item["vid"] == ASUS_VID]}
        if op == "hid_exchange":
            iface = req.get("iface")
            return hid_exchange(
                int(req["vid"]),
                int(req.get("pid") or 0),
                str(req["packet"]),
                None if iface is None else int(iface),
                int(req.get("size") or 65),
            )
        return {"ok": False, "message": "unknown op"}
    except Exception as exc:
        log.warning("helper op %s failed: %s", op, exc)
        return {"ok": False, "message": str(exc)}


def _peer_uid(sock: socket.socket) -> int:
    SO_PEERCRED = 17
    data = sock.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", data)
    return uid


class _Server(socket.socket):
    pass


def serve(path: Path | None = None) -> None:
    if os.geteuid() != 0:
        raise SystemExit("ghelper-priv daemon must run as root")
    path = path or helper_socket()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
    server.listen(8)
    server.settimeout(0.4)
    log.info("helper listening on %s", path)

    def _request_stop(signum, _frame) -> None:
        log.info("helper signal %s", signum)
        STOP.set()

    import signal
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    def _reply(conn: socket.socket, payload: bytes) -> None:
        try:
            conn.sendall(payload)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def handle(conn: socket.socket) -> None:
        with conn:
            try:
                conn.settimeout(2.0)
                uid = _peer_uid(conn)
                if uid != 0 and uid < 1000:
                    _reply(conn, b'{"ok": false, "message": "uid not allowed"}\n')
                    return
                data = b""
                while b"\n" not in data and len(data) < 65536:
                    try:
                        chunk = conn.recv(4096)
                    except TimeoutError:
                        break
                    if not chunk:
                        break
                    data += chunk
                line = data.split(b"\n", 1)[0].strip()
                if not line:
                    return
                try:
                    req = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    _reply(conn, b'{"ok": false, "message": "bad json"}\n')
                    return
                reply = dispatch(req if isinstance(req, dict) else {})
                _reply(conn, (json.dumps(reply) + "\n").encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError) as exc:
                log.info("client closed: %s", exc)
            except Exception as exc:
                log.warning("client failed: %s", exc)

    while not STOP.is_set():
        try:
            conn, _addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        worker = threading.Thread(target=handle, args=(conn,), name="ghelper-helper-client", daemon=True)
        _HANDLERS.append(worker)
        worker.start()
    try:
        server.close()
    except OSError:
        pass
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
    for worker in list(_HANDLERS):
        worker.join(timeout=1.5)
    log.info("helper stopped")


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"daemon", "serve"}:
        serve()
        return 0
    if argv[0] == "apply" and len(argv) >= 2:
        reply = dispatch(json.loads(argv[1]))
        print(json.dumps(reply))
        return 0 if reply.get("ok") else 1
    print("usage: ghelper-priv daemon | ghelper-priv apply '{json}'")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
