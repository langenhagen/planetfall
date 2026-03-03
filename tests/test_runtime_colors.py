"""Tests for shared runtime color helpers."""

from unittest import TestCase

from planetfall.game.runtime_colors import lerp_rgb_color, resolve_color

CHECKER = TestCase()


def test_resolve_color_falls_back_to_white() -> None:
    """Unknown color names should fall back to white."""
    unknown = resolve_color("definitely_not_a_color")
    white = resolve_color("white")
    CHECKER.assertEqual(unknown, white)


def test_lerp_rgb_color_clamps_factor_below_zero() -> None:
    """Clamp negative interpolation factors to the start color."""
    color = lerp_rgb_color((10, 20, 30), (200, 220, 240), -0.3)
    CHECKER.assertAlmostEqual(color.r, 10 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.g, 20 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.b, 30 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.a, 1.0, places=6)


def test_lerp_rgb_color_clamps_factor_above_one() -> None:
    """Clamp interpolation factors above one to the end color."""
    color = lerp_rgb_color((10, 20, 30), (200, 220, 240), 1.2)
    CHECKER.assertAlmostEqual(color.r, 200 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.g, 220 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.b, 240 / 255.0, places=6)
    CHECKER.assertAlmostEqual(color.a, 1.0, places=6)
