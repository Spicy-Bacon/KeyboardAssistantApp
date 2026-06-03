from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keyboard_assistant.platform.windows_install import uninstall_zipapp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Uninstall Keyboard Assistant for the current Windows user.")
    parser.add_argument("--install-dir", type=Path, default=None, help="Override install directory.")
    parser.add_argument("--start-menu-dir", type=Path, default=None, help="Override Start Menu launcher directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    uninstall_zipapp(install_root=args.install_dir, start_menu_dir=args.start_menu_dir)
    print("Uninstalled Keyboard Assistant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
