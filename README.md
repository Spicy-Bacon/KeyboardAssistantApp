# Keyboard Assistant

Local-first desktop typing assistant prototype based on the PRD in this repo.

This first build focuses on the foundation:

- Fresh-install typo, apostrophe, capitalization, spacing, repeated-character, confusion-pair, and phrase suggestions.
- Conservative fuzzy suggestions for common keyboard-neighbor, transposed-letter, and missing-character typos.
- Structured local language data loaded from bundled TSV files; no internet or AI required.
- Typed-buffer context tracking for apps where full text context is unavailable.
- Local SQLite schema for settings, app profiles, dictionary, corrections, and learning events.
- App/sensitive-context policy stubs for Windows-focused desktop behavior.
- CLI demo and unit tests using only the Python standard library.

## Fresh-Install Intelligence

The correction engine is layered and local-first:

- Built-in TSV data covers common typos, contractions, common words, confusion pairs, and phrase predictions.
- `CandidateGenerator` creates deterministic candidates from exact typo data, contractions, capitalization rules, repeated letters, keyboard-neighbor slips, transpositions, edit-distance fixes, confusion pairs, default phrases, and local phrase history.
- `SuggestionRanker` scores candidates with base confidence, word frequency, edit closeness, context match, accepted/ignored/reverted history, app-specific word frequency, and real-word risk penalties.
- Auto-apply is conservative. Obvious typos and safe contractions can auto-apply; ambiguous real-word corrections usually stay as visible suggestions.
- Local learning can improve rankings, but the app is useful with an empty database and local AI disabled.
- Local AI is optional and disabled by default. It is only used as a delayed enhancement when explicitly configured, and the built-in correction engine does not need internet access.

## Run the Demo

```powershell
python -m keyboard_assistant.cli "teh quick brown fox"
python -m keyboard_assistant.cli "dont forget"
python -m keyboard_assistant.cli suggest "thank "
python -m keyboard_assistant.cli suggest "let me "
python -m keyboard_assistant.cli --interactive
```

If running directly from the repo without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.cli "i am going home"
```

## Run the Desktop Prototype

This starts the current Windows-focused live prototype. It uses a global keyboard hook, a typed-buffer fallback, and a small always-on-top suggestion overlay.

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.desktop
python -m keyboard_assistant.desktop --debug
python -m keyboard_assistant.desktop --doctor
python -m keyboard_assistant.desktop --overlay-demo
python -m keyboard_assistant.desktop --inject-demo "Keyboard Assistant injection test"
```

When Windows exposes a notification area, the live prototype adds a tray icon with:

- Pause / Resume
- Settings
- Exit

In non-interactive or restricted contexts where the notification area is unavailable, the app falls back to keyboard controls without failing startup.
Only one live assistant instance is allowed at a time. If another copy is already running, startup exits with an explicit message.

Use `--debug` when testing the live hook; it prints received key events, the typed buffer, current app identifier, policy reason, suggestion counts, and session counters on shutdown. Use `--doctor` to run desktop subsystem checks for the database, correction engine, active app detector, overlay, and keyboard hook. Use `--overlay-demo` to show a sample suggestion popup without relying on the keyboard hook. Use `--inject-demo` with Notepad focused to test whether Windows text insertion works independently of the hook and overlay.

## Run Settings

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.settings_app
```

The native settings window currently supports assistant on/off, correction strength, learning on/off, local data counts, clearing learning data, app behavior rules, personal dictionary management, overlay appearance, and local AI settings.

Current live controls:

- The left choice is the word you typed.
- The middle choice is focused by default. It is the correction when one exists; otherwise it is the word you typed.
- The right choice is the next-word suggestion when one exists.
- `Left` / `Right` or `Up` / `Down` moves the highlighted choice.
- `Space` accepts the highlighted choice and inserts the typed space. If the highlighted choice is the unchanged word you typed, the real Space key passes through normally.
- Mouse click accepts the clicked choice without inserting an extra space.
- `Esc` declines all visible suggestions.

Current limitations:

- This is a prototype, not a packaged background tray app.
- The tray icon uses the Windows notification area directly and needs validation in a normal desktop session.
- Text context comes from the fallback typed buffer, not full target-app text extraction.
- Normal key handling is queued off the low-level hook callback so typing stays responsive while suggestions are computed.
- The typed buffer resets when the active app, window, or focused field changes to avoid stale cross-app context.
- Cursor following uses best-effort Windows caret detection with mouse-position fallback.
- Overlay placement clamps to the visible screen and flips above the caret near the bottom edge.
- Sensitive field detection is conservative but not complete yet.

## Run Tests

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
python scripts\validate_language_data.py
python scripts\audit_language_data_quality.py
python -m unittest tests.test_fresh_install_benchmark -v
python scripts\profile_startup.py
```

