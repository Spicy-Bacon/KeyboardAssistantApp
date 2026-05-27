from __future__ import annotations

from keyboard_assistant.core.context import extract_text_context
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.data.defaults import CONTRACTIONS, CONTEXTUAL_REPLACEMENTS, TYPO_MAP
from keyboard_assistant.storage.database import Database


AUTO_APPLY_THRESHOLD = 0.92


class CorrectionEngine:
    """Fast local correction engine that does not depend on an LLM."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def suggest(self, text: str, app_context: AppContext | None = None) -> list[Suggestion]:
        app_context = app_context or AppContext()
        context = extract_text_context(text)
        candidates: list[Suggestion] = []

        if context.has_double_space:
            candidates.append(
                Suggestion(
                    original=text,
                    replacement=" ".join(text.split()),
                    kind="spacing",
                    confidence=0.94,
                    auto_apply=True,
                )
            )

        word = context.current_word
        if word:
            candidates.extend(self._word_suggestions(word, context.starts_new_sentence))

        candidates.extend(self._contextual_suggestions(context.previous_words, word))
        return self._rank(candidates, app_context)

    def _word_suggestions(self, word: str, starts_new_sentence: bool) -> list[Suggestion]:
        lower = word.lower()
        suggestions: list[Suggestion] = []

        if self.database.is_never_correct_word(word):
            return []

        if lower in TYPO_MAP:
            replacement = _match_case(word, TYPO_MAP[lower])
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement=replacement,
                    kind="typo",
                    confidence=0.96,
                    auto_apply=True,
                )
            )

        if lower in CONTRACTIONS:
            replacement = _match_case(word, CONTRACTIONS[lower])
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement=replacement,
                    kind="apostrophe",
                    confidence=0.95,
                    auto_apply=True,
                )
            )

        repeated = _collapse_repeated_letters(lower)
        if repeated != lower and repeated in TYPO_MAP.values():
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement=_match_case(word, repeated),
                    kind="repeated_character",
                    confidence=0.90,
                    auto_apply=False,
                )
            )

        if lower == "i":
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement="I",
                    kind="capitalization",
                    confidence=0.98,
                    auto_apply=True,
                )
            )
        elif starts_new_sentence and word[:1].islower() and not suggestions:
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement=word[:1].upper() + word[1:],
                    kind="capitalization",
                    confidence=0.88,
                    auto_apply=False,
                )
            )

        return suggestions

    def _contextual_suggestions(self, previous_words: tuple[str, ...], current_word: str) -> list[Suggestion]:
        if not previous_words or not current_word:
            return []
        previous = previous_words[-1].lower()
        key = (previous, current_word.lower())
        replacement = CONTEXTUAL_REPLACEMENTS.get(key)
        if not replacement:
            return []
        return [
            Suggestion(
                original=current_word,
                replacement=_match_case(current_word, replacement),
                kind="contextual",
                confidence=0.84,
                auto_apply=False,
            )
        ]

    def _rank(self, suggestions: list[Suggestion], app_context: AppContext) -> list[Suggestion]:
        adjusted: list[Suggestion] = []
        for suggestion in suggestions:
            score = suggestion.confidence
            score += min(self.database.accepted_score(suggestion.original, suggestion.replacement), 0.08)
            score -= min(self.database.ignored_score(suggestion.original, suggestion.replacement), 0.20)
            score = max(0.0, min(score, 1.0))
            adjusted.append(
                suggestion.with_confidence(
                    score,
                    auto_apply=suggestion.auto_apply and score >= AUTO_APPLY_THRESHOLD,
                )
            )

        adjusted.sort(key=lambda item: (item.confidence, item.kind), reverse=True)
        return adjusted[:3]


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _collapse_repeated_letters(word: str) -> str:
    if not word:
        return word
    result = [word[0]]
    repeat_count = 1
    for char in word[1:]:
        if char == result[-1]:
            repeat_count += 1
            if repeat_count <= 2:
                result.append(char)
        else:
            repeat_count = 1
            result.append(char)
    return "".join(result)
