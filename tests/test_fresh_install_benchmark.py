import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from keyboard_assistant.core.assistant import KeyboardAssistant
from keyboard_assistant.storage.database import Database


FIXTURE = Path(__file__).parent / "fixtures" / "fresh_install_cases.json"
MIN_PASS_RATE = 0.85
MAX_FALSE_AUTO_RATE = 0.03
MIN_NEGATIVE_NO_AUTOCORRECT_RATE = 0.98


class FreshInstallBenchmarkTests(unittest.TestCase):
    def test_fresh_install_benchmark_passes_target(self) -> None:
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 100)
        self.assertGreaterEqual(
            sum(1 for case in cases if case["expected_suggestion"] is None),
            120,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            database = Database(Path(tempdir) / "fresh-install.sqlite3")
            database.initialize()
            database.set_bool_setting("learning_enabled", False)
            database.set_model_settings(enabled=False, provider="none", model="")
            assistant = KeyboardAssistant(database)

            failures: list[str] = []
            false_auto_count = 0
            category_totals: dict[str, int] = defaultdict(int)
            category_passes: dict[str, int] = defaultdict(int)
            for case in cases:
                suggestions = assistant.suggest(case["input"])
                expected = case["expected_suggestion"]
                category = case.get("type", "uncategorized")
                category_totals[category] += 1
                if expected is None:
                    auto_suggestions = [suggestion for suggestion in suggestions if suggestion.auto_apply]
                    if auto_suggestions:
                        false_auto_count += 1
                        failures.append(f"{case['input']!r}: unexpected auto {auto_suggestions[0].replacement!r}")
                    else:
                        category_passes[category] += 1
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
                else:
                    category_passes[category] += 1

            pass_rate = (len(cases) - len(failures)) / len(cases)
            false_auto_rate = false_auto_count / len(cases)
            report_lines = ["Fresh-install benchmark report:"]
            report_lines.append(f"- total_pass_rate: {len(cases) - len(failures)}/{len(cases)} ({pass_rate:.1%})")
            for category in sorted(category_totals):
                total = category_totals[category]
                passed = category_passes[category]
                report_lines.append(f"- {category}: {passed}/{total} ({passed / total:.1%})")
            report_lines.append(f"- false_auto_corrections: {false_auto_count}")
            report_lines.append(f"- false_auto_correction_rate: {false_auto_rate:.1%}")
            print("\n" + "\n".join(report_lines))
            self.assertGreaterEqual(pass_rate, MIN_PASS_RATE, "\n".join(failures[:20]))
            self.assertLessEqual(false_auto_rate, MAX_FALSE_AUTO_RATE, "\n".join(failures[:20]))
            negative_total = category_totals["negative_no_autocorrect"]
            negative_pass_rate = category_passes["negative_no_autocorrect"] / negative_total
            self.assertGreaterEqual(negative_pass_rate, MIN_NEGATIVE_NO_AUTOCORRECT_RATE, "\n".join(failures[:20]))


if __name__ == "__main__":
    unittest.main()
