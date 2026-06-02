# Fresh Install Intelligence Upgrade

## Goal

Make KeyboardAssistantApp significantly smarter immediately after installation, without requiring user training, internet access, cloud APIs, LangChain, or local AI.

The app should still work without local AI. Local AI is only an optional enhancement.

Do not focus on UI polish, themes, packaging, or new visible modes. Focus only on correction intelligence, default data, candidate generation, ranking, local learning interaction, tests, and safe imports.

---

## Phase 1: Diagnostic

Review the current codebase before changing anything.

Check:

1. Project structure
2. Correction engine
3. Default data in defaults.py
4. Typo correction logic
5. Contraction correction logic
6. Capitalisation logic
7. Contextual correction logic
8. Next-word / phrase suggestion logic
9. Suggestion ranking
10. Local learning system
11. Local AI layer
12. Tests
13. Windows-only import issues

Produce a short diagnostic note in:

```text
docs/fresh_install_diagnostic.md
```

Do not rewrite the app during this phase.

Acceptance criteria:

- Diagnostic file exists.
- Diagnostic explains what already works.
- Diagnostic explains what is weak.
- Diagnostic lists files that need changes.
- Diagnostic includes a safe implementation plan.

---

## Phase 2: Default Language Data Files

Move built-in correction data out of hardcoded `defaults.py` into structured local data files.

Create:

```text
src/keyboard_assistant/data/common_typos.tsv
src/keyboard_assistant/data/contractions.tsv
src/keyboard_assistant/data/common_words.tsv
src/keyboard_assistant/data/confusion_sets.tsv
src/keyboard_assistant/data/common_phrases.tsv
```

### `common_typos.tsv`

Format:

```text
typo<TAB>correction<TAB>confidence
```

Include at least 300 common English typo corrections.

Cover:

- common misspellings
- letter swaps
- keyboard slips
- missing letters
- extra letters
- repeated letters

Examples:

```text
teh	the	0.98
recieve	receive	0.96
definately	definitely	0.96
becuase	because	0.96
seperate	separate	0.95
```

### `contractions.tsv`

Format:

```text
input<TAB>correction<TAB>category<TAB>confidence
```

Categories:

```text
safe_auto
suggest_only
contextual
```

Safe examples:

```text
dont	don't	safe_auto	0.98
cant	can't	safe_auto	0.98
doesnt	doesn't	safe_auto	0.97
im	I'm	safe_auto	0.97
youre	you're	safe_auto	0.96
theyre	they're	safe_auto	0.96
```

Contextual or suggest-only examples:

```text
ill	I'll	contextual	0.75
hell	he'll	contextual	0.70
shell	she'll	contextual	0.70
were	we're	suggest_only	0.65
well	we'll	contextual	0.70
```

### `common_words.tsv`

Format:

```text
word<TAB>frequency_score
```

Include a useful built-in English word list with frequency scores.

It should be much larger than the current `COMMON_WORDS` list and include:

- everyday words
- email words
- academic words
- messaging words
- safe common proper nouns if useful

### `confusion_sets.tsv`

Format:

```text
wrong_phrase_or_word<TAB>suggestion<TAB>context_hint<TAB>confidence
```

Include examples like:

```text
your welcome	you're welcome	phrase	0.95
should of	should have	phrase	0.95
could of	could have	phrase	0.95
would of	would have	phrase	0.95
to much	too much	phrase	0.90
meat	meet	will,you,later	0.80
loose	lose	verb_context	0.75
then	than	comparison_context	0.70
```

Real-word ambiguity should usually be suggest-only.

### `common_phrases.tsv`

Format:

```text
prefix<TAB>suggestion<TAB>confidence
```

Include common phrase predictions:

```text
thank	you	0.95
thank you	for	0.90
let me	know	0.93
please let	me	0.90
as soon	as	0.92
at the	moment	0.88
in the	morning	0.85
by the	way	0.85
I will	check	0.82
I have	attached	0.85
if you	have	0.82
feel free	to	0.85
looking forward	to	0.90
best	regards	0.86
```

Update `defaults.py` so it loads data from these files while preserving backward compatibility.

Add tests confirming all data files load correctly.

Acceptance criteria:

- All five data files exist.
- Data files are loaded by the app.
- Existing imports still work.
- Tests verify file loading.
- Existing tests still pass.

---

## Phase 3: CandidateGenerator

Create:

```text
src/keyboard_assistant/core/candidate_generator.py
```

The `CandidateGenerator` should generate suggestions from:

