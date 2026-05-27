from __future__ import annotations

from keyboard_assistant.core.models import AppContext
from keyboard_assistant.data.defaults import DEFAULT_EXCLUDED_APP_HINTS


class SensitiveContextFilter:
    def __init__(self, excluded_app_hints: set[str] | None = None) -> None:
        self.excluded_app_hints = excluded_app_hints or DEFAULT_EXCLUDED_APP_HINTS

    def should_disable(self, app_context: AppContext) -> bool:
        if app_context.is_password or app_context.is_private:
            return True

        identifier = app_context.app_identifier.lower()
        title = app_context.window_title.lower()
        field_type = app_context.field_type.lower()

        if field_type in {"password", "terminal", "code", "game"}:
            return True
        if identifier in self.excluded_app_hints:
            return True
        if "password" in title or "private browsing" in title or "incognito" in title:
            return True
        return False