The fresh-install benchmark uses `tests/fixtures/fresh_install_cases.json`, disables learning and local AI, and enforces an 85% minimum deterministic pass rate.
The verbose benchmark output reports pass rates by category and the false auto-correction count.

## Language Data

Bundled language data lives in `src/keyboard_assistant/data/` and is validated before expansion:

```powershell
python scripts\validate_language_data.py
```

Current TSV formats:

- `common_typos.tsv`: `typo<TAB>correction<TAB>confidence`
- `common_words.tsv`: `word<TAB>frequency_score` using numeric Zipf-style scores where higher means more common
- `common_phrases.tsv`: `prefix<TAB>suggestion<TAB>confidence`
- `confusion_sets.tsv`: `wrong_phrase_or_word<TAB>suggestion<TAB>context_hint<TAB>confidence`
- `contractions.tsv`: `input<TAB>correction<TAB>category<TAB>confidence`

Current bundled dataset sizes:

- `15,356` common typo rules
- `50,502` common word frequency entries
- `18,813` phrase prediction rules
- `576` confusion rules
- `82` contraction rules

The data loader parses these files once through `importlib.resources`, so the same path works from source checkouts and the packaged zipapp. Runtime lookup structures are precomputed as dictionaries, sets, word-length buckets, phrase prefix maps, full phrase-prefix indexes, and confusion-rule first-word indexes.

## Build a Packaged Artifact

The current dependency-free packaging path builds a Python zipapp:

```powershell
python scripts\build_zipapp.py
python dist\keyboard-assistant.pyz --help
python dist\keyboard-assistant.pyz cli suggest teh
python dist\keyboard-assistant.pyz desktop
python dist\keyboard-assistant.pyz settings
```

The current Windows install wrapper copies the built zipapp into the current user's local app data, creates Start Menu `.cmd` launchers, and can optionally register startup-on-login:

```powershell
python scripts\build_zipapp.py
python scripts\install_windows.py
python scripts\install_windows.py --enable-startup
python scripts\uninstall_windows.py
```

This is not an MSI installer yet, but it provides a repeatable user-local install path without global Python packages.

## Manage Settings

The same CLI can manage the local settings database:

```powershell
$env:PYTHONPATH="src"

python -m keyboard_assistant.cli settings show
python -m keyboard_assistant.cli settings set assistant off
python -m keyboard_assistant.cli settings set assistant on
python -m keyboard_assistant.cli settings set strength light
python -m keyboard_assistant.cli settings set learning off

python -m keyboard_assistant.cli apps set code.exe --status off --name "Visual Studio Code"
python -m keyboard_assistant.cli apps set notepad.exe --status limited --strength light
python -m keyboard_assistant.cli apps list

python -m keyboard_assistant.cli dictionary add Qwen --never-correct
python -m keyboard_assistant.cli dictionary list
python -m keyboard_assistant.cli dictionary export dictionary.json
python -m keyboard_assistant.cli dictionary import dictionary.json
python -m keyboard_assistant.cli dictionary remove Qwen

python -m keyboard_assistant.cli privacy summary
python -m keyboard_assistant.cli privacy clear-learning

python -m keyboard_assistant.cli diagnostics show
python -m keyboard_assistant.cli diagnostics clear

python -m keyboard_assistant.cli appearance show
python -m keyboard_assistant.cli appearance set --theme light --size small --opacity 85 --animations off

python -m keyboard_assistant.cli local-ai status
python -m keyboard_assistant.cli local-ai set --enabled on --provider ollama --model qwen2.5:3b
python -m keyboard_assistant.cli local-ai test

python -m keyboard_assistant.cli startup status
python -m keyboard_assistant.cli startup enable
python -m keyboard_assistant.cli startup disable
```

Correction strength behavior:

- `light`: fewer auto-corrections; suggestions still appear.
- `balanced`: auto-corrects obvious high-confidence fixes.
- `aggressive`: allows more proactive auto-correction.

Local AI is optional and disabled by default. The core correction engine works without it and never needs internet access. The current provider layer supports Ollama over `127.0.0.1` when explicitly enabled.
When enabled, local AI is used only after short pauses at word boundaries, enough context exists, and the rule engine does not already have a confident suggestion. Requests are debounced, stale responses are discarded, live requests use a short timeout, and typing never waits for the model.

Repeated personal-looking words, such as names or model/product terms with capital letters or digits, are learned into the local personal dictionary after repeated use when learning is enabled.

Diagnostics are local JSON-lines logs next to the SQLite database. They record lifecycle events, state changes, exception types, and counts, but redact raw typed text and suggestion text fields.

## Current Scope

The live desktop path is now present, but the next production work is hardening app compatibility, settings, tray behavior, and packaging.