1. Exact typo map
2. Contractions
3. Capitalisation rules
4. Repeated letter correction
5. Keyboard-neighbour mistakes
6. Transposed letters
7. Missing letter / extra letter edits
8. Confusion sets
9. Default phrase predictions
10. User phrase history if available

Candidate object fields:

```text
original_text
suggestion_text
suggestion_type
base_confidence
source
should_auto_apply
metadata
```

Suggestion types:

```text
typo
contraction
capitalization
repeated_letter
keyboard_slip
transposition
edit_distance
confusion_pair
phrase_prediction
user_phrase_prediction
```

Requirements:

- Do not call local AI inside `CandidateGenerator`.
- Keep it fast and deterministic.
- Do not make auto-correction aggressive.
- Real-word confusion pairs should usually be suggest-only.
- Integrate carefully with the existing `CorrectionEngine`.
- Keep public methods working.
- Add unit tests for each candidate source.

Acceptance criteria:

- CandidateGenerator exists.
- Candidate object/model exists.
- Unit tests cover each candidate source.
- Existing public correction API still works.
- Existing tests still pass.

---

## Phase 4: SuggestionRanker

Create:

```text
src/keyboard_assistant/core/suggestion_ranker.py
```

The `SuggestionRanker` should score candidates using:

1. Base confidence
2. Word frequency score
3. Edit distance closeness
4. Keyboard-neighbour likelihood
5. Context match
6. User accepted suggestion history
7. User ignored suggestion history
8. User reverted correction history
9. Real-word risk penalty
10. App-specific learning if available

Use a clear, tunable scoring formula.

Example:

```text
final_score =
    base_confidence
  + typo_map_bonus
  + word_frequency_bonus
  + keyboard_distance_bonus
  + context_bonus
  + user_accepted_bonus
  - user_ignored_penalty
  - user_reverted_penalty
  - real_word_risk_penalty
```

Requirements:

- Deterministic ranking.
- Only auto-apply very high-confidence suggestions.
- Real-word ambiguity should usually be suggest-only.
- Integrate with `CorrectionEngine`.
- Keep public interface working.
- Add tests.

Required examples:

- `teh` should rank `the` very highly.
- `dont` should rank `don't` very highly.
- `form -> from` should not auto-apply because both are real words.
- `your welcome -> you're welcome` should suggest.
- Repeatedly ignored suggestions should rank lower.
- Repeatedly accepted suggestions should rank higher.

Acceptance criteria:

- SuggestionRanker exists.
- Ranking tests pass.
- CorrectionEngine uses the ranker.
- Auto-apply behaviour is conservative.

---

## Phase 5: Capitalisation Intelligence

Improve capitalisation suggestions for:

1. Standalone `i -> I`
2. Start-of-sentence lowercase word
3. Word after `.`, `!`, or `?`
4. Proper noun exceptions where available
5. Do not break words like `iPhone`, `eBay`, `macOS`

Examples:

```text
i am going home -> I am going home
hello. how are you -> hello. How are you
thanks! i will check -> thanks! I will check
ok? let me know -> ok? Let me know
```

Update old tests that expected no suggestion for `hello. how`.

Acceptance criteria:

- Sentence-start capitalisation works.
- Standalone `i` works.
- Mid-sentence words are not randomly capitalised.
- Known mixed-case words are not broken.
- Tests pass.

---

## Phase 6: Contraction Intelligence

Use `contractions.tsv`.

Implement categories:

```text
safe_auto
suggest_only
contextual
```

Safe contractions can be high-confidence.

Contextual contractions should usually be suggestions only unless context clearly supports them.

Do not aggressively change valid real words.

Add tests for safe and dangerous contractions.

Acceptance criteria:

- Safe contractions are high-confidence.
- Dangerous contractions are suggest-only/contextual.
- Ignored/reverted behaviour can lower future confidence.
- Tests pass.

---

## Phase 7: Confusion-Pair Intelligence

Use `confusion_sets.tsv`.

Support:

1. `your welcome -> you're welcome`
2. `should of -> should have`
3. `could of -> could have`
4. `would of -> would have`
5. `to much -> too much`
6. `I will meat you later -> meet`
7. `their / there / they're`
8. `your / you're`
9. `its / it's`
10. `then / than`
11. `loose / lose`
12. `affect / effect`

Requirements:

- Usually suggest-only.
- Auto-apply only for extremely safe phrase patterns like `should of`.
- Add tests for ambiguous cases not being auto-applied.

Acceptance criteria:

