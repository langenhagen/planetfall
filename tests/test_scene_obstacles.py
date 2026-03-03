"""Tests for obstacle-focused scene blueprint generation."""

from random import Random
from unittest import TestCase

from planetfall.game.scene import (
    OBSTACLE_MODEL_NAME,
    OBSTACLE_PATTERN_COUNT,
    build_fall_band_blueprints,
)

CHECKER = TestCase()


def deterministic_rng(seed: int) -> Random:
    """Create deterministic non-crypto RNG for gameplay layout tests."""
    return Random(seed)  # noqa: S311  # nosec B311


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


def test_obstacle_patterns_cover_all_variants() -> None:  # noqa: C901
    # C901: complex test for coverage of all obstacle patterns.
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
