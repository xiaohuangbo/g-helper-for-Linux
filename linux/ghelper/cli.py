"""Headless commands. These never import Gtk."""

from __future__ import annotations

import json

from ghelper.controller import Controller
from ghelper.priv import helper_running, spawn_helper


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--cli":
        argv = argv[1:]
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("ghelper status | set-profile <mode> | set-charge <20-100> | set-kbd <level> | devices | helper | acpi-get <hex>")
        return 0
    cmd = argv[0]
    if cmd == "helper":
        if helper_running():
            print("helper: running")
            return 0
        if "--start" in argv:
            result = spawn_helper()
            print(result.message)
            return 0 if result.ok else 1
        print("helper: stopped")
        return 1
    ctl = Controller()
    if cmd == "status":
        print(json.dumps(ctl.snapshot(), ensure_ascii=False, indent=2, default=str))
        return 0
    if cmd == "set-profile" and len(argv) >= 2:
        result = ctl.set_mode(argv[1])
        print(result.message or ("ok" if result.ok else "failed"))
        return 0 if result.ok else 1
    if cmd == "set-charge" and len(argv) >= 2:
        result = ctl.set_charge_limit(int(argv[1]))
        print(result.message or ("ok" if result.ok else "failed"))
        return 0 if result.ok else 1
    if cmd == "set-kbd" and len(argv) >= 2:
        result = ctl.set_keyboard_brightness(int(argv[1]))
        print(result.message or ("ok" if result.ok else "failed"))
        return 0 if result.ok else 1
    if cmd == "devices":
        print(json.dumps(ctl.peripherals.discover(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "acpi-get" and len(argv) >= 2:
        result = ctl.hw.acpi_read(int(argv[1], 0))
        print(json.dumps(result.to_dict(), ensure_ascii=False, default=str))
        return 0 if result.ok else 1
    print("unknown command: " + cmd)
    return 2
