import unittest
from unittest.mock import patch

from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.ui.suggestion_overlay import calculate_overlay_position
from keyboard_assistant.ui.suggestion_overlay import choice_index_at_x
from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay
from keyboard_assistant.ui.suggestion_overlay import _format_label


class OverlayGeometryTests(unittest.TestCase):
    def test_positions_below_anchor_when_space_allows(self) -> None:
        self.assertEqual(
            calculate_overlay_position(100, 100, 200, 34, 1920, 1080),
            (110, 118),
        )

    def test_clamps_to_right_edge(self) -> None:
        x, y = calculate_overlay_position(1900, 100, 200, 34, 1920, 1080)
        self.assertEqual(x, 1712)
        self.assertEqual(y, 118)

    def test_positions_above_anchor_near_bottom(self) -> None:
        x, y = calculate_overlay_position(100, 1060, 200, 34, 1920, 1080)
        self.assertEqual(x, 110)
        self.assertEqual(y, 1016)

    def test_clamps_to_top_edge(self) -> None:
        x, y = calculate_overlay_position(0, 0, 200, 34, 1920, 40)
        self.assertEqual(x, 10)
        self.assertEqual(y, 8)

    def test_clamps_invalid_negative_anchor(self) -> None:
        x, y = calculate_overlay_position(-500, -300, 200, 34, 1920, 1080)
        self.assertEqual(x, 8)
        self.assertEqual(y, 8)

    def test_middle_choice_labels(self) -> None:
        typed = Suggestion("recieve", "recieve", "typed", 1.0)
        correction = Suggestion("recieve", "receive", "typo", 0.96)
        next_word = Suggestion("", "today", "next_word", 0.72)
        self.assertEqual(_format_label(0, typed, focus_index=1), "recieve")
        self.assertEqual(_format_label(1, correction, focus_index=1), "receive")
        self.assertEqual(_format_label(2, next_word, focus_index=1), "today")

    def test_choice_hit_testing(self) -> None:
        bounds = [(10, 110), (110, 240), (240, 360)]
        self.assertEqual(choice_index_at_x(bounds, 10), 0)
        self.assertEqual(choice_index_at_x(bounds, 150), 1)
        self.assertEqual(choice_index_at_x(bounds, 359), 2)
        self.assertIsNone(choice_index_at_x(bounds, 9))
        self.assertIsNone(choice_index_at_x(bounds, 360))

    def test_overlay_instantiation_requires_windows(self) -> None:
        with patch("keyboard_assistant.ui.suggestion_overlay._is_windows_overlay_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Windows-only"):
                SuggestionOverlay()


if __name__ == "__main__":
    unittest.main()
