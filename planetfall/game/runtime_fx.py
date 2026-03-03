"""Runtime effects helpers (rumble, feedback).

Owns gamepad rumble resolution and impact feedback.
"""

import importlib
from contextlib import suppress
from functools import lru_cache
from typing import Protocol, cast

from ursina import Entity, Vec3, camera, color


class GamepadVibrateCallable(Protocol):  # pylint: disable=too-few-public-methods
    # R0903: protocol is single-call hook.
    """Callable protocol for Ursina's optional gamepad vibrate hook."""

    def __call__(self, **_kwargs: float) -> object:
        """Trigger gamepad vibration with motor intensities and duration."""


@lru_cache(maxsize=1)
def resolve_gamepad_vibrate_callable() -> GamepadVibrateCallable | None:
    """Resolve and cache the optional Ursina gamepad vibrate callable."""
    with suppress(Exception):
        gamepad_module = importlib.import_module("ursina.gamepad")
        if not hasattr(gamepad_module, "vibrate"):
            return None
        vibrate = gamepad_module.vibrate
        if callable(vibrate):
            return cast("GamepadVibrateCallable", vibrate)
    return None


def trigger_impact_rumble(intensity: float) -> None:
    """Trigger brief gamepad rumble on obstacle impact, if available."""
    vibrate = resolve_gamepad_vibrate_callable()
    if vibrate is None:
        return

    with suppress(Exception):
        vibrate(
            low_freq_motor=max(0.2, min(1.0, intensity)),
            high_freq_motor=max(0.2, min(1.0, intensity + 0.1)),
            duration=0.09,
        )


def create_hit_flash() -> Entity:
    """Create a full-screen flash overlay for obstacle impacts."""
    return Entity(
        name="hit_flash_overlay",
        parent=camera.ui,
        model="quad",
        scale=Vec3(2.0, 2.0, 1.0),
        color=color.rgba(255, 255, 255, 0),
        enabled=False,
        z=-1.0,
    )
