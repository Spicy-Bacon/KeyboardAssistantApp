from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from types import ModuleType


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_ENTRY_NAME = "KeyboardAssistant"
_REGISTRY_SENTINEL = object()


@dataclass(frozen=True)
class StartupStatus:
    supported: bool
    enabled: bool
    command: str = ""


class WindowsStartupManager:
    def __init__(
        self,
        entry_name: str = DEFAULT_ENTRY_NAME,
        registry: ModuleType | object | None = _REGISTRY_SENTINEL,
    ) -> None:
        self.entry_name = entry_name
        self._registry = _load_winreg() if registry is _REGISTRY_SENTINEL else registry

    @property
    def supported(self) -> bool:
        return self._registry is not None

    def status(self) -> StartupStatus:
        if self._registry is None:
            return StartupStatus(supported=False, enabled=False)
        try:
            with self._registry.OpenKey(self._registry.HKEY_CURRENT_USER, RUN_KEY, 0, self._registry.KEY_READ) as key:
                command, _value_type = self._registry.QueryValueEx(key, self.entry_name)
        except OSError:
            return StartupStatus(supported=True, enabled=False)
        return StartupStatus(supported=True, enabled=True, command=str(command))

    def enable(self, command: str) -> None:
        if not command.strip():
            raise ValueError("startup command is required")
        if self._registry is None:
            raise RuntimeError("startup registration is only supported on Windows")
        with self._registry.CreateKeyEx(
            self._registry.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            self._registry.KEY_SET_VALUE,
        ) as key:
            self._registry.SetValueEx(key, self.entry_name, 0, self._registry.REG_SZ, command)

    def disable(self) -> None:
        if self._registry is None:
            raise RuntimeError("startup registration is only supported on Windows")
        try:
            with self._registry.OpenKey(
                self._registry.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                self._registry.KEY_SET_VALUE,
            ) as key:
                self._registry.DeleteValue(key, self.entry_name)
        except OSError:
            return


def default_startup_command() -> str:
    launcher = Path(sys.argv[0])
    if launcher.suffix.lower() == ".pyz":
        return subprocess.list2cmdline([sys.executable, str(launcher), "desktop"])
    return subprocess.list2cmdline([sys.executable, "-m", "keyboard_assistant.desktop"])


def _load_winreg() -> ModuleType | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    return winreg
