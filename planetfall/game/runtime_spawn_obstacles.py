"""Obstacle spawn helpers for runtime entities."""

from ursina import Entity

from planetfall.game.scene_base import OBSTACLE_MODEL_NAME

ASTEROID_MODEL_NAME: str = OBSTACLE_MODEL_NAME
ASTEROID_TEXTURE_VARIANTS: tuple[str, ...] = (
    "images/rock.png",
    "images/asteroid2.png",
    "images/asteroid3.png",
    "images/asteroid4.png",
    "images/asteroid5.png",
    "images/asteroid6.png",
)
ASTEROID_SCALE_MIN = 0.6
ASTEROID_SCALE_MAX = 2.5

__all__ = [
    "ASTEROID_MODEL_NAME",
    "ASTEROID_TEXTURE_VARIANTS",
    "ASTEROID_SCALE_MAX",
    "ASTEROID_SCALE_MIN",
    "choose_asteroid_variant",
    "create_asteroid_instance",
]


def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid texture by seed."""
    variant_index = variation_seed % len(ASTEROID_TEXTURE_VARIANTS)
    texture_path = ASTEROID_TEXTURE_VARIANTS[variant_index]
    return texture_path, texture_path


def create_asteroid_instance(
    *,
    name: str,
    model_name: str,
    texture_path: str | None,
) -> Entity:
    """Create a billboard asteroid entity with a rock texture."""
    return Entity(
        name=name,
        model="quad",
        billboard=True,
        texture=texture_path,
    )
