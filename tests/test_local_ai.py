import unittest
import tempfile
import threading
import time
from pathlib import Path

from keyboard_assistant.ai.local_ai import LIVE_LOCAL_AI_TIMEOUT_SECONDS, LocalAIResult, LocalAIService
from keyboard_assistant.ai.local_ai import _disable_thinking_prompt
from keyboard_assistant.ai.suggestion_worker import LocalAISuggestionWorker
from keyboard_assistant.ai.suggestion_worker import _clean_ai_text
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.storage.database import Database


class LocalAIServiceTests(unittest.TestCase):
    def test_disabled_status(self) -> None:
        service = LocalAIService(provider_name="none", model="", enabled=False)
        self.assertEqual(service.status(), "disabled")

    def test_disabled_test_is_unavailable(self) -> None:
        service = LocalAIService(provider_name="none", model="", enabled=False)
        result = service.test()
        self.assertFalse(result.ok)
        self.assertIn("disabled", result.error)

    def test_unsupported_provider(self) -> None:
        service = LocalAIService(provider_name="custom", model="model", enabled=True)
        result = service.test()
        self.assertFalse(result.ok)
        self.assertIn("unsupported", result.error)

    def test_disable_thinking_prompt_is_idempotent(self) -> None:
        self.assertEqual(_disable_thinking_prompt("/no_think\nhello"), "/no_think\nhello")
        self.assertEqual(_disable_thinking_prompt("hello"), "/no_think\nhello")

    def test_suggest_next_uses_live_timeout(self) -> None:
        class RecordingProvider:
            def __init__(self) -> None:
                self.timeout_seconds = 0.0

            def generate(self, _prompt: str, _model: str, timeout_seconds: float = 0.0) -> LocalAIResult:
                self.timeout_seconds = timeout_seconds
                return LocalAIResult(ok=True, text="next")

        service = LocalAIService(provider_name="ollama", model="fake", enabled=True)
        provider = RecordingProvider()
        service.provider = provider

        result = service.suggest_next("I will now continue ")
        self.assertTrue(result.ok)
        self.assertEqual(provider.timeout_seconds, LIVE_LOCAL_AI_TIMEOUT_SECONDS)


class FakeAIService:
    def __init__(self, provider_name: str, model: str, enabled: bool) -> None:
        self.enabled = enabled

    def suggest_next(self, context: str) -> LocalAIResult:
        if not self.enabled:
            return LocalAIResult(ok=False, text="", error="disabled")
        return LocalAIResult(ok=True, text="beta" if "second" in context else "alpha")


class LocalAISuggestionWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_disabled_worker_does_not_callback(self) -> None:
        called = threading.Event()
        worker = LocalAISuggestionWorker(
            self.db,
            lambda _text, _suggestions: called.set(),
            delay_seconds=0.01,
            service_factory=FakeAIService,
        )
        worker.request("I will now continue ", AppContext())
        self.assertFalse(called.wait(0.05))

    def test_enabled_worker_callbacks_with_suggestion(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        called = threading.Event()
        seen: list[str] = []

        def on_suggestions(_text: str, suggestions: list) -> None:
            seen.append(suggestions[0].replacement)
            called.set()

        worker = LocalAISuggestionWorker(
            self.db,
            on_suggestions,
            delay_seconds=0.01,
            service_factory=FakeAIService,
        )
        worker.request("I will now continue ", AppContext())
        self.assertTrue(called.wait(0.2))
        self.assertEqual(seen, ["alpha"])

    def test_worker_skips_short_context(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        called = threading.Event()
        worker = LocalAISuggestionWorker(
            self.db,
            lambda _text, _suggestions: called.set(),
            delay_seconds=0.01,
            service_factory=FakeAIService,
        )
        worker.request("I will ", AppContext())
        self.assertFalse(called.wait(0.05))

    def test_worker_skips_when_rule_suggestion_is_confident(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        called = threading.Event()
        worker = LocalAISuggestionWorker(
            self.db,
            lambda _text, _suggestions: called.set(),
            delay_seconds=0.01,
            service_factory=FakeAIService,
        )
        worker.request(
            "I will now continue ",
            AppContext(),
            rule_suggestions=[Suggestion("", "check", "next_word", 0.90)],
        )
        self.assertFalse(called.wait(0.05))

    def test_new_request_cancels_pending_request(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        called = threading.Event()
        seen: list[str] = []

        def on_suggestions(_text: str, suggestions: list) -> None:
            seen.append(suggestions[0].replacement)
            called.set()

        worker = LocalAISuggestionWorker(
            self.db,
            on_suggestions,
            delay_seconds=0.05,
            service_factory=FakeAIService,
        )
        worker.request("first context continues ", AppContext())
        worker.request("second context continues ", AppContext())
        self.assertTrue(called.wait(0.3))
        time.sleep(0.05)
        self.assertEqual(seen, ["beta"])

    def test_outdated_running_request_is_ignored(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        first_started = threading.Event()
        release_first = threading.Event()
        called = threading.Event()
        seen: list[str] = []

        class SlowFirstAIService:
            calls = 0

            def __init__(self, provider_name: str, model: str, enabled: bool) -> None:
                self.enabled = enabled

            def suggest_next(self, context: str) -> LocalAIResult:
                type(self).calls += 1
                if type(self).calls == 1:
                    first_started.set()
                    release_first.wait(0.5)
                    return LocalAIResult(ok=True, text="stale")
                return LocalAIResult(ok=True, text="fresh")

        def on_suggestions(_text: str, suggestions: list) -> None:
            seen.append(suggestions[0].replacement)
            called.set()

        worker = LocalAISuggestionWorker(
            self.db,
            on_suggestions,
            delay_seconds=0.01,
            service_factory=SlowFirstAIService,
        )
        worker.request("first context continues ", AppContext())
        self.assertTrue(first_started.wait(0.2))
        worker.request("second context continues ", AppContext())
        release_first.set()
        self.assertTrue(called.wait(0.5))
        time.sleep(0.05)
        self.assertEqual(seen, ["fresh"])

    def test_meta_answer_is_not_used_as_suggestion(self) -> None:
        self.assertEqual(_clean_ai_text('We are given the text: "I will"'), "")
        self.assertEqual(_clean_ai_text("finish the work"), "finish the work")

    def test_worker_reports_provider_exception_without_callback(self) -> None:
        self.db.set_model_settings(provider="ollama", model="fake", enabled=True)
        called = threading.Event()
        error_seen = threading.Event()
        errors: list[BaseException] = []

        class FailingAIService:
            def __init__(self, provider_name: str, model: str, enabled: bool) -> None:
                pass

            def suggest_next(self, context: str) -> LocalAIResult:
                raise TimeoutError("model timed out")

        worker = LocalAISuggestionWorker(
            self.db,
            lambda _text, _suggestions: called.set(),
            on_error=lambda exc: (errors.append(exc), error_seen.set()),
            delay_seconds=0.01,
            service_factory=FailingAIService,
        )
        worker.request("I will now continue ", AppContext())

        self.assertTrue(error_seen.wait(0.2))
        self.assertFalse(called.is_set())
        self.assertIsInstance(errors[0], TimeoutError)


if __name__ == "__main__":
    unittest.main()
