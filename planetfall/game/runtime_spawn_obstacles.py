"""Obstacle spawn helpers for runtime entities."""

ASTEROID_MODEL_NAME = "models/asteroids/Asteroid_1.bam"
ASTEROID_MODEL_VARIANTS: tuple[str, ...] = (
    "models/asteroids/Asteroid_1.bam",
    "models/asteroids/Rocky_Asteroid_2.bam",
    "models/asteroids/Rocky_Asteroid_3.bam",
    "models/asteroids/Rocky_Asteroid_4.bam",
    "models/asteroids/Rocky_Asteroid_5.bam",
    "models/asteroids/Rocky_Asteroid_6.bam",
)
ASTEROID_DIFFUSE_TEXTURE_BY_MODEL: dict[str, str] = {
    "models/asteroids/Asteroid_1.bam": (
        "models/asteroids/Textures_Asteroid_1/Asteroid_1_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_2.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_2/Rocky_Asteroid_2_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_3.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_3/Rocky_Asteroid_3_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_4.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_4/Rocky_Asteroid_4_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_5.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_5/Rocky_Asteroid_5_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_6.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_6/Rocky_Asteroid_6_Diffuse_1K.png"
    ),
}
ASTEROID_SCALE_MIN = 0.6
ASTEROID_SCALE_MAX = 2.5

__all__ = [
    "ASTEROID_DIFFUSE_TEXTURE_BY_MODEL",
    "ASTEROID_MODEL_NAME",
    "ASTEROID_MODEL_VARIANTS",
    "ASTEROID_SCALE_MAX",
    "ASTEROID_SCALE_MIN",
    "choose_asteroid_variant",
]


def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid model and diffuse texture by seed."""
    variant_index = variation_seed % len(ASTEROID_MODEL_VARIANTS)
    model_name = ASTEROID_MODEL_VARIANTS[variant_index]
    return model_name, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name]
