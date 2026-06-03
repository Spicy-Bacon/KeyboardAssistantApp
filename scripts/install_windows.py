from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIST_PYZ = ROOT / "dist" / "keyboard-assistant.pyz"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keyboard_assistant.platform.windows_install import install_zipapp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Keyboard Assistant for the current Windows user.")
    parser.add_argument("--source", type=Path, default=DIST_PYZ, help="Built keyboard-assistant.pyz path.")
    parser.add_argument("--install-dir", type=Path, default=None, help="Override install directory.")
    parser.add_argument("--start-menu-dir", type=Path, default=None, help="Override Start Menu launcher directory.")
    parser.add_argument("--enable-startup", action="store_true", help="Launch Keyboard Assistant at Windows login.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.source.exists():
        print(f"Missing {args.source}. Build it first with: python scripts\\build_zipapp.py", file=sys.stderr)
        return 1

    result = install_zipapp(
        source_pyz=args.source,
        install_root=args.install_dir,
        start_menu_dir=args.start_menu_dir,
        enable_startup=args.enable_startup,
    )
    print(f"Installed: {result.installed_pyz}")
    print(f"Launcher: {result.desktop_launcher}")
    print(f"Settings: {result.settings_launcher}")
    print(f"Startup: {'enabled' if result.startup_enabled else 'unchanged'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
