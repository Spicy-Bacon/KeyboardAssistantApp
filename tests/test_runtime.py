import tempfile
import unittest
from contextlib import redirect_stdout
import io
from pathlib import Path
import time
from unittest.mock import Mock, patch

from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.platform.keyboard_listener import KeyboardEvent
from keyboard_assistant.platform.text_injector import NullTextInjector
from keyboard_assistant.runtime.desktop_runtime import (
    DesktopAssistantRuntime,
    _buffer_metadata,
)
from keyboard_assistant.runtime.components import (
    NullKeyboardListener,
    NullOverlay,
    NullTrayIcon,
)
from keyboard_assistant.storage.database import Database


class StaticAppDetector:
    def __init__(self, context: AppContext | None = None) -> None:
        self.context = context or AppContext(app_identifier="notepad.exe")

    def current_app(self) -> AppContext:
        return self.context


class StaticCursorLocator:
    def __init__(self, x: int = 100, y: int = 100) -> None:
        self.x = x
        self.y = y

    def current_anchor(self):
        return type("Point", (), {"x": self.x, "y": self.y})()


class StaticComponentFactory:
    def __init__(self) -> None:
        self.injector = NullTextInjector()
        self.overlay = NullOverlay()
        self.tray = NullTrayIcon()
        self.listener = NullKeyboardListener()
        self.app_detector = StaticAppDetector()
        self.cursor_locator = StaticCursorLocator()

    def create_text_injector(self):
        return self.injector

    def create_overlay(self, on_close, on_select):
        return self.overlay

    def create_tray(self, on_toggle_pause, on_open_settings, on_exit, is_paused):
        return self.tray

    def create_keyboard_listener(self, on_event, on_error=None):
        return self.listener

    def create_app_detector(self):
        return self.app_detector

    def create_cursor_locator(self):
        return self.cursor_locator


class FailingTextInjectorFactory(StaticComponentFactory):
    def create_text_injector(self):
        raise RuntimeError("no sendinput")


class FailingTrayFactory(StaticComponentFactory):
    def create_tray(self, on_toggle_pause, on_open_settings, on_exit, is_paused):
        raise RuntimeError("tray unavailable")


class DesktopAssistantRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def make_runtime(self, **overrides) -> DesktopAssistantRuntime:
        kwargs = {
            "injector": overrides.pop("injector", NullTextInjector()),
            "overlay": overrides.pop("overlay", NullOverlay()),
            "tray": overrides.pop("tray", NullTrayIcon()),
            "listener": overrides.pop("listener", NullKeyboardListener()),
            "app_detector": overrides.pop("app_detector", StaticAppDetector()),
            "cursor_locator": overrides.pop("cursor_locator", StaticCursorLocator()),
        }
        kwargs.update(overrides)
        with redirect_stdout(io.StringIO()):
            return DesktopAssistantRuntime(self.db, **kwargs)

    def test_runtime_initialises_with_null_injector(self) -> None:
        runtime = self.make_runtime()

        self.assertIsInstance(runtime.injector, NullTextInjector)
        self.assertTrue(runtime.health.text_injector_started)
        self.assertIn("text_injector_injected", runtime.health.events)
        runtime.stop()

    def test_runtime_constructs_components_from_factory(self) -> None:
        factory = StaticComponentFactory()
        with redirect_stdout(io.StringIO()):
            runtime = DesktopAssistantRuntime(self.db, component_factory=factory, allow_null_injector=True)

        self.assertIs(runtime.injector, factory.injector)
        self.assertIs(runtime.overlay, factory.overlay)
        self.assertIs(runtime.tray, factory.tray)
        self.assertIs(runtime.listener, factory.listener)
        runtime.stop()

    def test_text_injector_failure_can_fall_back_and_records_health(self) -> None:
        runtime = self.make_runtime(
            injector=None,
            component_factory=FailingTextInjectorFactory(),
            allow_null_injector=True,
        )

        self.assertIsInstance(runtime.injector, NullTextInjector)
        self.assertTrue(runtime.health.text_injector_failed)
        self.assertIn("text_injector", runtime.health.last_exception)
        runtime.stop()

    def test_text_injector_failure_without_fallback_is_clear(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Text injector failed to start"):
            self.make_runtime(
                injector=None,
                component_factory=FailingTextInjectorFactory(),
                allow_null_injector=False,
            )

    def test_toggle_pause(self) -> None:
        runtime = self.make_runtime()

        self.assertFalse(runtime.is_paused())
        self.assertTrue(runtime.toggle_pause())
        self.assertFalse(runtime.toggle_pause())
        runtime.stop()

    def test_tray_runtime_error_falls_back_to_null_tray(self) -> None:
        runtime = self.make_runtime(tray=None, component_factory=FailingTrayFactory())

        self.assertIsInstance(runtime.tray, NullTrayIcon)
        self.assertTrue(runtime.health.tray_icon_failed)
        self.assertIn("tray_icon", runtime.health.last_exception)
        runtime.stop()

    def test_runtime_health_snapshot_is_diagnostics_safe(self) -> None:
        runtime = self.make_runtime()
        snapshot = runtime.health.snapshot()

        self.assertTrue(snapshot["database_opened"])
        self.assertTrue(snapshot["language_data_loaded"])
        self.assertIn("overlay_injected", snapshot["events"])
        runtime.stop()

    def test_keyboard_events_are_processed_from_queue(self) -> None:
        runtime = self.make_runtime()
        runtime._start_event_worker()
        runtime._handle_keyboard_event(KeyboardEvent(key="char", char="r"))
        deadline = time.time() + 2
        while runtime.buffer.text != "r" and time.time() < deadline:
            time.sleep(0.01)

        self.assertEqual(runtime.buffer.text, "r")
        runtime.stop()

    def test_listener_start_failure_is_recorded_and_worker_stops(self) -> None:
        listener = Mock()
        listener.start.side_effect = RuntimeError("hook denied")
        runtime = self.make_runtime(listener=listener)

        with self.assertRaises(RuntimeError):
            runtime.run()

        self.assertTrue(runtime.health.keyboard_hook_failed)
        self.assertIn("keyboard_hook", runtime.health.last_exception)
        self.assertIsNone(runtime._event_worker)
        runtime.stop()

    def test_space_accepts_focused_visible_suggestion(self) -> None:
        injector = Mock()
        runtime = self.make_runtime(injector=injector)
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
        ]
        runtime._selection_index = 1

        self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
        injector.replace_previous_text.assert_called_once_with(3, "the ")
        runtime.stop()

    def test_space_passes_through_when_middle_choice_is_unchanged_word(self) -> None:
        injector = Mock()
        runtime = self.make_runtime(injector=injector)
        runtime._suggestions = [
            Suggestion("hello", "hello", "typed", 1.0),
            Suggestion("hello", "hello", "typed", 1.0),
            Suggestion("", "there", "next_word", 0.72),
        ]
        runtime._selection_index = 1

        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
        injector.replace_previous_text.assert_not_called()
        runtime.stop()

    def test_arrow_keys_choose_suggestion_for_space_accept(self) -> None:
        injector = Mock()
        overlay = NullOverlay()
        overlay.show_suggestions = Mock()
        runtime = self.make_runtime(injector=injector, overlay=overlay)
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
            Suggestion("", "today", "next_word", 0.72),
        ]
        runtime._selection_index = 1

        self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="right")))
        self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
        injector.replace_previous_text.assert_called_once_with(0, "today ")
        runtime.stop()

    def test_left_arrow_can_choose_typed_word(self) -> None:
        injector = Mock()
        overlay = NullOverlay()
        overlay.show_suggestions = Mock()
        runtime = self.make_runtime(injector=injector, overlay=overlay)
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
            Suggestion("", "today", "next_word", 0.72),
        ]
        runtime._selection_index = 1

        self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="left")))
        self.assertEqual(runtime._selection_index, 0)
        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
        injector.replace_previous_text.assert_not_called()
        runtime.stop()

    def test_mouse_click_accepts_clicked_suggestion_without_space(self) -> None:
        injector = Mock()
        runtime = self.make_runtime(injector=injector)
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
            Suggestion("", "today", "next_word", 0.72),
        ]

        runtime._accept_selected_from_overlay(2)
        injector.replace_previous_text.assert_called_once_with(0, "today")
        runtime.stop()

    def test_tab_and_backspace_are_not_suggestion_shortcuts(self) -> None:
        injector = Mock()
        runtime = self.make_runtime(injector=injector)
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
        ]
        runtime._last_correction = None

        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="tab")))
        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="backspace")))
        injector.replace_previous_text.assert_not_called()
        runtime.stop()

    def test_backspace_removes_last_character_from_buffer(self) -> None:
        runtime = self.make_runtime()
        for char in "teh":
            runtime.buffer.push(char)

        runtime._process_keyboard_event(KeyboardEvent(key="backspace"))

        self.assertEqual(runtime.buffer.text, "te")
        runtime.stop()

    def test_backspace_hides_suggestions_when_word_becomes_empty(self) -> None:
        overlay = NullOverlay()
        overlay.hide = Mock()
        runtime = self.make_runtime(overlay=overlay)
        runtime.buffer.push("a")
        runtime._suggestions = [Suggestion("a", "a", "typed", 1.0)]

        runtime._process_keyboard_event(KeyboardEvent(key="backspace"))

        self.assertEqual(runtime.buffer.text, "")
        overlay.hide.assert_called()
        self.assertFalse(runtime._suggestions)
        runtime.stop()

    def test_arrow_key_without_visible_suggestions_clears_buffer(self) -> None:
        overlay = NullOverlay()
        overlay.hide = Mock()
        runtime = self.make_runtime(overlay=overlay)
        for char in "hello":
            runtime.buffer.push(char)

        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="left")))

        self.assertEqual(runtime.buffer.text, "")
        self.assertFalse(runtime._suggestions)
        overlay.hide.assert_called()
        runtime.stop()

    def test_delete_clears_buffer_and_hides_stale_suggestions(self) -> None:
        overlay = NullOverlay()
        overlay.hide = Mock()
        runtime = self.make_runtime(overlay=overlay)
        runtime.buffer.push("x")
        runtime._suggestions = [Suggestion("x", "x", "typed", 1.0)]

        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="delete")))

        self.assertEqual(runtime.buffer.text, "")
        self.assertFalse(runtime._suggestions)
        overlay.hide.assert_called()
        runtime.stop()

    def test_home_and_end_clear_buffer(self) -> None:
        runtime = self.make_runtime()
        runtime.buffer.push("a")
        runtime._handle_keyboard_event(KeyboardEvent(key="home"))
        self.assertEqual(runtime.buffer.text, "")
        runtime.buffer.push("b")
        runtime._handle_keyboard_event(KeyboardEvent(key="end"))
        self.assertEqual(runtime.buffer.text, "")
        runtime.stop()

    def test_ctrl_shortcut_marks_buffer_unreliable(self) -> None:
        runtime = self.make_runtime()
        runtime.buffer.push("a")

        self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="v", ctrl=True)))

        self.assertEqual(runtime.buffer.text, "")
        self.assertFalse(runtime._buffer_sync.reliable)
        runtime.stop()

    def test_escape_declines_all_visible_suggestions(self) -> None:
        runtime = self.make_runtime()
        runtime._suggestions = [
            Suggestion("teh", "teh", "typed", 1.0),
            self.assistant_suggestion(),
            Suggestion("tge", "the", "keyboard_neighbor", 0.86),
        ]

        self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="escape")))
        runtime._process_keyboard_event(KeyboardEvent(key="escape"))
        self.assertEqual(runtime.stats.suggestions_ignored, 2)
        runtime.stop()

    def test_display_choices_put_typed_left_correction_middle_next_word_right(self) -> None:
        runtime = self.make_runtime()
        for char in "recieve":
            runtime.buffer.push(char)
        choices = runtime._display_choices(
            [
                Suggestion("recieve", "receive", "typo", 0.96),
                Suggestion("", "today", "next_word", 0.72),
            ],
            AppContext(app_identifier="notepad.exe"),
        )

        self.assertEqual([choice.replacement for choice in choices], ["recieve", "receive", "today"])
        runtime.stop()

    def test_display_choices_put_good_word_in_middle(self) -> None:
        runtime = self.make_runtime()
        for char in "studying":
            runtime.buffer.push(char)
        choices = runtime._display_choices([], AppContext(app_identifier="notepad.exe"))

        self.assertEqual(choices[0].replacement, "studying")
        self.assertEqual(choices[1].replacement, "studying")
        self.assertEqual(choices[1].kind, "typed")
        self.assertEqual(choices[2].replacement, "in")
        runtime.stop()

    def test_app_change_clears_typed_buffer_before_next_character(self) -> None:
        detector = StaticAppDetector(AppContext(app_identifier="notepad.exe", window_title="A"))
        runtime = self.make_runtime(app_detector=detector)
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
        detector.context = AppContext(app_identifier="wordpad.exe", window_title="B")
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))

        self.assertEqual(runtime.buffer.text, "b")
        self.assertEqual(runtime.stats.app_context_changes, 1)
        runtime.stop()

    def test_field_change_clears_typed_buffer_before_next_character(self) -> None:
        detector = StaticAppDetector(
            AppContext(app_identifier="notepad.exe", window_class_name="Edit", field_name="body")
        )
        runtime = self.make_runtime(app_detector=detector)
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
        detector.context = AppContext(app_identifier="notepad.exe", window_class_name="Edit", field_name="title")
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))

        self.assertEqual(runtime.buffer.text, "b")
        self.assertEqual(runtime.stats.app_context_changes, 1)
        runtime.stop()

    def test_window_title_change_does_not_clear_typed_buffer(self) -> None:
        detector = StaticAppDetector(
            AppContext(app_identifier="notepad.exe", window_title="A", window_class_name="Notepad")
        )
        runtime = self.make_runtime(app_detector=detector)
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
        detector.context = AppContext(app_identifier="notepad.exe", window_title="B", window_class_name="Notepad")
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))

        self.assertEqual(runtime.buffer.text, "ab")
        self.assertEqual(runtime.stats.app_context_changes, 0)
        runtime.stop()

    def test_cursor_anchor_change_clears_typed_buffer_before_next_character(self) -> None:
        cursor = StaticCursorLocator(100, 100)
        runtime = self.make_runtime(cursor_locator=cursor)
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
        cursor.x = 300
        cursor.y = 220
        runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))

        self.assertEqual(runtime.buffer.text, "b")
        self.assertGreaterEqual(runtime.stats.buffer_resets, 1)
        runtime.stop()

    def test_stop_cleans_up_runtime_components(self) -> None:
        listener = Mock()
        tray = Mock()
        overlay = Mock()
        ai_worker = Mock()
        runtime = self.make_runtime(listener=listener, tray=tray, overlay=overlay, ai_worker=ai_worker)

        runtime.stop()

        listener.stop.assert_called_once()
        ai_worker.cancel.assert_called_once()
        tray.close.assert_called_once()
        overlay.close.assert_called_once()

    def test_stop_continues_cleanup_when_component_raises(self) -> None:
        listener = Mock()
        listener.stop.side_effect = RuntimeError("listener stuck")
        tray = Mock()
        overlay = Mock()
        ai_worker = Mock()
        runtime = self.make_runtime(listener=listener, tray=tray, overlay=overlay, ai_worker=ai_worker)

        runtime.stop()

        listener.stop.assert_called_once()
        ai_worker.cancel.assert_called_once()
        tray.close.assert_called_once()
        overlay.close.assert_called_once()
        self.assertIn("keyboard_listener", runtime.health.last_exception)

    def test_buffer_metadata_does_not_expose_typed_text(self) -> None:
        metadata = _buffer_metadata("secret typed content")

        self.assertIn("len=", metadata)
        self.assertNotIn("secret", metadata)
        self.assertNotIn("typed", metadata)
        self.assertNotIn("content", metadata)

    def assistant_suggestion(self) -> Suggestion:
        return Suggestion("teh", "the", "typo", 0.96, auto_apply=True)


if __name__ == "__main__":
    unittest.main()
