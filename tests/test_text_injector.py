import ctypes
import unittest

from keyboard_assistant.platform.text_injector import INPUT, KEYBDINPUT, KEYEVENTF_UNICODE, _keyboard_input


class TextInjectorTests(unittest.TestCase):
    def test_input_structure_is_full_windows_union_size(self) -> None:
        self.assertGreaterEqual(ctypes.sizeof(INPUT), ctypes.sizeof(KEYBDINPUT) + ctypes.sizeof(ctypes.c_ulong))

    def test_keyboard_input_sets_keyboard_union(self) -> None:
        event = _keyboard_input(0, ord("A"), KEYEVENTF_UNICODE)
        self.assertEqual(event.type, 1)
        self.assertEqual(event.union.ki.wScan, ord("A"))
        self.assertEqual(event.union.ki.dwFlags, KEYEVENTF_UNICODE)


if __name__ == "__main__":
    unittest.main()
