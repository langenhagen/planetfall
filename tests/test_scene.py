"""Tests for procedural falling-course scene blueprints."""

from random import Random
from unittest import TestCase

from planetfall.game.scene import (
    COIN_SCORE_VALUE,
    HIGH_VALUE_COIN_SCORE_VALUE,
    LANE_POSITIONS,
    build_fall_band_blueprints,
)

CHECKER = TestCase()


def deterministic_rng(seed: int) -> Random:
    """Create deterministic non-crypto RNG for gameplay layout tests."""
    return Random(seed)  # noqa: S311  # nosec B311


def test_build_fall_band_blueprints_contains_decor_and_collidables() -> None:
    """Include decorative shards plus obstacle/coin gameplay objects."""
    blueprints = build_fall_band_blueprints(
        band_index=0,
        y_position=-50.0,
        rng=deterministic_rng(7),
    )
    kinds = {blueprint.entity_kind for blueprint in blueprints}
    CHECKER.assertIn("decor", kinds)
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
