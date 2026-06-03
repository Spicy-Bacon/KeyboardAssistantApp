import unittest

from keyboard_assistant.core.context import TypedBuffer, extract_text_context


class TextContextTests(unittest.TestCase):
    def test_extracts_current_word(self) -> None:
        context = extract_text_context("hello. how ar")
        self.assertEqual(context.current_word, "ar")
        self.assertEqual(context.previous_words[-1], "how")
        self.assertFalse(context.starts_new_sentence)

    def test_detects_sentence_start(self) -> None:
        context = extract_text_context("hello. h")
        self.assertEqual(context.current_word, "h")
        self.assertTrue(context.starts_new_sentence)

    def test_typed_buffer_handles_backspace(self) -> None:
        buffer = TypedBuffer()
        for char in "tehx\b":
            buffer.push(char)
        self.assertEqual(buffer.text, "teh")

    def test_typed_buffer_replaces_suffix(self) -> None:
        buffer = TypedBuffer()
        for char in "I typed teh":
            buffer.push(char)
        buffer.replace_suffix("teh", "the ")
        self.assertEqual(buffer.text, "I typed the ")

    def test_typed_buffer_empty_suffix_appends(self) -> None:
        buffer = TypedBuffer()
        for char in "I will ":
            buffer.push(char)
        buffer.replace_suffix("", "go")
        self.assertEqual(buffer.text, "I will go")


if __name__ == "__main__":
    unittest.main()
