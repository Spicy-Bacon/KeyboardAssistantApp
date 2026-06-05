import unittest
from unittest.mock import patch

from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.core.models import AppearanceSettings
from keyboard_assistant.ui.suggestion_overlay import calculate_overlay_position
from keyboard_assistant.ui.suggestion_overlay import build_overlay_layout
from keyboard_assistant.ui.suggestion_overlay import chip_rects
from keyboard_assistant.ui.suggestion_overlay import choice_index_at_x
from keyboard_assistant.ui.suggestion_overlay import is_drag_handle_x
from keyboard_assistant.ui.suggestion_overlay import OverlayRenderState
from keyboard_assistant.ui.suggestion_overlay import rect_center
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
        self.assertGreaterEqual(rects[0][0], 32)

    def test_selected_chip_has_internal_margin(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        layout = build_overlay_layout(["typed", "receive", "today"], appearance, focus_index=1)
        left, top, right, bottom = layout.chip_rects[layout.focus_index]

        self.assertGreater(left, 0)
        self.assertGreater(top, 0)
        self.assertLess(right, layout.width)
        self.assertLess(bottom, layout.height)

    def test_text_rects_are_centered_in_chip_boxes(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        layout = build_overlay_layout(["typed", "receive", "today"], appearance, focus_index=1)

        for chip, text in zip(layout.chip_rects, layout.text_rects, strict=True):
            self.assertEqual(rect_center(chip), rect_center(text))

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

    def test_focus_index_changes_selected_chip_without_changing_layout(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        labels = ["typed", "corrected", "next"]
        left_focused = build_overlay_layout(labels, appearance, focus_index=0)
        middle_focused = build_overlay_layout(labels, appearance, focus_index=1)

        self.assertEqual(left_focused.chip_rects, middle_focused.chip_rects)
        self.assertEqual(left_focused.focus_index, 0)
        self.assertEqual(middle_focused.focus_index, 1)

    def test_position_clamps_to_offset_monitor_bounds(self) -> None:
        x, y = calculate_overlay_position(
            3900,
            500,
            300,
            38,
            1920,
            1080,
            screen_left=1920,
            screen_top=0,
        )

        self.assertGreaterEqual(x, 1928)
        self.assertLessEqual(x, 3532)
        self.assertEqual(y, 518)

    def test_render_state_repeated_updates_do_not_crash(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        state = OverlayRenderState(appearance)
        suggestions = _sample_suggestions()

        for _ in range(10):
            layout = state.update(suggestions, appearance, focus_index=1, now=1.0)

        self.assertTrue(state.visible)
        self.assertEqual(layout.labels, ("typed", "receive", "today"))

    def test_empty_suggestions_hide_render_state(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        state = OverlayRenderState(appearance)
        state.update(_sample_suggestions(), appearance, focus_index=1, now=1.0)

        layout = state.update([], appearance, now=1.1)

        self.assertFalse(state.visible)
        self.assertEqual(layout.labels, ())

    def test_transition_state_updates_without_windows_gui(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium", animations_enabled=True)
        state = OverlayRenderState(appearance)
        state.update(_sample_suggestions(), appearance, focus_index=1, now=1.0)

        state.update(
            [
                Suggestion("typed", "typed", "typed", 1.0),
                Suggestion("typed", "received", "typo", 0.96),
                Suggestion("", "tomorrow", "next_word", 0.72),
            ],
            appearance,
            focus_index=1,
            now=1.02,
        )

        self.assertTrue(state.transition.is_active(now=1.03))
        self.assertGreater(state.transition.slide_offset(38, now=1.03), 0)

    def test_drag_handle_hit_area_is_separate_from_choices(self) -> None:
        appearance = AppearanceSettings(theme="dark", suggestion_size="medium")
        rects = chip_rects(["left", "middle", "right"], appearance)
        bounds = [(left, right) for left, _top, right, _bottom in rects]

        self.assertTrue(is_drag_handle_x(8))
        self.assertIsNone(choice_index_at_x(bounds, 8))
        self.assertFalse(is_drag_handle_x(rects[0][0]))

    def test_overlay_instantiation_requires_windows(self) -> None:
        with patch("keyboard_assistant.ui.suggestion_overlay._is_windows_overlay_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Windows-only"):
                SuggestionOverlay()


def _sample_suggestions() -> list[Suggestion]:
    return [
        Suggestion("typed", "typed", "typed", 1.0),
        Suggestion("typed", "receive", "typo", 0.96),
        Suggestion("", "today", "next_word", 0.72),
    ]


if __name__ == "__main__":
    unittest.main()
