"""Tests for camera path helpers and auto-yaw."""

from math import atan2, degrees
from typing import Protocol
from unittest import TestCase

from ursina import Vec3

from planetfall.game import config
from planetfall.game.runtime import resolve_camera_band_progress
from planetfall.game.runtime_camera import (
    resolve_path_yaw_target,
    sample_path_center,
    sample_path_direction,
)
from planetfall.game.scene_base import BAND_SPACING, path_center, path_direction

CHECKER = TestCase()


class Vec3Like(Protocol):
    """Minimal protocol for Vec3-like test values."""

    @property
    def x(self) -> float:
        """X component."""
        raise NotImplementedError

    @property
    def y(self) -> float:
        """Y component."""
        raise NotImplementedError

    @property
    def z(self) -> float:
        """Z component."""
        raise NotImplementedError


def assert_vec3_close(left: Vec3Like, right: Vec3Like, *, places: int = 4) -> None:
    """Compare Vec3-ish values with float tolerance."""
    right_x = float(right.x)
    right_y = float(right.y)
    right_z = float(right.z)
    CHECKER.assertAlmostEqual(float(left.x), right_x, places=places)
    CHECKER.assertAlmostEqual(float(left.y), right_y, places=places)
    CHECKER.assertAlmostEqual(float(left.z), right_z, places=places)


def test_resolve_camera_band_progress_accounts_for_offset() -> None:
    """Compute fractional band index using a y-offset."""
    fall_settings = config.FallSettings()

    progress = resolve_camera_band_progress(
        player_y=fall_settings.initial_spawn_y - 4.0,
        fall_settings=fall_settings,
        y_offset=-2.0,
    )

    expected = (4.0 + 2.0) / BAND_SPACING
    CHECKER.assertAlmostEqual(progress, expected, places=3)


def test_sample_path_center_matches_integer_band() -> None:
    """Sampled center matches path center at integer progress."""
    band_index = 6

    sampled = sample_path_center(band_progress=float(band_index))
    expected = path_center(band_index)

    assert_vec3_close(sampled, expected)


def test_sample_path_direction_is_normalized() -> None:
    """Sampled path direction stays normalized."""
    sampled = sample_path_direction(band_progress=3.25)

    length = float(sampled.length())
    CHECKER.assertGreater(length, 0.0)
    CHECKER.assertAlmostEqual(length, 1.0, places=3)


def test_sample_path_direction_matches_integer_band() -> None:
    """Sampled direction matches path direction at integer progress."""
    band_index = 4

    sampled = sample_path_direction(band_progress=float(band_index))
    expected = path_direction(band_index)

    assert_vec3_close(sampled, expected)


def test_resolve_path_yaw_target_matches_path_direction() -> None:
    """Yaw target aligns with forward path direction."""
    band_progress = 5.0
    target_yaw = resolve_path_yaw_target(
        band_progress=band_progress,
        lookahead_bands=1.0,
    )

    CHECKER.assertIsNotNone(target_yaw)
    if target_yaw is None:
        return
    base_anchor = sample_path_center(band_progress=band_progress)
    lookahead_anchor = sample_path_center(band_progress=band_progress + 1.0)
    direction = Vec3(
        lookahead_anchor.x - base_anchor.x,
        0.0,
        lookahead_anchor.z - base_anchor.z,
    )
    expected_yaw = degrees(atan2(direction.x, direction.z))
    CHECKER.assertAlmostEqual(float(target_yaw), expected_yaw, places=3)


def test_resolve_path_yaw_target_returns_none_for_zero_direction() -> None:
    """Zero-length lookahead direction should disable yaw target."""
    target_yaw = resolve_path_yaw_target(
        band_progress=5.0,
        lookahead_bands=0.0,
    )
    CHECKER.assertIsNone(target_yaw)
