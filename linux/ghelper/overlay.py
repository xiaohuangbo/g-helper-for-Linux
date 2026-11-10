"""Lightweight metrics overlay.

On Wayland this uses gtk4-layer-shell when the typelib is installed, so the
panel stays above other windows without stealing focus. On X11, or if layer
shell is missing, it falls back to a keep-above window.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ghelper.i18n import t


class Overlay:
    def __init__(self, app):
        self.app = app
        self.window: Gtk.Window | None = None
        self.label: Gtk.Label | None = None
        self.backend = "none"

    def present(self) -> None:
        if self.window is None:
            self._build()
        assert self.window is not None
        self.window.present()
        self.refresh()

    def hide(self) -> None:
        if self.window:
            self.window.hide()

    def close(self) -> None:
        window = self.window
        self.window = None
        self.label = None
        if window is not None:
            window.destroy()

    def toggle(self) -> bool:
        if self.window and self.window.get_visible():
            self.hide()
            return False
        self.present()
        return True

    def refresh(self, snap: dict | None = None) -> None:
        if not self.label or not self.window or not self.window.get_visible():
            return
        if snap is None:
            snap = self.app.controller.snapshot()
        temp = snap["temps"].get("package_c")
        fans = ", ".join("%s %s" % (fan["label"], fan["rpm"] if fan["rpm"] is not None else "-") for fan in snap["fans"][:3])
        bat = snap["battery"].get("primary") or {}
        mode = snap["performance"].get("current") or "-"
        text = "G-Helper  %s\nCPU %s C\n%s\n%s %s%%  %s" % (
            mode,
            "-" if temp is None else temp,
            fans or t("无风扇读数", "no fan"),
            bat.get("status") or "",
            bat.get("capacity") if bat.get("capacity") is not None else "-",
            self.backend,
        )
        self.label.set_label(text)

    def _build(self) -> None:
        win = Gtk.Window(title="G-Helper Overlay")
        win.set_decorated(False)
        win.set_default_size(220, 110)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=8, margin_bottom=8, margin_start=10, margin_end=10)
        self.label = Gtk.Label(xalign=0)
        self.label.set_wrap(True)
        box.append(self.label)
        win.set_child(box)
        if self._layer(win):
            self.backend = "wayland-layer"
        else:
            win.set_keep_above(True)
            self.backend = "window"
        self.window = win

    def _layer(self, win: Gtk.Window) -> bool:
        try:
            gi.require_version("GtkLayerShell", "0.1")
            from gi.repository import GtkLayerShell
        except Exception:
            return False
        try:
            GtkLayerShell.init_for_window(win)
            GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
            GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_margin(win, GtkLayerShell.Edge.TOP, 28)
            GtkLayerShell.set_margin(win, GtkLayerShell.Edge.LEFT, 28)
            return True
        except Exception:
            return False
