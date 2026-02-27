"""Tests for deterministic asteroid variant selection."""

from typing import cast
from unittest import TestCase

from ursina import Vec3

from planetfall.game.config import GameplayTuningSettings
from planetfall.game.runtime import (
    ASTEROID_DIFFUSE_TEXTURE_BY_MODEL,
    ASTEROID_MODEL_NAME,
    ASTEROID_MODEL_VARIANTS,
    choose_asteroid_variant,
    deterministic_probability_hit,
    spawn_entity_from_blueprint,
)
from planetfall.game.scene import FallingBlueprint

CHECKER = TestCase()


def test_choose_asteroid_variant_cycles_all_models() -> None:
    """Cover all asteroid variants when stepping seed values."""
    seen_models = {
        choose_asteroid_variant(seed)[0]
        for seed in range(len(ASTEROID_MODEL_VARIANTS) * 2)
    }
    CHECKER.assertEqual(seen_models, set(ASTEROID_MODEL_VARIANTS))


def test_choose_asteroid_variant_returns_matching_texture() -> None:
    """Return texture path matching the selected asteroid model."""
    for seed in range(len(ASTEROID_MODEL_VARIANTS)):
        model_name, texture_path = choose_asteroid_variant(seed)
        CHECKER.assertEqual(texture_path, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name])


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
    dynamic_index = None
    for blueprint_index in range(32):
        variation_seed = blueprint_index * 17
        should_spin = deterministic_probability_hit(
            seed=variation_seed + 3,
            probability=0.7,
        )
        if not should_spin and static_index is None:
            static_index = blueprint_index
        if should_spin and dynamic_index is None:
            dynamic_index = blueprint_index
        if static_index is not None and dynamic_index is not None:
            break

    CHECKER.assertIsNotNone(static_index)
    CHECKER.assertIsNotNone(dynamic_index)

    static_spawned = spawn_entity_from_blueprint(
        blueprint=blueprint,
        band_index=0,
        blueprint_index=cast("int", static_index),
        gameplay_settings=GameplayTuningSettings(),
    )
    dynamic_spawned = spawn_entity_from_blueprint(
        blueprint=blueprint,
        band_index=0,
        blueprint_index=cast("int", dynamic_index),
        gameplay_settings=GameplayTuningSettings(),
    )

    static_is_static = (
        static_spawned.spin_speed_x
        == static_spawned.spin_speed_y
        == static_spawned.spin_speed_z
        == static_spawned.drift_speed_x
        == static_spawned.drift_speed_z
        == 0.0
    )
    dynamic_is_static = (
        dynamic_spawned.spin_speed_x
        == dynamic_spawned.spin_speed_y
        == dynamic_spawned.spin_speed_z
        == dynamic_spawned.drift_speed_x
        == dynamic_spawned.drift_speed_z
        == 0.0
    )

    CHECKER.assertTrue(static_is_static)
    CHECKER.assertFalse(dynamic_is_static)
