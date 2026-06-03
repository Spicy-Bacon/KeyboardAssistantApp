from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "keyboard_assistant" / "data"

RISKY_DIRECT_TYPOS = {
    ("form", "from"),
    ("from", "form"),
    ("were", "we're"),
    ("well", "we'll"),
    ("ill", "I'll"),
    ("shell", "she'll"),
    ("hell", "he'll"),
    ("then", "than"),
    ("than", "then"),
}

OFFENSIVE_OR_SPAM_HINTS = {
    "casino",
    "crypto",
    "porn",
    "xxx",
}


@dataclass
class Finding:
    filename: str
    line_number: int
    category: str
    detail: str


@dataclass
class AuditSummary:
    counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    removed_rows: dict[str, int] = field(default_factory=dict)

    def add(self, filename: str, line_number: int, category: str, detail: str) -> None:
        self.findings.append(Finding(filename, line_number, category, detail))

    def count_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return counts


def audit_language_data(data_dir: Path = DATA_DIR) -> AuditSummary:
    summary = AuditSummary()
    common_words = _load_word_set(data_dir / "common_words.tsv")
    _audit_typos(data_dir / "common_typos.tsv", common_words, summary)
    _audit_common_words(data_dir / "common_words.tsv", summary)
    _audit_phrases(data_dir / "common_phrases.tsv", summary)
    _audit_confusion_sets(data_dir / "confusion_sets.tsv", summary)
    _audit_contractions(data_dir / "contractions.tsv", summary)
    return summary


def cleanup_obviously_unsafe(data_dir: Path = DATA_DIR) -> AuditSummary:
    summary = audit_language_data(data_dir)
    for filename, predicate in {
        "common_typos.tsv": _remove_typo_row,
        "common_phrases.tsv": _remove_phrase_row,
    }.items():
        path = data_dir / filename
        rows = path.read_text(encoding="utf-8").splitlines()
        kept: list[str] = []
        removed = 0
        for raw_line in rows:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                kept.append(raw_line)
                continue
            if predicate(stripped):
                removed += 1
                continue
            kept.append(raw_line)
        if removed:
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
            summary.removed_rows[filename] = removed
    return summary


