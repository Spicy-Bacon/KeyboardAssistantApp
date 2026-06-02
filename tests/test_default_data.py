import unittest
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
        self.assertGreaterEqual(len(defaults.TYPO_RULES), 300)
        self.assertEqual(defaults.TYPO_MAP["teh"], "the")
        self.assertEqual(defaults.TYPO_MAP["recieve"], "receive")
        self.assertGreater(defaults.TYPO_CONFIDENCE["teh"], 0.9)

    def test_contractions_include_safe_and_contextual_categories(self) -> None:
        self.assertEqual(defaults.CONTRACTIONS["dont"], "don't")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["dont"], "safe_auto")
        self.assertEqual(defaults.CONTRACTIONS["ill"], "I'll")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["ill"], "contextual")
        self.assertEqual(defaults.CONTRACTIONS["were"], "we're")
        self.assertEqual(defaults.CONTRACTION_CATEGORIES["were"], "suggest_only")

    def test_common_words_load_frequency_scores(self) -> None:
        self.assertGreater(len(defaults.COMMON_WORDS), 200)
        self.assertIn("academic", defaults.COMMON_WORDS)
        self.assertIn("email", defaults.COMMON_WORDS)
        self.assertGreater(defaults.COMMON_WORD_FREQUENCIES["the"], defaults.COMMON_WORD_FREQUENCIES["email"])

    def test_confusion_sets_load_context_rules(self) -> None:
        rules = {(rule.wrong, rule.suggestion): rule for rule in defaults.CONFUSION_RULES}
        self.assertIn(("your welcome", "you're welcome"), rules)
        self.assertIn(("should of", "should have"), rules)
        self.assertEqual(defaults.CONTEXTUAL_REPLACEMENTS[("will", "meat")], "meet")

    def test_common_phrases_load_next_word_fallbacks(self) -> None:
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("thank",)], "you")
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("let", "me")], "know")
        self.assertEqual(defaults.NEXT_WORD_FALLBACKS[("i", "will")], "check")


if __name__ == "__main__":
    unittest.main()
