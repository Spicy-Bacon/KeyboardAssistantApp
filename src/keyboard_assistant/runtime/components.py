from __future__ import annotations

from typing import Callable, Protocol

from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.platform.cursor import ScreenPoint
from keyboard_assistant.platform.keyboard_listener import KeyboardEvent


class TextInjector(Protocol):
    def replace_previous_text(self, original_length: int, replacement: str) -> None:
        ...

    def type_text(self, text: str) -> None:
        ...


class Overlay(Protocol):
    def run(self) -> None:
        ...

    def close(self) -> None:
        ...

    def call_soon(self, callback: Callable[[], object]) -> None:
        ...

    def apply_appearance(self, appearance: dict[str, object]) -> None:
        ...

    def show_suggestions(self, suggestions: list[Suggestion], x: int, y: int, focus_index: int = 0) -> None:
        ...

    def hide(self) -> None:
        ...


class Tray(Protocol):
    def close(self) -> None:
        ...

    def update_tooltip(self) -> None:
        ...


class KeyboardListener(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class AppDetectorProtocol(Protocol):
    def current_app(self) -> AppContext:
        ...


class CursorLocatorProtocol(Protocol):
    def current_anchor(self) -> ScreenPoint:
        ...


class LocalAIWorkerProtocol(Protocol):
    def request(self, source_text: str, app_context: AppContext, rule_suggestions: list[Suggestion]) -> None:
        ...

    def cancel(self) -> None:
        ...


class NullTrayIcon:
    def close(self) -> None:
        pass

    def update_tooltip(self) -> None:
        pass


class NullOverlay:
    def run(self) -> None:
        pass

    def close(self) -> None:
        pass

    def call_soon(self, callback: Callable[[], object]) -> None:
        callback()

    def apply_appearance(self, _appearance: dict[str, object]) -> None:
        pass

    def show_suggestions(self, _suggestions: list[Suggestion], _x: int, _y: int, focus_index: int = 0) -> None:
        pass

    def hide(self) -> None:
        pass


class NullKeyboardListener:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
