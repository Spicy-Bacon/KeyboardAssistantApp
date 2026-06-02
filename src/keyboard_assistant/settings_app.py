from __future__ import annotations

import argparse
from pathlib import Path

from keyboard_assistant.storage.database import Database
from keyboard_assistant.ui.settings_window import SettingsWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Keyboard Assistant settings window.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".keyboard_assistant.sqlite3"),
        help="SQLite database path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Database(args.db)
    database.initialize()
    SettingsWindow(database).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

