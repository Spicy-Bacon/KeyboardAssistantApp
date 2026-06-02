import json
import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.storage.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_personal_dictionary_never_correct(self) -> None:
        self.db.add_personal_word("Yew", never_correct=True)
        self.assertTrue(self.db.is_never_correct_word("yew"))

    def test_word_frequency_upsert(self) -> None:
        self.assertEqual(self.db.increment_word_frequency("hello", "demo"), 1)
        self.assertEqual(self.db.increment_word_frequency("hello", "demo"), 2)
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT frequency FROM word_frequency_user WHERE word = ? AND app_identifier = ?",
                ("hello", "demo"),
            ).fetchone()
        self.assertEqual(row["frequency"], 2)
        self.assertEqual(self.db.word_frequency("hello", "demo"), 2)

    def test_default_settings_are_created(self) -> None:
        settings = self.db.get_settings()
        self.assertTrue(settings.assistant_enabled)
        self.assertEqual(settings.correction_strength, "balanced")
        self.assertTrue(settings.learning_enabled)
        self.assertEqual(self.db.get_appearance_settings().theme, "dark")

    def test_app_profile_upsert(self) -> None:
        self.db.upsert_app_profile("notepad.exe", app_name="Notepad", assistant_status="limited")
        profile = self.db.get_app_profile("NOTEPAD.EXE")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.app_name, "Notepad")
        self.assertEqual(profile.assistant_status, "limited")

    def test_data_summary_counts_learning_data(self) -> None:
        self.db.record_ignored_suggestion("teh", "the", "typo")
        summary = self.db.data_summary()
        self.assertEqual(summary["ignored_suggestions"], 1)

    def test_clear_learning_data_leaves_dictionary(self) -> None:
        self.db.add_personal_word("Yew")
        self.db.record_ignored_suggestion("teh", "the", "typo")
        self.db.clear_learning_data()
        self.assertEqual(self.db.data_summary()["ignored_suggestions"], 0)
        self.assertEqual(self.db.data_summary()["personal_dictionary"], 1)

    def test_phrase_predictions_rank_frequency(self) -> None:
        self.db.increment_phrase_frequency("I will meet")
        self.db.increment_phrase_frequency("I will go")
        self.db.increment_phrase_frequency("I will go")
        self.assertEqual(self.db.phrase_predictions(("I", "will"))[0], "go")

    def test_model_settings_round_trip(self) -> None:
        self.db.set_model_settings(provider="ollama", model="qwen2.5:3b", enabled=True)
        settings = self.db.get_model_settings()
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["provider"], "ollama")
        self.assertEqual(settings["model"], "qwen2.5:3b")

    def test_appearance_settings_round_trip(self) -> None:
        self.db.set_appearance_settings(
            theme="light",
            suggestion_size="large",
            opacity=85,
            animations_enabled=False,
        )
        appearance = self.db.get_appearance_settings()
        self.assertEqual(appearance.theme, "light")
        self.assertEqual(appearance.suggestion_size, "large")
        self.assertEqual(appearance.opacity, 85)
        self.assertFalse(appearance.animations_enabled)

    def test_dictionary_export_writes_json(self) -> None:
        self.db.add_personal_word("Qwen", never_correct=True)
        export_path = Path(self.tempdir.name) / "dictionary.json"
        count = self.db.export_personal_dictionary(export_path)

        payload = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(count, 1)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["words"][0]["word"], "Qwen")
        self.assertTrue(payload["words"][0]["never_correct"])

    def test_dictionary_import_merges_words(self) -> None:
        self.db.add_personal_word("Qwen", never_correct=True)
        import_path = Path(self.tempdir.name) / "dictionary.json"
        import_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "words": [
                        {"word": "Qwen", "source": "imported", "frequency": 5, "never_correct": False},
                        {"word": "Codex", "source": "imported", "frequency": 2, "never_correct": True},
                    ],
                }
            ),
            encoding="utf-8",
        )

        count = self.db.import_personal_dictionary(import_path)
        words = {row["word"]: row for row in self.db.list_personal_words()}

        self.assertEqual(count, 2)
        self.assertEqual(words["Qwen"]["frequency"], 5)
        self.assertTrue(words["Qwen"]["never_correct"])
        self.assertEqual(words["Codex"]["frequency"], 2)
        self.assertTrue(words["Codex"]["never_correct"])


if __name__ == "__main__":
    unittest.main()
