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
            if score < min_confidence:
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
        score = candidate.base_confidence

        if candidate.source == "common_typos":
            score += 0.02
        if candidate.suggestion_type == "keyboard_slip":
            score += 0.02
        if candidate.suggestion_type in {"transposition", "edit_distance", "repeated_letter"}:
            score += 0.01
        if candidate.suggestion_type == "confusion_pair":
            score += 0.03 if candidate.metadata.get("context_hint") == "phrase" else 0.01
        if candidate.suggestion_type == "user_phrase_prediction":
            score += 0.04
        if candidate.suggestion_type == "phrase_prediction":
            score += 0.01

        score += _word_frequency_bonus(candidate.suggestion_text)
        score += _app_word_frequency_bonus(self.database, candidate.suggestion_text, app_context.app_identifier)
        score += min(self.database.accepted_score(candidate.original_text, candidate.suggestion_text), 0.08)
        score -= min(self.database.ignored_score(candidate.original_text, candidate.suggestion_text), 0.20)
        score -= min(self.database.reverted_score(candidate.original_text, candidate.suggestion_text), 0.20)

        if _has_real_word_risk(candidate):
            score -= 0.08

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


def _app_word_frequency_bonus(database: Database, text: str, app_identifier: str) -> float:
    if not app_identifier:
        return 0.0
    words = [part for part in text.split() if part]
    if not words:
        return 0.0
    best = max(database.word_frequency(word, app_identifier) for word in words)
    return min(best * 0.01, 0.03)


def _has_real_word_risk(candidate: Candidate) -> bool:
    original_words = {word.lower() for word in candidate.original_text.split()}
    suggestion_words = {word.lower().strip("'") for word in candidate.suggestion_text.split()}
    if candidate.suggestion_type == "confusion_pair":
        return True
    if candidate.metadata.get("category") in {"contextual", "suggest_only"}:
        return True
    return bool(original_words and original_words <= COMMON_WORDS and suggestion_words and suggestion_words <= COMMON_WORDS)


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
