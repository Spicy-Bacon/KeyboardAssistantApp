from __future__ import annotations

import argparse
from pathlib import Path
import sys

from keyboard_assistant import __version__
from keyboard_assistant.ai.local_ai import LocalAIService
from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.diagnostics.logger import DiagnosticsLogger, default_log_path
from keyboard_assistant.platform.startup import WindowsStartupManager, default_startup_command
from keyboard_assistant.storage.database import Database
from keyboard_assistant.storage.database import VALID_ASSISTANT_STATUSES, VALID_CORRECTION_STRENGTHS
from keyboard_assistant.storage.database import VALID_SUGGESTION_SIZES, VALID_THEMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyboard Assistant local controls.")
    parser.add_argument("--version", action="version", version=f"keyboard-assistant {__version__}")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".keyboard_assistant.sqlite3"),
        help="SQLite database path.",
    )
    subparsers = parser.add_subparsers(dest="command")

    suggest = subparsers.add_parser("suggest", help="Analyze text and print suggestions.")
    suggest.add_argument("text", nargs="*", help="Text to analyze.")
    suggest.add_argument("--interactive", "-i", action="store_true", help="Run an interactive prompt.")

    settings = subparsers.add_parser("settings", help="View or change global assistant settings.")
    settings_sub = settings.add_subparsers(dest="settings_command")
    settings_sub.add_parser("show", help="Show current settings.")
    set_setting = settings_sub.add_parser("set", help="Set a global setting.")
    set_setting.add_argument("key", choices=["assistant", "strength", "learning"])
    set_setting.add_argument("value")

    apps = subparsers.add_parser("apps", help="Manage app-specific behavior.")
    apps_sub = apps.add_subparsers(dest="apps_command")
    apps_sub.add_parser("list", help="List app profiles.")
    set_app = apps_sub.add_parser("set", help="Create or update an app profile.")
    set_app.add_argument("identifier", help="Executable or app identifier, for example code.exe.")
    set_app.add_argument("--name", default=None, help="Display name.")
    set_app.add_argument("--status", choices=sorted(VALID_ASSISTANT_STATUSES), default=None)
    set_app.add_argument("--strength", choices=sorted(VALID_CORRECTION_STRENGTHS), default=None)
    set_app.add_argument("--learning", choices=["on", "off"], default=None)

    dictionary = subparsers.add_parser("dictionary", help="Manage personal dictionary.")
    dict_sub = dictionary.add_subparsers(dest="dictionary_command")
    dict_sub.add_parser("list", help="List personal dictionary words.")
    add_word = dict_sub.add_parser("add", help="Add a personal dictionary word.")
    add_word.add_argument("word")
    add_word.add_argument("--never-correct", action="store_true")
    remove_word = dict_sub.add_parser("remove", help="Remove a personal dictionary word.")
    remove_word.add_argument("word")
    export_dictionary = dict_sub.add_parser("export", help="Export personal dictionary to JSON.")
    export_dictionary.add_argument("path", type=Path)
    import_dictionary = dict_sub.add_parser("import", help="Import personal dictionary from JSON.")
    import_dictionary.add_argument("path", type=Path)

    privacy = subparsers.add_parser("privacy", help="Inspect or clear local learning data.")
    privacy_sub = privacy.add_subparsers(dest="privacy_command")
    privacy_sub.add_parser("summary", help="Show local data counts.")
    privacy_sub.add_parser("clear-learning", help="Clear adaptive learning data.")

    diagnostics = subparsers.add_parser("diagnostics", help="Inspect or clear privacy-safe diagnostics.")
    diagnostics_sub = diagnostics.add_subparsers(dest="diagnostics_command")
    show_diagnostics = diagnostics_sub.add_parser("show", help="Show recent diagnostic events.")
    show_diagnostics.add_argument("--limit", type=int, default=20)
    diagnostics_sub.add_parser("clear", help="Delete diagnostic log.")

    appearance = subparsers.add_parser("appearance", help="View or change overlay appearance.")
    appearance_sub = appearance.add_subparsers(dest="appearance_command")
    appearance_sub.add_parser("show", help="Show appearance settings.")
    set_appearance = appearance_sub.add_parser("set", help="Set appearance settings.")
    set_appearance.add_argument("--theme", choices=sorted(VALID_THEMES), default=None)
    set_appearance.add_argument("--size", choices=sorted(VALID_SUGGESTION_SIZES), default=None)
    set_appearance.add_argument("--opacity", type=int, default=None)
    set_appearance.add_argument("--animations", choices=["on", "off"], default=None)

    local_ai = subparsers.add_parser("local-ai", help="Manage optional local AI settings.")
    local_ai_sub = local_ai.add_subparsers(dest="local_ai_command")
    local_ai_sub.add_parser("status", help="Show local AI status.")
    configure_ai = local_ai_sub.add_parser("set", help="Configure local AI.")
    configure_ai.add_argument("--enabled", choices=["on", "off"], default=None)
    configure_ai.add_argument("--provider", choices=["none", "ollama"], default=None)
    configure_ai.add_argument("--model", default=None)
    configure_ai.add_argument("--endpoint", default=None)
    configure_ai.add_argument("--timeout", type=float, default=None)
    test_ai = local_ai_sub.add_parser("test", help="Send a short test prompt to the configured local model.")
    test_ai.add_argument("--prompt", default="Suggest the next word after: I will")

    doctor = subparsers.add_parser("doctor", help="Run privacy-safe runtime diagnostics.")
    doctor.add_argument("--test-hook", action="store_true", help="Attempt to install the Windows keyboard hook.")

    startup = subparsers.add_parser("startup", help="Manage Windows startup-on-login registration.")
    startup_sub = startup.add_subparsers(dest="startup_command")
    startup_sub.add_parser("status", help="Show startup registration status.")
    enable_startup = startup_sub.add_parser("enable", help="Launch Keyboard Assistant when Windows starts.")
    enable_startup.add_argument("--command", default=None, help="Override the startup command.")
    startup_sub.add_parser("disable", help="Remove startup registration.")
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


