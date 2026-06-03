# Privacy Design

KeyboardAssistantApp is designed as a local-first keyboard assistant. Its core correction path runs from bundled local data and the user's local SQLite database.

## Local-First Defaults

- No cloud APIs are used by the correction engine.
- LangChain is not used.
- Internet is not required at runtime.
- Local AI is optional and disabled by default.
- The app remains usable without local AI.

## Optional Local AI

When enabled, local AI is intended for local providers such as Ollama. The configured provider, model, endpoint, and timeout are local settings. Local AI suggestions are suggest-only and never auto-applied by default.

If local AI is enabled but unreachable, the app should keep the rule-based assistant usable and report the provider as unavailable.

## Data Stored Locally

The SQLite database stores:

- global assistant settings
- correction strength and learning setting
- app-specific profiles
- overlay appearance settings
- optional local AI configuration
- personal dictionary words
- never-correct words
- accepted suggestion records
- ignored suggestion records
- reverted correction records
- learned word and phrase frequency

Diagnostics are stored in a local JSONL log next to the selected database path by default.

## Data Not Intentionally Stored

The app should not intentionally store:

- passwords
- full typed documents
- raw typed text in diagnostics
- browser URLs or command lines in diagnostics
- cloud API transcripts

Learning records do store short correction and suggestion pairs when learning is enabled. This is local data, but it can still be personal. Users who do not want adaptive learning should disable learning or clear learning data.

## Diagnostics Redaction

`DiagnosticsLogger` redacts metadata keys that look like text, input, prompt, title, password, token, secret, or similar sensitive fields. Runtime debug output reports buffer metadata such as length rather than raw typed text.

Redaction is a defense-in-depth measure, not a reason to send raw typed text to diagnostics.

## Database And Log Location

By default, local development uses:

- database: `.keyboard_assistant.sqlite3`
- diagnostics log: `.keyboard_assistant.diagnostics.log`

Installed builds may use a user-local app directory. Use doctor diagnostics to confirm the active database and log paths.

## Clearing Or Disabling Learning

Show local data counts:

```powershell
python -m keyboard_assistant.cli privacy summary
```

Clear adaptive learning data:

```powershell
python -m keyboard_assistant.cli privacy clear-learning
```

Disable learning:

```powershell
python -m keyboard_assistant.cli settings set learning off
```

Clearing learning data leaves the personal dictionary intact.

## Sensitive Context Handling

The app uses active app and focused control metadata to avoid corrections in sensitive contexts such as password fields, credential windows, private browsing titles, payment/security fields, terminals, and risky developer contexts.

This detection is best effort. It depends on what Windows and the target app expose. The app must not claim perfect password-field detection. If suggestions appear in a sensitive field, disable the app profile and file a bug with the app name, field type, and window class when possible.

## Current Limitations

- Context comes mostly from the typed buffer, not full target-app document extraction.
- Password and sensitive-field detection is not perfect across all apps and web controls.
- Local learning records can contain short suggestion pairs that may be personal.
- The desktop app is Windows-focused.
- Optional local AI provider behavior depends on the user's local setup.
