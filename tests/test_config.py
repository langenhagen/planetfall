"""Tests for configuration defaults."""

from unittest import TestCase

from planetfall.game.config import CameraSettings, FallSettings, GameSettings

CHECKER = TestCase()


def test_game_settings_default_camera_matches_camera_settings() -> None:
    """GameSettings defaults should match nested defaults."""
    settings = GameSettings()
    CHECKER.assertEqual(settings.camera, CameraSettings())


def test_fall_settings_initial_spawn_y_is_negative() -> None:
    """Initial spawn starts below the origin to place the player above bands."""
    settings = FallSettings()
    CHECKER.assertLess(settings.initial_spawn_y, 0.0)
