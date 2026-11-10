from __future__ import annotations

from pathlib import Path


def read_text(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def read_int(path: str | Path) -> int | None:
    text = read_text(path)
    if text is None or text == "":
        return None
    try:
        return int(text, 0) if text.lower().startswith("0x") else int(float(text))
    except ValueError:
        return None


def write_text(path: str | Path, value: str) -> None:
    text = value if value.endswith("\n") else value + "\n"
    Path(path).write_text(text, encoding="utf-8")


def dmi(name: str) -> str:
    return read_text("/sys/class/dmi/id/" + name) or ""
