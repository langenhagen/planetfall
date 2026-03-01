"""Tests for runtime collision recovery behavior."""

from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, cast
from unittest import TestCase
from unittest.mock import patch

from ursina import Vec3

from planetfall.game.config import FallSettings, GameplayTuningSettings
from planetfall.game.runtime import (
    FallingRunState,
    MotionState,
    SpawnedObject,
    apply_obstacle_recovery,
    process_collisions,
)

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
        patch("planetfall.game.runtime.destroy_entity_tree") as destroy_mock,
        patch("planetfall.game.runtime.play_obstacle_hit_sfx") as sfx_mock,
        patch("planetfall.game.runtime.trigger_impact_rumble") as rumble_mock,
        patch("planetfall.game.runtime.apply_obstacle_recovery") as recovery_mock,
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
