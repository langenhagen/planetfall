"""Tests for runtime collision helpers."""

from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, cast
from unittest import TestCase
from unittest.mock import patch

# B104: ignore non-bound socket in test import; attr-defined for stubs.
# pylint: disable=no-member  # no-member: Vec3 exposes runtime attrs in tests.
from ursina import Vec3

from planetfall.game.config import FallSettings, GameplayTuningSettings
from planetfall.game.runtime import (
    FallingRunState,
    MotionState,
    SpawnedObject,
    apply_obstacle_recovery,
    process_collisions,
)
from planetfall.game.runtime_collisions import _compute_collision_hits

if TYPE_CHECKING:
    from ursina import Entity

CHECKER = TestCase()


@dataclass(slots=True)
class DummyPlayer:
    """Tiny test helper with the y attribute used in recovery logic."""

    y: float


@dataclass(slots=True)
class DummyEntity:
    """Minimal entity-like object used for collision behavior tests."""

    position: Vec3
    y: float = 0.0
    children: list[object] = field(default_factory=list)

    @property
    def x(self) -> float:
        """Expose x component like a real Ursina entity."""
        return float(self.position.x)

    @x.setter
    def x(self, value: float) -> None:
        self.position = Vec3(value, self.position.y, self.position.z)

    @property
    def z(self) -> float:
        """Expose z component like a real Ursina entity."""
        return float(self.position.z)

    @z.setter
    def z(self, value: float) -> None:
        self.position = Vec3(self.position.x, self.position.y, value)


def test_apply_obstacle_recovery_lifts_player_and_damps_speed() -> None:
    """Raise the player and damp movement after obstacle impact."""
    player = cast("Entity", DummyPlayer(y=-180.0))
    motion_state = MotionState(horizontal_speed=7.5, depth_speed=-4.0)

    apply_obstacle_recovery(
        player=player,
        motion_state=motion_state,
        recovery_height=12.0,
    )

    CHECKER.assertEqual(player.y, -168.0)
    CHECKER.assertEqual(motion_state.horizontal_speed, 1.5)
    CHECKER.assertEqual(motion_state.depth_speed, -0.8)


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


def test_process_collisions_keeps_obstacle_during_hit_cooldown() -> None:
    """Do not delete an obstacle when hit cooldown is still active."""
    player = cast("Entity", DummyEntity(position=Vec3(0.0, 0.0, 0.0)))
    obstacle_entity = cast("Entity", DummyEntity(position=Vec3(0.2, 0.0, 0.0)))
    spawned_obstacle = SpawnedObject(
        entity=obstacle_entity,
        entity_kind="obstacle",
        color_name="gray",
        model_name="cube",
        collision_radius=1.0,
        score_value=0,
        band_index=0,
    )
    run_state = FallingRunState(
        score=100,
        last_hit_time=monotonic(),
        spawned_objects=[spawned_obstacle],
    )

    with (
        patch("planetfall.game.runtime_collisions.destroy_entity_tree") as destroy_mock,
        patch("planetfall.game.runtime_collisions.play_obstacle_hit_sfx") as sfx_mock,
        patch(
            "planetfall.game.runtime_collisions.trigger_impact_rumble",
        ) as rumble_mock,
        patch(
            "planetfall.game.runtime_collisions.apply_obstacle_recovery",
        ) as recovery_mock,
    ):
        process_collisions(
            player=player,
            motion_state=MotionState(),
            run_state=run_state,
            fall_settings=FallSettings(),
            gameplay_settings=GameplayTuningSettings(),
        )

    CHECKER.assertFalse(destroy_mock.called)
    CHECKER.assertFalse(sfx_mock.called)
    CHECKER.assertFalse(rumble_mock.called)
    CHECKER.assertFalse(recovery_mock.called)
    CHECKER.assertEqual(len(run_state.spawned_objects), 1)
    CHECKER.assertEqual(run_state.reset_count, 0)
    CHECKER.assertEqual(run_state.score, 100)


def test_process_collisions_batches_large_inputs() -> None:
    """Batch collision hits when many objects are present."""
    spawned_objects: list[SpawnedObject] = []
    hit_index = 0
    for index in range(5):
        x_pos = 0.4 if index == hit_index else 500.0 + index
        coin_entity = cast("Entity", DummyEntity(position=Vec3(x_pos, 0.0, 0.0)))
        spawned_objects.append(
            SpawnedObject(
                entity=coin_entity,
                entity_kind="coin",
                color_name="yellow",
                model_name="models/coins/coin.bam",
                collision_radius=0.7,
                score_value=5,
                band_index=0,
                base_scale=Vec3(1.0, 1.0, 1.0),
            ),
        )

    hits = _compute_collision_hits(
        player_position=Vec3(0.0, 0.0, 0.0),
        player_radius=0.95,
        spawned_objects=spawned_objects,
    )

    CHECKER.assertTrue(bool(hits[hit_index]))
    CHECKER.assertFalse(bool(hits[1]))
