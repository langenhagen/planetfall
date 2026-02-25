"""Tests for runtime collision recovery behavior."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest import TestCase

from planetfall.game.runtime import MotionState, apply_obstacle_recovery

if TYPE_CHECKING:
    from ursina import Entity

CHECKER = TestCase()


@dataclass(slots=True)
class DummyPlayer:
    """Tiny test helper with the y attribute used in recovery logic."""

    y: float


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
