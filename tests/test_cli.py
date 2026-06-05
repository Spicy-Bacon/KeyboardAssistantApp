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

    def test_doctor_command_reports_core_checks(self) -> None:
        exit_code, output = self.run_cli("doctor")

        self.assertEqual(exit_code, 0)
        self.assertIn("python:", output)
        self.assertIn("database:", output)
        self.assertIn("language_data:", output)
        self.assertIn("correction_engine:", output)

    def test_settings_show_json(self) -> None:
        exit_code, output = self.run_cli("settings", "show", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["correction_strength"], "balanced")
        self.assertTrue(payload["assistant_enabled"])
        self.assertTrue(payload["learning_enabled"])
        self.assertFalse(payload["local_ai_enabled"])

    def test_settings_set_json_keeps_human_output_available(self) -> None:
        exit_code, output = self.run_cli("settings", "set", "strength", "light", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["settings"]["correction_strength"], "light")

        exit_code, output = self.run_cli("settings", "set", "strength", "balanced")
        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Updated.\n")

    def test_appearance_show_json(self) -> None:
        exit_code, output = self.run_cli("appearance", "show", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["theme"], "dark")
        self.assertEqual(payload["suggestion_size"], "medium")
        self.assertEqual(payload["opacity"], 94)
        self.assertTrue(payload["animations_enabled"])

    def test_apps_list_json(self) -> None:
        self.run_cli("apps", "set", "code.exe", "--name", "Visual Studio Code", "--status", "off")

        exit_code, output = self.run_cli("apps", "list", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["profiles"][0]["app_identifier"], "code.exe")
        self.assertEqual(payload["excluded_apps"][0]["assistant_status"], "off")

    def test_apps_remove_json(self) -> None:
        self.run_cli("apps", "set", "code.exe", "--status", "off")

        exit_code, output = self.run_cli("apps", "remove", "code.exe", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["apps"]["profiles"], [])

    def test_dictionary_list_json(self) -> None:
        self.run_cli("dictionary", "add", "Qwen", "--never-correct")

        exit_code, output = self.run_cli("dictionary", "list", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["words"][0]["word"], "Qwen")
        self.assertTrue(payload["never_correct_words"][0]["never_correct"])

    def test_privacy_summary_json_uses_counts_not_raw_text(self) -> None:
        from keyboard_assistant.storage.database import Database

        database = Database(self.db_path)
        database.initialize()
        database.record_accepted_suggestion("private typed text", "private replacement", "typo")

        exit_code, output = self.run_cli("privacy", "summary", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["local_only"])
        self.assertEqual(payload["data_counts"]["accepted_suggestions"], 1)
        self.assertNotIn("private typed text", output)
        self.assertNotIn("private replacement", output)

    def test_local_ai_status_json(self) -> None:
        exit_code, output = self.run_cli("local-ai", "status", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["provider"], "none")
        self.assertFalse(payload["required"])

    def test_doctor_json_reports_core_checks(self) -> None:
        exit_code, output = self.run_cli("doctor", "--json")

        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        check_names = {check["name"] for check in payload["checks"]}
        self.assertIn("python", check_names)
        self.assertIn("database", check_names)
        self.assertIn("language_data", check_names)
        self.assertIn("correction_engine", check_names)

    def test_version_command_exits_zero(self) -> None:
        exit_code, output = self.run_cli("--version")
        self.assertEqual(exit_code, 0)
        self.assertIn("keyboard-assistant 0.1.0", output)


if __name__ == "__main__":
    unittest.main()
