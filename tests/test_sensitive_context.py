import unittest

from keyboard_assistant.core.models import AppContext
from keyboard_assistant.privacy.sensitive_context import SensitiveContextFilter


class SensitiveContextFilterTests(unittest.TestCase):
    def test_disables_password_context(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(context_filter.should_disable(AppContext(is_password=True)))

    def test_disables_terminal_context(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(context_filter.should_disable(AppContext(app_identifier="powershell.exe")))

    def test_disables_private_browser_title(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(
            context_filter.should_disable(
                AppContext(app_identifier="msedge.exe", window_title="New tab - InPrivate")
            )
        )

    def test_disables_address_bar_field(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(context_filter.should_disable(AppContext(app_identifier="chrome.exe", field_type="omnibox")))

    def test_disables_credential_window(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(
            context_filter.should_disable(
                AppContext(app_identifier="credentialuibroker.exe", window_class_name="Credential Dialog")
            )
        )

    def test_disables_payment_or_security_text(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertTrue(context_filter.should_disable(AppContext(field_name="Credit card number")))
        self.assertTrue(context_filter.should_disable(AppContext(window_title="Enter verification code")))

    def test_allows_normal_context(self) -> None:
        context_filter = SensitiveContextFilter()
        self.assertFalse(context_filter.should_disable(AppContext(app_identifier="notepad.exe")))


if __name__ == "__main__":
    unittest.main()
