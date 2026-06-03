from __future__ import annotations

import ctypes
import platform
import sys
import threading
import time
from dataclasses import dataclass

from keyboard_assistant import __version__
from keyboard_assistant.ai.local_ai import LIVE_LOCAL_AI_TIMEOUT_SECONDS, LocalAIService
from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.data import defaults
from keyboard_assistant.diagnostics.logger import DiagnosticsLogger, default_log_path
from keyboard_assistant.storage.database import Database


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def run_desktop_doctor(database: Database, test_hook: bool = True) -> list[DoctorCheck]:
    checks = [
        DoctorCheck("os", True, platform.platform()),
        DoctorCheck("python", True, sys.version.split()[0]),
        DoctorCheck("package", True, f"keyboard-assistant {__version__}"),
        DoctorCheck(
            "windows_api",
            hasattr(ctypes, "windll"),
            "ctypes.windll available" if hasattr(ctypes, "windll") else "not Windows",
        ),
    ]
    checks.append(_check_database(database))
    checks.append(_check_language_data())
    checks.append(_check_corrections(database))
    checks.append(_check_active_app())
    checks.append(_check_text_injector())
    checks.append(_check_overlay())
    checks.append(_check_tray())
    if test_hook:
        checks.append(_check_keyboard_hook())
    else:
        checks.append(_check_keyboard_listener_available())
    checks.append(_check_local_ai(database))
    checks.append(_check_diagnostics(database))
    return checks


def format_doctor_checks(checks: list[DoctorCheck]) -> str:
    lines = []
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        lines.append(f"{status:4} {check.name}: {check.detail}")
    return "\n".join(lines)


def run_overlay_demo(seconds: float = 3.0) -> None:
    from keyboard_assistant.platform.cursor import CursorLocator
    from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay

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
    from keyboard_assistant.platform.text_injector import WindowsTextInjector

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


def _check_language_data() -> DoctorCheck:
    counts = {
        "typos": len(defaults.TYPO_RULES),
        "words": len(defaults.COMMON_WORDS),
        "phrases": len(defaults.PHRASE_RULES),
        "confusion_rules": len(defaults.CONFUSION_RULES),
        "contractions": len(defaults.CONTRACTION_RULES),
    }
    if not all(counts.values()):
        return DoctorCheck("language_data", False, f"missing data: {counts}")
    detail = ", ".join(f"{key}={value}" for key, value in counts.items())
    return DoctorCheck("language_data", True, detail)


def _check_corrections(database: Database) -> DoctorCheck:
    try:
        suggestions = KeyboardAssistant(database).suggest("recieve")
    except Exception as exc:
        return DoctorCheck("correction_engine", False, f"{type(exc).__name__}: {exc}")
    if not suggestions:
        return DoctorCheck("correction_engine", False, "sample typo did not produce a suggestion")
    return DoctorCheck("correction_engine", True, "sample typo produced a suggestion")


def _check_active_app() -> DoctorCheck:
    from keyboard_assistant.platform.app_detector import AppDetector

    try:
        context = AppDetector().current_app()
    except Exception as exc:
        return DoctorCheck("active_app", False, f"{type(exc).__name__}: {exc}")
    identifier = context.app_identifier or "(unknown)"
    field_type = context.field_type or "(unknown field)"
    return DoctorCheck("active_app", True, f"{identifier}; field={field_type}")


def _check_text_injector() -> DoctorCheck:
    from keyboard_assistant.platform.text_injector import WindowsTextInjector

    try:
        WindowsTextInjector()
    except Exception as exc:
        return DoctorCheck("text_injector", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("text_injector", True, "available")


def _check_overlay() -> DoctorCheck:
    from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay

    try:
        overlay = SuggestionOverlay()
        overlay.close()
    except Exception as exc:
        return DoctorCheck("overlay", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("overlay", True, "created and closed")


def _check_tray() -> DoctorCheck:
    try:
        tray = None
        tray = __import__("keyboard_assistant.ui.tray_icon", fromlist=["TrayIcon"]).TrayIcon(
            on_toggle_pause=lambda: False,
            on_open_settings=lambda: None,
            on_exit=lambda: None,
            is_paused=lambda: False,
        )
        tray.close()
    except Exception as exc:
        if tray is not None:
            try:
                tray.close()
            except Exception:
                pass
        return DoctorCheck("tray", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("tray", True, "created and closed")


def _check_keyboard_listener_available() -> DoctorCheck:
    from keyboard_assistant.platform.keyboard_listener import WindowsKeyboardListener

    try:
        listener = WindowsKeyboardListener(lambda _event: False)
        listener.stop()
    except Exception as exc:
        return DoctorCheck("keyboard_listener", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("keyboard_listener", True, "constructible")


def _check_keyboard_hook() -> DoctorCheck:
    from keyboard_assistant.platform.keyboard_listener import WindowsKeyboardListener

    try:
        listener = WindowsKeyboardListener(lambda _event: False)
        listener.start()
        listener.stop()
    except Exception as exc:
        return DoctorCheck("keyboard_hook", False, f"{type(exc).__name__}: {exc}")
    return DoctorCheck("keyboard_hook", True, "installed and removed")


def _check_local_ai(database: Database) -> DoctorCheck:
    settings = database.get_model_settings()
    enabled = bool(settings["enabled"])
    provider = str(settings["provider"])
    model = str(settings["model"])
    endpoint = str(settings["endpoint"])
    timeout_seconds = float(settings["timeout_seconds"])
    service = LocalAIService(provider_name=provider, model=model, enabled=enabled, endpoint=endpoint, timeout_seconds=timeout_seconds)
    if not enabled:
        return DoctorCheck("local_ai", True, "disabled")
    result = service.test("Return one word: ok", timeout_seconds=LIVE_LOCAL_AI_TIMEOUT_SECONDS)
    if result.ok:
        return DoctorCheck("local_ai", True, f"{provider} model={model} reachable")
    return DoctorCheck("local_ai", False, f"{provider} model={model or '(not configured)'} unavailable: {result.error}")


def _check_diagnostics(database: Database) -> DoctorCheck:
    log_path = default_log_path(database.path)
    logger = DiagnosticsLogger(log_path)
    events = logger.read_events(limit=100)
    error_count = sum(1 for event in events if event.level == "error")
    return DoctorCheck("diagnostics", True, f"path={log_path}; recent_errors={error_count}")
