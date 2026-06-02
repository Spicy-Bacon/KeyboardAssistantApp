from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
DATA_FILENAMES = (
    "common_typos.tsv",
    "contractions.tsv",
    "common_words.tsv",
    "confusion_sets.tsv",
    "common_phrases.tsv",
)


@dataclass(frozen=True)
class TypoRule:
    typo: str
    correction: str
    confidence: float


@dataclass(frozen=True)
class ContractionRule:
    input_text: str
    correction: str
    category: str
    confidence: float


@dataclass(frozen=True)
class ConfusionRule:
    wrong: str
    suggestion: str
    context_hint: str
    confidence: float


@dataclass(frozen=True)
class PhraseRule:
    prefix: str
    suggestion: str
    confidence: float


def _read_tsv(filename: str, expected_columns: int) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    raw_text = resources.files(__package__).joinpath(filename).read_text(encoding="utf-8")
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        parts = tuple(part.strip() for part in line.split("\t"))
        if len(parts) != expected_columns or any(part == "" for part in parts):
            raise ValueError(f"{filename}:{line_number} must have {expected_columns} tab-separated columns")
        rows.append(parts)
    return rows


def _float(value: str, filename: str, key: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{filename}:{key} confidence must be a number") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{filename}:{key} confidence must be between 0 and 1")
    return parsed


def _load_typo_rules() -> tuple[TypoRule, ...]:
    return tuple(
        TypoRule(typo.lower(), correction, _float(confidence, "common_typos.tsv", typo))
        for typo, correction, confidence in _read_tsv("common_typos.tsv", 3)
    )


def _load_contraction_rules() -> tuple[ContractionRule, ...]:
    allowed_categories = {"safe_auto", "contextual", "suggest_only"}
    rules: list[ContractionRule] = []
    for input_text, correction, category, confidence in _read_tsv("contractions.tsv", 4):
        if category not in allowed_categories:
            raise ValueError(f"contractions.tsv:{input_text} has unsupported category {category!r}")
        rules.append(
            ContractionRule(
                input_text.lower(),
                correction,
                category,
                _float(confidence, "contractions.tsv", input_text),
            )
        )
    return tuple(rules)


def _load_common_word_frequencies() -> dict[str, float]:
    frequencies: dict[str, float] = {}
    for word, frequency in _read_tsv("common_words.tsv", 2):
        try:
            parsed = float(frequency)
        except ValueError as exc:
            raise ValueError(f"common_words.tsv:{word} frequency_score must be numeric") from exc
        if parsed <= 0:
            raise ValueError(f"common_words.tsv:{word} frequency_score must be positive")
        frequencies[word.lower()] = parsed
    return frequencies


def _index_words_by_length(words: set[str]) -> dict[int, tuple[str, ...]]:
    by_length: dict[int, list[str]] = {}
    for word in words:
        by_length.setdefault(len(word), []).append(word)
    return {length: tuple(sorted(length_words)) for length, length_words in by_length.items()}


def _load_confusion_rules() -> tuple[ConfusionRule, ...]:
    return tuple(
        ConfusionRule(wrong.lower(), suggestion, context_hint.lower(), _float(confidence, "confusion_sets.tsv", wrong))
        for wrong, suggestion, context_hint, confidence in _read_tsv("confusion_sets.tsv", 4)
    )


def _load_phrase_rules() -> tuple[PhraseRule, ...]:
    return tuple(
        PhraseRule(prefix.lower(), suggestion, _float(confidence, "common_phrases.tsv", prefix))
        for prefix, suggestion, confidence in _read_tsv("common_phrases.tsv", 3)
    )


def _legacy_contextual_replacements(rules: tuple[ConfusionRule, ...]) -> dict[tuple[str, str], str]:
    replacements: dict[tuple[str, str], str] = {}
    for rule in rules:
        wrong_words = rule.wrong.split()
        suggestion_words = rule.suggestion.split()
        if len(wrong_words) != 2 or len(suggestion_words) != 2:
            continue
        if wrong_words[0] == suggestion_words[0] and wrong_words[1] != suggestion_words[1]:
            replacements[(wrong_words[0], wrong_words[1])] = suggestion_words[1]
        elif wrong_words[1] == suggestion_words[1] and wrong_words[0] != suggestion_words[0]:
            replacements[(wrong_words[0], wrong_words[1])] = suggestion_words[0]
    return replacements


def _legacy_next_word_fallbacks(rules: tuple[PhraseRule, ...]) -> dict[tuple[str, ...], str]:
    fallbacks: dict[tuple[str, ...], str] = {}
    for rule in rules:
        fallbacks.setdefault(tuple(rule.prefix.split()), rule.suggestion)
    return fallbacks


def _legacy_next_word_confidence(rules: tuple[PhraseRule, ...]) -> dict[tuple[str, ...], float]:
    confidence: dict[tuple[str, ...], float] = {}
    for rule in rules:
        confidence.setdefault(tuple(rule.prefix.split()), rule.confidence)
    return confidence


TYPO_RULES = _load_typo_rules()
TYPO_MAP = {rule.typo: rule.correction for rule in TYPO_RULES}
TYPO_CONFIDENCE = {rule.typo: rule.confidence for rule in TYPO_RULES}

CONTRACTION_RULES = _load_contraction_rules()
CONTRACTIONS = {rule.input_text: rule.correction for rule in CONTRACTION_RULES}
CONTRACTION_CATEGORIES = {rule.input_text: rule.category for rule in CONTRACTION_RULES}
CONTRACTION_CONFIDENCE = {rule.input_text: rule.confidence for rule in CONTRACTION_RULES}

COMMON_WORD_FREQUENCIES = _load_common_word_frequencies()
COMMON_WORDS = set(COMMON_WORD_FREQUENCIES)
COMMON_WORDS_BY_LENGTH = _index_words_by_length(COMMON_WORDS)

CONFUSION_RULES = _load_confusion_rules()
CONTEXTUAL_REPLACEMENTS = _legacy_contextual_replacements(CONFUSION_RULES)

PHRASE_RULES = _load_phrase_rules()
NEXT_WORD_FALLBACKS = _legacy_next_word_fallbacks(PHRASE_RULES)
NEXT_WORD_CONFIDENCE = _legacy_next_word_confidence(PHRASE_RULES)

DEFAULT_EXCLUDED_APP_HINTS = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windowsterminal.exe",
    "code.exe",
    "devenv.exe",
    "pycharm64.exe",
    "rider64.exe",
    "credentialuibroker.exe",
    "logonui.exe",
    "consent.exe",
}
