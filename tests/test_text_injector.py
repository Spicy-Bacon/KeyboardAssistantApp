import ctypes
import unittest
from unittest.mock import patch

from keyboard_assistant.platform.text_injector import INPUT, KEYBDINPUT, KEYEVENTF_UNICODE, WindowsTextInjector, _keyboard_input


class TextInjectorTests(unittest.TestCase):
    def test_input_structure_is_full_windows_union_size(self) -> None:
        self.assertGreaterEqual(ctypes.sizeof(INPUT), ctypes.sizeof(KEYBDINPUT) + ctypes.sizeof(ctypes.c_ulong))

    def test_keyboard_input_sets_keyboard_union(self) -> None:
        event = _keyboard_input(0, ord("A"), KEYEVENTF_UNICODE)
        self.assertEqual(event.type, 1)
        self.assertEqual(event.union.ki.wScan, ord("A"))
        self.assertEqual(event.union.ki.dwFlags, KEYEVENTF_UNICODE)

    def test_text_injector_requires_windows_at_instantiation(self) -> None:
        with patch("keyboard_assistant.platform.text_injector._is_windows_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "only available on Windows"):
                WindowsTextInjector()


if __name__ == "__main__":
    unittest.main()
