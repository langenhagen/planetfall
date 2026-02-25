"""Tests for procedural falling-course scene blueprints."""

from random import Random
from unittest import TestCase

from barproj.game.scene import (
    BAND_SPACING,
    LANE_POSITIONS,
    band_y_position,
    build_fall_band_blueprints,
)

CHECKER = TestCase()


def test_band_y_position_steps_downward_by_spacing() -> None:
    """Translate sequential band index values into descending y positions."""
    first = band_y_position(start_y=-36.0, band_index=0)
    fourth = band_y_position(start_y=-36.0, band_index=3)
    CHECKER.assertEqual(first, -36.0)
    CHECKER.assertEqual(fourth, -36.0 - (3 * BAND_SPACING))


def test_build_fall_band_blueprints_contains_decor_and_collidables() -> None:
    """Include decorative shards plus obstacle/coin gameplay objects."""
    blueprints = build_fall_band_blueprints(
        band_index=0,
        y_position=-50.0,
        rng=Random(7),
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
        rng=Random(5),
    )
    names = {blueprint.name for blueprint in blueprints}
    CHECKER.assertNotIn("frame_wall_left", names)
    CHECKER.assertNotIn("frame_wall_right", names)


def test_build_fall_band_blueprints_keeps_positions_inside_lane_bounds() -> None:
    """Place all collidable objects in the intended playable lane area."""
    blueprints = build_fall_band_blueprints(
        band_index=2,
        y_position=-90.0,
        rng=Random(11),
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
        rng=Random(42),
    )
    second = build_fall_band_blueprints(
        band_index=3,
        y_position=-144.0,
        rng=Random(42),
    )
    CHECKER.assertEqual(first, second)
