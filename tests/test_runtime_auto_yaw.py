"""Tests for auto yaw helpers."""

from dataclasses import dataclass
from unittest import TestCase

from ursina import Vec3

from planetfall.game.config import FallSettings
from planetfall.game.runtime import (
    CameraState,
    FallingRunState,
    SpawnedObject,
    resolve_auto_yaw_axis,
)

CHECKER = TestCase()


@dataclass(slots=True)
class DummyEntity:
    """Minimal entity-like object for auto yaw tests."""

    position: Vec3

    @property
    def x(self) -> float:
        """Expose x component like a real entity."""
        # pylint: disable=no-member
        return float(self.position.x)

    @property
    def y(self) -> float:
        """Expose y component like a real entity."""
        # pylint: disable=no-member
        return float(self.position.y)

    @property
    def z(self) -> float:
        """Expose z component like a real entity."""
        # pylint: disable=no-member
        return float(self.position.z)


def test_resolve_auto_yaw_axis_targets_coin_road() -> None:
    """Auto yaw should steer toward the averaged coin lane ahead."""
    run_state = FallingRunState()
    coin_entity = DummyEntity(position=Vec3(20.0, -200.0, 0.0))
    run_state.spawned_objects.append(
        SpawnedObject(
            entity=coin_entity,
            entity_kind="coin",
            color_name="yellow",
            model_name="models/coins/coin.bam",
            collision_radius=0.7,
            score_value=1,
            band_index=0,
        ),
    )
    axis = resolve_auto_yaw_axis(
        run_state=run_state,
        player_position=Vec3(0.0, 0.0, 0.0),
        fall_settings=FallSettings(),
        camera_state=CameraState(yaw_angle=0.0, pitch_angle=0.0, distance=12.0),
        yaw_turn_speed=90.0,
    )
    CHECKER.assertGreater(axis, 0.0)


def test_resolve_auto_yaw_axis_returns_zero_without_coins() -> None:
    """Auto yaw should stay neutral when no coins are in range."""
    axis = resolve_auto_yaw_axis(
        run_state=FallingRunState(),
        player_position=Vec3(0.0, 0.0, 0.0),
        fall_settings=FallSettings(),
        camera_state=CameraState(yaw_angle=0.0, pitch_angle=0.0, distance=12.0),
        yaw_turn_speed=90.0,
    )
    CHECKER.assertEqual(axis, 0.0)
