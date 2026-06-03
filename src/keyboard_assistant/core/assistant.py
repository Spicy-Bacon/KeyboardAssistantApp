from __future__ import annotations

from dataclasses import dataclass

from keyboard_assistant.core.correction_engine import CorrectionEngine
from keyboard_assistant.core.context import extract_text_context
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.privacy.sensitive_context import SensitiveContextFilter
from keyboard_assistant.storage.database import Database


@dataclass(frozen=True)
class SuggestionPolicy:
    allowed: bool
    reason: str
    correction_strength: str = "balanced"


class KeyboardAssistant:
    """Coordinates privacy policy, correction, and local learning storage."""

    def __init__(
        self,
        database: Database,
        correction_engine: CorrectionEngine | None = None,
        sensitive_filter: SensitiveContextFilter | None = None,
    ) -> None:
        self.database = database
        self.correction_engine = correction_engine or CorrectionEngine(database=database)
        self.sensitive_filter = sensitive_filter or SensitiveContextFilter()

    def suggest(self, text: str, app_context: AppContext | None = None) -> list[Suggestion]:
        suggestions, _policy = self.suggest_with_policy(text, app_context)
        return suggestions

    def suggest_with_policy(
        self,
        text: str,
        app_context: AppContext | None = None,
    ) -> tuple[list[Suggestion], SuggestionPolicy]:
        app_context = app_context or AppContext()
        policy = self.suggestion_policy(app_context)
        if not policy.allowed:
            return [], policy
        return (
            self.correction_engine.suggest(
                text,
                app_context=app_context,
                correction_strength=policy.correction_strength,
            ),
            policy,
        )

    def suggestion_policy(self, app_context: AppContext | None = None) -> SuggestionPolicy:
        app_context = app_context or AppContext()
        settings = self.database.get_settings()
        if not settings.assistant_enabled:
            return SuggestionPolicy(False, "assistant_off", settings.correction_strength)
        app_profile = self.database.get_app_profile(app_context.app_identifier)
        if app_profile and app_profile.assistant_status == "off":
            return SuggestionPolicy(False, "app_profile_off", app_profile.correction_strength)
        if self.sensitive_filter.should_disable(app_context):
            return SuggestionPolicy(False, "sensitive_context", settings.correction_strength)

        correction_strength = app_profile.correction_strength if app_profile else settings.correction_strength
        if app_profile and app_profile.assistant_status == "limited":
            correction_strength = "light"
            return SuggestionPolicy(True, "app_profile_limited", correction_strength)
        return SuggestionPolicy(True, "enabled", correction_strength)

    def accept(self, suggestion: Suggestion, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        if not self._learning_enabled(app_context):
            return
        self.database.record_correction_history(
            original_text=suggestion.original,
            corrected_text=suggestion.replacement,
            correction_type=suggestion.kind,
            confidence=suggestion.confidence,
            app_identifier=app_context.app_identifier,
            accepted=True,
        )
        self.database.record_accepted_suggestion(
            input_text=suggestion.original,
            suggestion_text=suggestion.replacement,
            suggestion_type=suggestion.kind,
            app_identifier=app_context.app_identifier,
        )
        self.database.increment_word_frequency(suggestion.replacement, app_context.app_identifier)

    def ignore(self, suggestion: Suggestion, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        if not self._learning_enabled(app_context):
            return
        self.database.record_ignored_suggestion(
            input_text=suggestion.original,
            suggestion_text=suggestion.replacement,
            suggestion_type=suggestion.kind,
            app_identifier=app_context.app_identifier,
        )

    def revert(self, original_text: str, corrected_text: str, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        if not self._learning_enabled(app_context):
            return
        latest = self.database.latest_correction()
        if latest and latest.original_text == original_text and latest.corrected_text == corrected_text:
            self.database.mark_correction_reverted(latest.id)
        self.database.record_reverted_correction(original_text, corrected_text, app_context.app_identifier)

    def observe_text(self, text: str, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        if not self._learning_enabled(app_context):
            return
        if self.sensitive_filter.should_disable(app_context):
            return
        context = extract_text_context(text)
        words = tuple(part for part in (*context.previous_words, context.current_word) if part)
        if not words:
            return
        frequency = self.database.increment_word_frequency(words[-1], app_context.app_identifier)
        if frequency >= 3 and _looks_like_personal_word(words[-1]):
            self.database.add_personal_word(words[-1], source="auto")
        for size in (2, 3, 4):
            if len(words) >= size:
                self.database.increment_phrase_frequency(" ".join(words[-size:]), app_context.app_identifier)

    def _learning_enabled(self, app_context: AppContext) -> bool:
        settings = self.database.get_settings()
        if not settings.learning_enabled:
            return False
        app_profile = self.database.get_app_profile(app_context.app_identifier)
        return app_profile.learning_enabled if app_profile else True


def _looks_like_personal_word(word: str) -> bool:
    return len(word) >= 3 and any(char.isupper() or char.isdigit() for char in word)
