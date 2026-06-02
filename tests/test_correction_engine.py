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

    def test_keyboard_neighbor_typo_suggestion(self) -> None:
        suggestions = self.assistant.suggest("tge")
        self.assertEqual(suggestions[0].replacement, "the")
        self.assertEqual(suggestions[0].kind, "keyboard_neighbor")
        self.assertFalse(suggestions[0].auto_apply)

    def test_transposed_word_suggestion(self) -> None:
        suggestions = self.assistant.suggest("peolpe")
        self.assertEqual(suggestions[0].replacement, "people")
        self.assertEqual(suggestions[0].kind, "transposition")
        self.assertFalse(suggestions[0].auto_apply)

    def test_missing_character_word_suggestion(self) -> None:
        suggestions = self.assistant.suggest("abot")
        self.assertEqual(suggestions[0].replacement, "about")
        self.assertEqual(suggestions[0].kind, "edit_distance")
        self.assertFalse(suggestions[0].auto_apply)

    def test_common_word_does_not_get_fuzzy_suggestion(self) -> None:
        suggestions = self.assistant.suggest("hello about")
        self.assertEqual(suggestions, [])

    def test_apostrophe_suggestion(self) -> None:
        suggestions = self.assistant.suggest("dont")
        self.assertEqual(suggestions[0].replacement, "don't")

    def test_contextual_contraction_is_not_auto_applied(self) -> None:
        suggestions = self.assistant.suggest("ill")
        self.assertEqual(suggestions[0].replacement, "I'll")
        self.assertFalse(suggestions[0].auto_apply)

    def test_capitalizes_i(self) -> None:
        suggestions = self.assistant.suggest("i")
        self.assertEqual(suggestions[0].replacement, "I")

    def test_sentence_start_capitalization(self) -> None:
        suggestions = self.assistant.suggest("hello. how")
        self.assertEqual(suggestions[0].replacement, "How")
        self.assertEqual(suggestions[0].kind, "capitalization")
        self.assertTrue(suggestions[0].auto_apply)

    def test_sentence_start_after_exclamation_and_question(self) -> None:
        self.assertEqual(self.assistant.suggest("thanks! i")[0].replacement, "I")
        self.assertEqual(self.assistant.suggest("ok? let")[0].replacement, "Let")

    def test_known_mixed_case_words_are_preserved(self) -> None:
        self.assertEqual(self.assistant.suggest("iPhone"), [])
        suggestion = self.assistant.suggest("iphone")[0]
        self.assertEqual(suggestion.replacement, "iPhone")
        self.assertFalse(suggestion.auto_apply)

    def test_sensitive_context_disables_suggestions(self) -> None:
        suggestions = self.assistant.suggest("teh", AppContext(is_password=True))
        self.assertEqual(suggestions, [])

    def test_suggestion_policy_explains_sensitive_context(self) -> None:
        suggestions, policy = self.assistant.suggest_with_policy("teh", AppContext(is_password=True))
        self.assertEqual(suggestions, [])
        self.assertFalse(policy.allowed)
        self.assertEqual(policy.reason, "sensitive_context")

    def test_ignored_suggestions_reduce_confidence(self) -> None:
        suggestion = self.assistant.suggest("teh")[0]
        for _ in range(3):
            self.assistant.ignore(suggestion)
        reduced = self.assistant.suggest("teh")[0]
        self.assertLess(reduced.confidence, suggestion.confidence)

    def test_global_assistant_off_suppresses_suggestions(self) -> None:
        self.db.set_bool_setting("assistant_enabled", False)
        self.assertEqual(self.assistant.suggest("teh"), [])

    def test_light_strength_prevents_auto_apply(self) -> None:
        self.db.set_setting("correction_strength", "light")
        suggestion = self.assistant.suggest("teh")[0]
        self.assertEqual(suggestion.replacement, "the")
        self.assertFalse(suggestion.auto_apply)

    def test_aggressive_strength_keeps_auto_apply(self) -> None:
        self.db.set_setting("correction_strength", "aggressive")
        suggestion = self.assistant.suggest("teh")[0]
        self.assertTrue(suggestion.auto_apply)

    def test_app_profile_off_suppresses_suggestions(self) -> None:
        self.db.upsert_app_profile("notepad.exe", assistant_status="off")
        suggestions = self.assistant.suggest("teh", AppContext(app_identifier="notepad.exe"))
        self.assertEqual(suggestions, [])

    def test_app_profile_limited_uses_light_strength(self) -> None:
        self.db.upsert_app_profile("notepad.exe", assistant_status="limited")
        suggestion = self.assistant.suggest("teh", AppContext(app_identifier="notepad.exe"))[0]
        self.assertFalse(suggestion.auto_apply)
        policy = self.assistant.suggestion_policy(AppContext(app_identifier="notepad.exe"))
        self.assertEqual(policy.reason, "app_profile_limited")
        self.assertEqual(policy.correction_strength, "light")

    def test_learning_disabled_skips_history(self) -> None:
        suggestion = self.assistant.suggest("teh")[0]
        self.db.set_bool_setting("learning_enabled", False)
        self.assistant.ignore(suggestion)
        self.assertEqual(self.db.ignored_score("teh", "the"), 0)

    def test_observe_text_learns_phrase_prediction(self) -> None:
        self.assistant.observe_text("I will meet")
        suggestions = self.assistant.suggest("I will ")
        self.assertEqual(suggestions[0].replacement, "meet")
        self.assertEqual(suggestions[0].kind, "next_word")

    def test_accept_records_correction_history(self) -> None:
        suggestion = self.assistant.suggest("teh")[0]
        self.assistant.accept(suggestion)
        latest = self.db.latest_correction()
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.original_text, "teh")
        self.assertEqual(latest.corrected_text, "the")

    def test_revert_records_reverted_correction(self) -> None:
        suggestion = self.assistant.suggest("teh")[0]
        self.assistant.accept(suggestion)
        self.assistant.revert("teh", "the")
        summary = self.db.data_summary()
        self.assertEqual(summary["reverted_corrections"], 1)

    def test_repeated_custom_word_is_added_to_personal_dictionary(self) -> None:
        for _ in range(3):
            self.assistant.observe_text("Using Qwen")
        words = [row["word"] for row in self.db.list_personal_words()]
        self.assertIn("Qwen", words)


if __name__ == "__main__":
    unittest.main()
