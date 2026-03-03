"""Tests for runtime movement and camera math helpers."""

from unittest import TestCase

from ursina import Vec3

from planetfall.game.runtime_controls import (
    clamp_to_play_area,
    compute_control_axes,
    compute_fall_speed,
    compute_look_angles,
    compute_smoothed_lateral_speed,
    compute_zoom_distance,
    rotate_planar_velocity_by_yaw,
    should_despawn_object,
    should_spawn_next_band,
)

CHECKER = TestCase()


def test_compute_fall_speed_increases_with_dive_input() -> None:
    """Increase fall rate when positive dive input is applied."""
    speed = compute_fall_speed(
        base_speed=20.0,
        dive_axis=0.5,
        boost_multiplier=1.2,
        brake_multiplier=0.55,
    )
    CHECKER.assertGreater(speed, 20.0)


def test_compute_fall_speed_brakes_but_never_stops() -> None:
    """Reduce fall speed with brake input without reaching zero."""
    speed = compute_fall_speed(
        base_speed=20.0,
        dive_axis=-1.0,
        boost_multiplier=1.2,
        brake_multiplier=0.55,
    )
    CHECKER.assertGreater(speed, 0.0)
    CHECKER.assertLess(speed, 20.0)


def test_compute_smoothed_lateral_speed_accelerates_toward_target() -> None:
    """Increase lateral speed gradually when axis input is applied."""
    speed = compute_smoothed_lateral_speed(
        current_speed=0.0,
        axis_input=1.0,
        max_speed=18.0,
        acceleration_rate=9.5,
        deceleration_rate=11.0,
        dt=0.1,
    )
    CHECKER.assertGreater(speed, 0.0)
    CHECKER.assertLess(speed, 18.0)


def test_compute_smoothed_lateral_speed_decelerates_toward_zero() -> None:
    """Reduce lateral speed smoothly when axis input is released."""
    speed = compute_smoothed_lateral_speed(
        current_speed=8.0,
        axis_input=0.0,
        max_speed=18.0,
        acceleration_rate=9.5,
        deceleration_rate=11.0,
        dt=0.1,
    )
    CHECKER.assertGreaterEqual(speed, 0.0)
    CHECKER.assertLess(speed, 8.0)


def test_compute_look_angles_updates_and_clamps_pitch() -> None:
    """Apply look velocity while constraining pitch to limits."""
    yaw, pitch = compute_look_angles(
        yaw_angle=10.0,
        pitch_angle=20.0,
        look_velocity=Vec3(0.2, 1.5, 0.0),
        mouse_look_speed=100.0,
        min_pitch=8.0,
        max_pitch=55.0,
    )
    CHECKER.assertAlmostEqual(yaw, 30.0, places=5)
    CHECKER.assertEqual(pitch, 55.0)


def test_compute_control_axes_prefers_stronger_look_input() -> None:
    """Dominant look axis should win between mouse and gamepad."""
    held = {
        "gamepad right stick x": 0.2,
        "gamepad right stick y": -0.4,
    }
    mouse_velocity = Vec3(0.5, -0.1, 0.0)

    _, _, _, _, look_vector = compute_control_axes(held, mouse_velocity)

    CHECKER.assertAlmostEqual(look_vector.x, 0.5, places=5)
    CHECKER.assertAlmostEqual(look_vector.y, -0.1, places=5)


def test_compute_zoom_distance_respects_limits() -> None:
    """Clamp camera zoom between min and max distances."""
    zoom_in = compute_zoom_distance(
        current_distance=10.0,
        scroll_direction=1,
        min_distance=9.0,
        max_distance=15.0,
        zoom_step=2.0,
    )
    zoom_out = compute_zoom_distance(
        current_distance=14.5,
        scroll_direction=-1,
        min_distance=9.0,
        max_distance=15.0,
        zoom_step=2.0,
    )
    CHECKER.assertEqual(zoom_in, 9.0)
    CHECKER.assertEqual(zoom_out, 15.0)


def test_clamp_to_play_area_limits_distance_from_center() -> None:
    """Keep x/z position inside the configured movement radius."""
    x_pos, z_pos = clamp_to_play_area(10.0, 0.0, 8.2)
    CHECKER.assertEqual(x_pos, 8.2)
    CHECKER.assertEqual(z_pos, 0.0)


def test_rotate_planar_velocity_by_yaw_identity_at_zero() -> None:
    """Keep camera-relative movement unchanged at zero yaw."""
    x_speed, z_speed = rotate_planar_velocity_by_yaw(
        right_speed=2.0,
        forward_speed=3.0,
        yaw_degrees=0.0,
    )
    CHECKER.assertAlmostEqual(x_speed, 2.0, places=5)
    CHECKER.assertAlmostEqual(z_speed, 3.0, places=5)


def test_rotate_planar_velocity_by_yaw_rotates_ninety_degrees() -> None:
    """Rotate camera-relative movement into world space at 90 degrees yaw."""
    x_speed, z_speed = rotate_planar_velocity_by_yaw(
        right_speed=2.0,
        forward_speed=3.0,
        yaw_degrees=90.0,
    )
    CHECKER.assertAlmostEqual(x_speed, 3.0, places=5)
    CHECKER.assertAlmostEqual(z_speed, -2.0, places=5)


def test_should_spawn_next_band_uses_ahead_window() -> None:
    """Spawn when next band is not deep enough relative to player depth."""
    CHECKER.assertTrue(
        should_spawn_next_band(
            next_band_y=-40.0,
            player_y=-20.0,
            spawn_ahead_distance=200.0,
        ),
    )
    CHECKER.assertFalse(
        should_spawn_next_band(
            next_band_y=-260.0,
            player_y=-20.0,
            spawn_ahead_distance=200.0,
        ),
    )


def test_should_despawn_object_when_far_above_player() -> None:
    """Remove objects that are sufficiently above the current camera focus."""
    CHECKER.assertTrue(
        should_despawn_object(
            object_y=-10.0,
            player_y=-80.0,
            cleanup_above_distance=40.0,
        ),
    )
    CHECKER.assertFalse(
        should_despawn_object(
            object_y=-50.0,
            player_y=-80.0,
            cleanup_above_distance=40.0,
        ),
    )
