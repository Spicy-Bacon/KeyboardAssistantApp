from __future__ import annotations

import argparse
from pathlib import Path

from keyboard_assistant.diagnostics.doctor import (
    format_doctor_checks,
    run_desktop_doctor,
    run_injection_demo,
    run_overlay_demo,
)
from keyboard_assistant.diagnostics.logger import DiagnosticsLogger, default_log_path
from keyboard_assistant.platform.single_instance import SingleInstance
from keyboard_assistant.runtime.desktop_runtime import DesktopAssistantRuntime
from keyboard_assistant.runtime.windows_factory import WindowsRuntimeComponentFactory
from keyboard_assistant.storage.database import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Keyboard Assistant desktop prototype.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".keyboard_assistant.sqlite3"),
        help="SQLite database path.",
    )
    parser.add_argument("--debug", action="store_true", help="Print key events and suggestion diagnostics.")
    parser.add_argument("--doctor", action="store_true", help="Run desktop subsystem checks and exit.")
    parser.add_argument("--overlay-demo", action="store_true", help="Show a sample suggestion overlay and exit.")
    parser.add_argument(
        "--inject-demo",
        nargs="?",
        const="Keyboard Assistant injection test",
        default=None,
        help="Type sample text into the focused app after a short countdown and exit.",
    )
    parser.add_argument("--inject-delay", type=float, default=3.0, help="Countdown seconds for --inject-demo.")
    parser.add_argument("--skip-hook-test", action="store_true", help="Do not install the keyboard hook during --doctor.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Database(args.db)
    database.initialize()
    if args.doctor:
        checks = run_desktop_doctor(database, test_hook=not args.skip_hook_test)
        print(format_doctor_checks(checks))
        return 0 if all(check.ok for check in checks) else 1
    if args.overlay_demo:
        print("Showing sample overlay for 3 seconds...", flush=True)
        run_overlay_demo()
        return 0
    if args.inject_demo is not None:
        run_injection_demo(args.inject_demo, countdown=args.inject_delay)
        return 0

    diagnostics = DiagnosticsLogger(default_log_path(args.db))
    instance = SingleInstance()
    if not instance.acquire():
        print("Keyboard Assistant is already running. Stop the existing instance before starting another one.")
        return 1
    try:
        runtime = DesktopAssistantRuntime(
            database,
            diagnostics=diagnostics,
            verbose=args.debug,
            component_factory=WindowsRuntimeComponentFactory(),
        )
        runtime.run()
    except Exception as exc:
        diagnostics.exception("runtime_crashed", exc)
        raise
    finally:
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
