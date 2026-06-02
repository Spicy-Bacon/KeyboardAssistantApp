# Codex Handoff Pack for KeyboardAssistantApp

This pack contains the files needed to ask Codex to upgrade the app's fresh-install intelligence.

## Files

1. `AGENTS.md`
   - Put this in the root of your repo.
   - Codex uses it as project-level guidance.

2. `TASK_FRESH_INSTALL_INTELLIGENCE.md`
   - Put this in the root of your repo.
   - This is the full phase-by-phase implementation plan.

3. `CODEX_START_PROMPT.txt`
   - Paste this into Codex after the two markdown files are in your repo.

## Recommended workflow

From your project root:

```powershell
git checkout -b fresh-install-intelligence
```

Then copy these files into the root of your project:

```text
AGENTS.md
TASK_FRESH_INSTALL_INTELLIGENCE.md
CODEX_START_PROMPT.txt
```

Then open Codex and paste the contents of:

```text
CODEX_START_PROMPT.txt
```

## Important

Review the final diff before merging back to your main/develop branch.
