"""Tests for procedural falling-course scene blueprints."""

from random import Random
from unittest import TestCase

from planetfall.game.scene import (
    COIN_MODEL_NAME,
    COIN_PATTERN_COUNT,
    COIN_SCORE_VALUE,
    HIGH_VALUE_COIN_SCORE_VALUE,
    LANE_POSITIONS,
    MAX_COIN_ABS,
    OBSTACLE_MODEL_NAME,
    OBSTACLE_PATTERN_COUNT,
    build_fall_band_blueprints,
)

CHECKER = TestCase()


def deterministic_rng(seed: int) -> Random:
    """Create deterministic non-crypto RNG for gameplay layout tests."""
    return Random(seed)  # noqa: S311  # nosec B311


def test_build_fall_band_blueprints_contains_collidables() -> None:
    """Include obstacle and coin gameplay objects each generated band."""
    blueprints = build_fall_band_blueprints(
        band_index=0,
        y_position=-50.0,
        rng=deterministic_rng(7),
    )
    kinds = {blueprint.entity_kind for blueprint in blueprints}
    CHECKER.assertIn("obstacle", kinds)
    CHECKER.assertIn("coin", kinds)


def test_build_fall_band_blueprints_has_no_outer_wall_segments() -> None:
    """Avoid enclosing wall segments so the run feels open-air."""
    blueprints = build_fall_band_blueprints(
        band_index=1,
        y_position=-68.0,
        rng=deterministic_rng(5),
    )
    names = {blueprint.name for blueprint in blueprints}
    CHECKER.assertNotIn("frame_wall_left", names)
    CHECKER.assertNotIn("frame_wall_right", names)


def test_build_fall_band_blueprints_keeps_positions_inside_lane_bounds() -> None:
    """Place all collidable objects in the intended playable lane area."""
    blueprints = build_fall_band_blueprints(
        band_index=2,
        y_position=-90.0,
        rng=deterministic_rng(11),
    )
    collidable_blueprints = [
        blueprint for blueprint in blueprints if blueprint.collision_radius > 0.0
    ]
    max_lane_abs = max(abs(value) for value in LANE_POSITIONS)

    CHECKER.assertTrue(collidable_blueprints)
    for blueprint in collidable_blueprints:
        CHECKER.assertLessEqual(abs(blueprint.position.x), max_lane_abs)
        CHECKER.assertLessEqual(abs(blueprint.position.z), max_lane_abs)

    coin_blueprints = [
        blueprint for blueprint in blueprints if blueprint.entity_kind == "coin"
    ]
    for coin_blueprint in coin_blueprints:
        CHECKER.assertLessEqual(abs(coin_blueprint.position.x), MAX_COIN_ABS)
        CHECKER.assertLessEqual(abs(coin_blueprint.position.z), MAX_COIN_ABS)


def test_build_fall_band_blueprints_is_reproducible_for_seed() -> None:
    """Generate deterministic blueprint layouts from a fixed random seed."""
    first = build_fall_band_blueprints(
        band_index=3,
        y_position=-144.0,
        rng=deterministic_rng(42),
    )
    second = build_fall_band_blueprints(
        band_index=3,
        y_position=-144.0,
        rng=deterministic_rng(42),
    )
    CHECKER.assertEqual(first, second)


def test_bonus_arc_contains_high_value_coins() -> None:
    """Spawn occasional bonus arc coins with higher score values."""
    blueprints = build_fall_band_blueprints(
        band_index=7,
        y_position=-160.0,
        rng=deterministic_rng(19),
    )
    coin_scores = [
        blueprint.score_value
        for blueprint in blueprints
        if blueprint.entity_kind == "coin"
    ]
    CHECKER.assertIn(HIGH_VALUE_COIN_SCORE_VALUE, coin_scores)
    CHECKER.assertIn(COIN_SCORE_VALUE, coin_scores)


