"""Map G-Helper performance modes onto Linux platform profiles.

Kernel asus-nb-wmi throttle_thermal_policy:
  0 balanced, 1 overboost/turbo, 2 silent.
platform_profile names vary: quiet, low-power, cool, balanced, performance.
"""

from __future__ import annotations

BUILTIN_MODES = ("silent", "balanced", "turbo")

PROFILE_CANDIDATES = {
    "silent": ("quiet", "low-power", "cool"),
    "balanced": ("balanced",),
    "turbo": ("performance",),
}

TTP_FOR_MODE = {"silent": 2, "balanced": 0, "turbo": 1}

MODE_LABELS = {
    "silent": ("静音", "Silent"),
    "balanced": ("平衡", "Balanced"),
    "turbo": ("增强", "Turbo"),
}


def profile_for_mode(mode: str, choices: list[str]) -> str | None:
    wanted = PROFILE_CANDIDATES.get(mode, ())
    have = {item.lower(): item for item in choices}
    for name in wanted:
        if name in have:
            return have[name]
    return None


def mode_for_profile(profile: str | None) -> str | None:
    if not profile:
        return None
    key = profile.lower()
    for mode, names in PROFILE_CANDIDATES.items():
        if key in names:
            return mode
    return None


def mode_for_ttp(value: int | None) -> str | None:
    if value is None:
        return None
    for mode, code in TTP_FOR_MODE.items():
        if code == value:
            return mode
    return None


def available_modes(choices: list[str]) -> list[str]:
    return [mode for mode in BUILTIN_MODES if profile_for_mode(mode, choices)]
