# Keyboard Assistant Frontend

Experimental Tauri settings UI for Keyboard Assistant.

## Run

```powershell
cd frontend
npm install
npm run tauri dev
```

For a browser-only UI preview:

```powershell
cd frontend
npm install
npm run dev
```

## Build Check

```powershell
cd frontend
npm run build
```

The Tauri commands call the existing Python CLI through subprocesses. They set `PYTHONPATH` to the repository `src/` directory and keep the SQLite database and correction engine owned by the Python backend.

Set `KEYBOARD_ASSISTANT_PYTHON` if the desired interpreter is not available as `python`.
