import tempfile
import unittest
from pathlib import Path

from ghelper.hw.curves import clamp_points, pack_curve, unpack_curve
from ghelper.hw.modes import available_modes, mode_for_profile, profile_for_mode
from ghelper.hw.whitelist import is_allowed, validate_value
from ghelper.peripherals.catalog import identify
from ghelper.session import requested_backend


class ModesTest(unittest.TestCase):
    def test_vivobook_choices(self):
        choices = ["balanced", "performance"]
        self.assertEqual(profile_for_mode("turbo", choices), "performance")
        self.assertIsNone(profile_for_mode("silent", choices))
        self.assertEqual(available_modes(choices), ["balanced", "turbo"])
        self.assertEqual(mode_for_profile("performance"), "turbo")

    def test_rog_quiet(self):
        choices = ["quiet", "balanced", "performance"]
        self.assertEqual(profile_for_mode("silent", choices), "quiet")
        self.assertEqual(available_modes(choices), ["silent", "balanced", "turbo"])


class WhitelistTest(unittest.TestCase):
    def test_rejects_escape(self):
        self.assertFalse(is_allowed("/etc/passwd"))
        self.assertFalse(is_allowed("/sys/firmware/acpi/platform_profile/../../../../etc/passwd"))
        self.assertFalse(is_allowed("relative"))

    def test_accepts_known_nodes(self):
        self.assertTrue(is_allowed("/sys/firmware/acpi/platform_profile"))
        self.assertTrue(is_allowed("/sys/class/power_supply/BAT0/charge_control_end_threshold"))
        self.assertTrue(is_allowed("/sys/class/leds/asus::kbd_backlight/brightness"))
        self.assertTrue(is_allowed("/sys/kernel/debug/asus-nb-wmi/dev_id"))
        self.assertFalse(is_allowed("/sys/kernel/debug/asus-nb-wmi/other"))


class CurveTest(unittest.TestCase):
    def test_pack_roundtrip(self):
        points = clamp_points([(30, 0), (40, 20), (50, 40), (60, 50), (70, 70), (80, 80), (90, 90), (100, 100)])
        blob = pack_curve(points)
        self.assertEqual(len(blob), 16)
        self.assertEqual(unpack_curve(blob)[0][0], 30)


class CatalogTest(unittest.TestCase):
    def test_tx_mouse(self):
        meta = identify(0x1A8D)
        self.assertEqual(meta["kind"], "mouse")
        self.assertIn("TX", meta["name"])


class BatteryTextTest(unittest.TestCase):
    def test_format(self):
        from ghelper.peripherals.battery import format_battery

        self.assertEqual(format_battery(None), "读取中")
        self.assertEqual(format_battery({"wired": True}), "有线")
        self.assertIn("80%", format_battery({"percent": 80, "charging": True}))
        self.assertEqual(format_battery({"percent": None, "message": "permission denied"}), "需要授权后才能读电量")


class HidFrameTest(unittest.TestCase):
    def test_linux_payload_matches_windows_layout(self):
        from ghelper.hidframe import is_command_response, to_windows_layout

        request = bytes([0x00, 0x12, 0x07])
        linux_reply = bytes([0x12, 0x07, 0x00, 0x00, 0x13])
        self.assertTrue(is_command_response(request, linux_reply))
        framed = to_windows_layout(request, linux_reply)
        self.assertEqual(framed[1:3], bytes([0x12, 0x07]))
        self.assertEqual(framed[5], 0x13)


class SessionTest(unittest.TestCase):
    def test_backend_preference(self):
        self.assertEqual(requested_backend([]), "wayland,x11")
        self.assertEqual(requested_backend(["--backend", "x11"]), "x11")
        self.assertEqual(requested_backend(["--backend=wayland"]), "wayland")


class ConfigTest(unittest.TestCase):
    def test_roundtrip(self):
        from ghelper.config import Config

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = Config.load(path)
            cfg.set("charge_limit", 70)
            again = Config.load(path)
            self.assertEqual(again.get("charge_limit"), 70)


if __name__ == "__main__":
    unittest.main()
