"""Obstacle spawn helpers for runtime entities."""

from typing import Final, Protocol, cast

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
    """Select deterministic asteroid texture by seed."""
    variant_index = variation_seed % len(ASTEROID_TEXTURE_VARIANTS)
    texture_path = ASTEROID_TEXTURE_VARIANTS[variant_index]
    return texture_path, texture_path


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


def _load_asteroid_model(texture_path: str) -> _InstancedModel:
    """Load and cache a textured quad for instanced asteroids.

    Creates a flat quad model, applies the variant texture, and caches the
    Panda3D node so every entity of the same variant shares one draw call.
    """
    model = _ASTEROID_MODEL_CACHE.get(texture_path)
    if model is None:
        model = Entity(model="quad").model
        if model is None:
            message = "Failed to load quad model"
            raise ValueError(message)
        if not hasattr(model, "setTexture"):
            message = f"Unexpected model type for quad: {type(model)}"
            raise TypeError(message)
        if not hasattr(model, "instanceTo"):
            message = "Quad model missing instanceTo"
            raise TypeError(message)
        model = cast("_InstancedModel", model)

        texture = _ASTEROID_TEXTURE_CACHE.get(texture_path)
        if texture is None:
            loaded_texture = cast("object", Entity(texture=texture_path).texture)
            if loaded_texture is not None:
                texture = _unwrap_asteroid_texture(loaded_texture, texture_path)
                _ASTEROID_TEXTURE_CACHE[texture_path] = texture

        if texture is not None:
            model.setTexture(texture, 1)
        _ASTEROID_MODEL_CACHE[texture_path] = model
    return model


def create_asteroid_instance(
    *,
    name: str,
    model_name: str,
    texture_path: str | None,
) -> Entity:
    """Create an instanced asteroid entity from a cached textured quad."""
    entity = Entity(name=name, rotation_x=90)
    if texture_path is not None:
        model = _load_asteroid_model(texture_path)
        model.instanceTo(entity)
    return entity
