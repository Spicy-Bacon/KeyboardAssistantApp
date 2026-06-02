from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "keyboard_assistant" / "data"
ALLOWED_CONTRACTION_CATEGORIES = {"safe_auto", "suggest_only", "contextual"}


@dataclass(frozen=True)
class FileSpec:
    filename: str
    columns: int
    unique_key_columns: tuple[int, ...]


@dataclass
class ValidationSummary:
    counts: dict[str, int] = field(default_factory=dict)
    duplicate_count: int = 0
    invalid_row_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


SPECS = {
    "common_typos.tsv": FileSpec("common_typos.tsv", 3, (0,)),
    "common_words.tsv": FileSpec("common_words.tsv", 2, (0,)),
    "common_phrases.tsv": FileSpec("common_phrases.tsv", 3, (0, 1)),
    "confusion_sets.tsv": FileSpec("confusion_sets.tsv", 4, (0, 1)),
    "contractions.tsv": FileSpec("contractions.tsv", 4, (0,)),
}

SUMMARY_LABELS = {
    "common_typos.tsv": "typos",
    "common_words.tsv": "words",
    "common_phrases.tsv": "phrases",
    "confusion_sets.tsv": "confusion_rules",
    "contractions.tsv": "contractions",
}


def validate_language_data(data_dir: Path = DATA_DIR) -> ValidationSummary:
    summary = ValidationSummary()
    for spec in SPECS.values():
        _validate_file(data_dir, spec, summary)
    return summary


def format_summary(summary: ValidationSummary) -> str:
    lines = ["Language data validation summary:"]
    for filename in SPECS:
        label = SUMMARY_LABELS[filename]
        lines.append(f"- {label}: {summary.counts.get(filename, 0)}")
    lines.append(f"- duplicates: {summary.duplicate_count}")
    lines.append(f"- invalid_rows: {summary.invalid_row_count}")
    if summary.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in summary.errors)
    else:
        lines.append("OK")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    data_dir = Path(argv[0]) if argv else DATA_DIR
    summary = validate_language_data(data_dir)
    print(format_summary(summary))
    return 0 if summary.ok else 1


def _validate_file(data_dir: Path, spec: FileSpec, summary: ValidationSummary) -> None:
    path = data_dir / spec.filename
    if not path.exists():
        summary.invalid_row_count += 1
        summary.errors.append(f"{spec.filename}: file is missing")
        summary.counts[spec.filename] = 0
        return

    seen: set[tuple[str, ...]] = set()
    valid_rows = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        parts = tuple(part.strip() for part in line.split("\t"))
        row_errors = _validate_row(spec.filename, line_number, parts, spec.columns)
        if row_errors:
            summary.invalid_row_count += 1
            summary.errors.extend(row_errors)
            continue

        key = tuple(parts[index].lower() for index in spec.unique_key_columns)
        if key in seen:
            summary.duplicate_count += 1
            summary.errors.append(f"{spec.filename}:{line_number}: duplicate key {key!r}")
            continue
        seen.add(key)
        valid_rows += 1

    summary.counts[spec.filename] = valid_rows


def _validate_row(filename: str, line_number: int, parts: tuple[str, ...], expected_columns: int) -> list[str]:
    errors: list[str] = []
    if len(parts) != expected_columns:
        return [f"{filename}:{line_number}: expected {expected_columns} tab-separated columns, got {len(parts)}"]
    if any(part == "" for part in parts):
        errors.append(f"{filename}:{line_number}: required fields must not be empty")

    if filename == "common_typos.tsv":
        typo, correction, confidence = parts
        if typo.lower() == correction.lower():
            errors.append(f"{filename}:{line_number}: typo must differ from correction")
        errors.extend(_confidence_errors(filename, line_number, confidence))
    elif filename == "common_words.tsv":
        errors.extend(_numeric_score_errors(filename, line_number, parts[1]))
    elif filename == "common_phrases.tsv":
        errors.extend(_confidence_errors(filename, line_number, parts[2]))
    elif filename == "confusion_sets.tsv":
        errors.extend(_confidence_errors(filename, line_number, parts[3]))
    elif filename == "contractions.tsv":
        category = parts[2]
        if category not in ALLOWED_CONTRACTION_CATEGORIES:
            errors.append(f"{filename}:{line_number}: unsupported category {category!r}")
        errors.extend(_confidence_errors(filename, line_number, parts[3]))
    return errors


def _confidence_errors(filename: str, line_number: int, value: str) -> list[str]:
    try:
        confidence = float(value)
    except ValueError:
        return [f"{filename}:{line_number}: confidence must be a number"]
    if confidence < 0.0 or confidence > 1.0:
        return [f"{filename}:{line_number}: confidence must be between 0 and 1"]
    return []


def _numeric_score_errors(filename: str, line_number: int, value: str) -> list[str]:
    try:
        float(value)
    except ValueError:
        return [f"{filename}:{line_number}: frequency_score must be numeric"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
