from __future__ import annotations

import sys

CLI_COMMANDS = {
    "status", "set-profile", "set-charge", "set-kbd", "devices", "helper",
    "acpi-get", "help", "--help", "-h", "--cli",
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in CLI_COMMANDS:
        from ghelper.cli import main as cli_main
        return cli_main(argv)
    from ghelper.session import prepare_display
    info = prepare_display(argv)
    from ghelper.ui.app import run
    return run(argv, info)
