from __future__ import annotations

from keyboard_assistant.core.candidate_generator import Candidate
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.data.defaults import COMMON_WORDS, COMMON_WORD_FREQUENCIES
from keyboard_assistant.storage.database import Database


AUTO_APPLY_THRESHOLDS = {
    "light": 1.01,
    "balanced": 0.92,
    "aggressive": 0.84,
}

MIN_SUGGESTION_CONFIDENCE = {
    "light": 0.86,
    "balanced": 0.72,
    "aggressive": 0.60,
}

KIND_MAP = {
    "contraction": "apostrophe",
    "repeated_letter": "repeated_character",
    "keyboard_slip": "keyboard_neighbor",
    "confusion_pair": "contextual",
    "phrase_prediction": "next_word",
    "user_phrase_prediction": "next_word",
}

SOURCE_BONUSES = {
    "common_typos": 0.02,
    "contractions": 0.01,
    "confusion_sets_phrase": 0.03,
    "confusion_sets_context": 0.01,
    "common_phrases": 0.01,
    "user_phrase_history": 0.04,
}

TYPE_BONUSES = {
    "keyboard_slip": 0.02,
    "transposition": 0.01,
    "edit_distance": 0.01,
    "repeated_letter": 0.01,
}


class SuggestionRanker:
    """Scores deterministic candidates with conservative auto-apply rules."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def rank(
        self,
        candidates: list[Candidate],
        app_context: AppContext | None = None,
        correction_strength: str = "balanced",
    ) -> list[Suggestion]:
        app_context = app_context or AppContext()
        min_confidence = MIN_SUGGESTION_CONFIDENCE.get(
            correction_strength,
            MIN_SUGGESTION_CONFIDENCE["balanced"],
        )
        ranked: list[tuple[float, Candidate]] = []
        for candidate in candidates:
            score = self._score(candidate, app_context)
            if score < _candidate_min_confidence(candidate, min_confidence):
                continue
            ranked.append((score, candidate))

        ranked.sort(
            key=lambda item: (
                item[0],
                _source_priority(item[1]),
                item[1].base_confidence,
                item[1].suggestion_text.lower(),
            ),
            reverse=True,
        )
        return [
            self._to_suggestion(candidate, score, correction_strength)
            for score, candidate in ranked[:3]
        ]

    def _score(self, candidate: Candidate, app_context: AppContext) -> float:
        # Keep the formula additive and bounded so new data can improve ranking
        # without making ambiguous real-word corrections auto-apply.
        score = candidate.base_confidence
        score += _source_bonus(candidate)
        score += TYPE_BONUSES.get(candidate.suggestion_type, 0.0)
        score += _edit_closeness_bonus(candidate)
        score += _word_frequency_bonus(candidate.suggestion_text)
        score += _app_word_frequency_bonus(self.database, candidate.suggestion_text, app_context.app_identifier)
        score += min(self.database.accepted_score(candidate.original_text, candidate.suggestion_text), 0.08)
        score -= min(self.database.ignored_score(candidate.original_text, candidate.suggestion_text), 0.20)
        score -= min(self.database.reverted_score(candidate.original_text, candidate.suggestion_text), 0.20)

        score -= _real_word_risk_penalty(candidate)

        return max(0.0, min(score, 1.0))

    def _to_suggestion(self, candidate: Candidate, score: float, correction_strength: str) -> Suggestion:
        auto_threshold = AUTO_APPLY_THRESHOLDS.get(correction_strength, AUTO_APPLY_THRESHOLDS["balanced"])
        auto_apply = (
            candidate.should_auto_apply
            and not _has_real_word_risk(candidate)
            and score >= auto_threshold
        )
        return Suggestion(
            original=candidate.original_text,
            replacement=candidate.suggestion_text,
            kind=KIND_MAP.get(candidate.suggestion_type, candidate.suggestion_type),
            confidence=score,
            auto_apply=auto_apply,
        )


def _word_frequency_bonus(text: str) -> float:
    words = [part.lower() for part in text.split() if part]
    if not words:
        return 0.0
    best = max(COMMON_WORD_FREQUENCIES.get(word, 0) for word in words)
    return min(best / 10000 * 0.04, 0.04)


def _source_bonus(candidate: Candidate) -> float:
    if candidate.suggestion_type == "confusion_pair":
        return (
            SOURCE_BONUSES["confusion_sets_phrase"]
            if candidate.metadata.get("context_hint") == "phrase"
            else SOURCE_BONUSES["confusion_sets_context"]
        )
    return SOURCE_BONUSES.get(candidate.source, 0.0)


def _edit_closeness_bonus(candidate: Candidate) -> float:
    original_words = candidate.original_text.split()
    suggestion_words = candidate.suggestion_text.split()
    if len(original_words) != 1 or len(suggestion_words) != 1:
        return 0.0
    original = original_words[0].lower()
    suggestion = suggestion_words[0].lower().strip("'")
    if not original.isalpha() or not suggestion.isalpha():
        return 0.0
    distance = _edit_distance(original, suggestion)
    if distance > 2:
        return 0.0
    closeness = 1.0 - (distance / max(len(original), len(suggestion), 1))
    return min(max(closeness, 0.0) * 0.015, 0.015)


def _app_word_frequency_bonus(database: Database, text: str, app_identifier: str) -> float:
    if not app_identifier:
        return 0.0
    words = [part for part in text.split() if part]
    if not words:
        return 0.0
    best = max(database.word_frequency(word, app_identifier) for word in words)
    return min(best * 0.01, 0.03)


def _candidate_min_confidence(candidate: Candidate, default_minimum: float) -> float:
    if candidate.suggestion_type == "contraction" and candidate.metadata.get("category") in {
        "contextual",
        "suggest_only",
    }:
        return min(default_minimum, 0.62)
    return default_minimum


def _real_word_risk_penalty(candidate: Candidate) -> float:
    if candidate.suggestion_type == "contraction":
        return 0.0
    return 0.08 if _has_real_word_risk(candidate) else 0.0


def _has_real_word_risk(candidate: Candidate) -> bool:
    if candidate.suggestion_type == "capitalization":
        return False
    original_words = {word.lower() for word in candidate.original_text.split()}
    suggestion_words = {word.lower().strip("'") for word in candidate.suggestion_text.split()}
    if candidate.suggestion_type == "confusion_pair":
        return True
    if candidate.metadata.get("category") in {"contextual", "suggest_only"}:
        return True
    return bool(original_words and original_words <= COMMON_WORDS and suggestion_words and suggestion_words <= COMMON_WORDS)


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[right_index - 1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _source_priority(candidate: Candidate) -> int:
    priorities = {
        "user_phrase_history": 80,
        "common_typos": 70,
        "contractions": 65,
        "confusion_sets": 55,
        "common_words": 45,
        "common_phrases": 35,
        "capitalization_rule": 30,
        "repeated_letter_rule": 25,
    }
    return priorities.get(candidate.source, 0)
