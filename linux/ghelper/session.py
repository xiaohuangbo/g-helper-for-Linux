"""Display session selection.

Wayland is preferred. X11 remains an explicit fallback. GDK_BACKEND must be
set before Gtk or Gdk is imported. prepare_display() is the only place that
does that.
"""

from __future__ import annotations

import os
from typing import Any


def requested_backend(argv: list[str] | None = None) -> str:
    forced = os.environ.get("GHELPER_GDK_BACKEND", "").strip()
    argv = argv or []
    for index, arg in enumerate(argv):
        if arg == "--backend" and index + 1 < len(argv):
            forced = argv[index + 1]
        elif arg.startswith("--backend="):
            forced = arg.split("=", 1)[1]
    forced = forced.lower()
    if forced in {"wayland", "x11"}:
        return forced
    return "wayland,x11"


def prepare_display(argv: list[str] | None = None) -> dict[str, Any]:
    choice = requested_backend(argv)
    os.environ["GDK_BACKEND"] = choice
    os.environ.setdefault("GTK_CSD", "1")
    return {
        "requested": choice,
        "wayland_display": os.environ.get("WAYLAND_DISPLAY") or "",
        "x11_display": os.environ.get("DISPLAY") or "",
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP") or "",
        "session_type": os.environ.get("XDG_SESSION_TYPE") or "",
    }


def actual_backend() -> str:
    """Call only after Gtk has opened a display."""
    try:
        import gi

        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        if display is None:
            return "none"
        name = display.get_name() or ""
        if name.startswith("wayland"):
            return "wayland"
        # X11 displays are reported as :0 / :1, not the string x11.
        if "x11" in name or name.startswith(":") or name.startswith("X"):
            return "x11"
        return name or "unknown"
    except Exception as exc:
        return "error:" + str(exc)
