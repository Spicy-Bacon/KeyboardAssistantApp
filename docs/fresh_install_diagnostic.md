# Fresh Install Diagnostic

## What already works

- The project has a clear local-first structure: core correction logic, local data, SQLite learning, optional local AI, Windows runtime/platform code, and deterministic tests.
- The correction engine already handles exact typo replacements, missing apostrophes, repeated-character cleanup, fuzzy single-edit corrections, keyboard-neighbour slips, transpositions, spacing cleanup, and learned phrase predictions.
- Current workspace already includes later-phase scaffolding (`CandidateGenerator`, `SuggestionRanker`, and TSV language data), so the next phases should audit and harden those pieces instead of duplicating them.
- The assistant policy correctly suppresses suggestions when the global assistant is off, an app profile is off/limited, or a sensitive context is detected.
- Local learning records accepted, ignored, reverted, word-frequency, and phrase-frequency data in SQLite.
- Optional local AI is separated from the rule-based engine and is disabled by default.
- Windows-only runtime APIs are mostly guarded so correction-engine tests can run without installing keyboard hooks.

## What is weak

- Fresh-install intelligence is still mostly data-limited: the app depends on compact built-in defaults and learns useful phrase predictions only after observing user text.
- Candidate generation and ranking are coupled inside `CorrectionEngine`, which makes it harder to add new correction sources safely.
- Capitalisation logic is minimal and does not yet suggest sentence-start capitalisation.
- Contraction handling needs category-aware behavior so safe contractions can be high-confidence while ambiguous forms remain suggest-only.
- Real-word confusion handling is too shallow for common cases like `your welcome`, `should of`, `then/than`, `its/it's`, and `loose/lose`.
- Default phrase prediction exists, but learned phrase prediction and default phrase prediction are not yet ranked through a unified scoring layer.
- Ranking uses simple confidence plus accept/ignore nudges; it does not yet account for edit closeness, word frequency, real-word risk, context match, reverted corrections, or app-specific learning.
- Existing fresh-install modules need acceptance validation phase-by-phase: especially data packaging, conservative auto-apply behavior, sentence-start capitalisation, confusion-pair breadth, benchmark coverage, and non-Windows import safety.

## Files that need changes

- `src/keyboard_assistant/data/defaults.py`
- `src/keyboard_assistant/data/common_typos.tsv`
- `src/keyboard_assistant/data/contractions.tsv`
- `src/keyboard_assistant/data/common_words.tsv`
- `src/keyboard_assistant/data/confusion_sets.tsv`
- `src/keyboard_assistant/data/common_phrases.tsv`
- `src/keyboard_assistant/core/candidate_generator.py`
- `src/keyboard_assistant/core/suggestion_ranker.py`
- `src/keyboard_assistant/core/correction_engine.py`
- `src/keyboard_assistant/core/context.py`
- `src/keyboard_assistant/storage/database.py`
- `src/keyboard_assistant/ai/suggestion_worker.py`
- `tests/test_default_data.py`
- `tests/test_candidate_generator.py`
- `tests/test_suggestion_ranker.py`
- `tests/test_correction_engine.py`
- `tests/test_local_ai.py`
- `tests/fixtures/fresh_install_cases.json`

## Safe implementation plan

1. Move built-in language data into local TSV files while keeping the legacy constants importable from `defaults.py`.
2. Add a deterministic `CandidateGenerator` that emits structured candidates from exact typos, contractions, capitalisation, fuzzy edits, confusion sets, default phrases, and user phrase history.
3. Add a deterministic `SuggestionRanker` that combines base confidence, frequency, edit quality, context, user learning, reverted corrections, app-specific history, and real-word risk.
4. Improve capitalisation only where context is clear: standalone `i`, sentence starts, and after `.`, `!`, or `?`, while preserving mixed-case words.
5. Apply contraction categories conservatively: safe forms may auto-apply; ambiguous real words should usually remain suggestions.
6. Add confusion-pair support as mostly suggest-only, with very safe phrase fixes allowed to auto-apply only at high confidence.
7. Rank learned phrase predictions above default phrase predictions and keep optional local AI as a non-blocking enhancement.
8. Add a fresh-install benchmark fixture with at least 100 deterministic cases and target at least 85% pass rate.
9. Recheck Windows-safe imports and keep desktop/CLI entry points working.
10. Tune local AI scheduling without making the rule engine depend on it.
11. Finish with integration cleanup, README updates, full tests, benchmark tests, and CLI smoke tests.
