"""Tests for post-processing option and render mode transitions."""

from unittest import TestCase

import pytest

from planetfall.game.runtime_postfx import next_post_process_option, toggle_render_mode

CHECKER = TestCase()


def test_next_post_process_option_cycles_labels_and_wraps() -> None:
    """Cycle through labels in order and wrap back to the first option."""
    options = (
        ("Off", None),
        ("SSAO", object()),
        ("Vertical Blur", object()),
    )

    next_index, next_name, _ = next_post_process_option(
        current_index=0,
        options=options,
    )
    CHECKER.assertEqual(next_index, 1)
    CHECKER.assertEqual(next_name, "SSAO")

    next_index, next_name, _ = next_post_process_option(
        current_index=next_index,
        options=options,
    )
    CHECKER.assertEqual(next_index, 2)
    CHECKER.assertEqual(next_name, "Vertical Blur")

    next_index, next_name, _ = next_post_process_option(
        current_index=next_index,
        options=options,
    )
    CHECKER.assertEqual(next_index, 0)
    CHECKER.assertEqual(next_name, "Off")


def test_next_post_process_option_rejects_empty_options() -> None:
    """Reject empty option sets to avoid index and label mismatches."""
    with pytest.raises(ValueError, match="cannot be empty"):
        next_post_process_option(current_index=0, options=())


def test_toggle_render_mode_flips_between_default_and_wireframe() -> None:
    """Toggle render mode states without cycling through extra modes."""
    CHECKER.assertEqual(toggle_render_mode("default"), "wireframe")
    CHECKER.assertEqual(toggle_render_mode("wireframe"), "default")


def test_next_post_process_option_handles_single_option() -> None:
    """Single option should always return index 0 and same label."""
    options = (("Off", None),)
    next_index, next_name, next_shader = next_post_process_option(
        current_index=0,
        options=options,
    )
    CHECKER.assertEqual(next_index, 0)
    CHECKER.assertEqual(next_name, "Off")
    CHECKER.assertIsNone(next_shader)


def test_next_post_process_option_wraps_large_index() -> None:
    """Indices larger than the option count should wrap correctly."""
    options = (("Off", None), ("Blur", object()))
    next_index, next_name, _ = next_post_process_option(
        current_index=5,
        options=options,
    )
    CHECKER.assertEqual(next_index, 0)
    CHECKER.assertEqual(next_name, "Off")


def test_next_post_process_option_handles_negative_index() -> None:
    """Negative indices should still advance and wrap forward."""
    options = (("Off", None), ("Blur", object()))
    next_index, next_name, _ = next_post_process_option(
        current_index=-1,
        options=options,
    )
    CHECKER.assertEqual(next_index, 0)
    CHECKER.assertEqual(next_name, "Off")
