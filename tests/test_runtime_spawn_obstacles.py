"""Tests for obstacle spawn helpers."""

from unittest import TestCase

from planetfall.game.runtime_spawn_obstacles import (
    ASTEROID_TEXTURE_VARIANTS,
    choose_asteroid_variant,
)

CHECKER = TestCase()


def test_choose_asteroid_variant_cycles_all_variants() -> None:
    """Cover all asteroid texture variants when stepping seed values."""
    seen_textures = {
        choose_asteroid_variant(seed)[0]
        for seed in range(len(ASTEROID_TEXTURE_VARIANTS) * 2)
    }
    CHECKER.assertEqual(seen_textures, set(ASTEROID_TEXTURE_VARIANTS))


def test_choose_asteroid_variant_returns_matching_model_and_texture() -> None:
    """Both return values should be the same texture path."""
    for seed in range(len(ASTEROID_TEXTURE_VARIANTS)):
        model_name, texture_path = choose_asteroid_variant(seed)
        CHECKER.assertEqual(model_name, texture_path)
        CHECKER.assertIn(texture_path, ASTEROID_TEXTURE_VARIANTS)


def test_choose_asteroid_variant_wraps_negative_seed() -> None:
    """Negative seeds should still resolve a valid texture."""
    model_name, texture_path = choose_asteroid_variant(-1)
    CHECKER.assertIn(model_name, ASTEROID_TEXTURE_VARIANTS)
    CHECKER.assertEqual(model_name, texture_path)
