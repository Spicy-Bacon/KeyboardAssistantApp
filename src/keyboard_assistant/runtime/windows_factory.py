from __future__ import annotations

from collections.abc import Callable

from keyboard_assistant.platform.app_detector import AppDetector
from keyboard_assistant.platform.cursor import CursorLocator
from keyboard_assistant.platform.keyboard_listener import KeyboardEvent, WindowsKeyboardListener
from keyboard_assistant.platform.text_injector import WindowsTextInjector
from keyboard_assistant.runtime.components import (
    AppDetectorProtocol,
    CursorLocatorProtocol,
    KeyboardListener,
    Overlay,
    TextInjector,
    Tray,
)
from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay
from keyboard_assistant.ui.tray_icon import TrayIcon


class WindowsRuntimeComponentFactory:
    """Creates Windows desktop components for the runtime orchestration layer."""

    def create_text_injector(self) -> TextInjector:
        return WindowsTextInjector()

    def create_overlay(self, on_close: Callable[[], None], on_select: Callable[[int], None]) -> Overlay:
        return SuggestionOverlay(on_close=on_close, on_select=on_select)

    def create_tray(
        self,
        on_toggle_pause: Callable[[], bool],
        on_open_settings: Callable[[], None],
        on_exit: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> Tray:
        return TrayIcon(
            on_toggle_pause=on_toggle_pause,
            on_open_settings=on_open_settings,
            on_exit=on_exit,
            is_paused=is_paused,
        )

    def create_keyboard_listener(
        self,
        on_event: Callable[[KeyboardEvent], bool | None],
        on_error: Callable[[BaseException], None] | None = None,
    ) -> KeyboardListener:
        return WindowsKeyboardListener(on_event, on_error=on_error)

    def create_app_detector(self) -> AppDetectorProtocol:
        return AppDetector()

    def create_cursor_locator(self) -> CursorLocatorProtocol:
        return CursorLocator()
