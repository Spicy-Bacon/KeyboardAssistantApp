import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.diagnostics.logger import DiagnosticsLogger, default_log_path
from keyboard_assistant.storage.database import Database


class DiagnosticsLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.tempdir.name) / "diagnostics.log"
        self.logger = DiagnosticsLogger(self.log_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_redacts_text_fields(self) -> None:
        self.logger.info("suggestion_seen", input_text="secret typed text", replacement="secret")
        event = self.logger.read_events()[0]
        self.assertEqual(event.metadata["input_text"], "<redacted>")
        self.assertEqual(event.metadata["replacement"], "<redacted>")

    def test_clear_removes_log(self) -> None:
        self.logger.info("runtime_started")
        self.assertTrue(self.log_path.exists())
        self.logger.clear()
        self.assertFalse(self.log_path.exists())

    def test_default_log_path_uses_database_stem(self) -> None:
        path = default_log_path(Path(self.tempdir.name) / "app.sqlite3")
        self.assertEqual(path.name, "app.diagnostics.log")


class DiagnosticsDatabasePathTests(unittest.TestCase):
    def test_database_default_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            db = Database(Path(dirname) / "test.sqlite3")
            self.assertEqual(default_log_path(db.path).name, "test.diagnostics.log")


if __name__ == "__main__":
    unittest.main()

