"""Tests for coin-focused scene blueprint generation."""

from random import Random
from unittest import TestCase

from planetfall.game.scene import (
    COIN_MODEL_NAME,
    COIN_PATTERN_COUNT,
    COIN_SCORE_VALUE,
    HIGH_VALUE_COIN_SCORE_VALUE,
    build_fall_band_blueprints,
)

CHECKER = TestCase()


def deterministic_rng(seed: int) -> Random:
    """Create deterministic non-crypto RNG for gameplay layout tests."""
    return Random(seed)  # noqa: S311  # nosec B311


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


def test_coin_patterns_cover_all_variants() -> None:  # noqa: C901
    # C901: complex test for coverage of all coin patterns.
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
