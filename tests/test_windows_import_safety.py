import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_import_probe(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


class WindowsImportSafetyTests(unittest.TestCase):
    def assert_probe_ok(self, code: str) -> None:
        result = run_import_probe(code)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_tray_icon_imports_without_windows_callback_type(self) -> None:
        self.assert_probe_ok(
            """
            import ctypes
            if hasattr(ctypes, "WINFUNCTYPE"):
                delattr(ctypes, "WINFUNCTYPE")

            from keyboard_assistant.ui import tray_icon

            assert tray_icon.WNDCLASS is None
            assert tray_icon.NOTIFYICONDATA is None
            try:
                tray_icon.TrayIcon(
                    on_toggle_pause=lambda: False,
                    on_open_settings=lambda: None,
                    on_exit=lambda: None,
                    is_paused=lambda: False,
                )
            except RuntimeError as exc:
                assert str(exc) == "Tray icon is currently Windows-only."
            else:
                raise AssertionError("TrayIcon should reject non-Windows instantiation")
            """
        )

    def test_suggestion_overlay_imports_without_windows_callback_type(self) -> None:
        self.assert_probe_ok(
            """
            import ctypes
            if hasattr(ctypes, "WINFUNCTYPE"):
                delattr(ctypes, "WINFUNCTYPE")

            from keyboard_assistant.ui import suggestion_overlay

            assert suggestion_overlay.WNDCLASS is None
            assert suggestion_overlay.PAINTSTRUCT is None
            try:
                suggestion_overlay.SuggestionOverlay()
            except RuntimeError as exc:
                assert str(exc) == "Suggestion overlay is currently Windows-only."
            else:
                raise AssertionError("SuggestionOverlay should reject non-Windows instantiation")
            """
        )

    def test_keyboard_listener_imports_without_windows_callback_type(self) -> None:
        self.assert_probe_ok(
            """
            import ctypes
            if hasattr(ctypes, "WINFUNCTYPE"):
                delattr(ctypes, "WINFUNCTYPE")

            from keyboard_assistant.platform import keyboard_listener

            assert keyboard_listener.LowLevelKeyboardProc is None
            try:
                keyboard_listener.WindowsKeyboardListener(lambda event: False)
            except RuntimeError as exc:
                assert str(exc) == "Windows keyboard hooks are only available on Windows."
            else:
                raise AssertionError("WindowsKeyboardListener should reject non-Windows instantiation")
            """
        )

    def test_core_assistant_import_does_not_load_desktop_ui_modules(self) -> None:
        self.assert_probe_ok(
            """
            import sys
            from keyboard_assistant.core.assistant import KeyboardAssistant

            assert KeyboardAssistant is not None
            assert "keyboard_assistant.ui.tray_icon" not in sys.modules
            assert "keyboard_assistant.ui.suggestion_overlay" not in sys.modules
            """
        )


if __name__ == "__main__":
    unittest.main()
