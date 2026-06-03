# Manual Desktop Test Plan

Use this plan on Windows after the zipapp or source checkout launches successfully. Record the app version, Windows version, display scaling, monitor count, and database path before testing.

Recommended launch:

```powershell
$env:PYTHONPATH="src"
python -m keyboard_assistant.desktop --debug
```

For each case, verify that no raw typed text appears in diagnostics logs.

## Core Correction Cases

| Done | App / Context | Test Input | Expected Suggestion / Correction | Expected Non-Correction |
| --- | --- | --- | --- | --- |
| [ ] | Notepad | `teh ` | `the` appears and can be accepted with Space | Normal words such as `form`, `from`, `class`, `function` are not auto-corrected |
| [ ] | Notepad | `dont ` | `don't` appears | `ill`, `well`, `were`, `shell` are not aggressively changed |
| [ ] | Notepad | `recieve ` | `receive` appears | Existing correct word `receive` is left alone |
| [ ] | Notepad | `thank ` | `you` appears as a phrase suggestion | `thank` without trailing space does not spam next-word prediction |
| [ ] | Notepad | `let me ` | `know` appears | User can decline with Esc |
| [ ] | Notepad | `should of ` | `should have` appears as suggest-only | Ambiguous real-word corrections are not auto-applied |
| [ ] | Notepad | `your welcome ` | `you're welcome` appears as suggest-only | Space does not force unsafe real-word correction |

## Browser Fields

| Done | App / Context | Test Input | Expected Suggestion / Correction | Expected Non-Correction |
| --- | --- | --- | --- | --- |
| [ ] | Chrome / Edge normal text field | `teh ` | `the` appears near caret | Text remains editable after accept |
| [ ] | Chrome / Edge address/search bar | `https://example.com/teh` | No correction | URLs are not changed |
| [ ] | Chrome / Edge address/search bar | `C:\Users\yewha\file.txt` | No correction | File paths are not changed |
| [ ] | Gmail / Outlook Web body | `recieve ` | `receive` appears | Subject/body focus switches do not keep stale buffer text |
| [ ] | Gmail / Outlook Web body | `thank ` | `you` appears | Esc hides suggestions without changing text |

## Messaging And Documents

| Done | App / Context | Test Input | Expected Suggestion / Correction | Expected Non-Correction |
| --- | --- | --- | --- | --- |
| [ ] | Discord / WhatsApp Desktop | `dont ` | `don't` appears | Existing correct informal words are not over-corrected |
| [ ] | Discord / WhatsApp Desktop | `soooo ` | No auto-correction | Informal repeated-character words are not forced |
| [ ] | Microsoft Word / Google Docs | `recieve ` | `receive` appears | Word processor's own corrections do not duplicate text |
| [ ] | Microsoft Word / Google Docs | `looking forward ` | `to` appears | Phrase suggestions never auto-apply |

## Developer And Shell Contexts

| Done | App / Context | Test Input | Expected Suggestion / Correction | Expected Non-Correction |
| --- | --- | --- | --- | --- |
| [ ] | VS Code editor | `def recieve_message():` | No auto-correction | Code-like text is not changed |
| [ ] | VS Code editor | `from module import function` | No auto-correction | Code keywords are protected |
| [ ] | PowerShell / Windows Terminal | `python scripts\validate_language_data.py` | No correction | Terminal commands are not changed |
| [ ] | PowerShell / Windows Terminal | `git commit -m "teh"` | No correction | Command-line text is protected |

## Sensitive And System Contexts

| Done | App / Context | Test Input | Expected Suggestion / Correction | Expected Non-Correction |
| --- | --- | --- | --- | --- |
| [ ] | Password field | Any password-like text | No overlay | Password fields should not be captured or corrected |
| [ ] | File Explorer rename field | `recieve.txt` | No unsafe extension/path change | File names and extensions are protected |
| [ ] | Fullscreen/game context if practical | Random text / hotkeys | No disruptive overlay | Existing game controls still work |

Password detection is best effort. If a password field still receives suggestions, record the app, field type, and window title, then disable the app profile until fixed.

## Runtime Behaviour

| Done | Scenario | Expected Result |
| --- | --- | --- |
| [ ] | App switching from Notepad to browser | Typed buffer resets when the app identity changes |
| [ ] | Window title changes within same app | Typed buffer is not unnecessarily cleared |
| [ ] | Backspace through the current word | Suggestions update as characters are removed and hide when the word is empty |
| [ ] | Left/right/up/down with no visible suggestions | Cursor movement clears the typed buffer and hides stale suggestions |
| [ ] | Home/End/PageUp/PageDown/Delete | Buffer clears and suggestions hide without changing existing text |
| [ ] | Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z | Buffer clears or becomes unreliable; pasted/selected content is not auto-corrected |
| [ ] | Mouse click into another word in Notepad | Old suggestions disappear; new typing starts from a fresh buffer |
| [ ] | Overlay placement near screen edges | Overlay stays visible and does not cover typed text more than necessary |
| [ ] | Multi-monitor and 125%/150% scaling | Overlay appears near caret or cursor on the correct monitor |
| [ ] | Arrow keys | Left/right/up/down move selection when suggestions are visible |
| [ ] | Space | Accepts focused suggestion or passes through unchanged typed choice |
| [ ] | Esc | Declines all visible suggestions and hides overlay |
| [ ] | Mouse click | Accepts clicked suggestion without adding an extra space |
| [ ] | Pause/resume from tray | Pause hides suggestions and stops correction until resumed |
| [ ] | Tray icon | Tooltip/menu works, settings opens, exit shuts down cleanly |
| [ ] | Shutdown/restart | Listener, overlay, tray, and local AI worker clean up without leaving a stuck process |

## UI Preview

| Done | Scenario | Expected Result |
| --- | --- | --- |
| [ ] | `python -m keyboard_assistant.settings_app` | Opens the dark settings window with sidebar navigation, cards, readable controls, and saved settings |
| [ ] | `python -m keyboard_assistant.desktop --overlay-demo` | Shows a compact dark QuickType-style suggestion bar with centered chips and padded highlight |
| [ ] | `python -m keyboard_assistant.desktop --debug` | Live typing works with privacy-safe debug metadata and no raw typed text in diagnostics |
