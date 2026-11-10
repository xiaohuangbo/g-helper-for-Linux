from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from ghelper.paths import config_dir

SCHEMA = 1

DEFAULT: dict[str, Any] = {
    "schema": SCHEMA,
    "language": "auto",
    "start_minimized": False,
    "autostart": False,
    "overlay": {"enabled": False, "x": 32, "y": 32, "mode": "default"},
    "current_mode": "balanced",
    "charge_limit": 80,
    "kbd_level": None,
    "automation": {
        "enabled": True,
        "ac_mode": "turbo",
        "dc_mode": "silent",
        "ac_refresh": "max",
        "dc_refresh": "60",
        "gpu_optimized": False,
        "kbd_timeout_ac": 0,
        "kbd_timeout_dc": 60,
    },
    "custom_modes": [],
    "fan_curves": {},
    "limits": {},
    "hotkeys_enabled": True,
    "backend": "auto",
}


class Config:
    def __init__(self, data: dict[str, Any], path: Path):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or (config_dir() / "config.json")
        data = deepcopy(DEFAULT)
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = _merge(data, loaded)
            except (OSError, json.JSONDecodeError):
                pass
        data["schema"] = SCHEMA
        return cls(data, path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, indent=2, ensure_ascii=False) + "\n"
        fd, tmp = tempfile.mkstemp(prefix=".config-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()


def _merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out
