from __future__ import annotations

from collections.abc import Callable
import re
import threading

from keyboard_assistant.ai.local_ai import LocalAIResult, LocalAIService
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.storage.database import Database


AI_CONFIDENCE = 0.64
MIN_CONTEXT_CHARS = 12
MIN_CONTEXT_WORDS = 2
CONFIDENT_RULE_SUGGESTION = 0.76


class LocalAISuggestionWorker:
    """Debounced, cancellable local-AI suggestion runner."""

    def __init__(
        self,
        database: Database,
        on_suggestions: Callable[[str, list[Suggestion]], None],
        on_error: Callable[[BaseException], None] | None = None,
        delay_seconds: float = 0.45,
        service_factory: type[LocalAIService] = LocalAIService,
    ) -> None:
        self.database = database
        self.on_suggestions = on_suggestions
        self.on_error = on_error
        self.delay_seconds = delay_seconds
        self.service_factory = service_factory
        self._lock = threading.Lock()
        self._sequence = 0
        self._timer: threading.Timer | None = None

    def request(
        self,
        text: str,
        app_context: AppContext,
        rule_suggestions: list[Suggestion] | None = None,
    ) -> None:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            if self._timer:
                self._timer.cancel()
                self._timer = None

            if not self._should_request(text, rule_suggestions or []):
                return

            timer = threading.Timer(self.delay_seconds, self._run, args=(sequence, text, app_context))
            timer.daemon = True
            self._timer = timer
            timer.start()

    def cancel(self) -> None:
        with self._lock:
            self._sequence += 1
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def _run(self, sequence: int, text: str, app_context: AppContext) -> None:
        try:
            settings = self.database.get_model_settings()
            service = self._create_service(settings)
            result = service.suggest_next(text)
            suggestions = self._suggestions_from_result(result)
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return
        if not suggestions:
            return
        with self._lock:
            if sequence != self._sequence:
                return
        self.on_suggestions(text, suggestions)

    def _should_request(self, text: str, rule_suggestions: list[Suggestion] | None = None) -> bool:
        settings = self.database.get_model_settings()
        if not settings["enabled"] or settings["provider"] == "none":
            return False
        stripped = text.rstrip()
        if len(stripped) < MIN_CONTEXT_CHARS:
            return False
        if len(re.findall(r"[A-Za-z][A-Za-z']*", stripped)) < MIN_CONTEXT_WORDS:
            return False
        if not text[-1:].isspace() and text[-1:] not in ".!?":
            return False
        if _has_confident_rule_suggestion(rule_suggestions or []):
            return False
        return True

    def _suggestions_from_result(self, result: LocalAIResult) -> list[Suggestion]:
        if not result.ok:
            return []
        candidate = _clean_ai_text(result.text)
        if not candidate:
            return []
        return [
            Suggestion(
                original="",
                replacement=candidate,
                kind="local_ai",
                confidence=AI_CONFIDENCE,
                auto_apply=False,
            )
        ]

    def _create_service(self, settings: dict[str, str | bool]) -> LocalAIService:
        kwargs = {
            "provider_name": str(settings["provider"]),
            "model": str(settings["model"]),
            "enabled": bool(settings["enabled"]),
            "endpoint": str(settings.get("endpoint", "http://127.0.0.1:11434")),
            "timeout_seconds": float(settings.get("timeout_seconds", "30.0")),
        }
        try:
            return self.service_factory(**kwargs)
        except TypeError:
            return self.service_factory(
                provider_name=kwargs["provider_name"],
                model=kwargs["model"],
                enabled=kwargs["enabled"],
            )


def _clean_ai_text(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    first_line = first_line.strip().strip('"').strip("'")
    if _looks_like_meta_answer(first_line):
        return ""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*|[0-9]+", first_line)
    if not words:
        return ""
    return " ".join(words[:4])


def _looks_like_meta_answer(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith(
        (
            "we are",
            "we need",
            "the user",
            "given the",
            "okay",
            "the task",
        )
    )


def _has_confident_rule_suggestion(suggestions: list[Suggestion]) -> bool:
    return any(
        suggestion.kind not in {"typed", "local_ai"}
        and suggestion.confidence >= CONFIDENT_RULE_SUGGESTION
        for suggestion in suggestions
    )
