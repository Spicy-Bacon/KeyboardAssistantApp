import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.core.candidate_generator import Candidate
from keyboard_assistant.core.models import AppContext
from keyboard_assistant.core.suggestion_ranker import SuggestionRanker
from keyboard_assistant.storage.database import Database


class SuggestionRankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()
        self.ranker = SuggestionRanker(self.db)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_typo_ranks_highly_and_auto_applies(self) -> None:
        suggestion = self.ranker.rank([self.candidate("teh", "the", "typo", 0.96, "common_typos", True)])[0]
        self.assertEqual(suggestion.replacement, "the")
        self.assertGreaterEqual(suggestion.confidence, 0.98)
        self.assertTrue(suggestion.auto_apply)

    def test_contraction_ranks_highly_and_auto_applies(self) -> None:
        suggestion = self.ranker.rank(
            [
                self.candidate(
                    "dont",
                    "don't",
                    "contraction",
                    0.98,
                    "contractions",
                    True,
                    {"category": "safe_auto"},
                )
            ]
        )[0]
        self.assertEqual(suggestion.replacement, "don't")
        self.assertEqual(suggestion.kind, "apostrophe")
        self.assertTrue(suggestion.auto_apply)

    def test_real_word_candidate_does_not_auto_apply(self) -> None:
        suggestion = self.ranker.rank(
            [self.candidate("form", "from", "transposition", 0.95, "common_words", True)]
        )[0]
        self.assertEqual(suggestion.replacement, "from")
        self.assertFalse(suggestion.auto_apply)

    def test_confusion_pair_suggests_without_auto_apply(self) -> None:
        suggestion = self.ranker.rank(
            [
                self.candidate(
                    "your welcome",
                    "you're welcome",
                    "confusion_pair",
                    0.95,
                    "confusion_sets",
                    False,
                    {"context_hint": "phrase"},
                )
            ]
        )[0]
        self.assertEqual(suggestion.replacement, "you're welcome")
        self.assertFalse(suggestion.auto_apply)

    def test_ignored_suggestions_rank_lower(self) -> None:
        candidate = self.candidate("teh", "the", "typo", 0.96, "common_typos", True)
        original = self.ranker.rank([candidate])[0]
        for _ in range(3):
            self.db.record_ignored_suggestion("teh", "the", "typo")
        reduced = self.ranker.rank([candidate])[0]
        self.assertLess(reduced.confidence, original.confidence)

    def test_accepted_suggestions_rank_higher(self) -> None:
        candidate = self.candidate("recieve", "receive", "typo", 0.90, "common_typos", True)
        original = self.ranker.rank([candidate])[0]
        for _ in range(3):
            self.db.record_accepted_suggestion("recieve", "receive", "typo")
        boosted = self.ranker.rank([candidate])[0]
        self.assertGreater(boosted.confidence, original.confidence)

    def test_reverted_suggestions_rank_lower(self) -> None:
        candidate = self.candidate("teh", "the", "typo", 0.96, "common_typos", True)
        original = self.ranker.rank([candidate])[0]
        self.db.record_reverted_correction("teh", "the")
        reduced = self.ranker.rank([candidate])[0]
        self.assertLess(reduced.confidence, original.confidence)

    def test_app_specific_word_frequency_boosts_score(self) -> None:
        candidate = self.candidate("", "Exeter", "phrase_prediction", 0.72, "common_phrases", False)
        original = self.ranker.rank([candidate], AppContext(app_identifier="notepad.exe"))[0]
        for _ in range(3):
            self.db.increment_word_frequency("Exeter", "notepad.exe")
        boosted = self.ranker.rank([candidate], AppContext(app_identifier="notepad.exe"))[0]
        self.assertGreater(boosted.confidence, original.confidence)

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
