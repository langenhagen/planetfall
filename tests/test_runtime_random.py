"""Tests for deterministic runtime random helpers."""

from unittest import TestCase

from planetfall.game.runtime_random import (
    deterministic_probability_hit,
    discrete_value_in_range,
    signed_speed_from_seed,
)

CHECKER = TestCase()


def test_deterministic_probability_hit_clamps_bounds() -> None:
    """Clamp probabilities outside the 0-1 range."""
    CHECKER.assertFalse(deterministic_probability_hit(seed=7, probability=-0.4))
    CHECKER.assertTrue(deterministic_probability_hit(seed=7, probability=1.6))


def test_deterministic_probability_hit_is_stable_for_seed() -> None:
    """Ensure probability hit stays deterministic for the same seed."""
    result = deterministic_probability_hit(seed=1337, probability=0.42)
    for _ in range(3):
        CHECKER.assertEqual(
            deterministic_probability_hit(seed=1337, probability=0.42),
            result,
        )


def test_discrete_value_in_range_handles_single_variant() -> None:
    """Use minimum when variant count collapses."""
    CHECKER.assertEqual(
        discrete_value_in_range(
            seed=3,
            variant_count=1,
            minimum=-2.5,
            maximum=10.0,
        ),
        -2.5,
    )


def test_signed_speed_from_seed_flips_sign_by_seed() -> None:
    """Even seeds produce negative, odd seeds positive."""
    negative_speed = signed_speed_from_seed(
        seed=10,
        variant_count=5,
        minimum_magnitude=1.0,
        maximum_magnitude=3.0,
    )
    positive_speed = signed_speed_from_seed(
        seed=11,
        variant_count=5,
        minimum_magnitude=1.0,
        maximum_magnitude=3.0,
    )
    CHECKER.assertLess(negative_speed, 0.0)
    CHECKER.assertGreater(positive_speed, 0.0)
