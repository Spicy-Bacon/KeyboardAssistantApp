import unittest
import tempfile
import threading
import time
from pathlib import Path

from keyboard_assistant.ai.local_ai import LocalAIResult, LocalAIService
from keyboard_assistant.ai.local_ai import _disable_thinking_prompt
from keyboard_assistant.ai.suggestion_worker import LocalAISuggestionWorker
from keyboard_assistant.ai.suggestion_worker import _clean_ai_text
from keyboard_assistant.core.models import AppContext
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
        worker.request("I will now ", AppContext())
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
        worker.request("I will now ", AppContext())
        self.assertTrue(called.wait(0.2))
        self.assertEqual(seen, ["alpha"])

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
        worker.request("first context ", AppContext())
        worker.request("second context ", AppContext())
        self.assertTrue(called.wait(0.3))
        time.sleep(0.05)
        self.assertEqual(seen, ["beta"])

    def test_meta_answer_is_not_used_as_suggestion(self) -> None:
        self.assertEqual(_clean_ai_text('We are given the text: "I will"'), "")
        self.assertEqual(_clean_ai_text("finish the work"), "finish the work")


if __name__ == "__main__":
    unittest.main()
