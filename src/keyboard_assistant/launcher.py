from __future__ import annotations

import sys

from keyboard_assistant import __version__
from keyboard_assistant import cli, desktop, settings_app


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--version"]:
        print(f"keyboard-assistant {__version__}")
        return 0
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: keyboard-assistant.pyz {cli,desktop,settings} ...")
        print()
        print("commands:")
        print("  cli       Local controls and text suggestion demo")
        print("  desktop   Live desktop prototype")
        print("  settings  Native settings window")
        return 0 if argv else 2

    command = argv.pop(0)
    if command == "cli":
        return cli.main(argv)
    if command == "desktop":
        return desktop.main(argv)
    if command == "settings":
        return settings_app.main(argv)

    print(f"Unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
