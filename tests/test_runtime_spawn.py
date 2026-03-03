"""Tests for deterministic asteroid variant selection."""

from random import Random
from typing import cast
from unittest import TestCase

from ursina import Vec3

from planetfall.game.config import GameplayTuningSettings
from planetfall.game.runtime_random import deterministic_probability_hit
from planetfall.game.runtime_spawn import (
    ASTEROID_DIFFUSE_TEXTURE_BY_MODEL,
    ASTEROID_MODEL_NAME,
    ASTEROID_MODEL_VARIANTS,
    choose_asteroid_variant,
    rainbow_lane_rgb,
    rainbow_wave_rgb,
    schedule_next_powerup_spawn,
    spawn_entity_from_blueprint,
)
from planetfall.game.runtime_state import FallingRunState
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


def test_choose_asteroid_variant_wraps_negative_seed() -> None:
    """Negative seeds should still resolve a valid model and texture."""
    model_name, texture_path = choose_asteroid_variant(-1)
    CHECKER.assertIn(model_name, ASTEROID_MODEL_VARIANTS)
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


def test_rainbow_lane_rgb_clamps_to_lane_span() -> None:
    """Clamp lane colors to the same edge values when outside bounds."""
    at_min = rainbow_lane_rgb(-9999.0)
    at_max = rainbow_lane_rgb(9999.0)
    CHECKER.assertEqual(at_min, rainbow_lane_rgb(-100000.0))
    CHECKER.assertEqual(at_max, rainbow_lane_rgb(100000.0))


def test_rainbow_wave_rgb_is_normalized() -> None:
    """Ensure wave colors stay within expected 0..1 bounds."""
    red, green, blue = rainbow_wave_rgb(
        lane_x=4.0,
        band_index=3,
        runtime_time=1.25,
    )
    CHECKER.assertGreaterEqual(red, 0.0)
    CHECKER.assertLessEqual(red, 1.0)
    CHECKER.assertGreaterEqual(green, 0.0)
    CHECKER.assertLessEqual(green, 1.0)
    CHECKER.assertGreaterEqual(blue, 0.0)
    CHECKER.assertLessEqual(blue, 1.0)


def test_schedule_next_powerup_spawn_respects_minimum_interval() -> None:
    """Powerup spawn schedule should never be below the minimum interval."""
    run_state = FallingRunState()
    schedule_next_powerup_spawn(
        run_state=run_state,
        rng=Random(0),
        gameplay_settings=GameplayTuningSettings(
            powerup_spawn_interval_seconds=1.0,
            powerup_spawn_jitter_seconds=0.0,
        ),
        now=10.0,
    )
    CHECKER.assertEqual(run_state.next_powerup_spawn_at, 14.0)
