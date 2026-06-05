# Keyboard Assistant Frontend

Experimental Tauri settings UI for Keyboard Assistant.

## Run

```powershell
cd frontend
npm ci
npm run tauri dev
```

For a browser-only UI preview:

```powershell
cd frontend
npm ci
npm run dev
```

Browser/Vite preview uses clearly marked demo data when the Tauri backend is not available. You can also force demo mode with:

```powershell
$env:VITE_KEYBOARD_ASSISTANT_DEMO="1"
npm run dev
```

The real Tauri app does not silently fall back to mock data. If the Python backend command fails, the UI shows a visible backend unavailable banner.

## Build Check

```powershell
cd frontend
npm ci
npm run build
```

The Tauri commands call the existing Python CLI through subprocesses. They set `PYTHONPATH` to the repository `src/` directory and keep the SQLite database and correction engine owned by the Python backend.

Set `KEYBOARD_ASSISTANT_PYTHON` if the desired interpreter is not available as `python`.

Required local tools:

- Python with this repository's `src/` package available.
- Node/npm for frontend builds.
- Rust/Tauri prerequisites for `npm run tauri dev`.

Useful commands:

```powershell
cd frontend
npm ci
npm run build
npm run dev
npm run tauri dev
```
