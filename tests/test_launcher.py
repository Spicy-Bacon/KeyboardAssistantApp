import io
from contextlib import redirect_stdout
import unittest

from keyboard_assistant.launcher import main


class LauncherTests(unittest.TestCase):
    def test_version_command(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--version"])
        self.assertEqual(exit_code, 0)
        self.assertIn("keyboard-assistant 0.1.0", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
