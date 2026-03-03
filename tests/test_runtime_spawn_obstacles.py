"""Tests for obstacle spawn helpers."""

from unittest import TestCase

from planetfall.game.runtime_spawn_obstacles import (
    ASTEROID_DIFFUSE_TEXTURE_BY_MODEL,
    ASTEROID_MODEL_VARIANTS,
    choose_asteroid_variant,
)

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
