from __future__ import annotations

from keyboard_assistant.core.models import AppContext
from keyboard_assistant.data.defaults import DEFAULT_EXCLUDED_APP_HINTS


SENSITIVE_FIELD_TYPES = {
    "address_bar",
    "card",
    "card_number",
    "code",
    "credit_card",
    "cvv",
    "game",
    "omnibox",
    "one_time_code",
    "passcode",
    "password",
    "pin",
    "search",
    "security_code",
    "ssn",
    "terminal",
    "token",
    "url",
}

PRIVATE_TITLE_MARKERS = (
    "incognito",
    "inprivate",
    "private browsing",
    "private window",
)

SENSITIVE_TEXT_MARKERS = (
    "2fa",
    "authentication",
    "authenticator",
    "card number",
    "checkout",
    "credit card",
    "cvv",
    "enter password",
    "log in",
    "login",
    "one-time code",
    "passcode",
    "password",
    "payment",
    "pin",
    "security code",
    "sign in",
    "social security",
    "token",
    "verification code",
    "verify your identity",
)


class SensitiveContextFilter:
    def __init__(self, excluded_app_hints: set[str] | None = None) -> None:
        self.excluded_app_hints = excluded_app_hints or DEFAULT_EXCLUDED_APP_HINTS

    def should_disable(self, app_context: AppContext) -> bool:
        if app_context.is_password or app_context.is_private:
            return True

        identifier = app_context.app_identifier.lower()
        title = app_context.window_title.lower()
        field_name = app_context.field_name.lower()
        field_type = app_context.field_type.lower()
        window_class = app_context.window_class_name.lower()

        if field_type in SENSITIVE_FIELD_TYPES:
            return True
        if identifier in self.excluded_app_hints:
            return True
        if any(marker in title for marker in PRIVATE_TITLE_MARKERS):
            return True
        if any(marker in title or marker in field_name for marker in SENSITIVE_TEXT_MARKERS):
            return True
        if "credential" in identifier or "credential" in window_class:
            return True
        return False
