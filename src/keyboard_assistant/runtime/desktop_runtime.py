from __future__ import annotations

import queue
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import threading

from keyboard_assistant.ai.suggestion_worker import LocalAISuggestionWorker
from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.core.context import TextContext, TypedBuffer, extract_text_context
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.data.defaults import NEXT_WORD_FALLBACKS
from keyboard_assistant.diagnostics.logger import DiagnosticsLogger, default_log_path
from keyboard_assistant.platform.app_detector import AppDetector
from keyboard_assistant.platform.cursor import CursorLocator
from keyboard_assistant.platform.keyboard_listener import KeyboardEvent, WindowsKeyboardListener
from keyboard_assistant.platform.text_injector import NullTextInjector, WindowsTextInjector
from keyboard_assistant.runtime.health import RuntimeHealth
from keyboard_assistant.storage.database import Database
from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay
from keyboard_assistant.ui.tray_icon import TrayIcon


@dataclass(frozen=True)
class AppliedCorrection:
    original_text: str
    inserted_text: str
    recorded_replacement: str


@dataclass
class RuntimeStats:
    key_events: int = 0
    suggestions_generated: int = 0
    overlays_shown: int = 0
    suggestions_accepted: int = 0
    suggestions_ignored: int = 0
    corrections_reverted: int = 0
    injection_errors: int = 0
    app_context_changes: int = 0


class NullTrayIcon:
    def close(self) -> None:
        pass

    def update_tooltip(self) -> None:
        pass


class NullOverlay:
    def run(self) -> None:
        pass

    def close(self) -> None:
        pass

    def call_soon(self, callback) -> None:
        callback()

    def apply_appearance(self, _appearance) -> None:
        pass

    def show_suggestions(self, _suggestions, _x: int, _y: int, focus_index: int = 0) -> None:
        pass

    def hide(self) -> None:
        pass


