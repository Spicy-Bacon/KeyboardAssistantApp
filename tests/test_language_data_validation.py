import tempfile
import unittest
from pathlib import Path

from scripts.validate_language_data import SPECS, format_summary, validate_language_data


VALID_FILES = {
    "common_typos.tsv": "teh\tthe\t0.98\nrecieve\treceive\t0.96\n",
    "common_words.tsv": "the\t9.0\nreceive\t5.2\n",
    "common_phrases.tsv": "thank\tyou\t0.95\nlet me\tknow\t0.90\n",
    "confusion_sets.tsv": "should of\tshould have\tphrase\t0.95\n",
    "contractions.tsv": "dont\tdon't\tsafe_auto\t0.98\nill\tI'll\tcontextual\t0.75\n",
}


class LanguageDataValidationTests(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            _write_files(data_dir, VALID_FILES)

            summary = validate_language_data(data_dir)

            self.assertTrue(summary.ok, summary.errors)
            self.assertEqual(summary.duplicate_count, 0)
            self.assertEqual(summary.invalid_row_count, 0)
            self.assertEqual(summary.counts["common_typos.tsv"], 2)
            self.assertIn("OK", format_summary(summary))

    def test_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files.pop("common_words.tsv")
            _write_files(data_dir, files)

            summary = validate_language_data(data_dir)

            self.assertFalse(summary.ok)
            self.assertIn("common_words.tsv: file is missing", summary.errors)

    def test_duplicate_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files["common_typos.tsv"] = "teh\tthe\t0.98\nteh\tthe\t0.97\n"
            _write_files(data_dir, files)

            summary = validate_language_data(data_dir)

            self.assertFalse(summary.ok)
            self.assertEqual(summary.duplicate_count, 1)

    def test_invalid_confidence_and_category_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files["common_phrases.tsv"] = "thank\tyou\t1.5\n"
            files["contractions.tsv"] = "dont\tdon't\tunsafe\t0.98\n"
            _write_files(data_dir, files)

            summary = validate_language_data(data_dir)

            self.assertFalse(summary.ok)
            self.assertGreaterEqual(summary.invalid_row_count, 2)

    def test_real_language_data_passes(self) -> None:
        summary = validate_language_data()

        self.assertTrue(summary.ok, "\n".join(summary.errors[:20]))
        for filename in SPECS:
            self.assertGreater(summary.counts[filename], 0)


def _write_files(data_dir: Path, files: dict[str, str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (data_dir / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
