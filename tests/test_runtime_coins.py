"""Tests for runtime coin pickup and collection animation behavior."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from unittest import TestCase
from unittest.mock import patch

from ursina import Vec3

from planetfall.game.config import FallSettings, GameplayTuningSettings
from planetfall.game.runtime import (
    FallingRunState,
    MotionState,
    SpawnedObject,
    animate_spawned_objects,
    process_collisions,
)

if TYPE_CHECKING:
    from ursina import Entity

CHECKER = TestCase()


@dataclass(slots=True)
class DummyEntity:
    """Minimal entity-like object used for coin collision/animation tests."""

    position: Vec3
    rotation_y: float = 0.0
    scale: Vec3 = field(default_factory=lambda: Vec3(1.0, 1.0, 1.0))
    children: list[object] = field(default_factory=list)

    @property
    def x(self) -> float:
        """Expose x component like a real Ursina entity."""
        return float(self.position.x)

    @x.setter
    def x(self, value: float) -> None:
        self.position.x = value

    @property
    def y(self) -> float:
        """Expose y component like a real Ursina entity."""
        return float(self.position.y)

    @y.setter
    def y(self, value: float) -> None:
        self.position.y = value

    @property
    def z(self) -> float:
        """Expose z component like a real Ursina entity."""
        return float(self.position.z)

    @z.setter
    def z(self, value: float) -> None:
        self.position.z = value


def test_process_collisions_marks_coin_for_collect_animation() -> None:
    """Convert coin collisions into short collect animations before destroy."""
    player = cast("Entity", DummyEntity(position=Vec3(0.0, 0.0, 0.0)))
    coin_entity = cast("Entity", DummyEntity(position=Vec3(0.6, 0.0, 0.0)))
    spawned_coin = SpawnedObject(
        entity=coin_entity,
        entity_kind="coin",
        color_name="yellow",
        model_name="models/coins/coin.bam",
        collision_radius=0.7,
        score_value=10,
        band_index=0,
        base_scale=Vec3(1.0, 1.0, 1.0),
    )
    run_state = FallingRunState(spawned_objects=[spawned_coin])

    with (
        patch("planetfall.game.runtime_collisions.destroy_entity_tree") as destroy_mock,
        patch("planetfall.game.runtime_collisions.play_coin_pickup_sfx") as sfx_mock,
    ):
        process_collisions(
            player=player,
            motion_state=MotionState(),
            run_state=run_state,
            fall_settings=FallSettings(),
            gameplay_settings=GameplayTuningSettings(),
        )

    CHECKER.assertFalse(destroy_mock.called)
    CHECKER.assertTrue(sfx_mock.called)
    CHECKER.assertEqual(run_state.collected_coins, 1)
    CHECKER.assertEqual(run_state.score, 10)
    CHECKER.assertEqual(len(run_state.spawned_objects), 1)
    CHECKER.assertTrue(run_state.spawned_objects[0].is_collecting)
    CHECKER.assertEqual(run_state.spawned_objects[0].collision_radius, 0.0)


def test_animate_spawned_objects_destroys_coin_after_collect_animation() -> None:
    """Shrink and remove collected coins once the collect tween completes."""
    coin_entity = cast("Entity", DummyEntity(position=Vec3(2.0, 2.0, 2.0)))
    collecting_coin = SpawnedObject(
        entity=coin_entity,
        entity_kind="coin",
        color_name="yellow",
        model_name="models/coins/coin.bam",
        collision_radius=0.0,
        score_value=10,
        band_index=0,
        base_scale=Vec3(1.0, 1.0, 1.0),
        is_collecting=True,
        collect_started_at=10.0,
        collect_duration=0.2,
        collect_start_position=Vec3(2.0, 2.0, 2.0),
    )
    run_state = FallingRunState(spawned_objects=[collecting_coin])

    with patch("planetfall.game.runtime_animation.monotonic", return_value=10.1):
        animate_spawned_objects(
            run_state=run_state,
            gameplay_settings=GameplayTuningSettings(),
            dt=0.016,
            player_y=0.0,
            player_position=Vec3(0.0, 0.0, 0.0),
        )

    CHECKER.assertEqual(len(run_state.spawned_objects), 1)
    CHECKER.assertLess(run_state.spawned_objects[0].entity.scale.x, 1.0)
    CHECKER.assertGreater(run_state.spawned_objects[0].entity.scale.x, 0.0)

    with (
        patch("planetfall.game.runtime_animation.monotonic", return_value=10.3),
        patch("planetfall.game.runtime_animation.destroy_entity_tree") as destroy_mock,
    ):
        animate_spawned_objects(
            run_state=run_state,
            gameplay_settings=GameplayTuningSettings(),
            dt=0.016,
            player_y=0.0,
            player_position=Vec3(0.0, 0.0, 0.0),
        )

    CHECKER.assertTrue(destroy_mock.called)
    CHECKER.assertGreater(coin_entity.scale.x, 0.0)
    CHECKER.assertEqual(run_state.spawned_objects, [])


def test_magnet_pull_overrides_lane_motion_in_range() -> None:
    """Suspend lane motion while a coin is within magnet range."""
    player_position = Vec3(1.0, 0.0, 0.0)
    coin_entity = cast("Entity", DummyEntity(position=Vec3(0.0, 0.0, 0.0)))
    spawned_coin = SpawnedObject(
        entity=coin_entity,
        entity_kind="coin",
        color_name="yellow",
        model_name="models/coins/coin.bam",
        collision_radius=0.7,
        score_value=10,
        band_index=0,
        base_scale=Vec3(1.0, 1.0, 1.0),
        motion_kind="lane_wave",
        motion_amplitude=2.0,
        motion_frequency=1.0,
        motion_phase=0.0,
        base_x=0.0,
        base_y=0.0,
        base_z=0.0,
    )
    run_state = FallingRunState(
        spawned_objects=[spawned_coin],
        magnet_expires_at=9999.0,
    )
    gameplay_settings = GameplayTuningSettings(
        magnet_radius=5.0,
        magnet_strength=5.0,
    )

    with patch("planetfall.game.runtime_animation.monotonic", return_value=1.0):
        animate_spawned_objects(
            run_state=run_state,
            gameplay_settings=gameplay_settings,
            dt=0.2,
            player_y=0.0,
            player_position=player_position,
        )

    CHECKER.assertGreater(coin_entity.position.x, 0.0)
    CHECKER.assertEqual(coin_entity.position.z, 0.0)
