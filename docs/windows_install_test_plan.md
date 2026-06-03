# Windows Install / Uninstall Test Plan

Run this plan on a normal Windows desktop account. Use a disposable database for install verification unless explicitly testing persisted user data.

## Build

| Done | Step | Command / Action | Expected Result |
| --- | --- | --- | --- |
| [ ] | Build zipapp | `python scripts\build_zipapp.py` | `dist\keyboard-assistant.pyz` is created |
| [ ] | Smoke CLI | `python dist\keyboard-assistant.pyz cli --version` | Version prints and exits `0` |
| [ ] | Validate package | `python dist\keyboard-assistant.pyz cli suggest teh` | Suggests `the` |

## Install

| Done | Step | Command / Action | Expected Result |
| --- | --- | --- | --- |
| [ ] | Install | `python scripts\install_windows.py` | App files and launchers are copied to the configured user location |
| [ ] | Start Menu shortcut | Launch from Start Menu shortcut | Desktop prototype starts or reports a clear startup error |
| [ ] | Desktop prototype | `keyboard-assistant desktop` or installed shortcut | Overlay/tray start on Windows |
| [ ] | Settings app | Open from tray or launcher | Settings window opens and reads the same database |
| [ ] | Doctor | `keyboard-assistant doctor` or `python dist\keyboard-assistant.pyz cli doctor` | Reports OS, Python, database, language data, runtime component availability, and diagnostics path |
| [ ] | Single instance | Start desktop twice | Second instance exits with a clear "already running" message |

## Startup Registration

| Done | Step | Command / Action | Expected Result |
| --- | --- | --- | --- |
| [ ] | Status before enable | `keyboard-assistant startup status` | Shows current startup registration |
| [ ] | Enable startup | `keyboard-assistant startup enable` | Startup entry is created |
| [ ] | Reboot/login check | Sign out/in or reboot | App starts once, not multiple times |
| [ ] | Disable startup | `keyboard-assistant startup disable` | Startup entry is removed |
| [ ] | Status after disable | `keyboard-assistant startup status` | Shows startup off |

## Data Locations

| Done | Check | Expected Result |
| --- | --- | --- |
| [ ] | Database location | Database path is documented by doctor output and remains accessible |
| [ ] | Diagnostics log location | Log path is shown by doctor output and contains redacted metadata only |
| [ ] | Learning data persistence | Accepted/ignored suggestions persist across restart when learning is enabled |
| [ ] | Settings persistence | Assistant, strength, learning, appearance, and local AI settings survive restart |
| [ ] | Clear learning | `keyboard-assistant privacy clear-learning` removes adaptive learning rows but keeps dictionary words |

## Uninstall / Reinstall

| Done | Step | Command / Action | Expected Result |
| --- | --- | --- | --- |
| [ ] | Uninstall | `python scripts\uninstall_windows.py` | Owned shortcuts/installed files are removed |
| [ ] | Cleanup check | Inspect install directory and Start Menu | No owned launchers remain |
| [ ] | Persisted data check | Inspect database/log path | User database/log policy is respected; uninstall does not unexpectedly erase user data |
| [ ] | Reinstall | `python scripts\install_windows.py` | Reinstall succeeds cleanly |
| [ ] | Post-reinstall launch | Launch desktop and settings | App works with existing or newly initialized database |

## Failure Cases

| Done | Scenario | Expected Result |
| --- | --- | --- |
| [ ] | Missing Windows hook permission | Desktop exits with a clear keyboard-hook failure and logs diagnostics |
| [ ] | Text injection unavailable | Doctor reports text injector unavailable; runtime startup fails clearly unless explicitly using safe test fallback |
| [ ] | Overlay startup failure | Desktop reports overlay failure clearly and records diagnostics |
| [ ] | Tray failure | Runtime falls back to null tray and remains usable if overlay/listener/injector are healthy |