COMMANDS = {
    "suggest",
    "settings",
    "apps",
    "dictionary",
    "privacy",
    "diagnostics",
    "appearance",
    "local-ai",
    "startup",
    "doctor",
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        print(f"keyboard-assistant {__version__}")
        return 0
    if not _contains_command(argv) and not _is_top_level_help(argv):
        argv.insert(0, "suggest")

    parser = build_parser()
    args = parser.parse_args(argv)

    database = Database(args.db)
    database.initialize()
    assistant = KeyboardAssistant(database=database)

    if args.command == "settings":
        return _handle_settings(args, database)
    if args.command == "apps":
        return _handle_apps(args, database)
    if args.command == "dictionary":
        return _handle_dictionary(args, database)
    if args.command == "privacy":
        return _handle_privacy(args, database)
    if args.command == "diagnostics":
        return _handle_diagnostics(args, database)
    if args.command == "appearance":
        return _handle_appearance(args, database)
    if args.command == "local-ai":
        return _handle_local_ai(args, database)
    if args.command == "startup":
        return _handle_startup(args)
    if args.command == "doctor":
        return _handle_doctor(args, database)

    if getattr(args, "interactive", False):
        run_interactive(assistant)
        return 0

    text = " ".join(getattr(args, "text", []))
    if not text:
        parser.print_help()
        return 2

    print_suggestions(text, assistant)
    return 0


def _contains_command(argv: list[str]) -> bool:
    return any(arg in COMMANDS for arg in argv)


def _is_top_level_help(argv: list[str]) -> bool:
    return argv in (["-h"], ["--help"])


def _handle_settings(args: argparse.Namespace, database: Database) -> int:
    if args.settings_command in {None, "show"}:
        settings = database.get_settings()
        print(f"assistant: {'on' if settings.assistant_enabled else 'off'}")
        print(f"strength: {settings.correction_strength}")
        print(f"learning: {'on' if settings.learning_enabled else 'off'}")
        return 0

    value = args.value.strip().lower()
    if args.key == "assistant":
        database.set_bool_setting("assistant_enabled", _parse_on_off(value))
    elif args.key == "learning":
        database.set_bool_setting("learning_enabled", _parse_on_off(value))
    elif args.key == "strength":
        database.set_setting("correction_strength", value)
    print("Updated.")
    return 0


def _handle_apps(args: argparse.Namespace, database: Database) -> int:
    if args.apps_command in {None, "list"}:
        profiles = database.list_app_profiles()
        if not profiles:
            print("No app profiles.")
            return 0
        for profile in profiles:
            learning = "on" if profile.learning_enabled else "off"
            print(
                f"{profile.app_identifier}: status={profile.assistant_status}, "
                f"strength={profile.correction_strength}, learning={learning}, name={profile.app_name}"
            )
        return 0

    learning = None if args.learning is None else args.learning == "on"
    database.upsert_app_profile(
        app_identifier=args.identifier,
        app_name=args.name,
        assistant_status=args.status,
        correction_strength=args.strength,
        learning_enabled=learning,
    )
    print("Updated.")
    return 0


def _handle_dictionary(args: argparse.Namespace, database: Database) -> int:
    if args.dictionary_command in {None, "list"}:
        words = database.list_personal_words()
        if not words:
            print("Personal dictionary is empty.")
            return 0
        for word in words:
            never = " never-correct" if word["never_correct"] else ""
            print(f"{word['word']} ({word['source']}, frequency={word['frequency']}{never})")
        return 0

    if args.dictionary_command == "add":
        database.add_personal_word(args.word, never_correct=args.never_correct)
        print("Added.")
        return 0

    if args.dictionary_command == "remove":
        database.remove_personal_word(args.word)
        print("Removed.")
        return 0

    if args.dictionary_command == "export":
        count = database.export_personal_dictionary(args.path)
        print(f"Exported {count} words.")
        return 0

    if args.dictionary_command == "import":
        count = database.import_personal_dictionary(args.path)
        print(f"Imported {count} words.")
        return 0

    return 2


def _handle_privacy(args: argparse.Namespace, database: Database) -> int:
    if args.privacy_command in {None, "summary"}:
        for table, count in database.data_summary().items():
            print(f"{table}: {count}")
        return 0

    if args.privacy_command == "clear-learning":
        database.clear_learning_data()
        print("Cleared learning data.")
        return 0

    return 2


def _handle_diagnostics(args: argparse.Namespace, database: Database) -> int:
    logger = DiagnosticsLogger(default_log_path(database.path))
    if args.diagnostics_command in {None, "show"}:
        events = logger.read_events(limit=args.limit)
        if not events:
            print("No diagnostics.")
            return 0
        for event in events:
            print(f"{event.timestamp} {event.level} {event.event} {event.metadata}")
        return 0

    if args.diagnostics_command == "clear":
        logger.clear()
        print("Cleared diagnostics.")
        return 0

    return 2


def _handle_appearance(args: argparse.Namespace, database: Database) -> int:
    if args.appearance_command in {None, "show"}:
        appearance = database.get_appearance_settings()
        print(f"theme: {appearance.theme}")
        print(f"size: {appearance.suggestion_size}")
        print(f"opacity: {appearance.opacity}")
        print(f"animations: {'on' if appearance.animations_enabled else 'off'}")
        return 0

    if args.appearance_command == "set":
        animations = None if args.animations is None else args.animations == "on"
        database.set_appearance_settings(
            theme=args.theme,
            suggestion_size=args.size,
            opacity=args.opacity,
            animations_enabled=animations,
        )
        print("Updated.")
        return 0

    return 2


def _handle_local_ai(args: argparse.Namespace, database: Database) -> int:
    settings = database.get_model_settings()
    if args.local_ai_command in {None, "status"}:
        service = LocalAIService(
            provider_name=str(settings["provider"]),
            model=str(settings["model"]),
            enabled=bool(settings["enabled"]),
            endpoint=str(settings["endpoint"]),
            timeout_seconds=float(settings["timeout_seconds"]),
        )
        print(service.status())
        return 0

    if args.local_ai_command == "set":
        enabled = None if args.enabled is None else args.enabled == "on"
        database.set_model_settings(
            provider=args.provider,
            model=args.model,
            enabled=enabled,
            endpoint=args.endpoint,
            timeout_seconds=args.timeout,
        )
        print("Updated.")
        return 0

    if args.local_ai_command == "test":
        service = LocalAIService(
            provider_name=str(settings["provider"]),
            model=str(settings["model"]),
            enabled=bool(settings["enabled"]),
            endpoint=str(settings["endpoint"]),
            timeout_seconds=float(settings["timeout_seconds"]),
        )
        result = service.test(args.prompt)
        if result.ok:
            print(result.text)
            return 0
        print(f"Unavailable: {result.error}")
        return 1

    return 2


def _handle_doctor(args: argparse.Namespace, database: Database) -> int:
    from keyboard_assistant.diagnostics.doctor import format_doctor_checks, run_desktop_doctor

    checks = run_desktop_doctor(database, test_hook=args.test_hook)
    print(format_doctor_checks(checks))
    critical_names = {"python", "package", "database", "language_data", "correction_engine", "diagnostics"}
    return 0 if all(check.ok for check in checks if check.name in critical_names) else 1


def _handle_startup(args: argparse.Namespace) -> int:
    manager = WindowsStartupManager()
    if args.startup_command in {None, "status"}:
        status = manager.status()
        if not status.supported:
            print("startup: unsupported")
            return 0
        print(f"startup: {'on' if status.enabled else 'off'}")
        if status.command:
            print(f"command: {status.command}")
        return 0

    if args.startup_command == "enable":
        if not manager.supported:
            print("Startup registration is only supported on Windows.")
            return 1
        command = args.command or default_startup_command()
        manager.enable(command)
        print("Startup enabled.")
        return 0

    if args.startup_command == "disable":
        if not manager.supported:
            print("Startup registration is only supported on Windows.")
            return 1
        manager.disable()
        print("Startup disabled.")
        return 0

    return 2


def _parse_on_off(value: str) -> bool:
    if value in {"on", "true", "1", "yes"}:
        return True
    if value in {"off", "false", "0", "no"}:
        return False
    raise ValueError("value must be on or off")


if __name__ == "__main__":
    raise SystemExit(main())
