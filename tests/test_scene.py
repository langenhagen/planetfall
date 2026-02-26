"""Tests for procedural falling-course scene blueprints."""

from random import Random
from unittest import TestCase

from planetfall.game.scene import (
    COIN_MODEL_NAME,
    COIN_SCORE_VALUE,
    HIGH_VALUE_COIN_SCORE_VALUE,
    LANE_POSITIONS,
    MAX_COIN_ABS,
    OBSTACLE_MODEL_NAME,
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
    """Spawn obstacle blueprints using the imported asteroid OBJ asset."""
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
    """Spawn coin blueprints using the imported coin OBJ asset."""
    blueprints = build_fall_band_blueprints(
        band_index=2,
        y_position=-90.0,
        rng=deterministic_rng(11),
    )
    coin_models = {
        blueprint.model for blueprint in blueprints if blueprint.entity_kind == "coin"
    }
    CHECKER.assertEqual(coin_models, {COIN_MODEL_NAME})
