from __future__ import annotations

from keyboard_assistant.core.correction_engine import CorrectionEngine
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.privacy.sensitive_context import SensitiveContextFilter
from keyboard_assistant.storage.database import Database


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
        app_context = app_context or AppContext()
        if self.sensitive_filter.should_disable(app_context):
            return []
        return self.correction_engine.suggest(text, app_context=app_context)

    def accept(self, suggestion: Suggestion, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        self.database.record_accepted_suggestion(
            input_text=suggestion.original,
            suggestion_text=suggestion.replacement,
            suggestion_type=suggestion.kind,
            app_identifier=app_context.app_identifier,
        )
        self.database.increment_word_frequency(suggestion.replacement, app_context.app_identifier)

    def ignore(self, suggestion: Suggestion, app_context: AppContext | None = None) -> None:
        app_context = app_context or AppContext()
        self.database.record_ignored_suggestion(
            input_text=suggestion.original,
            suggestion_text=suggestion.replacement,
            suggestion_type=suggestion.kind,
            app_identifier=app_context.app_identifier,
        )