- Confusion-pair tests pass.
- Ambiguous real-word cases are not auto-applied aggressively.
- Safe phrase fixes can be high-confidence.

---

## Phase 8: Fresh Phrase Prediction

Use `common_phrases.tsv`.

Ranking order:

1. User-learned phrase prediction
2. Default common phrase prediction
3. Optional local AI suggestion if enabled and non-blocking

Requirements:

- Do not show phrase suggestions constantly after every word.
- Use confidence thresholds.
- Add tests.
- Do not call LLM for every next-word suggestion.

Acceptance criteria:

- Default phrase predictions work on fresh install.
- User-learned phrase predictions rank above default phrases.
- Local AI remains optional.
- Tests pass.

---

## Phase 9: Fresh Install Benchmark

Create:

```text
tests/fixtures/fresh_install_cases.json
```

Include at least 100 test cases covering:

1. Common typos
2. Contractions
3. Capitalisation
4. Repeated letters
5. Keyboard slips
6. Transposed letters
7. Missing letters
8. Extra letters
9. Contextual real-word mistakes
10. Next-word / phrase predictions
11. Cases that should not auto-correct

Each case should include:

```json
{
  "input": "teh",
  "expected_suggestion": "the",
  "type": "typo",
  "should_auto_apply": true
}
```

Benchmark rules:

1. Run fresh-install assistant with learning disabled.
2. Run local AI disabled.
3. Check whether expected suggestions appear.
4. Check auto-apply behaviour.
5. Report pass rate.

Acceptance target:

```text
At least 85% of benchmark cases pass.
False auto-correction should be very low.
```

Tests must be deterministic and must not require Windows keyboard hooks.

Acceptance criteria:

- Benchmark fixture exists.
- Benchmark test exists.
- Benchmark can run without local AI.
- Benchmark can run without internet.
- Benchmark does not require Windows hooks.

---

## Phase 10: Windows-Safe Imports

Fix Windows-only import and testing issues.

Requirements:

1. Windows APIs should only be imported or initialised when needed.
2. Modules should not crash just because imported on Linux/macOS/test environments.
3. If a Windows-only feature is instantiated on a non-Windows platform, raise a clear friendly error.
4. Add platform guards.
5. Add fallback stubs if useful for tests.
6. Correction engine tests should run without Windows keyboard hooks or overlay UI.
7. Do not remove Windows functionality.

Acceptance criteria:

- Correction tests can run on non-Windows.
- Importing the package does not immediately crash outside Windows.
- Windows desktop functionality remains intact on Windows.

---

## Phase 11: Local AI Tuning

Review and improve local AI integration.

Requirements:

1. Local AI remains optional.
2. App works without local AI.
3. Local AI does not run on every keystroke.
4. Local AI only runs when:
   - user pauses briefly
   - enough context exists
   - rule/dictionary engine is unsure
   - phrase prediction may benefit from context
5. AI requests are asynchronous.
6. Outdated AI suggestions are cancelled or ignored.
7. Live suggestion timeout should be around 1.5 to 3 seconds.
8. Keep longer timeout only for manual testing if needed.
9. Keep Ollama support if currently present.
10. No cloud APIs.
11. No LangChain.

Add tests for:

- local AI disabled
- local AI unavailable
- timeout behaviour
- outdated suggestion ignored
- fallback to rule-based suggestions

Acceptance criteria:

- Local AI remains optional.
- Typing is never blocked waiting for AI.
- Tests cover disabled/unavailable/timeout cases.

---

## Phase 12: Final Integration and Cleanup

Review:

1. Data loading
2. CandidateGenerator
3. SuggestionRanker
4. CorrectionEngine integration
5. Capitalisation
6. Contractions
7. Confusion sets
8. Phrase prediction
9. Local learning interaction
10. Local AI fallback
11. Tests
12. CLI behaviour
13. Desktop behaviour

Tasks:

1. Remove duplicated logic where safe.
2. Keep modules small and readable.
3. Ensure `defaults.py` is not overloaded with huge hardcoded data.
4. Ensure data files load correctly when packaged.
5. Ensure app works without internet.
6. Ensure app works without local AI.
7. Ensure tests are deterministic.
8. Update README with:
   - how fresh-install correction works
   - how to run tests
   - how to run benchmark tests
   - how local AI fits in

Acceptance criteria:

1. Existing tests pass.
2. Fresh install benchmark passes target threshold.
3. CLI still works.
4. Desktop prototype still launches.
5. No cloud APIs.
6. No LangChain.
7. No unnecessary dependencies.
