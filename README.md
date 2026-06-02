# Keyboard Assistant

Local-first desktop typing assistant prototype based on the PRD in this repo.

This first build focuses on the foundation:

- Rule-based typo, apostrophe, capitalization, spacing, and repeated-character suggestions.
- Conservative fuzzy suggestions for common keyboard-neighbor, transposed-letter, and missing-character typos.
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
```

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

Local AI is optional and disabled by default. The core correction engine works without it. The current provider layer supports Ollama over `127.0.0.1` when explicitly enabled.
When enabled, local AI is used only after short pauses at word boundaries. Requests are debounced, stale responses are discarded, and typing never waits for the model.

Repeated personal-looking words, such as names or model/product terms with capital letters or digits, are learned into the local personal dictionary after repeated use when learning is enabled.

Diagnostics are local JSON-lines logs next to the SQLite database. They record lifecycle events, state changes, exception types, and counts, but redact raw typed text and suggestion text fields.

## Current Scope

The live desktop path is now present, but the next production work is hardening app compatibility, settings, tray behavior, and packaging.
