"""Random helpers for deterministic runtime behavior.

Owns deterministic probability and seeded range helpers.
"""

from functools import lru_cache


@lru_cache(maxsize=2048)
def deterministic_probability_hit(*, seed: int, probability: float) -> bool:
    """Return deterministic pseudo-random chance hit from integer seed."""
    clamped_probability = max(0.0, min(1.0, probability))
    if clamped_probability <= 0.0:
        return False
    if clamped_probability >= 1.0:
        return True

    hashed_seed = (seed * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    return (hashed_seed / 0x80000000) < clamped_probability


@lru_cache(maxsize=2048)
def discrete_value_in_range(
    *,
    seed: int,
    variant_count: int,
    minimum: float,
    maximum: float,
) -> float:
    """Map an integer seed to one of N evenly spaced values in a range."""
    if variant_count <= 1:
        return minimum

    clamped_variant_count = max(2, variant_count)
    variant_index = seed % clamped_variant_count
    interpolation = variant_index / (clamped_variant_count - 1)
    return minimum + ((maximum - minimum) * interpolation)


@lru_cache(maxsize=2048)
def signed_speed_from_seed(
    *,
    seed: int,
    variant_count: int,
    minimum_magnitude: float,
    maximum_magnitude: float,
) -> float:
    """Generate deterministic signed speed with bidirectional variance."""
    magnitude = discrete_value_in_range(
        seed=seed,
        variant_count=variant_count,
        minimum=minimum_magnitude,
        maximum=maximum_magnitude,
    )
    direction = -1.0 if seed % 2 == 0 else 1.0
    return magnitude * direction
