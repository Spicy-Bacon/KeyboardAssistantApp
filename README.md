# Keyboard Assistant

Local-first desktop typing assistant prototype based on the PRD in this repo.

This first build focuses on the foundation:

- Rule-based typo, apostrophe, capitalization, spacing, and repeated-character suggestions.
- Typed-buffer context tracking for apps where full text context is unavailable.
- Local SQLite schema for settings, app profiles, dictionary, corrections, and learning events.
- App/sensitive-context policy stubs for Windows-focused desktop behavior.
- CLI demo and unit tests using only the Python standard library.

## Run the Demo

```powershell
python -m keyboard_assistant.cli "teh quick brown fox"
python -m keyboard_assistant.cli "dont forget"
python -m keyboard_assistant.cli --interactive
```

If running directly from the repo without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.cli "i am going home"
```

## Run Tests

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

## Current Scope

This is not yet a background keyboard hook or overlay UI. It establishes the correction, context, privacy, and persistence core that those layers will use next.

