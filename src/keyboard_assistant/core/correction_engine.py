from __future__ import annotations

from keyboard_assistant.core.candidate_generator import CandidateGenerator
from keyboard_assistant.core.context import extract_text_context
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.core.suggestion_ranker import SuggestionRanker
from keyboard_assistant.data.defaults import (
    COMMON_WORDS,
    CONTRACTION_CATEGORIES,
    CONTRACTION_CONFIDENCE,
    CONTRACTIONS,
    CONTEXTUAL_REPLACEMENTS,
    TYPO_CONFIDENCE,
    TYPO_MAP,
)
from keyboard_assistant.storage.database import Database


AUTO_APPLY_THRESHOLDS = {
    "light": 0.98,
    "balanced": 0.92,
    "aggressive": 0.84,
}

MIN_SUGGESTION_CONFIDENCE = {
    "light": 0.86,
    "balanced": 0.72,
    "aggressive": 0.60,
}

KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
KEYBOARD_NEIGHBORS = {
    key: {
        other
        for other_row_index, other_row in enumerate(KEYBOARD_ROWS)
        for other_col_index, other in enumerate(other_row)
        if other != key and abs(other_row_index - row_index) <= 1 and abs(other_col_index - col_index) <= 1
    }
    for row_index, row in enumerate(KEYBOARD_ROWS)
    for col_index, key in enumerate(row)
}


class CorrectionEngine:
    """Fast local correction engine that does not depend on an LLM."""

    def __init__(self, database: Database) -> None:
        self.database = database
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
                    confidence=TYPO_CONFIDENCE.get(lower, 0.96),
                    auto_apply=True,
                )
            )

        if lower in CONTRACTIONS:
            replacement = _match_case(word, CONTRACTIONS[lower])
            category = CONTRACTION_CATEGORIES.get(lower, "safe")
            suggestions.append(
                Suggestion(
                    original=word,
                    replacement=replacement,
                    kind="apostrophe",
                    confidence=CONTRACTION_CONFIDENCE.get(lower, 0.95),
                    auto_apply=category == "safe_auto",
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

        if not suggestions and _looks_like_correctable_word(lower):
            fuzzy = _best_fuzzy_word(lower)
            if fuzzy:
                replacement, confidence, kind = fuzzy
                suggestions.append(
                    Suggestion(
                        original=word,
                        replacement=_match_case(word, replacement),
                        kind=kind,
                        confidence=confidence,
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

    def _phrase_predictions(self, previous_words: tuple[str, ...], app_context: AppContext) -> list[Suggestion]:
        predictions = self.database.phrase_predictions(previous_words, app_context.app_identifier)
        return [
            Suggestion(
                original="",
                replacement=prediction,
                kind="next_word",
                confidence=max(0.82 - (index * 0.05), 0.65),
                auto_apply=False,
            )
            for index, prediction in enumerate(predictions)
        ]

    def _rank(
        self,
        suggestions: list[Suggestion],
        app_context: AppContext,
        correction_strength: str,
    ) -> list[Suggestion]:
        adjusted: list[Suggestion] = []
        auto_threshold = AUTO_APPLY_THRESHOLDS.get(correction_strength, AUTO_APPLY_THRESHOLDS["balanced"])
        min_confidence = MIN_SUGGESTION_CONFIDENCE.get(
            correction_strength,
            MIN_SUGGESTION_CONFIDENCE["balanced"],
        )
        for suggestion in suggestions:
            score = suggestion.confidence
            score += min(self.database.accepted_score(suggestion.original, suggestion.replacement), 0.08)
            score -= min(self.database.ignored_score(suggestion.original, suggestion.replacement), 0.20)
            score = max(0.0, min(score, 1.0))
            if score < min_confidence:
                continue
            adjusted.append(
                suggestion.with_confidence(
                    score,
                    auto_apply=suggestion.auto_apply and score >= auto_threshold,
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


def _looks_like_correctable_word(word: str) -> bool:
    return 3 <= len(word) <= 18 and word.isalpha() and word not in COMMON_WORDS


def _best_fuzzy_word(word: str) -> tuple[str, float, str] | None:
    candidates: list[tuple[str, float, str]] = []
    for known_word in COMMON_WORDS:
        if abs(len(known_word) - len(word)) > 1:
            continue
        if len(known_word) == len(word):
            if _is_transposition(word, known_word):
                candidates.append((known_word, 0.87, "transposition"))
            elif _is_keyboard_neighbor_substitution(word, known_word):
                candidates.append((known_word, 0.86, "keyboard_neighbor"))
        elif _is_single_insert_or_delete(word, known_word):
            candidates.append((known_word, 0.84, "edit_distance"))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], _word_frequency_hint(item[0]), -len(item[0])), reverse=True)
    return candidates[0]


def _is_transposition(word: str, known_word: str) -> bool:
    differences = [index for index, char in enumerate(word) if char != known_word[index]]
    if len(differences) != 2:
        return False
    first, second = differences
    return second == first + 1 and word[first] == known_word[second] and word[second] == known_word[first]


def _is_keyboard_neighbor_substitution(word: str, known_word: str) -> bool:
    differences = [(typed, expected) for typed, expected in zip(word, known_word) if typed != expected]
    if len(differences) != 1:
        return False
    typed, expected = differences[0]
    return typed in KEYBOARD_NEIGHBORS.get(expected, set())


def _is_single_insert_or_delete(word: str, known_word: str) -> bool:
    shorter, longer = (word, known_word) if len(word) < len(known_word) else (known_word, word)
    if len(longer) - len(shorter) != 1:
        return False
    short_index = 0
    edits = 0
    for char in longer:
        if short_index < len(shorter) and shorter[short_index] == char:
            short_index += 1
        else:
            edits += 1
            if edits > 1:
                return False
    return True


def _word_frequency_hint(word: str) -> int:
    common_order = (
        "the",
        "and",
        "you",
        "that",
        "for",
        "with",
        "this",
        "have",
        "not",
        "are",
        "about",
        "because",
        "please",
        "would",
        "should",
    )
    try:
        return len(common_order) - common_order.index(word)
    except ValueError:
        return 0
