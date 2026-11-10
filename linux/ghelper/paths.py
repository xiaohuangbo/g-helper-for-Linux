from __future__ import annotations

import os
from pathlib import Path

APP = "ghelper"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / APP


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    return Path(base) / APP


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(base) / APP


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/ghelper-{os.getuid()}")
    return Path(base) / APP


def helper_socket() -> Path:
    return Path(os.environ.get("GHELPER_HELPER_SOCK", "/run/ghelper/helper.sock"))


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def share_dir() -> Path:
    override = os.environ.get("GHELPER_SHARE")
    if override:
        return Path(override)
    source = package_root() / "share"
    installed = Path("/usr/share/ghelper")
    if (source / "icons").is_dir():
        return source
    if installed.is_dir():
        return installed
    return source


def icon_path() -> Path:
    return share_dir() / "icons" / "hicolor" / "scalable" / "apps" / "ghelper.svg"
