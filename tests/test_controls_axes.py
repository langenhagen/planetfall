"""Tests for runtime input-axis mapping helpers."""

from unittest import TestCase

from planetfall.game.runtime_controls import (
    apply_deadzone,
    compute_gamepad_axes,
    compute_keyboard_axes,
    dominant_axis,
)

CHECKER = TestCase()


def test_compute_keyboard_axes_default_zero() -> None:
    """Return zero movement when no relevant keys are held."""
    axes = compute_keyboard_axes({})
    CHECKER.assertEqual(axes, (0.0, 0.0, 0.0, 0.0))


def test_compute_keyboard_axes_combines_arrow_and_wasd_inputs() -> None:
    """Merge digital keyboard keys into movement, dive, and yaw axes."""
    held = {
        "right arrow": 1.0,
        "a": 0.25,
        "q": 0.5,
        "page down": 0.75,
        "s": 0.5,
        "up arrow": 1.0,
        "space": 1.0,
        "left shift": 0.0,
    }
    x_axis, z_axis, dive_axis, yaw_axis = compute_keyboard_axes(held)
    CHECKER.assertEqual(x_axis, 0.75)
    CHECKER.assertEqual(z_axis, 0.5)
    CHECKER.assertEqual(dive_axis, 1.0)
    CHECKER.assertEqual(yaw_axis, 0.25)


def test_compute_gamepad_axes_maps_ps_style_controls() -> None:
    """Map sticks, triggers, and shoulders to movement and yaw axes."""
    held = {
        "gamepad left stick x": 0.6,
        "gamepad left stick y": -0.75,
        "gamepad right shoulder": 0.0,
        "gamepad left shoulder": 1.0,
        "gamepad right trigger": 0.9,
        "gamepad left trigger": 0.25,
        "gamepad right stick x": 0.4,
        "gamepad right stick y": -0.2,
    }
    x_axis, z_axis, dive_axis, yaw_axis, look_x, look_y = compute_gamepad_axes(held)
    CHECKER.assertEqual(x_axis, 0.6)
    CHECKER.assertEqual(z_axis, -0.75)
    CHECKER.assertAlmostEqual(dive_axis, 0.65, places=5)
    CHECKER.assertEqual(yaw_axis, -1.0)
    CHECKER.assertAlmostEqual(look_x, 0.0048, places=5)
    CHECKER.assertAlmostEqual(look_y, -0.0024, places=5)


def test_apply_deadzone_filters_small_values() -> None:
    """Zero out tiny analog drift while keeping intentional input."""
    CHECKER.assertEqual(apply_deadzone(0.03), 0.0)
    CHECKER.assertEqual(apply_deadzone(-0.03), 0.0)
    CHECKER.assertEqual(apply_deadzone(0.2), 0.2)


def test_dominant_axis_prefers_stronger_source() -> None:
    """Choose whichever input source has larger magnitude."""
    CHECKER.assertEqual(dominant_axis(0.2, -0.6), -0.6)
    CHECKER.assertEqual(dominant_axis(-0.8, 0.4), -0.8)
