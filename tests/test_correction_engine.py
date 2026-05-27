import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.core.models import AppContext
from keyboard_assistant.storage.database import Database


class CorrectionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()
        self.assistant = KeyboardAssistant(self.db)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_common_typo_suggestion(self) -> None:
        suggestions = self.assistant.suggest("teh")
        self.assertEqual(suggestions[0].replacement, "the")
        self.assertTrue(suggestions[0].auto_apply)

    def test_apostrophe_suggestion(self) -> None:
        suggestions = self.assistant.suggest("dont")
        self.assertEqual(suggestions[0].replacement, "don't")

    def test_capitalizes_i(self) -> None:
        suggestions = self.assistant.suggest("i")
        self.assertEqual(suggestions[0].replacement, "I")

    def test_sentence_start_capitalization(self) -> None:
        suggestions = self.assistant.suggest("hello. how")
        self.assertEqual(suggestions[0].replacement, "How")
        self.assertFalse(suggestions[0].auto_apply)

    def test_sensitive_context_disables_suggestions(self) -> None:
        suggestions = self.assistant.suggest("teh", AppContext(is_password=True))
        self.assertEqual(suggestions, [])

    def test_ignored_suggestions_reduce_confidence(self) -> None:
        suggestion = self.assistant.suggest("teh")[0]
        for _ in range(3):
            self.assistant.ignore(suggestion)
        reduced = self.assistant.suggest("teh")[0]
        self.assertLess(reduced.confidence, suggestion.confidence)


if __name__ == "__main__":
    unittest.main()

