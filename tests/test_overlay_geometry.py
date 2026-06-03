import unittest
from unittest.mock import patch

from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.core.models import AppearanceSettings
from keyboard_assistant.ui.suggestion_overlay import calculate_overlay_position
from keyboard_assistant.ui.suggestion_overlay import chip_rects
from keyboard_assistant.ui.suggestion_overlay import choice_index_at_x
from keyboard_assistant.ui.suggestion_overlay import SuggestionOverlay
from keyboard_assistant.ui.suggestion_overlay import _format_label
from keyboard_assistant.ui.suggestion_overlay import _measure_width


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

    def test_chip_layout_handles_one_two_and_three_suggestions(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")

        self.assertEqual(len(chip_rects(["one"], appearance)), 1)
        self.assertEqual(len(chip_rects(["one", "two"], appearance)), 2)
        self.assertEqual(len(chip_rects(["one", "two", "three"], appearance)), 3)

    def test_chip_layout_uses_internal_overlay_margin(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        rects = chip_rects(["left", "middle", "right"], appearance)
        width = _measure_width(["left", "middle", "right"], appearance)

        self.assertGreater(rects[0][0], 0)
        self.assertLess(rects[-1][2], width)
        self.assertGreater(rects[0][1], 0)

    def test_chip_layout_uses_equal_width_slots(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        rects = chip_rects(["a", "longer", "mid"], appearance)
        widths = [right - left for left, _top, right, _bottom in rects]

        self.assertEqual(widths[0], widths[1])
        self.assertEqual(widths[1], widths[2])

    def test_focus_index_changes_label_without_changing_layout(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        labels = ["typed", "corrected", "next"]

        self.assertEqual(chip_rects(labels, appearance), chip_rects(labels, appearance))
        self.assertEqual(_format_label(1, Suggestion("teh", "the", "typo", 0.96), focus_index=1), "the")

    def test_overlay_instantiation_requires_windows(self) -> None:
        with patch("keyboard_assistant.ui.suggestion_overlay._is_windows_overlay_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Windows-only"):
                SuggestionOverlay()


if __name__ == "__main__":
    unittest.main()
