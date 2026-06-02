import json
import tempfile
import unittest
from pathlib import Path

from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.storage.database import Database


FIXTURE = Path(__file__).parent / "fixtures" / "fresh_install_cases.json"
MIN_PASS_RATE = 0.85
MAX_FALSE_AUTO_RATE = 0.03


class FreshInstallBenchmarkTests(unittest.TestCase):
    def test_fresh_install_benchmark_passes_target(self) -> None:
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 100)
        self.assertGreaterEqual(
            sum(1 for case in cases if case["expected_suggestion"] is None),
            20,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            database = Database(Path(tempdir) / "fresh-install.sqlite3")
            database.initialize()
            database.set_bool_setting("learning_enabled", False)
            database.set_model_settings(enabled=False, provider="none", model="")
            assistant = KeyboardAssistant(database)

            failures: list[str] = []
            false_auto_count = 0
            for case in cases:
                suggestions = assistant.suggest(case["input"])
                expected = case["expected_suggestion"]
                if expected is None:
                    auto_suggestions = [suggestion for suggestion in suggestions if suggestion.auto_apply]
                    if auto_suggestions:
                        false_auto_count += 1
                        failures.append(f"{case['input']!r}: unexpected auto {auto_suggestions[0].replacement!r}")
                    continue

                match = next((suggestion for suggestion in suggestions if suggestion.replacement == expected), None)
                if match is None:
                    failures.append(
                        f"{case['input']!r}: missing {expected!r}; got "
                        f"{[(s.replacement, s.kind, s.auto_apply) for s in suggestions]!r}"
                    )
                    continue
                if match.auto_apply and not case["should_auto_apply"]:
                    false_auto_count += 1
                    failures.append(f"{case['input']!r}: false auto {expected!r}")
                elif case["should_auto_apply"] and not match.auto_apply:
                    failures.append(f"{case['input']!r}: expected auto {expected!r}")

            pass_rate = (len(cases) - len(failures)) / len(cases)
            false_auto_rate = false_auto_count / len(cases)
            self.assertGreaterEqual(pass_rate, MIN_PASS_RATE, "\n".join(failures[:20]))
            self.assertLessEqual(false_auto_rate, MAX_FALSE_AUTO_RATE, "\n".join(failures[:20]))


if __name__ == "__main__":
    unittest.main()