def test_obstacles_use_asteroid_model_asset() -> None:
    """Spawn obstacle blueprints using the imported asteroid BAM asset."""
    blueprints = build_fall_band_blueprints(
        band_index=2,
        y_position=-90.0,
        rng=deterministic_rng(11),
    )
    obstacle_models = {
        blueprint.model
        for blueprint in blueprints
        if blueprint.entity_kind == "obstacle"
    }
    CHECKER.assertEqual(obstacle_models, {OBSTACLE_MODEL_NAME})


def test_coins_use_coin_model_asset() -> None:
    """Spawn coin blueprints using the imported coin BAM asset."""
    blueprints = build_fall_band_blueprints(
        band_index=2,
        y_position=-90.0,
        rng=deterministic_rng(11),
    )
    coin_models = {
        blueprint.model for blueprint in blueprints if blueprint.entity_kind == "coin"
    }
    CHECKER.assertEqual(coin_models, {COIN_MODEL_NAME})


def test_obstacle_patterns_cover_all_variants() -> None:
    """Exercise each obstacle pattern index at least once."""
    seen_patterns = set()
    for band_index in range(OBSTACLE_PATTERN_COUNT * 2):
        blueprints = build_fall_band_blueprints(
            band_index=band_index,
            y_position=-120.0,
            rng=deterministic_rng(23),
        )
        obstacle_names = {
            blueprint.name
            for blueprint in blueprints
            if blueprint.entity_kind == "obstacle"
        }
        if any(name.startswith("gate_block") for name in obstacle_names):
            seen_patterns.add("gate")
        if any(name.startswith("slalom_block") for name in obstacle_names):
            seen_patterns.add("slalom")
        if any(name.startswith("chicane_row") for name in obstacle_names):
            seen_patterns.add("chicane")
        if any(name.startswith("ring_block") for name in obstacle_names):
            seen_patterns.add("ring")
        if any(name.startswith("comet_block") for name in obstacle_names):
            seen_patterns.add("comet")
        if any(name.startswith("checker_block") for name in obstacle_names):
            seen_patterns.add("checker")
        if any(name.startswith("spiral_block") for name in obstacle_names):
            seen_patterns.add("spiral")
        if any(name.startswith("orbit_block") for name in obstacle_names):
            seen_patterns.add("orbit")
        if any(name.startswith("scatter_block") for name in obstacle_names):
            seen_patterns.add("scatter")
    CHECKER.assertEqual(
        seen_patterns,
        {
            "gate",
            "slalom",
            "chicane",
            "ring",
            "comet",
            "checker",
            "spiral",
            "orbit",
            "scatter",
        },
    )


def test_coin_patterns_cover_all_variants() -> None:
    """Exercise each coin pattern index at least once."""
    seen_patterns = set()
    for band_index in range(COIN_PATTERN_COUNT * 3):
        blueprints = build_fall_band_blueprints(
            band_index=band_index,
            y_position=-80.0,
            rng=deterministic_rng(31),
            coin_pattern_index=band_index,
        )
        coin_names = {
            blueprint.name
            for blueprint in blueprints
            if blueprint.entity_kind == "coin"
        }
        if any(name.startswith("coin_chain") for name in coin_names):
            seen_patterns.add("chain")
        if any(name.startswith("coin_wave") for name in coin_names):
            seen_patterns.add("wave")
        if any(name.startswith("coin_fan") for name in coin_names):
            seen_patterns.add("fan")
        if any(name.startswith("coin_ribbon") for name in coin_names):
            seen_patterns.add("ribbon")
        if any(name.startswith("coin_grid") for name in coin_names):
            seen_patterns.add("grid")
        if any(name.startswith("coin_orbit") for name in coin_names):
            seen_patterns.add("orbit")
        if any(name.startswith("coin_zigzag") for name in coin_names):
            seen_patterns.add("zigzag")
        if any(name.startswith("coin_spiral") for name in coin_names):
            seen_patterns.add("spiral")
        if any(name.startswith("coin_double_spiral") for name in coin_names):
            seen_patterns.add("double_spiral")
    CHECKER.assertEqual(
        seen_patterns,
        {
            "chain",
            "wave",
            "fan",
            "ribbon",
            "grid",
            "orbit",
            "zigzag",
            "spiral",
            "double_spiral",
        },
    )
