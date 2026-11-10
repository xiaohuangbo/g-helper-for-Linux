"""Client for the privileged helper, plus a direct-write fallback."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

from ghelper.hw.sysfs import write_text
from ghelper.hw.whitelist import is_allowed, validate_value
from ghelper.paths import helper_socket, package_root
from ghelper.result import Result

_CHILDREN: list = []


def helper_running() -> bool:
    """True only when the helper answers a ping. A bare connect is not a request."""
    path = helper_socket()
    if not path.exists():
        return False
    reply = call({"op": "ping"}, timeout=0.6)
    return bool(reply.get("ok"))


def call(req: dict, timeout: float = 4.0) -> dict:
    path = helper_socket()
    if not path.exists():
        return {"ok": False, "message": "privileged helper is not running"}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(path))
        sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(8192)
            if not chunk:
                break
            data += chunk
        if not data:
            return {"ok": False, "message": "empty helper reply"}
        return json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        sock.close()


def write_sysfs(path: str, value: str) -> Result:
    if not is_allowed(path, write=True):
        return Result(False, "path is not in the allow-list")
    try:
        cleaned = validate_value(path, value)
    except Exception as exc:
        return Result(False, str(exc))
    try:
        write_text(path, cleaned)
        return Result(True, "written", {"value": cleaned, "via": "direct"})
    except OSError as exc:
        reply = call({"op": "write", "path": path, "value": cleaned})
        if reply.get("ok"):
            return Result(True, "written via helper", {"value": cleaned, "via": "helper"})
        hint = reply.get("message") or str(exc)
        return Result(False, hint + ". Start the helper with: pkexec ghelper-priv daemon")


def acpi_get(device_id: int) -> Result:
    reply = call({"op": "acpi_get", "device": int(device_id)})
    return Result(bool(reply.get("ok")), reply.get("message") or "", reply.get("data"))


def acpi_set(device_id: int, value: int) -> Result:
    reply = call({"op": "acpi_set", "device": int(device_id), "value": int(value)})
    return Result(bool(reply.get("ok")), reply.get("message") or "", reply.get("data"))


def hid_exchange(vid: int, pid: int, packet: bytes, iface: int | None = None, size: int = 65) -> Result:
    """Read or write an ASUS HID report. Fall back to the helper only when it is actually listening."""
    direct = _hid_direct(vid, pid, packet, iface, size)
    if direct.ok or not helper_running():
        return direct
    reply = call({
        "op": "hid_exchange",
        "vid": vid,
        "pid": pid,
        "packet": packet.hex(),
        "iface": iface,
        "size": size,
    })
    if reply.get("ok"):
        data = reply.get("data") or {}
        raw = bytes.fromhex(data.get("hex") or "")
        return Result(True, "helper", {"response": raw, "path": data.get("path")})
    return Result(False, reply.get("message") or direct.message)


def _hid_direct(vid: int, pid: int, packet: bytes, iface: int | None, size: int) -> Result:
    try:
        from ghelper.helper import _match_hid
    except Exception as exc:
        return Result(False, str(exc))
    path = _match_hid(vid, pid, iface)
    if not path:
        return Result(False, "device not found")
    try:
        import select as select_mod

        import time

        from ghelper.hidframe import is_command_response, to_windows_layout

        length = max(len(packet), size)
        buf = bytearray(length)
        buf[: len(packet)] = packet
        fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        try:
            try:
                while True:
                    os.read(fd, 512)
            except BlockingIOError:
                pass
            os.write(fd, buf)
            deadline = time.monotonic() + 1.2
            while time.monotonic() < deadline:
                ready, _, _ = select_mod.select([fd], [], [], max(0.05, deadline - time.monotonic()))
                if not ready:
                    break
                data = os.read(fd, max(length, 64))
                if is_command_response(packet, data):
                    return Result(True, "direct", {"response": to_windows_layout(packet, data), "path": path})
            return Result(False, "HID read timed out", {"path": path})
        finally:
            os.close(fd)
    except PermissionError as exc:
        return Result(False, "permission denied: " + str(exc))
    except OSError as exc:
        return Result(False, str(exc))


def helper_command() -> list[str]:
    source = package_root() / "bin" / "ghelper-priv"
    if source.is_file():
        return [str(source), "daemon"]
    return ["ghelper-priv", "daemon"]


def spawn_helper() -> Result:
    """Ask polkit to start the daemon. Interactive; do not call from tests."""
    if helper_running():
        return Result(True, "already running")
    cmd = helper_command()
    if os.geteuid() == 0:
        import subprocess
        proc = subprocess.Popen(cmd, start_new_session=True)
        _CHILDREN.append(proc)
        return Result(True, "started as root")
    import subprocess
    pkexec = ["pkexec", *cmd]
    try:
        proc = subprocess.run(pkexec, check=False, timeout=120)
    except Exception as exc:
        return Result(False, str(exc))
    if proc.returncode != 0:
        return Result(False, "pkexec failed (%s)" % proc.returncode)
    return Result(helper_running(), "started" if helper_running() else "pkexec returned but socket is missing")


def shutdown_helper(timeout: float = 1.5) -> Result:
    """Ask the privileged helper to exit and unlink its socket."""
    path = helper_socket()
    if helper_running():
        reply = call({"op": "shutdown"}, timeout=timeout)
    else:
        reply = {"ok": True, "message": "helper already stopped"}
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    reap_zombies()
    return Result(bool(reply.get("ok")) or not helper_running(), reply.get("message") or "helper stopped")


def reap_zombies() -> None:
    """Wait for children we spawned so they cannot stay as zombies."""
    import subprocess
    for proc in list(_CHILDREN):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        else:
            proc.wait(timeout=0)
    _CHILDREN.clear()
    try:
        while True:
            pid, _status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
    except ChildProcessError:
        return
