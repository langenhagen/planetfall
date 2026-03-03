"""Tests for runtime state containers."""

from unittest import TestCase

from planetfall.game.runtime_state import CameraState, FallingRunState, SpawnedObject

CHECKER = TestCase()


def test_falling_run_state_starts_empty() -> None:
    """Default run state should start with no spawned objects."""
    run_state = FallingRunState()
    CHECKER.assertEqual(run_state.spawned_objects, [])


class _TestEntity:  # pylint: disable=too-few-public-methods
    """Minimal entity stub for SpawnedObject defaults."""

    def __init__(self, name: str) -> None:
        self.name = name


def test_spawned_object_defaults_motion_fields() -> None:
    """Spawned objects default to zeroed motion metadata."""
    entity = _TestEntity(name="test_spawned_object")
    spawned = SpawnedObject(
        entity=entity,  # type: ignore[arg-type]  # arg-type: test stub for Entity.
        entity_kind="coin",
        color_name="gold",
        model_name="coin",
        collision_radius=1.0,
        score_value=1,
        band_index=0,
    )
    CHECKER.assertEqual(spawned.spin_speed_x, 0.0)
    CHECKER.assertEqual(spawned.bob_amplitude, 0.0)
    CHECKER.assertEqual(spawned.drift_speed_z, 0.0)


def test_camera_state_defaults_follow_angle() -> None:
    """Camera state defaults yaw follow angle to zero."""
    camera_state = CameraState(yaw_angle=1.0, pitch_angle=2.0, distance=3.0)
    CHECKER.assertEqual(camera_state.yaw_follow_angle, 0.0)
