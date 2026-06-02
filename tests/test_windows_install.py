from pathlib import Path
import tempfile
import unittest

from keyboard_assistant.platform.windows_install import (
    DESKTOP_LAUNCHER,
    PYZ_NAME,
    SETTINGS_LAUNCHER,
    build_pyz_command,
    install_zipapp,
    uninstall_zipapp,
)


class FakeStartupManager:
    supported = True

    def __init__(self) -> None:
        self.enabled_command = ""
        self.disable_calls = 0

    def enable(self, command: str) -> None:
        self.enabled_command = command

    def disable(self) -> None:
        self.disable_calls += 1


class WindowsInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = self.root / "keyboard-assistant.pyz"
        self.source.write_bytes(b"zipapp")
        self.install_root = self.root / "install"
        self.menu_dir = self.root / "menu"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_build_pyz_command_quotes_paths(self) -> None:
        command = build_pyz_command(Path(r"C:\Program Files\Keyboard Assistant\keyboard-assistant.pyz"), "desktop")
        self.assertIn("keyboard-assistant.pyz", command)
        self.assertIn("desktop", command)

    def test_install_copies_zipapp_and_writes_launchers(self) -> None:
        startup = FakeStartupManager()

        result = install_zipapp(
            self.source,
            install_root=self.install_root,
            start_menu_dir=self.menu_dir,
            enable_startup=True,
            startup_manager=startup,
        )

        self.assertEqual(result.installed_pyz, self.install_root / PYZ_NAME)
        self.assertTrue(result.installed_pyz.exists())
        self.assertTrue((self.menu_dir / DESKTOP_LAUNCHER).exists())
        self.assertTrue((self.menu_dir / SETTINGS_LAUNCHER).exists())
        self.assertIn("desktop", (self.menu_dir / DESKTOP_LAUNCHER).read_text(encoding="utf-8"))
        self.assertIn("settings", (self.menu_dir / SETTINGS_LAUNCHER).read_text(encoding="utf-8"))
        self.assertIn("desktop", startup.enabled_command)
        self.assertTrue(result.startup_enabled)

    def test_uninstall_removes_owned_files(self) -> None:
        startup = FakeStartupManager()
        install_zipapp(
            self.source,
            install_root=self.install_root,
            start_menu_dir=self.menu_dir,
            startup_manager=startup,
        )

        uninstall_zipapp(
            install_root=self.install_root,
            start_menu_dir=self.menu_dir,
            startup_manager=startup,
        )

        self.assertFalse((self.install_root / PYZ_NAME).exists())
        self.assertFalse((self.menu_dir / DESKTOP_LAUNCHER).exists())
        self.assertFalse((self.menu_dir / SETTINGS_LAUNCHER).exists())
        self.assertEqual(startup.disable_calls, 1)


if __name__ == "__main__":
    unittest.main()
