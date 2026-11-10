"""GUI smoke test.

Builds the real window with a stub application, waits for the peripheral
battery poll, then checks that the labels are populated. Run with a live
Wayland or X11 session.
"""

from __future__ import annotations

import os
import sys
import time

CD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CD not in sys.path:
    sys.path.insert(0, CD)

os.environ.setdefault("GDK_BACKEND", "wayland,x11")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ghelper.controller import Controller
from ghelper.pages import PAGES
from ghelper.session import actual_backend
from ghelper.ui.window import MainWindow


class StubApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.ghelper.Smoke")
        self.launch_info = {"requested": os.environ.get("GDK_BACKEND"), "actual": "-", "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "")}
        self.backend = "unknown"
        self.hotkeys = None
        self.overlay = None
        self.tray = None
        self.controller = Controller()


def main() -> int:
    app = StubApp()
    failures = []

    def activate(_app):
        app.backend = actual_backend()
        app.launch_info["actual"] = app.backend
        window = MainWindow(app, app.controller)
        window.present()
        app.controller.batteries.start()
        app.controller.batteries.refresh_now()

        def check():
            window.refresh()
            peri = window._labels["peri"].get_label()
            overview = window._labels["peri-bat"].get_label()
            battery = app.controller.batteries.snapshot()
            print("BACKEND", app.backend)
            print("PERIPHERALS", peri.replace("\n", " | "))
            print("OVERVIEW", overview)
            print("CACHE", battery)
            if "TX" not in peri:
                failures.append("mouse not listed")
            if "19%" not in peri and "需要授权" not in peri and "助手" not in peri:
                failures.append("battery percent missing: " + peri)
            if "19%" not in overview and "需要授权" not in overview and "助手" not in overview:
                failures.append("overview battery missing: " + overview)
            lockdown = (window._labels.get("lockdown").get_label() if window._labels.get("lockdown") else "-")
            print("LOCKDOWN", lockdown)
            buttons = getattr(window, "_acpi_buttons", [])
            if buttons and any(button.get_sensitive() for button in buttons) and lockdown not in {"未启用", "not enabled"}:
                failures.append("ACPI controls should be disabled under lockdown")
            if lockdown in {"未启用", "not enabled"} and buttons and not all(button.get_sensitive() for button in buttons):
                failures.append("ACPI controls should be enabled without lockdown")
            for page_id, _zh, _en in PAGES:
                if not window.switch_page(page_id):
                    failures.append("switch_page failed: " + page_id)
                elif window.stack.get_visible_child_name() != page_id:
                    failures.append("page not visible: " + page_id)
            print("PAGES_OK", len(PAGES))
            window.destroy()
            app.quit()
            return False

        GLib.timeout_add(2500, check)

    app.connect("activate", activate)
    code = app.run([sys.argv[0]])
    if failures:
        print("FAILED", failures)
        return 1
    print("GUI_SMOKE_OK")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