def format_audit(summary: AuditSummary, example_limit: int = 20) -> str:
    lines = ["Language data quality audit:"]
    for filename, count in sorted(summary.counts.items()):
        lines.append(f"- {filename}: {count} rows")
    category_counts = summary.count_by_category()
    if category_counts:
        lines.append("Findings:")
        for category, count in sorted(category_counts.items()):
            lines.append(f"- {category}: {count}")
        lines.append("Examples:")
        for finding in summary.findings[:example_limit]:
            lines.append(f"- {finding.filename}:{finding.line_number}: {finding.category}: {finding.detail}")
    else:
        lines.append("Findings: none")
    if summary.removed_rows:
        lines.append("Removed rows:")
        for filename, count in sorted(summary.removed_rows.items()):
            lines.append(f"- {filename}: {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cleanup = "--cleanup" in argv
    data_args = [arg for arg in argv if arg != "--cleanup"]
    data_dir = Path(data_args[0]) if data_args else DATA_DIR
    summary = cleanup_obviously_unsafe(data_dir) if cleanup else audit_language_data(data_dir)
    print(format_audit(summary))
    return 0


def _audit_typos(path: Path, common_words: set[str], summary: AuditSummary) -> None:
    for line_number, parts in _iter_tsv(path, 3, summary):
        typo, correction, confidence = parts
        lower_typo = typo.lower()
        lower_correction = correction.lower()
        if (lower_typo, lower_correction) in {(a, b.lower()) for a, b in RISKY_DIRECT_TYPOS}:
            summary.add(path.name, line_number, "risky_direct_typo", f"{typo} -> {correction}")
        if lower_typo in common_words:
            summary.add(path.name, line_number, "typo_is_common_word", typo)
        if _similarity(lower_typo, lower_correction.strip("'")) < 0.30:
            summary.add(path.name, line_number, "low_edit_similarity", f"{typo} -> {correction}")
        if typo != lower_typo:
            summary.add(path.name, line_number, "typo_casing", typo)
        if _has_blocked_hint(typo) or _has_blocked_hint(correction):
            summary.add(path.name, line_number, "blocked_content_hint", f"{typo} -> {correction}")
        _flag_bad_confidence(path.name, line_number, confidence, summary)


def _audit_common_words(path: Path, summary: AuditSummary) -> None:
    for line_number, parts in _iter_tsv(path, 2, summary):
        word, score = parts
        if len(word) <= 1:
            summary.add(path.name, line_number, "very_short_word", word)
        if not re.fullmatch(r"[a-z][a-z'-]*", word):
            summary.add(path.name, line_number, "suspicious_word_token", word)
        if re.search(r"(.)\1{3,}", word):
            summary.add(path.name, line_number, "repeated_character_word", word)
        _flag_numeric_score(path.name, line_number, score, summary)


def _audit_phrases(path: Path, summary: AuditSummary) -> None:
    seen_rules: set[tuple[str, str]] = set()
    for line_number, parts in _iter_tsv(path, 3, summary):
        prefix, suggestion, confidence = parts
        if len(prefix.split()) > 4 or len(suggestion.split()) > 3:
            summary.add(path.name, line_number, "phrase_too_long", f"{prefix} -> {suggestion}")
        if suggestion.lower() in {"a", "an", "it", "the"} and len(prefix.split()) < 2:
            summary.add(path.name, line_number, "generic_low_value_phrase", f"{prefix} -> {suggestion}")
        rule_key = (prefix.lower(), suggestion.lower())
        if rule_key in seen_rules:
            summary.add(path.name, line_number, "duplicate_phrase_rule", f"{prefix} -> {suggestion}")
        else:
            seen_rules.add(rule_key)
        if _has_blocked_hint(prefix) or _has_blocked_hint(suggestion):
            summary.add(path.name, line_number, "blocked_content_hint", f"{prefix} -> {suggestion}")
        _flag_bad_confidence(path.name, line_number, confidence, summary)


def _audit_confusion_sets(path: Path, summary: AuditSummary) -> None:
    for line_number, parts in _iter_tsv(path, 4, summary):
        wrong, suggestion, context_hint, confidence = parts
        if len(wrong.split()) == 1 and context_hint in {"", "phrase"}:
            summary.add(path.name, line_number, "single_word_confusion_needs_context", f"{wrong} -> {suggestion}")
        if (wrong.lower(), suggestion.lower()) in {(a, b.lower()) for a, b in RISKY_DIRECT_TYPOS}:
            summary.add(path.name, line_number, "risky_confusion_pair", f"{wrong} -> {suggestion}")
        _flag_bad_confidence(path.name, line_number, confidence, summary)


def _audit_contractions(path: Path, summary: AuditSummary) -> None:
    protected_safe_auto = {"ill", "well", "were", "shell", "hell", "id"}
    for line_number, parts in _iter_tsv(path, 4, summary):
        input_text, correction, category, confidence = parts
        if input_text in protected_safe_auto and category == "safe_auto":
            summary.add(path.name, line_number, "dangerous_safe_auto_contraction", f"{input_text} -> {correction}")
        _flag_bad_confidence(path.name, line_number, confidence, summary)


def _iter_tsv(path: Path, expected_columns: int, summary: AuditSummary) -> list[tuple[int, tuple[str, ...]]]:
    rows: list[tuple[int, tuple[str, ...]]] = []
    valid_count = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        parts = tuple(part.strip() for part in line.split("\t"))
        if len(parts) != expected_columns:
            summary.add(path.name, line_number, "invalid_column_count", line)
            continue
        valid_count += 1
        rows.append((line_number, parts))
    summary.counts[path.name] = valid_count
    return rows


def _load_word_set(path: Path) -> set[str]:
    words: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts and parts[0]:
            words.add(parts[0].lower())
    return words


def _flag_bad_confidence(filename: str, line_number: int, value: str, summary: AuditSummary) -> None:
    try:
        confidence = float(value)
    except ValueError:
        summary.add(filename, line_number, "invalid_confidence", value)
        return
    if confidence < 0.0 or confidence > 1.0:
        summary.add(filename, line_number, "invalid_confidence", value)


def _flag_numeric_score(filename: str, line_number: int, value: str, summary: AuditSummary) -> None:
    try:
        float(value)
    except ValueError:
        summary.add(filename, line_number, "invalid_numeric_score", value)


def _remove_typo_row(line: str) -> bool:
    parts = tuple(part.strip() for part in line.split("\t"))
    if len(parts) != 3:
        return True
    typo, correction, confidence = parts
    if typo.lower() == correction.lower():
        return True
    if (typo.lower(), correction.lower()) in {(a, b.lower()) for a, b in RISKY_DIRECT_TYPOS}:
        return True
    if _has_blocked_hint(typo) or _has_blocked_hint(correction):
        return True
    try:
        parsed = float(confidence)
    except ValueError:
        return True
    return parsed < 0.0 or parsed > 1.0


def _remove_phrase_row(line: str) -> bool:
    parts = tuple(part.strip() for part in line.split("\t"))
    if len(parts) != 3:
        return True
    prefix, suggestion, confidence = parts
    if len(prefix.split()) > 6 or len(suggestion.split()) > 4:
        return True
    if _has_blocked_hint(prefix) or _has_blocked_hint(suggestion):
        return True
    try:
        parsed = float(confidence)
    except ValueError:
        return True
    return parsed < 0.0 or parsed > 1.0


def _has_blocked_hint(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in OFFENSIVE_OR_SPAM_HINTS)


def _similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    distance = _edit_distance(left, right)
    return 1.0 - (distance / max(len(left), len(right), 1))


def _edit_distance(left: str, right: str) -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
