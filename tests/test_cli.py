import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from keyboard_assistant.cli import main
from keyboard_assistant.platform.startup import StartupStatus


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "test.sqlite3"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--db", str(self.db_path), *args])
        return exit_code, stdout.getvalue()

    def test_dictionary_export_import_commands(self) -> None:
        export_path = Path(self.tempdir.name) / "dictionary.json"

        exit_code, output = self.run_cli("dictionary", "add", "Qwen", "--never-correct")
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Added.\n")

        exit_code, output = self.run_cli("dictionary", "export", str(export_path))
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Exported 1 words.\n")
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["words"][0]["word"], "Qwen")

        import_path = Path(self.tempdir.name) / "import.json"
        import_path.write_text(json.dumps(["Codex"]), encoding="utf-8")
        exit_code, output = self.run_cli("dictionary", "import", str(import_path))
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Imported 1 words.\n")

        exit_code, output = self.run_cli("dictionary", "list")
        self.assertEqual(exit_code, 0)
        self.assertIn("Qwen", output)
        self.assertIn("Codex", output)

    def test_startup_status_command(self) -> None:
        class Manager:
            def status(self) -> StartupStatus:
                return StartupStatus(supported=True, enabled=True, command="python -m keyboard_assistant.desktop")

        with patch("keyboard_assistant.cli.WindowsStartupManager", return_value=Manager()):
            exit_code, output = self.run_cli("startup", "status")

        self.assertEqual(exit_code, 0)
        self.assertIn("startup: on", output)
        self.assertIn("keyboard_assistant.desktop", output)

    def test_version_command_exits_zero(self) -> None:
        exit_code, output = self.run_cli("--version")
        self.assertEqual(exit_code, 0)
        self.assertIn("keyboard-assistant 0.1.0", output)


if __name__ == "__main__":
    unittest.main()
