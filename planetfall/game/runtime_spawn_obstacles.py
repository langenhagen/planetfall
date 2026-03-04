"""Obstacle spawn helpers for runtime entities."""

from typing import Final, Protocol, cast

from ursina import Entity

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
    "create_asteroid_instance",
]


class _TextureLike(Protocol):  # pylint: disable=too-few-public-methods
    """Minimal texture API needed for asteroid setup."""

    def getXSize(self, _unused: object = None) -> int:  # noqa: N802
        """Return texture width from Panda3D handle."""


class _InstancedModel(Protocol):  # pylint: disable=too-few-public-methods
    """Minimal model API needed for instanced asteroids."""

    def instanceTo(self, _parent: Entity) -> None:  # noqa: N802
        """Attach an instanced node to the parent entity."""

    def setTexture(self, _texture: _TextureLike, _priority: int) -> None:  # noqa: N802
        """Apply a texture to the underlying Panda3D model."""


_ASTEROID_MODEL_CACHE: Final[dict[str, _InstancedModel]] = {}
_ASTEROID_TEXTURE_CACHE: Final[dict[str, _TextureLike]] = {}


def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid model and diffuse texture by seed."""
    variant_index = variation_seed % len(ASTEROID_MODEL_VARIANTS)
    model_name = ASTEROID_MODEL_VARIANTS[variant_index]
    return model_name, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name]


def _unwrap_asteroid_texture(loaded_texture: object, texture_path: str) -> _TextureLike:
    """Return the Panda3D texture handle for an Ursina-loaded texture."""
    inner_texture = getattr(loaded_texture, "_texture", None)
    if inner_texture is not None:
        loaded_texture = inner_texture
    else:
        inner_texture = getattr(loaded_texture, "texture", None)
        if inner_texture is not None:
            loaded_texture = inner_texture
    if not hasattr(loaded_texture, "getXSize"):
        message = f"Unexpected texture type for {texture_path}: {type(loaded_texture)}"
        raise TypeError(message)
    return cast("_TextureLike", loaded_texture)


def _load_asteroid_model(
    model_name: str,
    texture_path: str | None,
) -> _InstancedModel:
    """Load and cache a model+texture for instanced asteroids.

    Uses Ursina to load model/texture once, then reuses the Panda3D node and
    texture handle for instancing. This avoids per-entity model loads while
    keeping the instancing path lightweight.
    """
    model = _ASTEROID_MODEL_CACHE.get(model_name)
    if model is None:
        model = Entity(model=model_name).model
        if model is None:
            message = f"Failed to load asteroid model: {model_name}"
            raise ValueError(message)
        if not hasattr(model, "setTexture"):
            message = f"Unexpected model type for {model_name}: {type(model)}"
            raise TypeError(message)
        if not hasattr(model, "instanceTo"):
            message = f"Asteroid model missing instanceTo: {model_name}"
            raise TypeError(message)
        model = cast("_InstancedModel", model)
        _ASTEROID_MODEL_CACHE[model_name] = model
    if texture_path is not None:
        texture = _ASTEROID_TEXTURE_CACHE.get(texture_path)
        if texture is None:
            loaded_texture = cast("object", Entity(texture=texture_path).texture)
            if loaded_texture is None:
                message = f"Failed to load texture: {texture_path}"
                raise ValueError(message)
            texture = _unwrap_asteroid_texture(loaded_texture, texture_path)
            _ASTEROID_TEXTURE_CACHE[texture_path] = texture
        model.setTexture(texture, 1)
    return model


def create_asteroid_instance(
    *,
    name: str,
    model_name: str,
    texture_path: str | None,
) -> Entity:
    """Create an instanced asteroid entity from a cached model."""
    entity = Entity(name=name)
    model = _load_asteroid_model(model_name, texture_path)
    model.instanceTo(entity)
    return entity
