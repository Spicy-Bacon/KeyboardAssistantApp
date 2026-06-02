import unittest
from unittest.mock import patch

from keyboard_assistant.platform.keyboard_listener import _fallback_vk_to_char


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


if __name__ == "__main__":
    unittest.main()
