"""Coin spawn helpers for runtime entities."""

from math import sin, tau

from planetfall.game.scene_base import MAX_COIN_ABS

__all__ = [
    "MOTION_KIND_INDEX_BY_NAME",
    "rainbow_lane_rgb",
    "rainbow_wave_rgb",
]

MOTION_KIND_INDEX_BY_NAME: dict[str, int] = {
    "": 0,
    "lane_wave": 1,
    "lane_orbit": 2,
    "lane_slalom": 3,
}


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