class NullKeyboardListener:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class DesktopAssistantRuntime:
    def __init__(
        self,
        database: Database,
        diagnostics: DiagnosticsLogger | None = None,
        verbose: bool = False,
        injector=None,
        overlay=None,
        tray=None,
        listener=None,
        app_detector=None,
        cursor_locator=None,
        ai_worker=None,
        allow_null_injector: bool = False,
    ) -> None:
        self.database = database
        self.diagnostics = diagnostics or DiagnosticsLogger(default_log_path(database.path))
        self.verbose = verbose
        self.health = RuntimeHealth(database_opened=True, language_data_loaded=True)
        self.assistant = KeyboardAssistant(database)
        model_settings = database.get_model_settings()
        self.health.local_ai_enabled = bool(model_settings["enabled"])
        self.health.assistant_status = "on" if database.get_settings().assistant_enabled else "off"
        self.ai_worker = ai_worker or LocalAISuggestionWorker(
            database,
            self._handle_ai_suggestions,
            on_error=self._handle_ai_error,
        )
        self.buffer = TypedBuffer()
        self.app_detector = app_detector or AppDetector()
        self.cursor_locator = cursor_locator or CursorLocator()
        if injector is not None:
            self.injector = injector
            self.health.text_injector_started = True
            self.health.mark("text_injector_injected")
        else:
            self.injector = self._create_text_injector(allow_null_injector=allow_null_injector)
        self._paused = False
        if overlay is not None:
            self.overlay = overlay
            self.health.overlay_started = True
            self.health.mark("overlay_injected")
        else:
            self.overlay = self._create_overlay()
        if tray is not None:
            self.tray = tray
            self.health.tray_icon_started = True
            self.health.mark("tray_icon_injected")
        else:
            self.tray = self._create_tray()
        self.listener = listener if listener is not None else self._create_listener()
        self._lock = threading.Lock()
        self._suggestions: list[Suggestion] = []
        self._selection_index = 0
        self._last_correction: AppliedCorrection | None = None
        self._stopped = False
        self._event_queue: queue.Queue[KeyboardEvent | None] = queue.Queue()
        self._event_worker: threading.Thread | None = None
        self._last_app_signature: tuple[str, str, str, str] | None = None
        self.stats = RuntimeStats()
        self.diagnostics.info("runtime_initialized", health=self.health.snapshot())
        self._print("Keyboard Assistant initialized.")

    def _create_text_injector(self, allow_null_injector: bool) -> WindowsTextInjector | NullTextInjector:
        try:
            injector = WindowsTextInjector()
            self.health.text_injector_started = True
            self.health.mark("text_injector_started")
            return injector
        except Exception as exc:
            self.health.text_injector_failed = True
            self.health.record_exception("text_injector", exc)
            self.diagnostics.exception("text_injector_start_failed", exc)
            if allow_null_injector:
                self.health.mark("text_injector_fallback")
                return NullTextInjector()
            raise RuntimeError("Text injector failed to start.") from exc

    def _create_overlay(self):
        try:
            overlay = SuggestionOverlay(on_close=self.stop, on_select=self._accept_selected_from_overlay)
            self.health.overlay_started = True
            self.health.mark("overlay_started")
            return overlay
        except Exception as exc:
            self.health.overlay_failed = True
            self.health.record_exception("overlay", exc)
            self.diagnostics.exception("overlay_start_failed", exc)
            raise RuntimeError("Suggestion overlay failed to start.") from exc

    def _create_tray(self):
        try:
            tray = TrayIcon(
                on_toggle_pause=self.toggle_pause,
                on_open_settings=self.open_settings,
                on_exit=self.stop,
                is_paused=self.is_paused,
            )
            self.health.tray_icon_started = True
            self.health.mark("tray_icon_started")
            return tray
        except Exception as exc:
            self.health.tray_icon_failed = True
            self.health.record_exception("tray_icon", exc)
            self.diagnostics.exception("tray_icon_start_failed", exc)
            return NullTrayIcon()

    def _create_listener(self):
        return WindowsKeyboardListener(
            self._handle_keyboard_event,
            on_error=self._handle_keyboard_listener_error,
        )

    def run(self) -> None:
        self.diagnostics.info("runtime_starting")
        self._print("Installing keyboard hook...")
        self._start_event_worker()
        try:
            self.listener.start()
        except Exception as exc:
            self.health.keyboard_hook_failed = True
            self.health.record_exception("keyboard_hook", exc)
            self.diagnostics.exception("keyboard_hook_start_failed", exc)
            self._stop_event_worker()
            raise
        self.health.keyboard_hook_started = True
        self.health.mark("keyboard_hook_started")
        self.diagnostics.info("keyboard_hook_started")
        self._print("Keyboard Assistant is running. Try Notepad with 'recieve', 'tge', or 'peolpe'.")
        self._print("Controls: Arrow keys choose, Space accepts, Esc declines, or click a choice.")
        try:
            self.overlay.run()
        finally:
            self.stop()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.listener.stop()
        self._stop_event_worker()
        self.ai_worker.cancel()
        self.tray.close()
        self.overlay.close()
        self.diagnostics.info("runtime_stopped", health=self.health.snapshot(), **self._stats_metadata())
        self._print("Keyboard Assistant stopped.")
        self._print(f"Session stats: {self._stats_metadata()}")

    def is_paused(self) -> bool:
        return self._paused

    def toggle_pause(self) -> bool:
        self._paused = not self._paused
        if self._paused:
            self.ai_worker.cancel()
        self._hide()
        self.diagnostics.info("runtime_pause_changed", paused=self._paused)
        return self._paused

    def open_settings(self) -> None:
        env = os.environ.copy()
        src_path = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "keyboard_assistant.settings_app",
                "--db",
                str(self.database.path),
            ],
            env=env,
            cwd=str(Path.cwd()),
        )
        self.diagnostics.info("settings_launched")

    def _handle_keyboard_event(self, event: KeyboardEvent) -> bool:
        self.stats.key_events += 1
        self._print(
            f"key={event.key!r} char={event.char!r} ctrl={event.ctrl} alt={event.alt} shift={event.shift}",
            debug_only=True,
        )
        if event.ctrl:
            return False

        if event.key == "escape":
            if self._has_visible_suggestions():
                self._queue_event(event)
                return True
            return False

        if event.key in {"left", "up"}:
            return self._move_selection(-1)

        if event.key in {"right", "down"}:
            return self._move_selection(1)

        if event.key == "backspace":
            self._queue_event(event)
            return False

        if event.key == "space":
            if self._has_visible_suggestions():
                if self._focused_choice_is_unchanged_word():
                    self._queue_event(event)
                    return False
                return self._accept_suggestion(self._selection_index, trailing_space=True)
            self._queue_event(event)
            return False

        if event.key in {"enter", "char"}:
            self._queue_event(event)
            return False

        return False

    def _process_keyboard_event(self, event: KeyboardEvent) -> None:
        if self._paused:
            return

        if event.key == "escape":
            self._decline_current_suggestions()
            return

        if event.key == "backspace":
            app_context = self._prepare_app_context()
            self.buffer.push("\b")
            self._update_suggestions(app_context)
            return

        if event.key == "space":
            app_context = self._prepare_app_context()
            self.buffer.push(" ")
            self.assistant.observe_text(self.buffer.text, app_context)
            self._update_suggestions(app_context)
            return

        if event.key == "enter":
            app_context = self._prepare_app_context()
            self.buffer.push("\n")
            self.assistant.observe_text(self.buffer.text, app_context)
            self._hide()
            return

        if event.key == "char" and event.char:
            app_context = self._prepare_app_context()
            self._last_correction = None
            self.buffer.push(event.char)
            self._update_suggestions(app_context)

    def _queue_event(self, event: KeyboardEvent) -> None:
        self._event_queue.put(event)

    def _start_event_worker(self) -> None:
        if self._event_worker and self._event_worker.is_alive():
            return
        self._event_worker = threading.Thread(target=self._event_loop, name="keyboard-assistant-events", daemon=True)
        self._event_worker.start()

    def _stop_event_worker(self) -> None:
        self._event_queue.put(None)
        if self._event_worker:
            self._event_worker.join(timeout=2)
            self._event_worker = None

    def _event_loop(self) -> None:
        while True:
            event = self._event_queue.get()
            if event is None:
                return
            try:
                self._process_keyboard_event(event)
            except Exception as exc:
                self.diagnostics.exception("keyboard_event_processing_failed", exc)
                self._print(f"Keyboard event processing failed: {type(exc).__name__}: {exc}")

    def _prepare_app_context(self) -> AppContext:
        app_context = self.app_detector.current_app()
        self.health.current_app = app_context.app_identifier
        signature = _app_signature(app_context)
        if self._last_app_signature is not None and signature != self._last_app_signature:
            self.buffer.clear()
            self._last_correction = None
            self.stats.app_context_changes += 1
            self.diagnostics.info("app_context_changed")
            self._hide()
        self._last_app_signature = signature
        return app_context

    def _update_suggestions(self, app_context: AppContext | None = None) -> None:
        app_context = app_context or self._prepare_app_context()
        suggestions, policy = self.assistant.suggest_with_policy(self.buffer.text, app_context)
        choices = self._display_choices(suggestions, app_context)
        self.stats.suggestions_generated += len(choices)
        self._print(
            f"buffer={self.buffer.text[-40:]!r} app={app_context.app_identifier!r} "
            f"policy={policy.reason} strength={policy.correction_strength} suggestions={len(choices)}",
            debug_only=True,
        )
        with self._lock:
            self._suggestions = choices
            self._selection_index = _default_selection_index(choices)
        self.ai_worker.request(self.buffer.text, app_context, rule_suggestions=choices)
        if not choices:
            self._hide()
            return
        point = self.cursor_locator.current_anchor()
        appearance = self.database.get_appearance_settings()
        self.overlay.call_soon(
            lambda: (
                self.overlay.apply_appearance(appearance),
                self.overlay.show_suggestions(choices, point.x, point.y, focus_index=self._selection_index),
            )
        )
        self.stats.overlays_shown += 1

    def _handle_ai_suggestions(self, source_text: str, ai_suggestions: list[Suggestion]) -> None:
        if self._paused or source_text != self.buffer.text:
            return
        with self._lock:
            app_context = self.app_detector.current_app()
            core_suggestions, _policy = self.assistant.suggest_with_policy(self.buffer.text, app_context)
            existing = self._display_choices([*core_suggestions, *ai_suggestions], app_context)
            self._suggestions = existing[:3]
            self._selection_index = min(self._selection_index, max(0, len(self._suggestions) - 1))
            suggestions = list(self._suggestions)
            focus_index = self._selection_index
        if suggestions:
            point = self.cursor_locator.current_anchor()
            appearance = self.database.get_appearance_settings()
            self.overlay.call_soon(
                lambda: (
                    self.overlay.apply_appearance(appearance),
                    self.overlay.show_suggestions(suggestions, point.x, point.y, focus_index=focus_index),
                )
            )
            self.stats.overlays_shown += 1
            self.diagnostics.info("local_ai_suggestions_received", count=len(ai_suggestions))

    def _handle_ai_error(self, exc: BaseException) -> None:
        self.health.local_ai_unavailable = True
        self.health.record_exception("local_ai", exc)
        self.diagnostics.exception("local_ai_worker_failed", exc)

    def _handle_keyboard_listener_error(self, exc: BaseException) -> None:
        self.health.record_exception("keyboard_callback", exc)
        self.diagnostics.exception("keyboard_callback_failed", exc)

    def _has_visible_suggestions(self) -> bool:
        with self._lock:
            return bool(self._suggestions)

    def _focused_choice_is_unchanged_word(self) -> bool:
        with self._lock:
            if len(self._suggestions) <= 1 or self._selection_index >= len(self._suggestions):
                return False
            suggestion = self._suggestions[self._selection_index]
        return suggestion.kind == "typed" and suggestion.original == suggestion.replacement

    def _move_selection(self, delta: int) -> bool:
        with self._lock:
            if not self._suggestions:
                return False
            self._selection_index = max(0, min(len(self._suggestions) - 1, self._selection_index + delta))
            suggestions = list(self._suggestions)
            focus_index = self._selection_index
        self._show_choices(suggestions, focus_index)
        return True

    def _show_choices(self, suggestions: list[Suggestion], focus_index: int) -> None:
        point = self.cursor_locator.current_anchor()
        appearance = self.database.get_appearance_settings()
        self.overlay.call_soon(
            lambda: (
                self.overlay.apply_appearance(appearance),
                self.overlay.show_suggestions(suggestions, point.x, point.y, focus_index=focus_index),
            )
        )

    def _accept_selected_from_overlay(self, index: int) -> None:
        self._accept_suggestion(index, trailing_space=False)

    def _accept_suggestion(self, index: int, trailing_space: bool) -> bool:
        with self._lock:
            if index < 0 or index >= len(self._suggestions):
                return False
            suggestion = self._suggestions[index]

        if suggestion.kind == "spacing":
            return False

        replacement = suggestion.replacement + (" " if trailing_space else "")
        try:
            self.injector.replace_previous_text(len(suggestion.original), replacement)
        except Exception as exc:
            self.stats.injection_errors += 1
            self.diagnostics.exception("text_injection_failed", exc)
            self._print(f"Text injection failed: {type(exc).__name__}: {exc}")
            return False
        self.buffer.replace_suffix(suggestion.original, replacement)
        if suggestion.kind != "typed":
            self.assistant.accept(suggestion, self.app_detector.current_app())
        self.stats.suggestions_accepted += 1
        self.diagnostics.info("suggestion_accepted", kind=suggestion.kind, confidence=round(suggestion.confidence, 3))
        self._last_correction = (
            None
            if suggestion.kind in {"typed", "next_word", "local_ai"}
            else AppliedCorrection(
                original_text=suggestion.original,
                inserted_text=replacement,
                recorded_replacement=suggestion.replacement,
            )
        )
        self._hide()
        return True

    def _revert_last_correction(self) -> bool:
        correction = self._last_correction
        if not correction:
            return False
        try:
            self.injector.replace_previous_text(len(correction.inserted_text), correction.original_text)
        except Exception as exc:
            self.stats.injection_errors += 1
            self.diagnostics.exception("text_injection_failed", exc)
            self._print(f"Text injection failed: {type(exc).__name__}: {exc}")
            return False
        self.buffer.replace_suffix(correction.inserted_text, correction.original_text)
        self.assistant.revert(
            correction.original_text,
            correction.recorded_replacement,
            self.app_detector.current_app(),
        )
        self.diagnostics.info("correction_reverted")
        self.stats.corrections_reverted += 1
        self._last_correction = None
        self._hide()
        return True

    def _decline_current_suggestions(self) -> None:
        self.ai_worker.cancel()
        with self._lock:
            suggestions = list(self._suggestions)
        for suggestion in suggestions:
            if suggestion.kind == "typed":
                continue
            self.assistant.ignore(suggestion, self.app_detector.current_app())
            self.stats.suggestions_ignored += 1
            self.diagnostics.info("suggestion_ignored", kind=suggestion.kind, confidence=round(suggestion.confidence, 3))
        self._hide()

    def _hide(self) -> None:
        with self._lock:
            self._suggestions = []
            self._selection_index = 0
        self.overlay.call_soon(self.overlay.hide)

    def _print(self, message: str, debug_only: bool = False) -> None:
        if debug_only and not self.verbose:
            return
        print(message, flush=True)

    def _stats_metadata(self) -> dict[str, int]:
        return {
            "key_events": self.stats.key_events,
            "suggestions_generated": self.stats.suggestions_generated,
            "overlays_shown": self.stats.overlays_shown,
            "suggestions_accepted": self.stats.suggestions_accepted,
            "suggestions_ignored": self.stats.suggestions_ignored,
            "corrections_reverted": self.stats.corrections_reverted,
            "injection_errors": self.stats.injection_errors,
            "app_context_changes": self.stats.app_context_changes,
        }

    def _display_choices(self, suggestions: list[Suggestion], app_context: AppContext) -> list[Suggestion]:
        context = extract_text_context(self.buffer.text)
        typed = context.current_word
        if not typed:
            return suggestions[:3]

        typed_choice = Suggestion(
            original=typed,
            replacement=typed,
            kind="typed",
            confidence=1.0,
            auto_apply=False,
        )
        correction = _best_word_correction(typed, suggestions)
        middle = correction or typed_choice
        right = _best_next_word_choice(suggestions) or self._phrase_prediction_choice(context, app_context)
        if right:
            return [typed_choice, middle, right]
        return [typed_choice, middle]

    def _phrase_prediction_choice(self, context: TextContext, app_context: AppContext) -> Suggestion | None:
        words = tuple(part for part in (*context.previous_words, context.current_word) if part)
        predictions = self.database.phrase_predictions(words, app_context.app_identifier, limit=1)
        if not predictions:
            predictions = _fallback_next_words(words)
        if not predictions:
            return None
        return Suggestion(
            original="",
            replacement=predictions[0],
            kind="next_word",
            confidence=0.72,
            auto_apply=False,
        )


def _app_signature(app_context: AppContext) -> tuple[str, str, str, str]:
    return (
        app_context.app_identifier.lower(),
        app_context.window_class_name,
        app_context.field_type,
        app_context.field_name,
    )


def _best_word_correction(typed_word: str, suggestions: list[Suggestion]) -> Suggestion | None:
    for suggestion in suggestions:
        if suggestion.original == typed_word and suggestion.replacement != typed_word and suggestion.kind not in {
            "next_word",
            "local_ai",
        }:
            return suggestion
    return None


def _best_next_word_choice(suggestions: list[Suggestion]) -> Suggestion | None:
    for suggestion in suggestions:
        if suggestion.kind in {"next_word", "local_ai"} and suggestion.replacement:
            return suggestion
    return None


def _fallback_next_words(words: tuple[str, ...]) -> list[str]:
    lowered = tuple(word.lower() for word in words)
    for size in range(min(3, len(lowered)), 0, -1):
        prediction = NEXT_WORD_FALLBACKS.get(lowered[-size:])
        if prediction:
            return [prediction]
    return []


def _default_selection_index(choices: list[Suggestion]) -> int:
    return 1 if len(choices) > 1 else 0
