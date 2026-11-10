"""Path allow-list for the privileged helper.

The helper runs as root. It must never become a generic file writer.
"""

from __future__ import annotations

from pathlib import Path

EXACT = {
    "/sys/firmware/acpi/platform_profile",
}

PLATFORM_NAMES = {
    "throttle_thermal_policy",
    "gpu_mux_mode",
    "dgpu_disable",
    "egpu_enable",
    "panel_od",
    "mini_led_mode",
    "fan_boost_mode",
}

DEBUG_NAMES = {"dev_id", "ctrl_param", "devs", "dsts", "method_id"}
LED_NAMES = {"brightness", "multi_intensity"}
BATTERY_NAMES = {"charge_control_end_threshold", "charge_control_start_threshold"}


def resolve(path: str) -> Path:
    raw = Path(path)
    if not raw.is_absolute():
        raise ValueError("path must be absolute")
    if ".." in raw.parts:
        raise ValueError("path traversal rejected")
    return raw


def is_allowed(path: str, write: bool = False) -> bool:
    del write
    try:
        resolved = resolve(path)
    except ValueError:
        return False
    text = str(resolved)
    if text in EXACT:
        return True
    if text.startswith("/sys/devices/platform/asus-nb-wmi/"):
        name = resolved.name
        if name in PLATFORM_NAMES:
            return True
        if name.startswith("pwm") and ("auto_point" in name or name.endswith("_enable")):
            return True
        if name.startswith("fan") and "auto_point" in name:
            return True
        return False
    if text.startswith("/sys/class/leds/asus::") and resolved.name in LED_NAMES:
        return True
    if text.startswith("/sys/class/power_supply/BAT") and resolved.name in BATTERY_NAMES:
        return True
    if text.startswith("/sys/class/backlight/") and resolved.name == "brightness":
        return True
    marker = "/firmware-attributes/asus-armoury/attributes/"
    if marker in text and resolved.name == "current_value":
        return True
    if text.startswith("/sys/kernel/debug/asus-nb-wmi/") or text.startswith("/sys/kernel/debug/asus-wmi/"):
        return resolved.name in DEBUG_NAMES
    return False


def validate_value(path: str, value: str) -> str:
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("value contains a control character")
    value = value.strip()
    if len(value) > 64:
        raise ValueError("value too long")
    resolved = str(resolve(path))
    if resolved.endswith("platform_profile"):
        choices = Path("/sys/firmware/acpi/platform_profile_choices").read_text(encoding="utf-8").split()
        if value not in choices:
            raise ValueError("profile not in choices")
        return value
    if resolved.endswith("charge_control_end_threshold") or resolved.endswith("charge_control_start_threshold"):
        number = int(value, 10)
        if not 20 <= number <= 100:
            raise ValueError("charge limit must be 20-100")
        return str(number)
    if (
        resolved.endswith("/brightness")
        or resolved.endswith("throttle_thermal_policy")
        or "auto_point" in resolved
        or resolved.endswith("_enable")
    ):
        number = int(value, 10)
        if number < 0 or number > 100000:
            raise ValueError("numeric value out of range")
        return str(number)
    if resolved.endswith("/current_value"):
        if not value or len(value) > 32:
            raise ValueError("attribute value rejected")
        return value
    if "/sys/kernel/debug/asus-" in resolved:
        int(value, 0)
        return value
    if resolved.split("/")[-1] in PLATFORM_NAMES:
        number = int(value, 10)
        if number < 0 or number > 16:
            raise ValueError("platform value out of range")
        return str(number)
    raise ValueError("no validator for path")
