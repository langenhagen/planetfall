"""Tests for coin spawn helpers."""

from unittest import TestCase

from planetfall.game.runtime_spawn_coins import rainbow_lane_rgb, rainbow_wave_rgb

CHECKER = TestCase()


def test_rainbow_lane_rgb_clamps_to_lane_span() -> None:
    """Clamp lane colors to the same edge values when outside bounds."""
    at_min = rainbow_lane_rgb(-9999.0)
    at_max = rainbow_lane_rgb(9999.0)
    CHECKER.assertEqual(at_min, rainbow_lane_rgb(-100000.0))
    CHECKER.assertEqual(at_max, rainbow_lane_rgb(100000.0))


def test_rainbow_wave_rgb_is_normalized() -> None:
    """Ensure wave colors stay within expected 0..1 bounds."""
    red, green, blue = rainbow_wave_rgb(
        lane_x=4.0,
        band_index=3,
        runtime_time=1.25,
    )
    CHECKER.assertGreaterEqual(red, 0.0)
    CHECKER.assertLessEqual(red, 1.0)
    CHECKER.assertGreaterEqual(green, 0.0)
    CHECKER.assertLessEqual(green, 1.0)
    CHECKER.assertGreaterEqual(blue, 0.0)
    CHECKER.assertLessEqual(blue, 1.0)
