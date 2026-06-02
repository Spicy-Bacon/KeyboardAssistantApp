# KeyboardAssistantApp Agent Instructions

## Product Direction

This project is a privacy-first desktop keyboard assistant. It should correct typos, apostrophes, capitalisation, and provide smart suggestions across desktop apps.

The app should feel minimal and local-first.

Current priority: **Fresh Install Intelligence**.

The app should feel smart immediately after installation, before any user training and without requiring local AI.

## Hard Rules

- Do not add LangChain.
- Do not add cloud APIs.
- Do not add visible modes.
- Do not rewrite the whole app.
- Do not remove existing working functionality.
- Keep the app usable without local AI.
- Keep local AI optional.
- Keep the app usable without internet.
- Do not call AI on every keystroke.
- Keep changes modular and reviewable.
- Add or update tests for every behaviour change.
- Do not make auto-correction too aggressive.
- Real-word ambiguous corrections should usually be suggestions, not auto-applied.
- Keep privacy rules unchanged.
- Keep the public CLI and desktop entry points working.

## Product Behaviour Rules

The assistant should use a layered intelligence system:

1. Built-in rules and data
2. Candidate generation
3. Suggestion ranking
4. User local learning
5. Optional local AI enhancement

The local AI layer is a bonus, not the core correction engine.

The app must work well when freshly installed with:

- local AI disabled
- learning data empty
- no internet access

## Engineering Style

- Prefer small modules.
- Prefer clear names.
- Prefer deterministic logic.
- Keep data files local under `src/keyboard_assistant/data/`.
- Avoid huge hardcoded dictionaries inside Python files.
- Keep `defaults.py` as a loader/compatibility layer, not a giant data dump.
- Add comments for scoring/ranking logic.
- Avoid over-engineering the UI.

## Testing Commands

From the project root on Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

CLI smoke test:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.cli "teh quick brown fox"
```

Interactive CLI test:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.cli --interactive
```

Desktop prototype test:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.desktop
```

## Platform Requirements

- Windows is the main target for the desktop prototype.
- Correction engine tests should not require Windows keyboard hooks.
- Windows-only APIs should be imported or initialised only when needed.
- Non-Windows import should not crash correction-engine tests.
- If a Windows-only feature is instantiated on a non-Windows platform, raise a clear friendly error.

## Fresh Install Intelligence Acceptance Target

Create and maintain a benchmark test set.

Target:

- At least 85% fresh-install benchmark pass rate.
- Very low false auto-correction rate.
- No local AI required.
- No internet required.
- Deterministic tests.

## Current Task File

Follow:

```text
TASK_FRESH_INSTALL_INTELLIGENCE.md
```

Implement it phase by phase.
