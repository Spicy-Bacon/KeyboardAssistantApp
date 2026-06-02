from __future__ import annotations

from keyboard_assistant.core.candidate_generator import CandidateGenerator
from keyboard_assistant.core.context import extract_text_context
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.core.suggestion_ranker import SuggestionRanker
from keyboard_assistant.storage.database import Database


class CorrectionEngine:
    """Fast local correction engine that does not depend on an LLM."""

    def __init__(self, database: Database) -> None:
        self.candidate_generator = CandidateGenerator(database)
        self.suggestion_ranker = SuggestionRanker(database)

    def suggest(
        self,
        text: str,
        app_context: AppContext | None = None,
        correction_strength: str = "balanced",
    ) -> list[Suggestion]:
        app_context = app_context or AppContext()
        context = extract_text_context(text)
        suggestions: list[Suggestion] = []

        if context.has_double_space:
            suggestions.append(
                Suggestion(
                    original=text,
                    replacement=" ".join(text.split()),
                    kind="spacing",
                    confidence=0.94,
                    auto_apply=True,
                )
            )

        suggestions.extend(
            self.suggestion_ranker.rank(
                self.candidate_generator.generate(text, app_context),
                app_context=app_context,
                correction_strength=correction_strength,
            )
        )
        return suggestions[:3]
