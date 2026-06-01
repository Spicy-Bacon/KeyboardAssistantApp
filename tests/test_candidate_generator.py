import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.core.candidate_generator import CandidateGenerator
from keyboard_assistant.core.models import AppContext
from keyboard_assistant.storage.database import Database


class CandidateGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()
        self.generator = CandidateGenerator(self.db)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_exact_typo_candidate(self) -> None:
        candidate = self.generator.generate("teh")[0]
        self.assertEqual(candidate.original_text, "teh")
        self.assertEqual(candidate.suggestion_text, "the")
        self.assertEqual(candidate.suggestion_type, "typo")
        self.assertEqual(candidate.source, "common_typos")
        self.assertTrue(candidate.should_auto_apply)

    def test_contraction_candidate(self) -> None:
        candidate = self.generator.generate("dont")[0]
        self.assertEqual(candidate.suggestion_text, "don't")
        self.assertEqual(candidate.suggestion_type, "contraction")
        self.assertEqual(candidate.metadata["category"], "safe_auto")
        self.assertTrue(candidate.should_auto_apply)

    def test_contextual_contraction_is_suggest_only(self) -> None:
        candidate = self.generator.generate("ill")[0]
        self.assertEqual(candidate.suggestion_text, "I'll")
        self.assertEqual(candidate.suggestion_type, "contraction")
        self.assertFalse(candidate.should_auto_apply)

    def test_capitalization_candidate(self) -> None:
        candidate = self.generator.generate("i")[0]
        self.assertEqual(candidate.suggestion_text, "I")
        self.assertEqual(candidate.suggestion_type, "capitalization")

    def test_repeated_letter_candidate(self) -> None:
        candidate = self.generator.generate("sooon")[0]
        self.assertEqual(candidate.suggestion_text, "soon")
        self.assertEqual(candidate.suggestion_type, "repeated_letter")
        self.assertFalse(candidate.should_auto_apply)

    def test_keyboard_slip_candidate(self) -> None:
        candidate = self.generator.generate("tge")[0]
        self.assertEqual(candidate.suggestion_text, "the")
        self.assertEqual(candidate.suggestion_type, "keyboard_slip")

    def test_transposition_candidate(self) -> None:
        candidate = self.generator.generate("peolpe")[0]
        self.assertEqual(candidate.suggestion_text, "people")
        self.assertEqual(candidate.suggestion_type, "transposition")

    def test_edit_distance_candidate(self) -> None:
        candidate = self.generator.generate("abot")[0]
        self.assertEqual(candidate.suggestion_text, "about")
        self.assertEqual(candidate.suggestion_type, "edit_distance")

    def test_confusion_pair_candidate(self) -> None:
        candidate = self.generator.generate("your welcome")[0]
        self.assertEqual(candidate.original_text, "your welcome")
        self.assertEqual(candidate.suggestion_text, "you're welcome")
        self.assertEqual(candidate.suggestion_type, "confusion_pair")
        self.assertFalse(candidate.should_auto_apply)

    def test_default_phrase_prediction_candidate(self) -> None:
        candidate = self.generator.generate("thank ")[0]
        self.assertEqual(candidate.suggestion_text, "you")
        self.assertEqual(candidate.suggestion_type, "phrase_prediction")
        self.assertEqual(candidate.source, "common_phrases")

    def test_user_phrase_prediction_candidate(self) -> None:
        self.db.increment_phrase_frequency("thank everyone", app_identifier="notepad.exe")
        candidate = self.generator.generate("thank ", AppContext(app_identifier="notepad.exe"))[0]
        self.assertEqual(candidate.suggestion_text, "everyone")
        self.assertEqual(candidate.suggestion_type, "user_phrase_prediction")
        self.assertEqual(candidate.source, "user_phrase_history")


if __name__ == "__main__":
    unittest.main()
