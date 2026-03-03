"""Tests for powerup spawn helpers."""

from random import Random
from unittest import TestCase

from planetfall.game.config import GameplayTuningSettings
from planetfall.game.runtime_spawn_powerups import schedule_next_powerup_spawn
from planetfall.game.runtime_state import FallingRunState

CHECKER = TestCase()


def test_schedule_next_powerup_spawn_respects_minimum_interval() -> None:
    """Powerup spawn schedule should never be below the minimum interval."""
    run_state = FallingRunState()
    schedule_next_powerup_spawn(
        run_state=run_state,
        rng=Random(0),  # noqa: S311  # nosec B311
        gameplay_settings=GameplayTuningSettings(
            powerup_spawn_interval_seconds=1.0,
            powerup_spawn_jitter_seconds=0.0,
        ),
        now=10.0,
    )
    CHECKER.assertEqual(run_state.next_powerup_spawn_at, 14.0)
