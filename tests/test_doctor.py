import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from keyboard_assistant.desktop import main
from keyboard_assistant.diagnostics.doctor import DoctorCheck, format_doctor_checks, run_desktop_doctor
from keyboard_assistant.storage.database import Database


class DoctorTests(unittest.TestCase):
    def test_format_doctor_checks(self) -> None:
        output = format_doctor_checks(
            [
                DoctorCheck("database", True, "ready"),
                DoctorCheck("keyboard_hook", False, "denied"),
            ]
        )
        self.assertIn("OK   database: ready", output)
        self.assertIn("FAIL keyboard_hook: denied", output)

    def test_doctor_report_includes_core_diagnostics_without_hook_test(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            database = Database(Path(tempdir) / "test.sqlite3")
            database.initialize()
            checks = run_desktop_doctor(database, test_hook=False)

        names = {check.name for check in checks}
        self.assertIn("os", names)
        self.assertIn("python", names)
        self.assertIn("package", names)
        self.assertIn("database", names)
        self.assertIn("language_data", names)
        self.assertIn("correction_engine", names)
        self.assertIn("text_injector", names)
        self.assertIn("keyboard_listener", names)
        self.assertIn("local_ai", names)
        self.assertIn("diagnostics", names)
        formatted = format_doctor_checks(checks)
        self.assertNotIn("recieve_message", formatted)

    def test_desktop_doctor_exits_nonzero_on_failed_check(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stdout = io.StringIO()
            with patch(
                "keyboard_assistant.desktop.run_desktop_doctor",
                return_value=[DoctorCheck("keyboard_hook", False, "denied")],
            ):
                with redirect_stdout(stdout):
                    exit_code = main(["--db", str(Path(tempdir) / "test.sqlite3"), "--doctor"])
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL keyboard_hook: denied", stdout.getvalue())

    def test_desktop_refuses_second_instance(self) -> None:
        class ExistingInstance:
            def acquire(self) -> bool:
                return False

            def close(self) -> None:
                raise AssertionError("close should not be called")

        with tempfile.TemporaryDirectory() as tempdir:
            stdout = io.StringIO()
            with patch("keyboard_assistant.desktop.SingleInstance", return_value=ExistingInstance()):
                with redirect_stdout(stdout):
                    exit_code = main(["--db", str(Path(tempdir) / "test.sqlite3")])

        self.assertEqual(exit_code, 1)
        self.assertIn("already running", stdout.getvalue())

    def test_overlay_demo_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stdout = io.StringIO()
            with patch("keyboard_assistant.desktop.run_overlay_demo") as demo:
                with redirect_stdout(stdout):
                    exit_code = main(["--db", str(Path(tempdir) / "test.sqlite3"), "--overlay-demo"])

        self.assertEqual(exit_code, 0)
        demo.assert_called_once_with()
        self.assertIn("Showing sample overlay", stdout.getvalue())

    def test_inject_demo_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch("keyboard_assistant.desktop.run_injection_demo") as demo:
                exit_code = main(
                    [
                        "--db",
                        str(Path(tempdir) / "test.sqlite3"),
                        "--inject-demo",
                        "hello",
                        "--inject-delay",
                        "0",
                    ]
                )

        self.assertEqual(exit_code, 0)
        demo.assert_called_once_with("hello", countdown=0.0)


if __name__ == "__main__":
    unittest.main()
