import tempfile
import unittest
from contextlib import redirect_stdout
import io
from pathlib import Path
import time
from unittest.mock import Mock, patch

from keyboard_assistant.platform.keyboard_listener import KeyboardEvent
from keyboard_assistant.runtime.desktop_runtime import DesktopAssistantRuntime, NullTrayIcon
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.storage.database import Database


class DesktopAssistantRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "test.sqlite3")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_toggle_pause(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                self.assertIsInstance(runtime.tray, NullTrayIcon)
                self.assertFalse(runtime.is_paused())
                self.assertTrue(runtime.toggle_pause())
                self.assertFalse(runtime.toggle_pause())
                runtime.stop()

    def test_keyboard_events_are_processed_from_queue(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime._start_event_worker()
                runtime._handle_keyboard_event(KeyboardEvent(key="char", char="r"))
                deadline = time.time() + 2
                while runtime.buffer.text != "r" and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(runtime.buffer.text, "r")
                runtime.stop()

    def test_space_accepts_focused_visible_suggestion(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("teh", "teh", "typed", 1.0),
                    self.assistant_suggestion(),
                ]
                runtime._selection_index = 1

                self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
                runtime.injector.replace_previous_text.assert_called_once_with(3, "the ")
                runtime.stop()

    def test_space_passes_through_when_middle_choice_is_unchanged_word(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("hello", "hello", "typed", 1.0),
                    Suggestion("hello", "hello", "typed", 1.0),
                    Suggestion("", "there", "next_word", 0.72),
                ]
                runtime._selection_index = 1

                self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
                runtime.injector.replace_previous_text.assert_not_called()
                runtime.stop()

    def test_arrow_keys_choose_suggestion_for_space_accept(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.cursor_locator.current_anchor = Mock(return_value=type("Point", (), {"x": 100, "y": 100})())
                runtime.overlay.call_soon = Mock(side_effect=lambda callback: callback())
                runtime.overlay.show_suggestions = Mock()
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("teh", "teh", "typed", 1.0),
                    self.assistant_suggestion(),
                    Suggestion("", "today", "next_word", 0.72),
                ]
                runtime._selection_index = 1

                self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="right")))
                self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
                runtime.injector.replace_previous_text.assert_called_once_with(0, "today ")
                runtime.stop()

    def test_left_arrow_can_choose_typed_word(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.cursor_locator.current_anchor = Mock(return_value=type("Point", (), {"x": 100, "y": 100})())
                runtime.overlay.call_soon = Mock(side_effect=lambda callback: callback())
                runtime.overlay.show_suggestions = Mock()
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("teh", "teh", "typed", 1.0),
                    self.assistant_suggestion(),
                    Suggestion("", "today", "next_word", 0.72),
                ]
                runtime._selection_index = 1

                self.assertTrue(runtime._handle_keyboard_event(KeyboardEvent(key="left")))
                self.assertEqual(runtime._selection_index, 0)
                self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="space", char=" ")))
                runtime.injector.replace_previous_text.assert_not_called()
                runtime.stop()

    def test_mouse_click_accepts_clicked_suggestion_without_space(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("teh", "teh", "typed", 1.0),
                    self.assistant_suggestion(),
                    Suggestion("", "today", "next_word", 0.72),
                ]

                runtime._accept_selected_from_overlay(2)
                runtime.injector.replace_previous_text.assert_called_once_with(0, "today")
                runtime.stop()

    def test_tab_and_backspace_are_not_suggestion_shortcuts(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.injector.replace_previous_text = Mock(return_value=None)
                runtime._suggestions = [
                    Suggestion("teh", "teh", "typed", 1.0),
                    self.assistant_suggestion(),
                ]
                runtime._last_correction = None

                self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="tab")))
                self.assertFalse(runtime._handle_keyboard_event(KeyboardEvent(key="backspace")))
                runtime.injector.replace_previous_text.assert_not_called()
                runtime.stop()

    def test_escape_declines_all_visible_suggestions(self) -> None:
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
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
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.buffer.push("r")
                runtime.buffer.push("e")
                runtime.buffer.push("c")
                runtime.buffer.push("i")
                runtime.buffer.push("e")
                runtime.buffer.push("v")
                runtime.buffer.push("e")
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
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                for char in "studying":
                    runtime.buffer.push(char)
                choices = runtime._display_choices([], AppContext(app_identifier="notepad.exe"))
                self.assertEqual(choices[0].replacement, "studying")
                self.assertEqual(choices[1].replacement, "studying")
                self.assertEqual(choices[1].kind, "typed")
                self.assertEqual(choices[2].replacement, "in")
                runtime.stop()

    def assistant_suggestion(self) -> Suggestion:
        return Suggestion("teh", "the", "typo", 0.96, auto_apply=True)

    def test_app_change_clears_typed_buffer_before_next_character(self) -> None:
        class SequenceAppDetector:
            def __init__(self) -> None:
                self.context = AppContext(app_identifier="notepad.exe", window_title="A")

            def current_app(self) -> AppContext:
                return self.context

        detector = SequenceAppDetector()
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.app_detector = detector
                runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
                detector.context = AppContext(app_identifier="wordpad.exe", window_title="B")
                runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))
                self.assertEqual(runtime.buffer.text, "b")
                self.assertEqual(runtime.stats.app_context_changes, 1)
                runtime.stop()

    def test_window_title_change_does_not_clear_typed_buffer(self) -> None:
        class SequenceAppDetector:
            def __init__(self) -> None:
                self.context = AppContext(app_identifier="notepad.exe", window_title="A", window_class_name="Notepad")

            def current_app(self) -> AppContext:
                return self.context

        detector = SequenceAppDetector()
        with patch("keyboard_assistant.runtime.desktop_runtime.TrayIcon", side_effect=OSError):
            with redirect_stdout(io.StringIO()):
                runtime = DesktopAssistantRuntime(self.db)
                runtime.app_detector = detector
                runtime._process_keyboard_event(KeyboardEvent(key="char", char="a"))
                detector.context = AppContext(app_identifier="notepad.exe", window_title="B", window_class_name="Notepad")
                runtime._process_keyboard_event(KeyboardEvent(key="char", char="b"))
                self.assertEqual(runtime.buffer.text, "ab")
                self.assertEqual(runtime.stats.app_context_changes, 0)
                runtime.stop()


if __name__ == "__main__":
    unittest.main()
