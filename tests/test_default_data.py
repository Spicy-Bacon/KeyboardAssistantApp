import unittest
import time
from importlib import resources

from keyboard_assistant.data import defaults


class DefaultDataTests(unittest.TestCase):
    def test_required_data_files_are_packaged_resources(self) -> None:
        data_root = resources.files("keyboard_assistant.data")
        for filename in defaults.DATA_FILENAMES:
            with self.subTest(filename=filename):
                resource = data_root.joinpath(filename)
                self.assertTrue(resource.is_file())
                self.assertGreater(len(resource.read_text(encoding="utf-8").splitlines()), 0)

    def test_common_typos_load_from_local_tsv(self) -> None:
        self.assertGreaterEqual(len(defaults.TYPO_RULES), 1500)
        self.assertEqual(defaults.TYPO_MAP["teh"], "the")
        self.assertEqual(defaults.TYPO_MAP["recieve"], "receive")
        self.assertGreater(defaults.TYPO_CONFIDENCE["teh"], 0.9)

    def test_common_typos_meet_expanded_quality_floor(self) -> None:
        typo_keys = [rule.typo for rule in defaults.TYPO_RULES]

        self.assertGreaterEqual(len(defaults.TYPO_RULES), 5000)
        self.assertEqual(len(typo_keys), len(set(typo_keys)))
        self.assertEqual(typo_keys, sorted(typo_keys))

        for rule in defaults.TYPO_RULES:
            with self.subTest(typo=rule.typo, correction=rule.correction):
                self.assertNotEqual(rule.typo, rule.correction.lower())
                self.assertGreaterEqual(rule.confidence, 0.0)
                self.assertLessEqual(rule.confidence, 1.0)

    def test_common_typos_do_not_directly_correct_risky_real_words(self) -> None:
        risky_pairs = [
            ("form", "from"),
            ("from", "form"),
            ("were", "we're"),
            ("were", "where"),
            ("well", "we'll"),
            ("ill", "I'll"),
            ("than", "then"),
            ("then", "than"),
            ("shell", "she'll"),
            ("hell", "he'll"),
        ]
        for typo, correction in risky_pairs:
            with self.subTest(typo=typo, correction=correction):
                self.assertNotEqual(defaults.TYPO_MAP.get(typo), correction)

    def test_contractions_include_safe_and_contextual_categories(self) -> None:
        self.assertEqual(defaults.CONTRACTIONS["dont"], "don't")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["dont"], "safe_auto")
        self.assertEqual(defaults.CONTRACTIONS["ill"], "I'll")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["ill"], "contextual")
        self.assertEqual(defaults.CONTRACTIONS["were"], "we're")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["were"], "suggest_only")

    def test_common_words_load_frequency_scores(self) -> None:
        self.assertGreaterEqual(len(defaults.COMMON_WORDS), 50000)
        self.assertIn("academic", defaults.COMMON_WORDS)
        self.assertIn("email", defaults.COMMON_WORDS)
        self.assertGreater(defaults.COMMON_WORD_FREQUENCIES["the"], defaults.COMMON_WORD_FREQUENCIES["email"])

    def test_common_words_meet_expanded_quality_floor(self) -> None:
        required_words = {
            "the",
            "be",
            "and",
            "you",
            "because",
            "receive",
            "definitely",
            "government",
            "university",
            "message",
            "keyboard",
        }
        self.assertTrue(required_words <= defaults.COMMON_WORDS)
        self.assertEqual(len(defaults.COMMON_WORD_FREQUENCIES), len(defaults.COMMON_WORDS))

        for word, score in defaults.COMMON_WORD_FREQUENCIES.items():
            with self.subTest(word=word):
                self.assertIsInstance(score, float)
                self.assertGreater(score, 0.0)

    def test_common_words_are_indexed_by_length_for_lookup(self) -> None:
        indexed_words = {
            word
            for words in defaults.COMMON_WORDS_BY_LENGTH.values()
            for word in words
        }

        self.assertEqual(indexed_words, defaults.COMMON_WORDS)
        self.assertIn("about", defaults.COMMON_WORDS_BY_LENGTH[len("about")])
        self.assertLess(
            len(defaults.COMMON_WORDS_BY_LENGTH[len("about")]),
            len(defaults.COMMON_WORDS),
        )

    def test_common_words_do_not_include_direct_typo_keys(self) -> None:
        allowed_real_words = {"form", "from", "were", "well", "than", "then"}
        typo_keys = set(defaults.TYPO_MAP) - allowed_real_words

        self.assertFalse(typo_keys & defaults.COMMON_WORDS)

    def test_confusion_sets_load_context_rules(self) -> None:
        rules = {(rule.wrong, rule.suggestion): rule for rule in defaults.CONFUSION_RULES}
        self.assertIn(("your welcome", "you're welcome"), rules)
        self.assertIn(("should of", "should have"), rules)
        self.assertEqual(defaults.CONTEXTUAL_REPLACEMENTS[("will", "meat")], "meet")

    def test_common_phrases_load_next_word_fallbacks(self) -> None:
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("thank",)], "you")
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("let", "me")], "know")
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("i", "will")], "check")

    def test_common_phrases_meet_expanded_quality_floor(self) -> None:
        phrase_pairs = {(rule.prefix, rule.suggestion): rule for rule in defaults.PHRASE_RULES}
        required_pairs = {
            ("thank", "you"),
            ("thank you", "for"),
            ("let me", "know"),
            ("please let", "me"),
            ("looking forward", "to"),
            ("as soon", "as"),
        }

        self.assertGreaterEqual(len(defaults.PHRASE_RULES), 10000)
        self.assertEqual(len(defaults.PHRASE_RULES), len(phrase_pairs))
        self.assertTrue(required_pairs <= set(phrase_pairs))

        for rule in defaults.PHRASE_RULES:
            with self.subTest(prefix=rule.prefix, suggestion=rule.suggestion):
                self.assertGreaterEqual(rule.confidence, 0.0)
                self.assertLessEqual(rule.confidence, 1.0)
                self.assertLessEqual(len(rule.suggestion.split()), 3)

    def test_common_phrase_lookup_uses_fast_fallback_map(self) -> None:
        start = time.perf_counter()
        for _ in range(1000):
            self.assertEqual(defaults.NEXT_WORD_FALLBACKS.get(("thank",)), "you")
            self.assertEqual(defaults.NEXT_WORD_FALLBACKS.get(("let", "me")), "know")
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.20)


if __name__ == "__main__":
    unittest.main()
