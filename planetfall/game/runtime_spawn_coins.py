"""Coin spawn helpers for runtime entities."""

from math import sin, tau
from typing import Final, Protocol, cast

from ursina import Entity

from planetfall.game.scene_base import MAX_COIN_ABS

__all__ = [
    "MOTION_KIND_INDEX_BY_NAME",
    "COIN_TEXTURE_PATH",
    "create_coin_instance",
    "rainbow_lane_rgb",
    "rainbow_wave_rgb",
]

COIN_TEXTURE_PATH: str = "images/coin.png"

MOTION_KIND_INDEX_BY_NAME: dict[str, int] = {
    "": 0,
    "lane_wave": 1,
    "lane_orbit": 2,
    "lane_slalom": 3,
}


class _CoinTextureLike(Protocol):  # pylint: disable=too-few-public-methods
    """Minimal texture API needed for coin sprite setup."""

    def getXSize(self, _unused: object = None) -> int:  # noqa: N802
        """Return texture width from Panda3D handle."""


class _CoinModel(Protocol):  # pylint: disable=too-few-public-methods
    """Minimal model API needed for instanced coin sprites."""

    def instanceTo(self, _parent: Entity) -> None:  # noqa: N802
        """Attach an instanced node to the parent entity."""

    def setTexture(self, _texture: _CoinTextureLike, _priority: int) -> None:  # noqa: N802
        """Apply a texture to the underlying Panda3D model."""


_COIN_MODEL_CACHE: Final[dict[str, _CoinModel]] = {}
_COIN_TEXTURE_CACHE: Final[dict[str, _CoinTextureLike]] = {}


def _unwrap_coin_texture(loaded_texture: object) -> _CoinTextureLike:
    """Return the Panda3D texture handle for an Ursina-loaded texture."""
    inner_texture = getattr(loaded_texture, "_texture", None)
    if inner_texture is not None:
        loaded_texture = inner_texture
    else:
        inner_texture = getattr(loaded_texture, "texture", None)
        if inner_texture is not None:
            loaded_texture = inner_texture
    if not hasattr(loaded_texture, "getXSize"):
        message = f"Unexpected texture type for coin: {type(loaded_texture)}"
        raise TypeError(message)
    return cast("_CoinTextureLike", loaded_texture)


def _load_coin_model() -> _CoinModel:
    """Load and cache a textured quad for instanced coin sprites.

    Creates a flat quad model with coin.png applied and caches the
    Panda3D node so every coin shares one draw call.
    """
    model = _COIN_MODEL_CACHE.get(COIN_TEXTURE_PATH)
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
        model = cast("_CoinModel", model)

        texture = _COIN_TEXTURE_CACHE.get(COIN_TEXTURE_PATH)
        if texture is None:
            loaded_texture = cast("object", Entity(texture=COIN_TEXTURE_PATH).texture)
            if loaded_texture is not None:
                texture = _unwrap_coin_texture(loaded_texture)
                _COIN_TEXTURE_CACHE[COIN_TEXTURE_PATH] = texture

        if texture is not None:
            model.setTexture(texture, 1)
        _COIN_MODEL_CACHE[COIN_TEXTURE_PATH] = model
    return model


def create_coin_instance(*, name: str) -> Entity:
    """Create an instanced coin sprite entity from the cached textured quad."""
    entity = Entity(name=name, rotation_x=90)
    model = _load_coin_model()
    model.instanceTo(entity)
    return entity


def rainbow_lane_rgb(lane_x: float) -> tuple[float, float, float]:
    """Return a bright rainbow color based on lateral lane position."""
    lane_span = max(0.01, MAX_COIN_ABS)
    clamped_x = max(-lane_span, min(lane_span, lane_x))
    phase = (clamped_x + lane_span) / (lane_span * 2.0)
    red = 0.5 + (0.5 * sin((tau * phase) + 0.0))
    green = 0.5 + (0.5 * sin((tau * phase) + 2.094))
    blue = 0.5 + (0.5 * sin((tau * phase) + 4.188))
    return red, green, blue


def rainbow_wave_rgb(
    *,
    lane_x: float,
    band_index: int,
    runtime_time: float,
) -> tuple[float, float, float]:
    """Return a rainbow color that ripples along the road."""
    lane_span = max(0.01, MAX_COIN_ABS)
    clamped_x = max(-lane_span, min(lane_span, lane_x))
    lane_phase = (clamped_x + lane_span) / (lane_span * 2.0)
    wave_phase = (band_index * 0.18) + (lane_phase * 1.6) + (runtime_time * 0.6)
    red = 0.5 + (0.5 * sin((tau * wave_phase) + 0.0))
    green = 0.5 + (0.5 * sin((tau * wave_phase) + 2.094))
    blue = 0.5 + (0.5 * sin((tau * wave_phase) + 4.188))
    return red, green, blue
