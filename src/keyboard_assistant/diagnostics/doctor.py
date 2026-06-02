from __future__ import annotations

import ctypes
import platform
import threading
import time
from dataclasses import dataclass

from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.platform.app_detector import AppDetector
from keyboard_assistant.platform.cursor import CursorLocator
from keyboard_assistant.platform.keyboard_listener import WindowsKeyboardListener
from keyboard_assistant.platform.text_injector import WindowsTextInjector
from keyboard_assistant.storage.database import Database
from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def run_desktop_doctor(database: Database, test_hook: bool = True) -> list[DoctorCheck]:
    checks = [
        DoctorCheck("python", True, f"{platform.python_version()} on {platform.platform()}"),
        DoctorCheck("windows_api", hasattr(ctypes, "windll"), "ctypes.windll available" if hasattr(ctypes, "windll") else "not Windows"),
    ]
    checks.append(_check_database(database))
    checks.append(_check_corrections(database))
    checks.append(_check_active_app())
    checks.append(_check_overlay())
    if test_hook:
        checks.append(_check_keyboard_hook())
    return checks


def format_doctor_checks(checks: list[DoctorCheck]) -> str:
    lines = []
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        lines.append(f"{status:4} {check.name}: {check.detail}")
    return "\n".join(lines)


def run_overlay_demo(seconds: float = 3.0) -> None:
    overlay = SuggestionOverlay()
    point = CursorLocator().current_anchor()
    overlay.show_suggestions(
        [
            Suggestion("recieve", "receive", "typo", 0.96),
            Suggestion("tge", "the", "keyboard_neighbor", 0.86),
        ],
        point.x,
        point.y,
    )

    def closer() -> None:
        time.sleep(seconds)
        overlay.call_soon(overlay.close)

    threading.Thread(target=closer, name="overlay-demo-close", daemon=True).start()
    overlay.run()


def run_injection_demo(text: str = "Keyboard Assistant injection test", countdown: float = 3.0) -> None:
    if countdown > 0:
        print(f"Focus a text field now. Typing in {countdown:g} seconds...", flush=True)
        time.sleep(countdown)
    WindowsTextInjector().type_text(text)


def _check_database(database: Database) -> DoctorCheck:
    try:
        database.initialize()
        summary = database.data_summary()
    except Exception as exc:
        return DoctorCheck("database", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("database", True, f"{database.path} ({summary['personal_dictionary']} dictionary words)")


def _check_corrections(database: Database) -> DoctorCheck:
    try:
        suggestions = KeyboardAssistant(database).suggest("recieve")
    except Exception as exc:
        return DoctorCheck("correction_engine", False, f"{type(exc).__name__}: {exc}")
    if not suggestions:
        return DoctorCheck("correction_engine", False, "no suggestion for 'recieve'")
    return DoctorCheck("correction_engine", True, f"recieve -> {suggestions[0].replacement}")


def _check_active_app() -> DoctorCheck:
    try:
        context = AppDetector().current_app()
    except Exception as exc:
        return DoctorCheck("active_app", False, f"{type(exc).__name__}: {exc}")
    identifier = context.app_identifier or "(unknown)"
    title = context.window_title or "(no title)"
    return DoctorCheck("active_app", True, f"{identifier} | {title[:80]}")


def _check_overlay() -> DoctorCheck:
    try:
        overlay = SuggestionOverlay()
        overlay.close()
    except Exception as exc:
        return DoctorCheck("overlay", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("overlay", True, "created and closed")


def _check_keyboard_hook() -> DoctorCheck:
    try:
        listener = WindowsKeyboardListener(lambda _event: False)
        listener.start()
        listener.stop()
    except Exception as exc:
        return DoctorCheck("keyboard_hook", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("keyboard_hook", True, "installed and removed")
