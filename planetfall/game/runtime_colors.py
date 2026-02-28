"""Color helpers shared across runtime modules."""

from functools import lru_cache
from typing import TYPE_CHECKING, cast

import ursina.color as color_module

from planetfall.game.runtime_controls import lerp_scalar

if TYPE_CHECKING:
    from ursina.color import Color


@lru_cache(maxsize=32)
def resolve_color(color_name: str) -> Color:
    """Resolve a color name from Ursina's built-in palette."""
    return cast("Color", getattr(color_module, color_name, color_module.white))


def rgba_color(red: float, green: float, blue: float, alpha: float = 1.0) -> Color:
    """Create a Color using Ursina's runtime rgba helper."""
    return cast("Color", color_module.rgba(red, green, blue, alpha))


def lerp_rgb_color(
    start_rgb: tuple[int, int, int],
    end_rgb: tuple[int, int, int],
    factor: float,
) -> Color:
    """Interpolate between two RGB tuples and return a Color."""
    clamped_factor = max(0.0, min(1.0, factor))
    red = round(lerp_scalar(float(start_rgb[0]), float(end_rgb[0]), clamped_factor))
    green = round(
        lerp_scalar(float(start_rgb[1]), float(end_rgb[1]), clamped_factor),
    )
    blue = round(lerp_scalar(float(start_rgb[2]), float(end_rgb[2]), clamped_factor))
    return rgba_color(red / 255.0, green / 255.0, blue / 255.0, 1.0)
