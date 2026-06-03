import tempfile
import unittest
import time
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

    def test_sentence_start_capitalization_candidate(self) -> None:
        candidate = self.generator.generate("hello. how")[0]
        self.assertEqual(candidate.original_text, "how")
        self.assertEqual(candidate.suggestion_text, "How")
        self.assertEqual(candidate.metadata["rule"], "sentence_start")
        self.assertTrue(candidate.should_auto_apply)

    def test_empty_buffer_words_are_not_sentence_capitalized(self) -> None:
        for word in ["form", "class", "function", "apple", "from"]:
            with self.subTest(word=word):
                candidates = self.generator.generate(word)
                self.assertFalse(
                    any(candidate.suggestion_text == word.capitalize() for candidate in candidates),
                    candidates,
                )

    def test_proper_case_candidate_is_suggest_only(self) -> None:
        candidate = self.generator.generate("iphone")[0]
        self.assertEqual(candidate.suggestion_text, "iPhone")
        self.assertEqual(candidate.metadata["rule"], "proper_case")
        self.assertFalse(candidate.should_auto_apply)

    def test_mixed_case_words_are_not_broken(self) -> None:
        candidates = self.generator.generate("iPhone")
        self.assertEqual(candidates, [])

    def test_repeated_letter_candidate(self) -> None:
        candidate = self.generator.generate("sooon")[0]
        self.assertEqual(candidate.suggestion_text, "soon")
        self.assertIn(candidate.suggestion_type, {"repeated_letter", "typo"})
        self.assertFalse(candidate.should_auto_apply)

    def test_keyboard_slip_candidate(self) -> None:
        candidate = self.generator.generate("tge")[0]
        self.assertEqual(candidate.suggestion_text, "the")
        self.assertEqual(candidate.suggestion_type, "keyboard_slip")

    def test_transposition_candidate(self) -> None:
        candidate = self.generator.generate("peolpe")[0]
        self.assertEqual(candidate.suggestion_text, "people")
        self.assertIn(candidate.suggestion_type, {"transposition", "typo"})

    def test_edit_distance_candidate(self) -> None:
        candidate = self.generator.generate("abot")[0]
        self.assertEqual(candidate.suggestion_text, "about")
        self.assertIn(candidate.suggestion_type, {"edit_distance", "typo"})

    def test_extra_letter_edit_distance_candidate(self) -> None:
        candidate = self.generator.generate("abouyt")[0]
        self.assertEqual(candidate.suggestion_text, "about")
        self.assertEqual(candidate.suggestion_type, "edit_distance")

    def test_confusion_pair_candidate(self) -> None:
        candidates = self.generator.generate("your welcome")
        candidate = next(candidate for candidate in candidates if candidate.original_text == "your welcome")
        self.assertEqual(candidate.original_text, "your welcome")
        self.assertEqual(candidate.suggestion_text, "you're welcome")
        self.assertEqual(candidate.suggestion_type, "confusion_pair")
        self.assertFalse(candidate.should_auto_apply)

    def test_default_phrase_prediction_candidate(self) -> None:
        candidate = self.generator.generate("thank ")[0]
        self.assertEqual(candidate.suggestion_text, "you")
        self.assertEqual(candidate.suggestion_type, "phrase_prediction")
        self.assertEqual(candidate.source, "common_phrases")

    def test_incomplete_word_does_not_trigger_phrase_prediction(self) -> None:
        candidates = self.generator.generate("thank")

        self.assertFalse(any(candidate.suggestion_type == "phrase_prediction" for candidate in candidates))

    def test_phrase_prediction_supports_one_two_and_three_word_prefixes(self) -> None:
        cases = {
            "thank ": "you",
            "thank you ": "for",
            "thank you for ": "your",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                candidate = next(
                    candidate
                    for candidate in self.generator.generate(text)
                    if candidate.suggestion_type == "phrase_prediction"
                )
                self.assertEqual(candidate.suggestion_text, expected)
                self.assertFalse(candidate.should_auto_apply)

    def test_user_phrase_prediction_candidate(self) -> None:
        self.db.increment_phrase_frequency("thank everyone", app_identifier="notepad.exe")
        candidate = self.generator.generate("thank ", AppContext(app_identifier="notepad.exe"))[0]
        self.assertEqual(candidate.suggestion_text, "everyone")
        self.assertEqual(candidate.suggestion_type, "user_phrase_prediction")
        self.assertEqual(candidate.source, "user_phrase_history")

    def test_candidates_are_deduplicated_by_original_suggestion_and_type(self) -> None:
        candidates = self.generator.generate("youre welcome")
        keys = [
            (candidate.original_text.lower(), candidate.suggestion_text.lower(), candidate.suggestion_type)
            for candidate in candidates
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_confusion_lookup_remains_fast_with_expanded_rules(self) -> None:
        start = time.perf_counter()
        for _ in range(100):
            self.generator.generate("please review the document before the meeting")
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.50)


if __name__ == "__main__":
    unittest.main()
