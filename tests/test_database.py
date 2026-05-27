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
        self.db.increment_word_frequency("hello", "demo")
        self.db.increment_word_frequency("hello", "demo")
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT frequency FROM word_frequency_user WHERE word = ? AND app_identifier = ?",
                ("hello", "demo"),
            ).fetchone()
        self.assertEqual(row["frequency"], 2)


if __name__ == "__main__":
    unittest.main()

