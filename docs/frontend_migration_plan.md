# Frontend Migration Plan

KeyboardAssistantApp is moving from the current Python/PySide settings UI toward a modern Tauri desktop frontend. This is a frontend migration only. The correction engine, runtime, SQLite database, language datasets, safety gate, CLI, and tests remain owned by the existing Python backend.

## Why Replace The Current PySide UI

The PySide settings app is functional, but it is tied to the current Python desktop stack and is harder to evolve into a polished cross-platform dashboard. A Tauri frontend gives the app a modern component model, richer styling, smoother interactions, and a cleaner path to one shared settings UI for Windows and macOS.

The PySide app remains available as a fallback while the Tauri UI stabilizes:

```powershell
python -m keyboard_assistant.settings_app
```

## Why Tauri

Tauri provides a small native shell with a web frontend, good desktop ergonomics, and a Rust command layer for carefully scoped native bridge work. It keeps the settings UI cross-platform without forcing the correction engine or runtime to move out of Python.

The first frontend uses:

- React + TypeScript
- Vite
- Tauri command handlers
- CSS variables for theming
- Python CLI subprocess calls for backend access

## Why Keep The Python Backend

The Python backend already owns the high-risk product logic:

- deterministic correction engine
- candidate generation and ranking
- `AutoApplySafetyGate`
- SQLite schema and learning data
- app profiles and dictionary
- optional local AI configuration
- Windows desktop runtime
- CLI and tests

Keeping this backend avoids rewriting privacy-sensitive correction behavior and keeps existing tests meaningful. Local AI remains optional, disabled by default, and never required for the app to work.

## Frontend/Backend Communication

Phase 1 uses subprocess calls from Tauri to the existing Python CLI. The Rust bridge allowlists command shapes and returns JSON to the React UI.

Current bridge direction:

```text
React UI
  -> Tauri command
  -> python -m keyboard_assistant.cli ... --json
  -> SQLite/database/backend APIs through Python
```

The frontend does not edit SQLite directly.

Supported first-pass CLI surfaces:

- `settings show --json`
- `settings set ... --json`
- `appearance show --json`
- `appearance set ... --json`
- `apps list --json`
- `apps set ... --json`
- `apps remove ... --json`
- `dictionary list --json`
- `dictionary add ... --json`
- `dictionary remove ... --json`
- `privacy summary --json`
- `privacy clear-learning --json`
- `local-ai status --json`
- `local-ai set ... --json`
- `doctor --json`

## Migration Order

The first Tauri screen migrates settings/dashboard workflows:

1. General assistant controls
2. Correction strength and learning controls
3. App exclusions and risky app behavior
4. Personal dictionary and never-correct words
5. Privacy summary and learning cleanup
6. Appearance settings
7. Optional local AI settings
8. Diagnostics and doctor output

The old settings app remains the fallback until the new UI has enough soak time.

## Frontend Structure

```text
frontend/
  package.json
  src/
    App.tsx
    backend.ts
    main.tsx
    styles.css
  src-tauri/
    Cargo.toml
    tauri.conf.json
    src/main.rs

src/keyboard_assistant/
  existing Python backend
  CLI
  database
  correction engine
  runtime
```

## Future Phases

Phase 2 can add a local-only IPC or service layer if subprocess calls become too limiting. That service must stay local-first, avoid cloud APIs, and preserve the CLI as a supported interface.

Phase 3 can move stable shell pieces to Rust if that reduces platform complexity. Correction logic should stay in Python unless there is a narrow, tested reason to move it.

## Future macOS Expansion

The Tauri UI should remain cross-platform. Platform runtime behavior should be split through factories:

- keep Windows hook/injection logic in Windows-specific modules
- add a macOS runtime factory later
- implement macOS event tap and accessibility permission handling separately
- avoid mixing Windows hook assumptions with macOS behavior
- keep the backend local and privacy-first on both platforms
