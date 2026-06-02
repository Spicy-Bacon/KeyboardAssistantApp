from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from keyboard_assistant.core.context import extract_text_context
from keyboard_assistant.core.models import AppContext
from keyboard_assistant.data.defaults import (
    COMMON_WORD_FREQUENCIES,
    COMMON_WORDS,
    CONFUSION_RULES,
    CONTRACTION_CATEGORIES,
    CONTRACTION_CONFIDENCE,
    CONTRACTIONS,
    NEXT_WORD_CONFIDENCE,
    NEXT_WORD_FALLBACKS,
    TYPO_CONFIDENCE,
    TYPO_MAP,
)
from keyboard_assistant.storage.database import Database


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

PROPER_CASE_WORDS = {
    "chatgpt": "ChatGPT",
    "ebay": "eBay",
    "exeter": "Exeter",
    "iphone": "iPhone",
    "macos": "macOS",
}
SAFE_AUTO_CONFUSION_PHRASES = {"should of", "could of", "would of"}


@dataclass(frozen=True)
class Candidate:
    original_text: str
    suggestion_text: str
    suggestion_type: str
    base_confidence: float
    source: str
    should_auto_apply: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class CandidateGenerator:
    """Fast deterministic candidate generation without local AI calls."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def generate(self, text: str, app_context: AppContext | None = None) -> list[Candidate]:
        app_context = app_context or AppContext()
        context = extract_text_context(text)
        word = context.current_word
        at_word_boundary = bool(text and text[-1].isspace())
        candidates: list[Candidate] = []

        if word and not at_word_boundary:
            can_capitalize_sentence_start = context.starts_new_sentence and bool(context.previous_words)
            candidates.extend(self._word_candidates(word, can_capitalize_sentence_start))
            candidates.extend(self._confusion_candidates((*context.previous_words, word)))

        if at_word_boundary:
            completed_words = tuple(part for part in (*context.previous_words, word) if part)
            candidates.extend(self._phrase_candidates(completed_words, app_context))
            candidates.extend(self._confusion_candidates(completed_words))

        return _dedupe_candidates(candidates)

    def _word_candidates(self, word: str, starts_new_sentence: bool) -> list[Candidate]:
        lower = word.lower()
        candidates: list[Candidate] = []

        if self.database.is_never_correct_word(word):
            return []

        if lower in TYPO_MAP:
            confidence = TYPO_CONFIDENCE.get(lower, 0.96)
            candidates.append(
                Candidate(
                    original_text=word,
                    suggestion_text=_match_case(word, TYPO_MAP[lower]),
                    suggestion_type="typo",
                    base_confidence=confidence,
                    source="common_typos",
                    should_auto_apply=confidence >= 0.90,
                    metadata={"match": "exact"},
                )
            )

        if lower in CONTRACTIONS:
            category = CONTRACTION_CATEGORIES.get(lower, "suggest_only")
            candidates.append(
                Candidate(
                    original_text=word,
                    suggestion_text=_match_case(word, CONTRACTIONS[lower]),
                    suggestion_type="contraction",
                    base_confidence=CONTRACTION_CONFIDENCE.get(lower, 0.95),
                    source="contractions",
                    should_auto_apply=category == "safe_auto",
                    metadata={"category": category},
                )
            )

        repeated = _collapse_repeated_letters(lower)
        if repeated != lower and repeated in COMMON_WORDS:
            candidates.append(
                Candidate(
                    original_text=word,
                    suggestion_text=_match_case(word, repeated),
                    suggestion_type="repeated_letter",
                    base_confidence=0.88,
                    source="repeated_letter_rule",
                    should_auto_apply=False,
                    metadata={"collapsed": repeated},
                )
            )

        if not candidates:
            candidates.extend(_capitalization_candidates(word, starts_new_sentence=False))

        if not candidates and word.islower() and _looks_like_correctable_word(lower):
            fuzzy = _best_fuzzy_word(lower)
            if fuzzy:
                replacement, confidence, suggestion_type = fuzzy
                candidates.append(
                    Candidate(
                        original_text=word,
                        suggestion_text=_match_case(word, replacement),
                        suggestion_type=suggestion_type,
                        base_confidence=confidence,
                        source="common_words",
                        should_auto_apply=False,
                        metadata={"frequency": COMMON_WORD_FREQUENCIES.get(replacement, 0)},
                    )
                )

        if not candidates:
            candidates.extend(_capitalization_candidates(word, starts_new_sentence))

        return candidates

    def _confusion_candidates(self, words: tuple[str, ...]) -> list[Candidate]:
        if not words:
            return []
        lowered = tuple(word.lower() for word in words)
        candidates: list[Candidate] = []
        for rule in CONFUSION_RULES:
            wrong_words = tuple(rule.wrong.split())
            if len(wrong_words) > len(lowered):
                continue
            for start in range(0, len(lowered) - len(wrong_words) + 1):
                end = start + len(wrong_words)
                if lowered[start:end] != wrong_words:
                    continue
                if len(wrong_words) == 1 and not _context_hint_matches(
                    rule.context_hint,
                    tuple((*lowered[:start], *lowered[end:])),
                ):
                    continue
                is_suffix = end == len(lowered)
                original_text, suggestion_text = _confusion_replacement_texts(
                    words[start:end],
                    tuple(rule.suggestion.split()),
                    suffix_match=is_suffix,
                )
                safe_phrase = is_suffix and rule.wrong in SAFE_AUTO_CONFUSION_PHRASES
                candidates.append(
                    Candidate(
                        original_text=original_text,
                        suggestion_text=suggestion_text,
                        suggestion_type="confusion_pair",
                        base_confidence=rule.confidence,
                        source="confusion_sets",
                        should_auto_apply=safe_phrase,
                        metadata={
                            "context_hint": rule.context_hint,
                            "safe_phrase": safe_phrase,
                            "suffix_match": is_suffix,
                        },
                    )
                )
        return candidates

    def _phrase_candidates(self, words: tuple[str, ...], app_context: AppContext) -> list[Candidate]:
        if not words:
            return []
        candidates: list[Candidate] = []
        user_predictions = self.database.phrase_predictions(words, app_context.app_identifier)
        for index, prediction in enumerate(user_predictions):
            candidates.append(
                Candidate(
                    original_text="",
                    suggestion_text=prediction,
                    suggestion_type="user_phrase_prediction",
                    base_confidence=max(0.90 - (index * 0.05), 0.70),
                    source="user_phrase_history",
                    should_auto_apply=False,
                    metadata={"rank": index},
                )
            )

        for size in range(min(3, len(words)), 0, -1):
            prefix = tuple(word.lower() for word in words[-size:])
            prediction = NEXT_WORD_FALLBACKS.get(prefix)
            if not prediction:
                continue
            candidates.append(
                Candidate(
                    original_text="",
                    suggestion_text=prediction,
                    suggestion_type="phrase_prediction",
                    base_confidence=NEXT_WORD_CONFIDENCE.get(prefix, 0.72),
                    source="common_phrases",
                    should_auto_apply=False,
                    metadata={"prefix": " ".join(prefix)},
                )
            )
            break
        return candidates


def _dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Candidate] = []
    for candidate in candidates:
        key = (candidate.original_text.lower(), candidate.suggestion_text.lower(), candidate.suggestion_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


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


def _is_plain_lowercase_word(word: str) -> bool:
    return len(word) > 1 and word.isalpha() and word.islower()


def _capitalization_candidates(word: str, starts_new_sentence: bool) -> list[Candidate]:
    lower = word.lower()
    if lower == "i":
        return [
            Candidate(
                original_text=word,
                suggestion_text="I",
                suggestion_type="capitalization",
                base_confidence=0.98,
                source="capitalization_rule",
                should_auto_apply=True,
                metadata={"rule": "standalone_i"},
            )
        ]
    if not _is_plain_lowercase_word(word):
        return []
    proper_case = PROPER_CASE_WORDS.get(lower)
    if proper_case and proper_case != word:
        return [
            Candidate(
                original_text=word,
                suggestion_text=proper_case,
                suggestion_type="capitalization",
                base_confidence=0.90,
                source="capitalization_rule",
                should_auto_apply=False,
                metadata={"rule": "proper_case"},
            )
        ]
    if starts_new_sentence:
        return [
            Candidate(
                original_text=word,
                suggestion_text=word[:1].upper() + word[1:],
                suggestion_type="capitalization",
                base_confidence=0.93,
                source="capitalization_rule",
                should_auto_apply=True,
                metadata={"rule": "sentence_start"},
            )
        ]
    return []


def _best_fuzzy_word(word: str) -> tuple[str, float, str] | None:
    candidates: list[tuple[str, float, str]] = []
    for known_word in COMMON_WORDS:
        if abs(len(known_word) - len(word)) > 1:
            continue
        if len(known_word) == len(word):
            if _is_transposition(word, known_word):
                candidates.append((known_word, 0.87, "transposition"))
            elif _is_keyboard_neighbor_substitution(word, known_word):
                candidates.append((known_word, 0.86, "keyboard_slip"))
        elif _is_single_insert_or_delete(word, known_word):
            candidates.append((known_word, 0.84, "edit_distance"))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], COMMON_WORD_FREQUENCIES.get(item[0], 0), -len(item[0])), reverse=True)
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


def _context_hint_matches(context_hint: str, words: tuple[str, ...]) -> bool:
    if not context_hint or context_hint == "phrase":
        return True
    hints = {part.strip().lower() for chunk in context_hint.split("|") for part in chunk.split(",") if part.strip()}
    if not hints:
        return False
    context_words = set(words)
    return bool(hints & context_words)


def _confusion_replacement_texts(
    original_words: tuple[str, ...],
    suggestion_words: tuple[str, ...],
    suffix_match: bool,
) -> tuple[str, str]:
    if suffix_match or len(original_words) != len(suggestion_words):
        return " ".join(original_words), " ".join(suggestion_words)

    changed_indexes = [
        index
        for index, (original, suggestion) in enumerate(zip(original_words, suggestion_words))
        if original.lower() != suggestion.lower()
    ]
    if len(changed_indexes) != 1:
        return " ".join(original_words), " ".join(suggestion_words)
    changed_index = changed_indexes[0]
    return original_words[changed_index], _match_case(original_words[changed_index], suggestion_words[changed_index])
