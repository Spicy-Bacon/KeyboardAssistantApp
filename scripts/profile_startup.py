from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def measure_startup() -> dict[str, float]:
    metrics: dict[str, float] = {}

    started = time.perf_counter()
    from keyboard_assistant.data import defaults

    metrics["data_import_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    from keyboard_assistant.core.assistant import KeyboardAssistant
    from keyboard_assistant.storage.database import Database

    metrics["core_import_seconds"] = time.perf_counter() - started

    with tempfile.TemporaryDirectory() as tempdir:
        started = time.perf_counter()
        database = Database(Path(tempdir) / "profile.sqlite3")
        database.initialize()
        metrics["database_initialize_seconds"] = time.perf_counter() - started

        started = time.perf_counter()
        assistant = KeyboardAssistant(database)
        metrics["assistant_initialize_seconds"] = time.perf_counter() - started

        started = time.perf_counter()
        assistant.suggest("teh")
        metrics["suggest_typo_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    for _ in range(10_000):
        defaults.TYPO_MAP.get("teh")
    metrics["typo_lookup_10k_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    for _ in range(10_000):
        defaults.NEXT_WORD_FALLBACKS.get(("thank",))
    metrics["phrase_lookup_10k_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    for _ in range(10_000):
        defaults.COMMON_WORD_FREQUENCIES.get("receive")
    metrics["word_frequency_lookup_10k_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    for _ in range(10_000):
        defaults.CONFUSION_RULES_BY_FIRST_WORD.get("your")
    metrics["confusion_lookup_10k_seconds"] = time.perf_counter() - started

    return metrics


def format_metrics(metrics: dict[str, float]) -> str:
    lines = ["Startup/profile metrics:"]
    for key in sorted(metrics):
        lines.append(f"- {key}: {metrics[key]:.6f}s")
    return "\n".join(lines)


def main() -> int:
    print(format_metrics(measure_startup()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
