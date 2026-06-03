import unittest

from scripts.profile_startup import format_metrics, measure_startup


class StartupProfileTests(unittest.TestCase):
    def test_profile_startup_reports_expected_metrics(self) -> None:
        metrics = measure_startup()
        output = format_metrics(metrics)

        for key in [
            "data_import_seconds",
            "core_import_seconds",
            "database_initialize_seconds",
            "assistant_initialize_seconds",
            "suggest_typo_seconds",
            "typo_lookup_10k_seconds",
            "phrase_lookup_10k_seconds",
            "word_frequency_lookup_10k_seconds",
            "confusion_lookup_10k_seconds",
        ]:
            self.assertIn(key, metrics)
            self.assertGreaterEqual(metrics[key], 0.0)
        self.assertIn("Startup/profile metrics:", output)


if __name__ == "__main__":
    unittest.main()
