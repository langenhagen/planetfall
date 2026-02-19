"""Tests for game runtime control math helpers."""

from unittest import TestCase

from ursina import Vec3

from fooproj.game.runtime import (
    apply_deadzone,
    compute_gamepad_axes,
    compute_keyboard_axes,
    compute_look_angles,
    compute_player_velocity,
    compute_prop_mass,
    compute_smoothed_forward_speed,
    compute_zoom_distance,
    dominant_axis,
    resolve_ground_contact,
)

CHECKER = TestCase()


def test_compute_keyboard_axes_default_zero() -> None:
    """Return zero movement when no relevant keys are held."""
    axes = compute_keyboard_axes({})
    CHECKER.assertEqual(axes, (0.0, 0.0, 0.0))


def test_compute_keyboard_axes_combines_opposites() -> None:
    """Subtract opposite directions for forward/strafe/turn axes."""
    held = {
        "up arrow": 1.0,
        "down arrow": 0.25,
        "right arrow": 1.0,
        "left arrow": 0.5,
        "page down": 0.75,
        "page up": 0.0,
    }
    axes = compute_keyboard_axes(held)
    CHECKER.assertEqual(axes, (0.75, 0.5, 0.75))


def test_compute_gamepad_axes_maps_ps_style_controls() -> None:
    """Map triggers and sticks to throttle/steer/look axes."""
    held = {
        "gamepad right trigger": 0.9,
        "gamepad left trigger": 0.25,
        "gamepad right shoulder": 1.0,
        "gamepad left shoulder": 0.0,
        "gamepad left stick x": -0.5,
        "gamepad right stick x": 0.4,
        "gamepad right stick y": -0.2,
    }
    forward, strafe, turn, look_x, look_y = compute_gamepad_axes(held)
    CHECKER.assertAlmostEqual(forward, 0.65, places=5)
    CHECKER.assertEqual(strafe, 1.0)
    CHECKER.assertEqual(turn, -0.5)
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


def test_compute_smoothed_forward_speed_accelerates_to_target() -> None:
    """Move speed toward requested target instead of snapping instantly."""
    next_speed = compute_smoothed_forward_speed(0.0, 1.0, 60.0, 0.1)
    CHECKER.assertGreater(next_speed, 0.0)
    CHECKER.assertLess(next_speed, 60.0)


def test_compute_smoothed_forward_speed_respects_analog_input() -> None:
    """Use fractional trigger input for proportional target speed."""
    next_speed = compute_smoothed_forward_speed(0.0, 0.5, 60.0, 0.1)
    CHECKER.assertGreater(next_speed, 0.0)
    CHECKER.assertLess(next_speed, 30.0)


def test_compute_smoothed_forward_speed_brakes_when_reversing() -> None:
    """Reverse input should reduce current forward speed rapidly."""
    next_speed = compute_smoothed_forward_speed(30.0, -1.0, 60.0, 0.1)
    CHECKER.assertLess(next_speed, 30.0)


def test_compute_look_angles_updates_yaw_and_pitch() -> None:
    """Apply mouse velocity to both yaw and pitch."""
    yaw, pitch = compute_look_angles(10.0, 15.0, Vec3(0.2, -0.1, 0.0), 100.0)
    CHECKER.assertAlmostEqual(yaw, 30.0, places=5)
    CHECKER.assertAlmostEqual(pitch, 5.0, places=5)


def test_compute_look_angles_clamps_pitch() -> None:
    """Clamp pitch to the configured up/down look limits."""
    _, high_pitch = compute_look_angles(0.0, 89.0, Vec3(0.0, 1.0, 0.0), 10.0)
    _, low_pitch = compute_look_angles(0.0, -89.0, Vec3(0.0, -1.0, 0.0), 10.0)
    CHECKER.assertEqual(high_pitch, 90.0)
    CHECKER.assertEqual(low_pitch, -90.0)


def test_compute_zoom_distance_scroll_up_zooms_in() -> None:
    """Decrease camera distance when scrolling up."""
    distance = compute_zoom_distance(10.0, 1, 4.0, 18.0, 1.5)
    CHECKER.assertEqual(distance, 8.5)


def test_compute_zoom_distance_scroll_down_zooms_out() -> None:
    """Increase camera distance when scrolling down."""
    distance = compute_zoom_distance(10.0, -1, 4.0, 18.0, 2.0)
    CHECKER.assertEqual(distance, 12.0)


def test_compute_zoom_distance_clamps_to_min_and_max() -> None:
    """Keep camera distance inside configured min/max bounds."""
    min_clamped = compute_zoom_distance(4.2, 1, 4.0, 18.0, 1.0)
    max_clamped = compute_zoom_distance(17.8, -1, 4.0, 18.0, 1.0)
    CHECKER.assertEqual(min_clamped, 4.0)
    CHECKER.assertEqual(max_clamped, 18.0)


def test_compute_zoom_distance_without_max_limit() -> None:
    """Allow unbounded zoom-out when max distance is disabled."""
    distance = compute_zoom_distance(18.0, -1, 4.0, None, 6.0)
    CHECKER.assertEqual(distance, 24.0)


def test_compute_player_velocity_uses_delta_time() -> None:
    """Calculate player frame velocity from position delta and dt."""
    velocity = compute_player_velocity(
        Vec3(2.0, 0.0, -4.0),
        Vec3(1.0, 0.0, -2.0),
        0.5,
    )
    CHECKER.assertEqual(velocity, Vec3(2.0, 0.0, -4.0))


def test_compute_player_velocity_handles_zero_dt() -> None:
    """Return zero velocity when dt is zero or negative."""
    velocity = compute_player_velocity(
        Vec3(10.0, 0.0, 5.0),
        Vec3(1.0, 0.0, -2.0),
        0.0,
    )
    CHECKER.assertEqual(velocity, Vec3(0.0, 0.0, 0.0))


def test_resolve_ground_contact_bounces_and_clamps() -> None:
    """Clamp below-ground props and reverse downward velocity."""
    y_pos, y_vel = resolve_ground_contact(position_y=0.1, velocity_y=-3.0, radius=0.45)
    CHECKER.assertEqual(y_pos, 0.45)
    CHECKER.assertAlmostEqual(y_vel, 1.05, places=5)


def test_resolve_ground_contact_keeps_above_ground_state() -> None:
    """Leave position and velocity unchanged when already above ground."""
    y_pos, y_vel = resolve_ground_contact(position_y=0.8, velocity_y=0.2, radius=0.45)
    CHECKER.assertEqual(y_pos, 0.8)
    CHECKER.assertEqual(y_vel, 0.2)


def test_compute_prop_mass_scales_with_size() -> None:
    """Give larger props higher mass than smaller ones."""
    small = compute_prop_mass(Vec3(0.8, 0.8, 0.8))
    large = compute_prop_mass(Vec3(1.0, 2.5, 1.0))
    CHECKER.assertGreater(large, small)
