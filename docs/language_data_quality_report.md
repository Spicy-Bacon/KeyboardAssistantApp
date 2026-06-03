# Language Data Quality Report

Generated during the quality, safety, and runtime stability upgrade.

## Dataset Counts

- `common_typos.tsv`: 15,356 rows
- `common_words.tsv`: 50,502 rows
- `common_phrases.tsv`: 18,813 rows
- `confusion_sets.tsv`: 576 rows
- `contractions.tsv`: 82 rows

## Audit Summary

Command:

```powershell
python scripts\audit_language_data_quality.py
```

Current quality findings:

- `generic_low_value_phrase`: 66
- `repeated_character_word`: 22
- `risky_confusion_pair`: 2
- `very_short_word`: 2

## Cleanup Applied

Removed one generated typo row:

- `pornunciation -> pronunciation`

Reason: the typo contained an explicit substring and violated the clean-data rule, even though the intended correction was harmless.

## Intentionally Kept

- `a` and `i` in `common_words.tsv`: valid high-frequency words.
- Expressive repeated-character words such as `hmmmm`, `soooo`, and `shhhh`: useful for recognizing valid informal words and avoiding false corrections.
- Multiple phrase variants for the same prefix: the loader keeps the highest-confidence fallback per prefix, while the raw dataset preserves alternatives for future ranking work.
- The audit now flags exact duplicate phrase rules instead of normal ranked variants for the same prefix.
- `than -> then` and `then -> than` in `confusion_sets.tsv`: kept as suggest-only confusion rules, not direct typo auto-corrections.

## Recommended Follow-Up

- Review low-value phrase suggestions such as one-word prefixes that predict `a`, `an`, `it`, or `the`.
- Review exact duplicate phrase rules if they appear in future data imports.
- Keep risky real-word pairs in `confusion_sets.tsv` only when they remain suggest-only and benchmark-covered.

## Remaining Risks

- Phrase data is large and has many prefix variants; this is safe, and the audit intentionally avoids treating normal variants as duplicate findings.
- Some informal common words are intentionally retained and may need app-specific ranking controls later.
- Real-word ambiguity remains the main false-positive risk, so the safety gate and benchmark should stay in place.
