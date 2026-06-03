import unittest
from unittest.mock import patch

from keyboard_assistant.platform.keyboard_listener import KeyboardEvent, WindowsKeyboardListener, _fallback_vk_to_char


class KeyboardListenerTests(unittest.TestCase):
    def test_fallback_maps_letters(self) -> None:
        with patch("keyboard_assistant.platform.keyboard_listener._is_caps_lock_on", return_value=False):
            self.assertEqual(_fallback_vk_to_char(0x41), "a")
            self.assertEqual(_fallback_vk_to_char(0x41, shift=True), "A")

    def test_fallback_respects_caps_lock(self) -> None:
        with patch("keyboard_assistant.platform.keyboard_listener._is_caps_lock_on", return_value=True):
            self.assertEqual(_fallback_vk_to_char(0x41), "A")
            self.assertEqual(_fallback_vk_to_char(0x41, shift=True), "a")

    def test_fallback_maps_digits_and_punctuation(self) -> None:
        self.assertEqual(_fallback_vk_to_char(0x31), "1")
        self.assertEqual(_fallback_vk_to_char(0x31, shift=True), "!")
        self.assertEqual(_fallback_vk_to_char(0xBF), "/")
        self.assertEqual(_fallback_vk_to_char(0xBF, shift=True), "?")

    def test_callback_exception_is_reported_and_not_suppressed(self) -> None:
        seen: list[BaseException] = []
        listener = object.__new__(WindowsKeyboardListener)
        listener.on_event = lambda _event: (_ for _ in ()).throw(ValueError("boom"))
        listener.on_error = seen.append
        listener.callback_error_count = 0

        self.assertFalse(listener._dispatch_event_safely(KeyboardEvent(key="char", char="a")))
        self.assertEqual(listener.callback_error_count, 1)
        self.assertIsInstance(seen[0], ValueError)


if __name__ == "__main__":
    unittest.main()
