"""Application controller.

The window, tray and CLI all call this object. It owns config, hardware and
peripheral sessions so those pieces can change independently.
"""

from __future__ import annotations

from ghelper import __version__
from ghelper.config import Config
from ghelper.hw.display import pick_refresh
from ghelper.hw.platform import Hardware
from ghelper.i18n import set_language
from ghelper.peripherals.battery import BatteryMonitor
from ghelper.peripherals.manager import PeripheralManager
from ghelper.result import Result


class Controller:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.load()
        set_language(self.config.get("language"))
        self.hw = Hardware()
        self.peripherals = PeripheralManager()
        self.batteries = BatteryMonitor(self.peripherals)
        self._last_ac: bool | None = None

    def snapshot(self) -> dict:
        snap = self.hw.snapshot()
        snap["peripherals"] = self.peripherals.discover()
        snap["peripheral_batteries"] = self.batteries.snapshot()
        snap["config"] = self.config.data
        snap["version"] = __version__
        return snap

    def set_mode(self, mode: str) -> Result:
        base = mode
        custom = self._custom(mode)
        if custom:
            base = custom.get("base") or "balanced"
        result = self.hw.set_mode(base)
        if not result.ok:
            return result
        self.config.data["current_mode"] = mode
        self._apply_saved_limits(mode, custom)
        self._apply_saved_curve(mode, custom)
        self.config.save()
        return result

    def cycle_mode(self, back: bool = False) -> Result:
        snap = self.hw.snapshot()
        offered = [item["id"] for item in snap["performance"]["modes"] if item["available"]]
        offered += [item["id"] for item in self.config.data.get("custom_modes", [])]
        if not offered:
            return Result(False, "no performance modes")
        current = self.config.get("current_mode") or snap["performance"]["current"]
        try:
            index = offered.index(current)
        except ValueError:
            index = 0
        index = (index - 1) if back else (index + 1)
        index %= len(offered)
        return self.set_mode(offered[index])

    def set_charge_limit(self, percent: int) -> Result:
        result = self.hw.set_charge_limit(percent)
        if result.ok:
            self.config.set("charge_limit", int(percent))
        return result

    def set_keyboard_brightness(self, level: int) -> Result:
        result = self.hw.set_keyboard_brightness(level)
        if result.ok:
            self.config.set("kbd_level", int(level))
        return result

    def bump_keyboard(self, delta: int) -> Result:
        snap = self.hw.snapshot()
        devices = snap["keyboard"]["devices"]
        if not devices:
            return Result(False, "no keyboard backlight")
        current = devices[0]["brightness"] or 0
        return self.set_keyboard_brightness(current + delta)

    def set_brightness(self, percent: int) -> Result:
        return self.hw.set_screen_brightness(percent)

    def set_refresh(self, output: str, mode: str) -> Result:
        return self.hw.set_refresh(output, mode)

    def set_attribute(self, name: str, value: str) -> Result:
        result = self.hw.set_attribute(name, value)
        if result.ok:
            limits = dict(self.config.data.get("limits") or {})
            limits[name] = value
            self.config.data["limits"] = limits
            self.config.save()
        return result

    def set_gpu_mode(self, mode: str) -> Result:
        if mode == "optimized":
            auto = dict(self.config.data.get("automation") or {})
            auto["gpu_optimized"] = True
            self.config.data["automation"] = auto
            self.config.save()
        return self.hw.set_gpu_mode(mode)

    def apply_fan_curve(self, fan_id: str, points: list[tuple[int, int]], mode: str | None = None) -> Result:
        result = self.hw.apply_fan_curve(fan_id, points)
        if result.ok:
            mode = mode or self.config.get("current_mode") or "balanced"
            curves = dict(self.config.data.get("fan_curves") or {})
            bucket = dict(curves.get(mode) or {})
            bucket[fan_id] = points
            curves[mode] = bucket
            self.config.data["fan_curves"] = curves
            self.config.save()
        return result

    def add_custom_mode(self, name: str, base: str) -> str:
        modes = list(self.config.data.get("custom_modes") or [])
        ident = "custom-%d" % (len(modes) + 1)
        modes.append({"id": ident, "name": name or ident, "base": base, "limits": {}, "curves": {}})
        self.config.data["custom_modes"] = modes
        self.config.save()
        return ident

    def remove_custom_mode(self, ident: str) -> None:
        modes = [item for item in self.config.data.get("custom_modes") or [] if item.get("id") != ident]
        self.config.data["custom_modes"] = modes
        self.config.save()

    def automation_tick(self) -> Result | None:
        auto = self.config.data.get("automation") or {}
        if not auto.get("enabled"):
            return None
        snap = self.hw.snapshot()
        ac = snap["battery"].get("ac_online")
        if ac is None or ac == self._last_ac:
            return None
        self._last_ac = ac
        mode = auto.get("ac_mode") if ac else auto.get("dc_mode")
        result = self.set_mode(mode) if mode else Result(True, "no mode")
        want = auto.get("ac_refresh") if ac else auto.get("dc_refresh")
        outputs = snap["display"]["outputs"]
        internal = next((item for item in outputs if "eDP" in item["name"] or item["name"].startswith("eDP")), None)
        if internal and want:
            picked = pick_refresh(internal.get("modes") or [], str(want))
            if picked:
                self.hw.set_refresh(internal["name"], picked)
        if auto.get("gpu_optimized"):
            self.hw.set_gpu_mode("standard" if ac else "eco")
        return result

    def _custom(self, mode: str) -> dict | None:
        for item in self.config.data.get("custom_modes") or []:
            if item.get("id") == mode:
                return item
        return None

    def _apply_saved_limits(self, mode: str, custom: dict | None) -> None:
        limits = {}
        if custom:
            limits.update(custom.get("limits") or {})
        else:
            limits.update(self.config.data.get("limits") or {})
        for name, value in limits.items():
            self.hw.set_attribute(str(name), str(value))

    def _apply_saved_curve(self, mode: str, custom: dict | None) -> None:
        curves = (custom or {}).get("curves") or (self.config.data.get("fan_curves") or {}).get(mode) or {}
        for fan_id, points in curves.items():
            try:
                cleaned = [(int(a), int(b)) for a, b in points]
            except (TypeError, ValueError):
                continue
            self.hw.apply_fan_curve(str(fan_id), cleaned)
