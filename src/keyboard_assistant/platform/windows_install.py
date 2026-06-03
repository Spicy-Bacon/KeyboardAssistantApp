from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import os
from pathlib import Path
import shutil
import subprocess
import sys

from keyboard_assistant.platform.startup import WindowsStartupManager


APP_DIR_NAME = "KeyboardAssistant"
PYZ_NAME = "keyboard-assistant.pyz"
ICON_NAME = "app_icon.ico"
DESKTOP_LAUNCHER = "Keyboard Assistant.cmd"
SETTINGS_LAUNCHER = "Keyboard Assistant Settings.cmd"


@dataclass(frozen=True)
class InstallResult:
    install_root: Path
    installed_pyz: Path
    installed_icon: Path
    desktop_launcher: Path
    settings_launcher: Path
    startup_enabled: bool


def default_install_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def default_start_menu_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Keyboard Assistant"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Keyboard Assistant"


def build_pyz_command(pyz_path: Path, command: str) -> str:
    return subprocess.list2cmdline([sys.executable, str(pyz_path), command])


def install_zipapp(
    source_pyz: str | Path,
    install_root: str | Path | None = None,
    start_menu_dir: str | Path | None = None,
    enable_startup: bool = False,
    startup_manager: WindowsStartupManager | None = None,
) -> InstallResult:
    source = Path(source_pyz)
    if not source.exists():
        raise FileNotFoundError(f"zipapp not found: {source}")

    root = Path(install_root) if install_root is not None else default_install_root()
    menu_dir = Path(start_menu_dir) if start_menu_dir is not None else default_start_menu_dir()
    root.mkdir(parents=True, exist_ok=True)
    menu_dir.mkdir(parents=True, exist_ok=True)

    installed_pyz = root / PYZ_NAME
    installed_icon = root / ICON_NAME
    shutil.copy2(source, installed_pyz)
    _copy_app_icon(installed_icon)

    desktop_launcher = menu_dir / DESKTOP_LAUNCHER
    settings_launcher = menu_dir / SETTINGS_LAUNCHER
    _write_cmd_launcher(desktop_launcher, build_pyz_command(installed_pyz, "desktop"))
    _write_cmd_launcher(settings_launcher, build_pyz_command(installed_pyz, "settings"))

    startup_enabled = False
    if enable_startup:
        manager = startup_manager or WindowsStartupManager()
        manager.enable(build_pyz_command(installed_pyz, "desktop"))
        startup_enabled = True

    return InstallResult(
        install_root=root,
        installed_pyz=installed_pyz,
        installed_icon=installed_icon,
        desktop_launcher=desktop_launcher,
        settings_launcher=settings_launcher,
        startup_enabled=startup_enabled,
    )


def uninstall_zipapp(
    install_root: str | Path | None = None,
    start_menu_dir: str | Path | None = None,
    startup_manager: WindowsStartupManager | None = None,
) -> None:
    manager = startup_manager or WindowsStartupManager()
    if manager.supported:
        manager.disable()

    root = Path(install_root) if install_root is not None else default_install_root()
    menu_dir = Path(start_menu_dir) if start_menu_dir is not None else default_start_menu_dir()
    for path in (menu_dir / DESKTOP_LAUNCHER, menu_dir / SETTINGS_LAUNCHER):
        _unlink_if_exists(path)
    _remove_empty_dir(menu_dir)

    _unlink_if_exists(root / PYZ_NAME)
    _unlink_if_exists(root / ICON_NAME)
    _remove_empty_dir(root)


def _write_cmd_launcher(path: Path, command: str) -> None:
    path.write_text(f"@echo off\r\nstart \"\" {command}\r\n", encoding="utf-8")


def _copy_app_icon(target: Path) -> None:
    icon_resource = resources.files("keyboard_assistant.assets").joinpath(ICON_NAME)
    with resources.as_file(icon_resource) as icon_path:
        shutil.copy2(icon_path, target)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _remove_empty_dir(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        return
