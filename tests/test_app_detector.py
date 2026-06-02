import unittest
from unittest.mock import patch

from keyboard_assistant.core.models import AppContext
from keyboard_assistant.platform.app_detector import AppDetector
from keyboard_assistant.platform.app_detector import classify_focused_control


class AppDetectorTests(unittest.TestCase):
    def test_classifies_password_edit_control(self) -> None:
        self.assertEqual(classify_focused_control("Edit", password_char=9679), "password")

    def test_classifies_standard_text_controls(self) -> None:
        self.assertEqual(classify_focused_control("Edit"), "text")
        self.assertEqual(classify_focused_control("RICHEDIT50W"), "text")

    def test_classifies_terminal_controls(self) -> None:
        self.assertEqual(classify_focused_control("Windows.UI.Terminal.Control"), "terminal")

    def test_unknown_control_is_not_sensitive_by_default(self) -> None:
        self.assertEqual(classify_focused_control("Chrome_WidgetWin_1"), "")

    def test_current_app_uses_short_cache(self) -> None:
        detector = AppDetector(cache_ttl_seconds=10)
        with patch("keyboard_assistant.platform.app_detector._is_windows_available", return_value=True):
            with patch(
                "keyboard_assistant.platform.app_detector._current_windows_app",
                return_value=AppContext(app_identifier="notepad.exe"),
            ) as current:
                self.assertEqual(detector.current_app().app_identifier, "notepad.exe")
                self.assertEqual(detector.current_app().app_identifier, "notepad.exe")
        self.assertEqual(current.call_count, 1)


if __name__ == "__main__":
    unittest.main()
