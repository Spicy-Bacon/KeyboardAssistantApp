import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.core.candidate_generator import Candidate
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.core.safety_gate import AutoApplySafetyGate, looks_code_like_text
from keyboard_assistant.core.suggestion_ranker import SuggestionRanker
from keyboard_assistant.storage.database import Database


class AutoApplySafetyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()
        self.gate = AutoApplySafetyGate(self.db)
        self.ranker = SuggestionRanker(self.db)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_safe_typo_can_auto_apply(self) -> None:
        suggestion = self.rank(self.candidate("teh", "the", "typo", 0.96, "common_typos", True))[0]
        self.assertTrue(suggestion.auto_apply)

    def test_safe_contraction_can_auto_apply(self) -> None:
        suggestion = self.rank(
            self.candidate(
                "dont",
                "don't",
                "contraction",
                0.98,
                "contractions",
                True,
                {"category": "safe_auto"},
            )
        )[0]
        self.assertTrue(suggestion.auto_apply)

    def test_standalone_i_can_auto_apply(self) -> None:
        suggestion = self.rank(
            self.candidate(
                "i",
                "I",
                "capitalization",
                0.98,
                "capitalization_rule",
                True,
                {"rule": "standalone_i"},
            )
        )[0]
        self.assertTrue(suggestion.auto_apply)

    def test_protected_words_do_not_auto_apply(self) -> None:
        cases = [
            self.candidate("form", "from", "transposition", 0.95, "common_words", True),
            self.candidate("were", "we're", "contraction", 0.82, "contractions", True, {"category": "suggest_only"}),
            self.candidate("well", "we'll", "contraction", 0.74, "contractions", True, {"category": "contextual"}),
            self.candidate("ill", "I'll", "contraction", 0.78, "contractions", True, {"category": "contextual"}),
            self.candidate("apple", "Apple", "capitalization", 0.93, "capitalization_rule", True, {"rule": "sentence_start"}),
            self.candidate("class", "Class", "capitalization", 0.93, "capitalization_rule", True, {"rule": "sentence_start"}),
        ]
        for candidate in cases:
            with self.subTest(original=candidate.original_text, replacement=candidate.suggestion_text):
                suggestions = self.rank(candidate)
                if suggestions:
                    self.assertFalse(suggestions[0].auto_apply)

    def test_code_like_text_blocks_auto_apply(self) -> None:
        candidate = self.candidate("recieve", "receive", "typo", 0.96, "common_typos", True)
        for text in [
            "recieve_message",
            "def recieve_message():",
            "userName",
            "KeyboardAssistantApp",
            "npm-install",
            "src/keyboard_assistant/core",
            "https://example.com",
            "test_file.py",
            "--help",
            "public static void main",
        ]:
            with self.subTest(text=text):
                suggestions = self.rank(candidate, source_text=text)
                self.assertFalse(suggestions[0].auto_apply if suggestions else False)
                self.assertTrue(looks_code_like_text(text))

    def test_risky_app_context_blocks_auto_apply(self) -> None:
        suggestion = self.rank(
            self.candidate("teh", "the", "typo", 0.96, "common_typos", True),
            app_context=AppContext(app_identifier="code.exe"),
        )[0]
        self.assertFalse(suggestion.auto_apply)

    def test_ignored_or_reverted_suggestion_blocks_auto_apply(self) -> None:
        candidate = self.candidate("teh", "the", "typo", 0.96, "common_typos", True)
        self.db.record_ignored_suggestion("teh", "the", "typo")
        self.assertFalse(self.rank(candidate)[0].auto_apply)

        self.tempdir.cleanup()
        self.setUp()
        self.db.record_reverted_correction("teh", "the")
        self.assertFalse(self.rank(candidate)[0].auto_apply)

    def test_local_ai_and_phrase_predictions_do_not_auto_apply(self) -> None:
        phrase = self.rank(self.candidate("", "you", "phrase_prediction", 0.95, "common_phrases", True))[0]
        learned = self.rank(self.candidate("", "everyone", "user_phrase_prediction", 0.95, "user_phrase_history", True))[0]
        local_ai = Suggestion("", "tomorrow", "local_ai", 0.99, auto_apply=True)

        self.assertFalse(phrase.auto_apply)
        self.assertFalse(learned.auto_apply)
        self.assertFalse(self.gate.allow_suggestion_auto_apply(local_ai))

    def rank(
        self,
        candidate: Candidate,
        app_context: AppContext | None = None,
        source_text: str = "",
    ) -> list[Suggestion]:
        return self.ranker.rank(
            [candidate],
            app_context=app_context or AppContext(),
            correction_strength="balanced",
            source_text=source_text,
        )

    def candidate(
        self,
        original: str,
        suggestion: str,
        suggestion_type: str,
        confidence: float,
        source: str,
        auto_apply: bool,
        metadata: dict | None = None,
    ) -> Candidate:
        return Candidate(
            original_text=original,
            suggestion_text=suggestion,
            suggestion_type=suggestion_type,
            base_confidence=confidence,
            source=source,
            should_auto_apply=auto_apply,
            metadata=metadata or {},
        )


if __name__ == "__main__":
    unittest.main()
