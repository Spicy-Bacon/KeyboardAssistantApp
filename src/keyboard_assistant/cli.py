from __future__ import annotations

import argparse
from pathlib import Path

from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.storage.database import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyboard Assistant local correction demo.")
    parser.add_argument("text", nargs="*", help="Text to analyze.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run an interactive prompt.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".keyboard_assistant.sqlite3"),
        help="SQLite database path.",
    )
    return parser


def print_suggestions(text: str, assistant: KeyboardAssistant) -> None:
    suggestions = assistant.suggest(text)
    if not suggestions:
        print("No suggestion.")
        return

    for index, suggestion in enumerate(suggestions, start=1):
        auto = " auto" if suggestion.auto_apply else ""
        print(
            f"{index}. {suggestion.replacement} "
            f"({suggestion.kind}, confidence={suggestion.confidence:.2f}{auto})"
        )


def run_interactive(assistant: KeyboardAssistant) -> None:
    print("Keyboard Assistant demo. Enter blank text to exit.")
    while True:
        try:
            text = input("> ").rstrip("\n")
        except EOFError:
            break
        if not text:
            break
        print_suggestions(text, assistant)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    database = Database(args.db)
    database.initialize()
    assistant = KeyboardAssistant(database=database)

    if args.interactive:
        run_interactive(assistant)
        return 0

    text = " ".join(args.text)
    if not text:
        parser.print_help()
        return 2

    print_suggestions(text, assistant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

