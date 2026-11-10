"""Laptop hardware facade.

Reads are unprivileged. Writes try the sysfs node directly and fall back to
the polkit helper. Missing features stay visible but disabled so ROG, TUF and
Vivobook machines share one code path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ghelper.hw import display as display_hw
from ghelper.hw import ids
from ghelper.hw.curves import clamp_points, duty_to_pwm, pwm_to_duty
from ghelper.hw.modes import (
    MODE_LABELS,
    TTP_FOR_MODE,
    available_modes,
    mode_for_profile,
    mode_for_ttp,
    profile_for_mode,
)
from ghelper.hw.sysfs import dmi, read_int, read_text
from ghelper.priv import acpi_get, acpi_set, helper_running, write_sysfs
from ghelper.result import Result

PLATFORM = Path("/sys/devices/platform/asus-nb-wmi")
PROFILE = Path("/sys/firmware/acpi/platform_profile")
PROFILE_CHOICES = Path("/sys/firmware/acpi/platform_profile_choices")
ARMOURY = Path("/sys/class/firmware-attributes/asus-armoury/attributes")
LED = Path("/sys/class/leds")
LOCKDOWN = Path("/sys/kernel/security/lockdown")


def lockdown_state() -> str:
    """Kernel lockdown blocks debugfs, so ACPI scalar access stops working."""
    text = read_text(LOCKDOWN) or ""
    start = text.find("[")
    end = text.find("]", start + 1)
    if start >= 0 and end > start:
        return text[start + 1:end]
    return "none" if text else "unknown"


def family_of(product: str, board: str) -> str:
    blob = (product + " " + board).lower()
    if "ally" in blob:
        return "ally"
    if any(token in blob for token in ("vivobook", "zenbook", "proart", "expertbook")):
        return "vivobook"
    if "tuf" in blob or board.lower().startswith(("fa", "fx")):
        return "tuf"
    if any(token in blob for token in ("rog", "zephyrus", "strix", "scar", "flow")):
        return "rog"
    vendor = dmi("sys_vendor").lower()
    return "asus" if "asus" in vendor else "unknown"


def _profile_choices() -> list[str]:
    text = read_text(PROFILE_CHOICES) or ""
    return [item for item in text.split() if item]


def _asus_hwmons() -> list[Path]:
    found = []
    root = Path("/sys/class/hwmon")
    if not root.is_dir():
        return found
    for node in root.glob("hwmon*"):
        if read_text(node / "name") == "asus":
            found.append(node)
    return found


def _scan_temps() -> dict:
    package = None
    extras = []
    root = Path("/sys/class/hwmon")
    if not root.is_dir():
        return {"package_c": None, "sensors": []}
    for node in root.glob("hwmon*"):
        name = read_text(node / "name") or node.name
        for sensor in node.glob("temp*_input"):
            label = read_text(node / sensor.name.replace("_input", "_label")) or sensor.name
            raw = read_int(sensor)
            if raw is None:
                continue
            item = {"hwmon": name, "label": label, "c": round(raw / 1000, 1)}
            extras.append(item)
            if package is None and name == "coretemp" and "package" in label.lower():
                package = item["c"]
            if package is None and name in {"k10temp", "zenpower"} and label.lower() in {"tctl", "tdie"}:
                package = item["c"]
    if package is None:
        for item in extras:
            if item["hwmon"] in {"coretemp", "acpitz", "k10temp"}:
                package = item["c"]
                break
    return {"package_c": package, "sensors": extras[:24]}


def _battery() -> dict:
    root = Path("/sys/class/power_supply")
    bats = []
    if root.is_dir():
        for node in sorted(root.glob("BAT*")):
            energy_now = read_int(node / "energy_now")
            energy_full = read_int(node / "energy_full")
            power = read_int(node / "power_now")
            voltage = read_int(node / "voltage_now")
            bats.append({
                "name": node.name,
                "status": read_text(node / "status"),
                "capacity": read_int(node / "capacity"),
                "charge_limit": read_int(node / "charge_control_end_threshold"),
                "charge_limit_path": str(node / "charge_control_end_threshold") if (node / "charge_control_end_threshold").exists() else None,
                "energy_now_wh": None if energy_now is None else round(energy_now / 1_000_000, 2),
                "energy_full_wh": None if energy_full is None else round(energy_full / 1_000_000, 2),
                "power_w": None if power is None else round(power / 1_000_000, 2),
                "voltage_v": None if voltage is None else round(voltage / 1_000_000, 2),
                "cycles": read_int(node / "cycle_count"),
                "model": read_text(node / "model_name"),
                "manufacturer": read_text(node / "manufacturer"),
            })
    ac = None
    if root.is_dir():
        for node in root.iterdir():
            if read_text(node / "type") == "Mains":
                ac = read_int(node / "online") == 1
                break
    return {"batteries": bats, "ac_online": ac, "primary": bats[0] if bats else None}


def _keyboard() -> dict:
    nodes = []
    if LED.is_dir():
        for node in LED.glob("asus::*"):
            if not (node / "brightness").exists():
                continue
            nodes.append({
                "name": node.name,
                "path": str(node / "brightness"),
                "brightness": read_int(node / "brightness"),
                "max": read_int(node / "max_brightness"),
            })
    return {"devices": nodes, "supported": bool(nodes)}


def _fans() -> list[dict]:
    fans = []
    for hwmon in _asus_hwmons():
        for sensor in sorted(hwmon.glob("fan*_input")):
            index = "".join(ch for ch in sensor.name if ch.isdigit())
            label = read_text(hwmon / ("fan%s_label" % index)) or sensor.name
            points = []
            for point in range(1, 9):
                temp = read_int(hwmon / ("pwm%s_auto_point%s_temp" % (index, point)))
                pwm = read_int(hwmon / ("pwm%s_auto_point%s_pwm" % (index, point)))
                if temp is None and pwm is None:
                    continue
                points.append({
                    "temp": temp,
                    "duty": None if pwm is None else pwm_to_duty(pwm),
                    "temp_path": str(hwmon / ("pwm%s_auto_point%s_temp" % (index, point))),
                    "pwm_path": str(hwmon / ("pwm%s_auto_point%s_pwm" % (index, point))),
                })
            key = "mid"
            low = label.lower()
            if "cpu" in low:
                key = "cpu"
            elif "gpu" in low:
                key = "gpu"
            fans.append({
                "id": key + index,
                "key": key,
                "label": label,
                "rpm": read_int(sensor),
                "pwm_enable": str(hwmon / ("pwm%s_enable" % index)),
                "curve_supported": len(points) >= 2,
                "points": points,
            })
    return fans


def _attributes() -> list[dict]:
    found = []
    if not ARMOURY.is_dir():
        return found
    for node in sorted(ARMOURY.iterdir()):
        if not node.is_dir() or node.name == "pending_reboot":
            continue
        possible = read_text(node / "possible_values")
        found.append({
            "name": node.name,
            "display": read_text(node / "display_name") or node.name,
            "type": read_text(node / "type"),
            "current": read_text(node / "current_value"),
            "min": read_text(node / "min_value"),
            "max": read_text(node / "max_value"),
            "possible": possible.split(";") if possible else [],
            "path": str(node / "current_value"),
        })
    return found


def _optional_platform_files() -> dict:
    names = (
        "gpu_mux_mode", "dgpu_disable", "egpu_enable", "panel_od",
        "mini_led_mode", "fan_boost_mode", "throttle_thermal_policy",
    )
    out = {}
    for name in names:
        path = PLATFORM / name
        out[name] = {"present": path.exists(), "value": read_text(path) if path.exists() else None, "path": str(path)}
    return out


def _gpu() -> dict:
    vendors = []
    drm = Path("/sys/class/drm")
    if drm.is_dir():
        for node in drm.glob("card*"):
            vendor = read_text(node / "device" / "vendor")
            if vendor:
                vendors.append(vendor)
    nvidia = None
    if shutil.which("nvidia-smi"):
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,power.draw", "--format=csv,noheader,nounits"],
            text=True, capture_output=True, timeout=4, check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            cols = [part.strip() for part in proc.stdout.strip().splitlines()[0].split(",")]
            nvidia = {"name": cols[0] if cols else "", "raw": proc.stdout.strip()}
    files = _optional_platform_files()
    modes = []
    if files["dgpu_disable"]["present"] or files["gpu_mux_mode"]["present"]:
        modes = ["eco", "standard"]
        if files["gpu_mux_mode"]["present"]:
            modes.append("ultimate")
        modes.append("optimized")
    return {"vendors": vendors, "nvidia": nvidia, "modes": modes, "files": files}


class Hardware:
    def snapshot(self) -> dict:
        product = dmi("product_name")
        board = dmi("board_name")
        choices = _profile_choices()
        profile = read_text(PROFILE)
        ttp = read_int(PLATFORM / "throttle_thermal_policy")
        current = mode_for_profile(profile) or mode_for_ttp(ttp)
        modes = []
        for mode in ("silent", "balanced", "turbo"):
            zh, en = MODE_LABELS[mode]
            modes.append({
                "id": mode,
                "label_zh": zh,
                "label_en": en,
                "available": profile_for_mode(mode, choices) is not None or (PLATFORM / "throttle_thermal_policy").exists(),
                "profile": profile_for_mode(mode, choices),
                "ttp": TTP_FOR_MODE[mode],
            })
        # A mode is only offered when the kernel advertises its profile, or
        # when no platform_profile exists and the thermal policy node does.
        if choices:
            offered = set(available_modes(choices))
            for item in modes:
                item["available"] = item["id"] in offered
        return {
            "product": {
                "vendor": dmi("sys_vendor"),
                "name": product,
                "board": board,
                "bios": dmi("bios_version"),
                "bios_date": dmi("bios_date"),
                "family": family_of(product, board),
            },
            "performance": {
                "choices": choices,
                "profile": profile,
                "ttp": ttp,
                "current": current,
                "modes": modes,
            },
            "battery": _battery(),
            "keyboard": _keyboard(),
            "fans": _fans(),
            "temps": _scan_temps(),
            "display": {
                "brightness": display_hw.brightness_snapshot(),
                "outputs": display_hw.outputs_snapshot(),
            },
            "gpu": _gpu(),
            "attributes": _attributes(),
            "acpi_catalog": [
                {**item, "values": {str(k): v for k, v in item.get("values", {}).items()}}
                for item in ids.ACPI_CATALOG
            ],
            "helper": {"running": helper_running()},
            "host": {"lockdown": lockdown_state()},
        }

    def set_mode(self, mode: str) -> Result:
        choices = _profile_choices()
        profile = profile_for_mode(mode, choices)
        messages = []
        ok = False
        if profile:
            result = write_sysfs(str(PROFILE), profile)
            ok = result.ok
            messages.append(result.message or profile)
        ttp_path = PLATFORM / "throttle_thermal_policy"
        if ttp_path.exists() and mode in TTP_FOR_MODE and (not choices or profile):
            result = write_sysfs(str(ttp_path), str(TTP_FOR_MODE[mode]))
            ok = ok or result.ok
            messages.append("ttp:" + (result.message or str(result.ok)))
        if not ok and not profile:
            return Result(False, "mode is not offered by this machine: " + mode)
        if not ok:
            acpi_mode = {"balanced": 0, "turbo": 1, "silent": 2}.get(mode)
            if acpi_mode is not None:
                acpi = acpi_set(ids.PERFORMANCE_MODE, acpi_mode)
                if not acpi.ok:
                    acpi = acpi_set(ids.VIVOBOOK_MODE, acpi_mode)
                return acpi
        return Result(ok, "; ".join(messages), {"mode": mode, "profile": profile})

    def set_charge_limit(self, percent: int) -> Result:
        percent = int(percent)
        battery = _battery()["primary"]
        if not battery or not battery.get("charge_limit_path"):
            return Result(False, "charge limit is not exposed by the kernel")
        result = write_sysfs(battery["charge_limit_path"], str(percent))
        if result.ok:
            return result
        return acpi_set(ids.BATTERY_LIMIT, percent)

    def set_keyboard_brightness(self, level: int) -> Result:
        kb = _keyboard()
        if not kb["devices"]:
            return Result(False, "no ASUS keyboard backlight")
        device = kb["devices"][0]
        maximum = device["max"] if device["max"] is not None else 3
        level = max(0, min(int(maximum), int(level)))
        return write_sysfs(device["path"], str(level))

    def set_screen_brightness(self, percent: int) -> Result:
        return display_hw.set_brightness_percent(percent)

    def set_refresh(self, output: str, mode: str) -> Result:
        return display_hw.set_mode(output, mode)

    def set_attribute(self, name: str, value: str) -> Result:
        path = ARMOURY / name / "current_value"
        if not path.exists():
            return Result(False, "attribute not present: " + name)
        return write_sysfs(str(path), value)

    def apply_fan_curve(self, fan_id: str, points: list[tuple[int, int]]) -> Result:
        points = clamp_points(points)
        for fan in _fans():
            if fan["id"] != fan_id and fan["key"] != fan_id:
                continue
            if not fan["curve_supported"]:
                return Result(False, "kernel does not expose a curve for " + fan["label"])
            enable = write_sysfs(fan["pwm_enable"], "1")
            if not enable.ok:
                return enable
            for index, (temp, duty) in enumerate(points, start=1):
                slot = fan["points"][index - 1] if index - 1 < len(fan["points"]) else None
                if slot is None:
                    break
                wrote = write_sysfs(slot["temp_path"], str(int(temp)))
                if not wrote.ok:
                    return wrote
                wrote = write_sysfs(slot["pwm_path"], str(duty_to_pwm(duty)))
                if not wrote.ok:
                    return wrote
            return Result(True, "curve applied", {"fan": fan_id})
        return Result(False, "fan not found: " + fan_id)

    def set_gpu_mode(self, mode: str) -> Result:
        files = _optional_platform_files()
        if mode == "optimized":
            return Result(True, "optimized is applied by automation when AC state changes")
        if mode == "eco" and files["dgpu_disable"]["present"]:
            return write_sysfs(files["dgpu_disable"]["path"], "1")
        if mode == "standard":
            if files["gpu_mux_mode"]["present"]:
                mux = write_sysfs(files["gpu_mux_mode"]["path"], "0")
                if not mux.ok:
                    return mux
            if files["dgpu_disable"]["present"]:
                return write_sysfs(files["dgpu_disable"]["path"], "0")
            return Result(True, "mux set") if files["gpu_mux_mode"]["present"] else Result(False, "GPU mode nodes are absent")
        if mode == "ultimate" and files["gpu_mux_mode"]["present"]:
            if files["dgpu_disable"]["present"]:
                write_sysfs(files["dgpu_disable"]["path"], "0")
            return write_sysfs(files["gpu_mux_mode"]["path"], "1")
        eco_id = ids.GPU_ECO_VIVO if family_of(dmi("product_name"), dmi("board_name")) == "vivobook" else ids.GPU_ECO_ROG
        mux_id = ids.GPU_MUX_VIVO if family_of(dmi("product_name"), dmi("board_name")) == "vivobook" else ids.GPU_MUX_ROG
        if mode == "eco":
            return acpi_set(eco_id, 1)
        if mode == "standard":
            return acpi_set(eco_id, 0)
        if mode == "ultimate":
            return acpi_set(mux_id, 1)
        return Result(False, "unsupported GPU mode")

    def acpi_read(self, device_id: int) -> Result:
        return acpi_get(device_id)

    def acpi_write(self, device_id: int, value: int) -> Result:
        return acpi_set(device_id, value)
