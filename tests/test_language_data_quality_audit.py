import tempfile
import unittest
from pathlib import Path

from scripts.audit_language_data_quality import audit_language_data, cleanup_obviously_unsafe, format_audit
from scripts.validate_language_data import validate_language_data


VALID_FILES = {
    "common_typos.tsv": "teh\tthe\t0.98\nrecieve\treceive\t0.96\n",
    "common_words.tsv": "the\t9.0\nreceive\t5.2\nform\t5.1\n",
    "common_phrases.tsv": "thank\tyou\t0.95\nlet me\tknow\t0.90\n",
    "confusion_sets.tsv": "should of\tshould have\tphrase\t0.95\n",
    "contractions.tsv": "dont\tdon't\tsafe_auto\t0.98\nill\tI'll\tcontextual\t0.75\n",
}


class LanguageDataQualityAuditTests(unittest.TestCase):
    def test_real_language_data_audit_runs(self) -> None:
        summary = audit_language_data()
        output = format_audit(summary)

        self.assertGreaterEqual(summary.counts["common_typos.tsv"], 5000)
        self.assertGreaterEqual(summary.counts["common_words.tsv"], 50000)
        self.assertGreaterEqual(summary.counts["common_phrases.tsv"], 10000)
        self.assertGreaterEqual(summary.counts["confusion_sets.tsv"], 500)
        self.assertIn("Language data quality audit:", output)

    def test_cleanup_removes_only_obviously_unsafe_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files["common_typos.tsv"] = (
                "teh\tthe\t0.98\n"
                "form\tfrom\t0.95\n"
                "same\tsame\t0.90\n"
                "bad\tgood\t1.5\n"
            )
            _write_files(data_dir, files)

            summary = cleanup_obviously_unsafe(data_dir)
            remaining = (data_dir / "common_typos.tsv").read_text(encoding="utf-8")

            self.assertEqual(summary.removed_rows["common_typos.tsv"], 3)
            self.assertIn("teh\tthe\t0.98", remaining)
            self.assertNotIn("form\tfrom", remaining)
            self.assertTrue(validate_language_data(data_dir).ok)

    def test_risky_direct_typo_corrections_are_not_present(self) -> None:
        summary = audit_language_data()
        risky_direct = [
            finding
            for finding in summary.findings
            if finding.filename == "common_typos.tsv" and finding.category == "risky_direct_typo"
        ]

        self.assertEqual(risky_direct, [])

    def test_phrase_suggestions_remain_short(self) -> None:
        summary = audit_language_data()
        too_long = [
            finding
            for finding in summary.findings
            if finding.filename == "common_phrases.tsv" and finding.category == "phrase_too_long"
        ]

        self.assertEqual(too_long, [])

    def test_phrase_variants_are_not_reported_as_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files["common_phrases.tsv"] = "thank\tyou\t0.95\nthank\tfully\t0.70\n"
            _write_files(data_dir, files)

            summary = audit_language_data(data_dir)
            duplicates = [finding for finding in summary.findings if finding.category == "duplicate_phrase_rule"]

            self.assertEqual(duplicates, [])

    def test_exact_duplicate_phrase_rules_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            data_dir = Path(tempdir)
            files = dict(VALID_FILES)
            files["common_phrases.tsv"] = "thank\tyou\t0.95\nthank\tyou\t0.90\n"
            _write_files(data_dir, files)

            summary = audit_language_data(data_dir)
            duplicates = [finding for finding in summary.findings if finding.category == "duplicate_phrase_rule"]

            self.assertEqual(len(duplicates), 1)


def _write_files(data_dir: Path, files: dict[str, str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (data_dir / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
