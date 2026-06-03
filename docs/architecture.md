# Architecture

KeyboardAssistantApp is a local-first Windows desktop keyboard assistant. The core correction engine is platform-independent; Windows-specific code is isolated behind runtime components so the full unit suite can run on non-Windows CI.

## High-Level Flow

```text
typed input
  -> TypedBuffer / TextContext
  -> policy / app context
  -> CandidateGenerator
  -> SuggestionRanker
  -> AutoApplySafetyGate
  -> overlay / text injector
  -> local learning feedback
```

## Core Language Pipeline

`TypedBuffer` keeps recent typed text. `extract_text_context` identifies the current word, previous words, and sentence-start state without requiring full document access.

`CandidateGenerator` creates conservative candidates from local data:

- exact typo rules
- contractions
- capitalization rules
- confusion-pair phrase rules
- edit-distance and keyboard-neighbor candidates
- default phrase predictions
- user-learned phrase predictions

`SuggestionRanker` scores candidates using base confidence, edit closeness, keyboard-neighbor hints, accepted/ignored/reverted history, user word frequency, and app context. Phrase predictions and local AI suggestions remain suggest-only.

`AutoApplySafetyGate` is the final auto-correction gate. It blocks auto-apply for code-like text, paths, URLs, command-line input, risky app contexts, local AI suggestions, phrase predictions, ambiguous real-word corrections, and previously ignored/reverted suggestions.

## Language Data Loading

Static language data lives in `src/keyboard_assistant/data/*.tsv` and is loaded with `importlib.resources`. Validation is structural and deterministic. The quality audit reports review risks separately from hard validation failures.

Loaded indexes include:

- typo map
- contraction map
- common word frequency map
- common word length buckets
- confusion first-word index
- phrase prefix index
- next-word fallback map

## Local Learning

SQLite stores local learning signals:

- accepted suggestions
- ignored suggestions
- reverted corrections
- phrase frequency
- word frequency
- personal dictionary and never-correct words

Learning is optional and can be disabled. Clearing learning data does not remove the personal dictionary.

## Optional Local AI

Local AI is optional and currently configured for local providers such as Ollama. It is never required for tests or normal correction. Local AI suggestions are asynchronous, suggest-only, and never auto-applied by default.

## Database Layer

`Database` owns SQLite schema initialization and persistence for:

- global settings
- app profiles
- appearance settings
- local AI settings
- personal dictionary
- learning tables

Connections are short-lived and committed through a context manager.

## Desktop Runtime

`DesktopAssistantRuntime` is orchestration. It coordinates:

- typed buffer updates
- app context checks
- suggestions and overlay display
- keyboard event queue
- suggestion acceptance
- local AI worker cancellation
- shutdown cleanup
- runtime health and diagnostics

Desktop components are injectable. Tests use null or mock components and do not require Windows hooks, overlays, tray APIs, or `SendInput`.

## Runtime Components And Protocols

`runtime/components.py` defines protocol-style interfaces for:

- text injector
- overlay
- tray
- keyboard listener
- app detector
- cursor locator
- local AI worker

It also contains null components for tests and explicit safe fallback paths.

## Windows-Specific Components

Windows implementations live outside the core correction pipeline:

- `WindowsKeyboardListener` installs the low-level keyboard hook.
- `WindowsTextInjector` uses `SendInput`.
- `SuggestionOverlay` displays the suggestion window.
- `TrayIcon` provides pause/settings/exit controls.
- `AppDetector` inspects the active app and focused control.
- `CursorLocator` finds the caret or cursor anchor.

Windows-only components raise clear errors when unavailable and are avoided during non-Windows unit tests.

## Diagnostics

`DiagnosticsLogger` writes privacy-safe JSONL diagnostics. It redacts text-like metadata fields and should not receive raw typed text from runtime debug paths. `RuntimeHealth` tracks startup, failure, and cleanup state for doctor output and crash reports.

## Settings And CLI

The CLI exposes local controls for suggestions, settings, app profiles, dictionary management, privacy cleanup, diagnostics, appearance, local AI, startup registration, and doctor checks.

The settings app is a desktop GUI for the same database-backed settings.

The new experimental frontend lives in `frontend/` as a Tauri + React + TypeScript app. It is separate from Python packaging and talks to the backend through allowlisted Tauri commands that call the existing Python CLI with `--json` output. The frontend does not write SQLite directly; the Python backend remains the source of truth for settings, app rules, dictionary entries, privacy summaries, local AI configuration, and doctor checks.

```text
Tauri React UI
  -> Rust command bridge
  -> python -m keyboard_assistant.cli ... --json
  -> Database / backend services
```

The PySide settings app remains available during the migration:

```powershell
python -m keyboard_assistant.settings_app
```

## Future macOS Expansion

The Tauri settings UI is intended to be shared across Windows and macOS. Runtime-specific behavior should stay behind platform factories. Windows hook, caret, app detection, and text injection logic should remain isolated from future macOS event tap, accessibility permission, and text insertion implementations.

The backend stays local-first on every platform. macOS support should add a macOS runtime factory and permission flow without changing the correction engine, language data, safety gate, or local-only storage model.

## Safety-First Correction Flow

The app prefers missed suggestions over false auto-corrections. Auto-apply is reserved for narrow, high-confidence cases such as exact non-word typos, safe contractions, standalone `i -> I`, and clear sentence-start capitalization. Real-word ambiguity usually remains suggest-only.
