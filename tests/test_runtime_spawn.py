"""Tests for runtime spawn orchestration."""

from typing import cast
from unittest import TestCase

from ursina import Vec3

from planetfall.game.config import GameplayTuningSettings
from planetfall.game.runtime_random import deterministic_probability_hit
from planetfall.game.runtime_spawn import spawn_entity_from_blueprint
from planetfall.game.runtime_spawn_obstacles import ASTEROID_MODEL_NAME
from planetfall.game.scene import FallingBlueprint

CHECKER = TestCase()


def test_spawn_entity_from_blueprint_allows_static_asteroid() -> None:
    """Some asteroids should be able to remain fully static."""
    blueprint = FallingBlueprint(
        name="static_asteroid",
        entity_kind="obstacle",
        model=ASTEROID_MODEL_NAME,
        color_name="white",
        scale=Vec3(1.0, 1.0, 1.0),
        position=Vec3(0.0, -10.0, 0.0),
        collision_radius=0.5,
    )
    static_index = None
    drift_index = None
    for blueprint_index in range(256):
        variation_seed = blueprint_index * 17
        should_spin = deterministic_probability_hit(
            seed=variation_seed + 3,
            probability=0.7,
        )
        if not should_spin and static_index is None:
            static_index = blueprint_index
        if should_spin:
            should_drift = deterministic_probability_hit(
                seed=variation_seed + 71,
                probability=0.3,
            )
            if should_drift and drift_index is None:
                drift_index = blueprint_index
        if static_index is not None and drift_index is not None:
            break

    CHECKER.assertIsNotNone(static_index)
    CHECKER.assertIsNotNone(drift_index)

    static_spawned = spawn_entity_from_blueprint(
        blueprint=blueprint,
        band_index=0,
        blueprint_index=cast("int", static_index),
        gameplay_settings=GameplayTuningSettings(),
    )
    drift_spawned = spawn_entity_from_blueprint(
        blueprint=blueprint,
        band_index=0,
        blueprint_index=cast("int", drift_index),
        gameplay_settings=GameplayTuningSettings(),
    )

    static_is_static = (
        static_spawned.drift_speed_x
        == static_spawned.drift_speed_z
        == 0.0
    )
    drift_has_drift = (
        drift_spawned.drift_speed_x != 0.0
        or drift_spawned.drift_speed_z != 0.0
    )

    CHECKER.assertTrue(static_is_static)
    CHECKER.assertTrue(drift_has_drift)
