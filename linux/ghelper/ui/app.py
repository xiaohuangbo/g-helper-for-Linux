from __future__ import annotations

import signal
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from ghelper import __app_id__, __version__
from ghelper.controller import Controller
from ghelper.hotkeys import HotkeyListener
from ghelper.i18n import set_language, t
from ghelper.logutil import get_logger
from ghelper.overlay import Overlay
from ghelper.paths import icon_path, share_dir
from ghelper.priv import reap_zombies, shutdown_helper
from ghelper.session import actual_backend
from ghelper.tray import Tray
from ghelper.ui.window import MainWindow

log = get_logger("ghelper.ui")


def _battery_summary(snap: dict) -> str:
    from ghelper.peripherals.battery import format_battery

    parts = []
    cache = snap.get("peripheral_batteries") or {}
    for device in snap.get("peripherals") or []:
        info = cache.get(device.get("pid")) or cache.get(int(device.get("pid") or 0))
        if not info or info.get("percent") is None:
            continue
        parts.append("%s %s" % (device.get("name") or "HID", format_battery(info)))
    return "  ".join(parts)


class GHelperApp(Adw.Application):
    def __init__(self, launch_info: dict, minimized: bool, self_test: bool):
        super().__init__(application_id=__app_id__, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.launch_info = launch_info
        self.minimized = minimized
        self.self_test = self_test
        self.controller = Controller()
        set_language(self.controller.config.get("language"))
        self.window: MainWindow | None = None
        self.tray: Tray | None = None
        self.overlay = None
        self.hotkeys: HotkeyListener | None = None
        self.backend = "unknown"
        self._timer = 0
        self._quitting = False
        self._stopped = False

    def do_activate(self):
        if self.window is None:
            self._install_css()
            self.backend = actual_backend()
            self.launch_info["actual"] = self.backend
            log.info("display backend requested=%s actual=%s", self.launch_info.get("requested"), self.backend)
            self.window = MainWindow(self, self.controller)
            self.window.connect("close-request", self._on_close)
            self.tray = Tray(self)
            if not self.tray.start():
                log.info("tray not shown: %s", self.tray.error)
                self.minimized = False
            self.overlay = Overlay(self)
            if self.controller.config.data.get("overlay", {}).get("enabled"):
                self.overlay.present()
            if self.controller.config.get("hotkeys_enabled", True):
                self.hotkeys = HotkeyListener(self._on_hotkey)
                self.hotkeys.start()
            self.controller.batteries.start()
            self._timer = GLib.timeout_add_seconds(3, self._tick)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._signal_quit)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._signal_quit)
        if self.self_test:
            self.window.present()
            print("GHELPER_SELF_TEST backend=%s" % self.backend)
            GLib.timeout_add(400, self._finish_self_test)
            return
        if self.minimized and self.tray and not self.tray.error:
            return
        self.window.present()

    def _finish_self_test(self):
        self.quit()
        return False

    def _install_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"@define-color accent_bg_color #9f1239;"
            b"@define-color accent_fg_color white;"
            b".gh-hero { font-weight: 700; font-size: 1.3em; }"
            b".gh-muted { opacity: 0.75; }"
            b".gh-card { padding: 12px; }"
        )
        display = Gtk.Widget.get_display if False else None
        from gi.repository import Gdk
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        theme = Gtk.IconTheme.get_for_display(display) if display else None
        if theme is not None:
            theme.add_search_path(str(share_dir() / "icons"))
            if icon_path().is_file():
                pass

    def toggle_window(self):
        if self.window is None:
            return
        # Presenting inside a D-Bus method handler can land in the middle of
        # GDK frame preparation and trip gdk_frame_timings_throttling_hint.
        GLib.idle_add(self._toggle_window_idle)

    def _toggle_window_idle(self):
        if self.window is None:
            return False
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.present()
        return False

    def show_page(self, page_id: str):
        GLib.idle_add(self._show_page_idle, page_id)

    def _show_page_idle(self, page_id: str):
        if self.window is None:
            return False
        self.window.present()
        self.window.switch_page(page_id)
        return False

    def stop_services_and_quit(self):
        self.quit()

    def cycle_from_tray(self):
        result = self.controller.cycle_mode()
        self._toast(result.message or t("已切换模式", "mode changed"))
        if self.window:
            self.window.refresh()

    def set_mode(self, mode: str):
        result = self.controller.set_mode(mode)
        self._toast(result.message if not result.ok else t("模式已应用", "mode applied") + ": " + mode)
        if self.window:
            self.window.refresh()

    def adjust_backlight(self, delta: int):
        result = self.controller.bump_keyboard(delta)
        if self.window and not result.ok:
            self.window.toast(result.message)

    def _on_hotkey(self, code: int, name: str):
        def handle():
            if self.window:
                self.window.note_hotkey(code, name)
            if name in {"PROG1", "F14", "F15"}:
                self.cycle_from_tray()
            elif name == "KBDILLUMDOWN":
                self.adjust_backlight(-1)
            elif name == "KBDILLUMUP":
                self.adjust_backlight(1)
            elif name == "BRIGHTNESSDOWN":
                self.controller.set_brightness(max(5, (self.window.brightness_percent if self.window else 40) - 5))
            elif name == "BRIGHTNESSUP":
                self.controller.set_brightness(min(100, (self.window.brightness_percent if self.window else 40) + 5))
            return False
        GLib.idle_add(handle)

    def _tick(self):
        try:
            self.controller.automation_tick()
            snap = self.controller.snapshot()
            if self.window and self.window.get_visible():
                self.window.refresh(snap)
            if self.overlay:
                self.overlay.refresh(snap)
            if self.tray:
                temp = snap["temps"].get("package_c")
                mode = snap["performance"].get("current") or "-"
                bats = _battery_summary(snap)
                tip = "G-Helper %s  %sC" % (mode, "-" if temp is None else temp)
                if bats:
                    tip += "  " + bats
                self.tray.set_tooltip(tip)
        except Exception as exc:
            log.warning("tick: %s", exc)
        return True

    def _on_close(self, window):
        if self._quitting or self._stopped:
            return False
        if self.tray and not self.tray.error:
            window.hide()
            return True
        return False

    def _toast(self, text: str):
        if self.window:
            self.window.toast(text)

    def _signal_quit(self):
        self.quit()
        return False

    def quit(self):
        self._quitting = True
        Adw.Application.quit(self)

    def shutdown_all(self):
        """Stop every thread, window and helper this process started."""
        if self._stopped:
            return
        self._stopped = True
        self._quitting = True
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        try:
            self.controller.batteries.stop()
        except Exception as exc:
            log.warning("battery stop: %s", exc)
        if self.hotkeys:
            self.hotkeys.stop()
            self.hotkeys = None
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        if self.tray:
            self.tray.stop()
            self.tray = None
        try:
            result = shutdown_helper()
            log.info("helper shutdown: %s", result.message)
        except Exception as exc:
            log.warning("helper shutdown: %s", exc)
        reap_zombies()

    def do_shutdown(self):
        self.shutdown_all()
        Adw.Application.do_shutdown(self)


def run(argv: list[str], info: dict) -> int:
    minimized = "--minimized" in argv or "--hidden" in argv
    self_test = "--self-test" in argv
    app = GHelperApp(info, minimized, self_test)
    return app.run([sys.argv[0]])
