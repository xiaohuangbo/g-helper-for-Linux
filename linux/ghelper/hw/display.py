"""Display brightness and refresh-rate control.

Refresh changes go through the desktop that owns the outputs:
KDE kscreen-doctor, wlroots wlr-randr, GNOME gdctl, then swaymsg.
Brightness uses the kernel backlight class and does not depend on the
compositor. Wayland and X11 both consume the same sysfs node.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from ghelper.hw.sysfs import read_int, read_text
from ghelper.priv import write_sysfs
from ghelper.result import Result

ANSI = re.compile("\x1b\\[[0-9;]*m")

# kscreen-doctor is a subprocess. Querying it on every UI tick blocks the
# GTK main loop long enough to trip GDK frame-timing checks.
OUTPUT_TTL = 5.0
_output_cache: tuple[float, list[dict]] | None = None


def backlight_devices() -> list[Path]:
    root = Path("/sys/class/backlight")
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / "brightness").exists())


def brightness_snapshot() -> dict:
    devices = []
    for dev in backlight_devices():
        current = read_int(dev / "brightness")
        maximum = read_int(dev / "max_brightness") or 1
        percent = None if current is None else round(current * 100 / maximum)
        devices.append({
            "name": dev.name,
            "path": str(dev / "brightness"),
            "current": current,
            "max": maximum,
            "percent": percent,
        })
    return {"devices": devices, "percent": devices[0]["percent"] if devices else None}


def set_brightness_percent(percent: int, device: str | None = None) -> Result:
    percent = max(1, min(100, int(percent)))
    devices = backlight_devices()
    if device:
        devices = [p for p in devices if p.name == device] or devices
    if not devices:
        return Result(False, "no backlight device")
    dev = devices[0]
    maximum = read_int(dev / "max_brightness") or 1
    raw = max(1, min(maximum, round(percent * maximum / 100)))
    return write_sysfs(str(dev / "brightness"), str(raw))


def _run(cmd: list[str], timeout: float = 2.5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)


def _kscreen_outputs() -> list[dict]:
    if not shutil.which("kscreen-doctor"):
        return []
    proc = _run(["kscreen-doctor", "-o"])
    text = ANSI.sub("", proc.stdout + "\n" + proc.stderr)
    outputs: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Output:"):
            parts = stripped.split()
            name = parts[2] if len(parts) >= 3 else parts[-1]
            current = {"name": name, "modes": [], "current": None, "enabled": "enabled" in stripped}
            outputs.append(current)
            continue
        if current is None:
            continue
        if stripped.startswith("Modes:"):
            modes = re.findall(r"(\d+x\d+@\d+(?:\.\d+)?)", stripped)
            current["modes"] = modes
            marked = re.findall(r"(\d+x\d+@\d+(?:\.\d+)?)\*", stripped)
            if marked:
                current["current"] = marked[-1]
    return outputs


def outputs_snapshot(force: bool = False) -> list[dict]:
    global _output_cache
    now = time.monotonic()
    if not force and _output_cache is not None and now - _output_cache[0] < OUTPUT_TTL:
        return [dict(item, modes=list(item.get("modes") or [])) for item in _output_cache[1]]
    found = _kscreen_outputs()
    if found:
        _output_cache = (now, [dict(item, modes=list(item.get("modes") or [])) for item in found])
        return found
    # DRM fallback: modes exist but the current mode is not always exposed.
    drm = Path("/sys/class/drm")
    outputs = []
    if not drm.is_dir():
        return outputs
    for node in sorted(drm.glob("card*-*")):
        if not (node / "status").exists():
            continue
        status = read_text(node / "status")
        if status != "connected":
            continue
        modes = (read_text(node / "modes") or "").splitlines()
        name = node.name.split("-", 1)[-1]
        outputs.append({"name": name, "modes": modes, "current": modes[0] if modes else None, "enabled": True, "source": "drm"})
    _output_cache = (now, [dict(item, modes=list(item.get("modes") or [])) for item in outputs])
    return outputs


def set_mode(output: str, mode: str) -> Result:
    mode = mode.strip()
    if shutil.which("kscreen-doctor"):
        proc = _run(["kscreen-doctor", "output.%s.mode.%s" % (output, mode)])
        if proc.returncode == 0:
            global _output_cache
            _output_cache = None
            return Result(True, "kscreen-doctor", {"output": output, "mode": mode})
        err = (proc.stderr or proc.stdout or "kscreen-doctor failed").strip()
    else:
        err = "kscreen-doctor not installed"
    if shutil.which("wlr-randr"):
        proc = _run(["wlr-randr", "--output", output, "--mode", mode.split("@")[0]])
        if proc.returncode == 0:
            return Result(True, "wlr-randr", {"output": output, "mode": mode})
    if shutil.which("swaymsg"):
        proc = _run(["swaymsg", "output", output, "mode", mode.replace("@", " ")])
        if proc.returncode == 0:
            return Result(True, "swaymsg", {"output": output, "mode": mode})
    return Result(False, err)


def pick_refresh(modes: list[str], want: str) -> str | None:
    if not modes:
        return None
    parsed = []
    for mode in modes:
        match = re.search(r"@(\d+(?:\.\d+)?)", mode)
        hz = float(match.group(1)) if match else 0
        parsed.append((hz, mode))
    if want == "max":
        return max(parsed, key=lambda item: item[0])[1]
    try:
        target = float(want)
    except ValueError:
        return None
    best = min(parsed, key=lambda item: abs(item[0] - target))
    return best[1]
