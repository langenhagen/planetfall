"""Powerup spawn helpers for runtime entities."""

from time import monotonic
from typing import TYPE_CHECKING

from ursina import Entity, Vec3

from planetfall.game.runtime_colors import rgba_color
from planetfall.game.runtime_state import FallingRunState, SpawnedObject

if TYPE_CHECKING:
    from random import Random

    from planetfall.game.config import (
        FallSettings,
        GameplayTuningSettings,
        MovementSettings,
    )

POWERUP_MODEL_NAME = "icosphere"
POWERUP_MAGNET_KIND = "magnet"
POWERUP_BASE_COLOR = rgba_color(1.0, 0.35, 0.9, 1.0)
POWERUP_HALO_COLOR = rgba_color(0.95, 0.2, 0.8, 0.22)

__all__ = [
    "POWERUP_BASE_COLOR",
    "POWERUP_HALO_COLOR",
    "POWERUP_MAGNET_KIND",
    "POWERUP_MODEL_NAME",
    "schedule_next_powerup_spawn",
    "spawn_powerup",
    "update_powerup_spawning",
]


def schedule_next_powerup_spawn(
    *,
    run_state: FallingRunState,
    rng: Random,
    gameplay_settings: GameplayTuningSettings,
    now: float,
) -> None:
    """Schedule the next powerup spawn time."""
    jitter = rng.uniform(
        -gameplay_settings.powerup_spawn_jitter_seconds,
        gameplay_settings.powerup_spawn_jitter_seconds,
    )
    interval = max(4.0, gameplay_settings.powerup_spawn_interval_seconds + jitter)
    run_state.next_powerup_spawn_at = now + interval


def spawn_powerup(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    # R0913: explicit spawn inputs.
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    movement_settings: MovementSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Spawn a single magnet powerup ahead of the player."""
    spawn_y = player_y - (fall_settings.spawn_ahead_distance * 0.35)
    max_radius = movement_settings.play_area_radius * 0.6
    spawn_x = rng.uniform(-max_radius, max_radius)
    spawn_z = rng.uniform(-max_radius, max_radius)
    entity_name = f"powerup_magnet_{int(spawn_y)}"
    entity = Entity(
        name=entity_name,
        model=POWERUP_MODEL_NAME,
        color=POWERUP_BASE_COLOR,
        scale=Vec3(1.2, 1.2, 1.2),
        position=Vec3(spawn_x, spawn_y, spawn_z),
    )
    entity.unlit = True
    Entity(
        parent=entity,
        name=f"{entity_name}_halo",
        model=POWERUP_MODEL_NAME,
        scale=Vec3(1.85, 1.85, 1.85),
        color=POWERUP_HALO_COLOR,
        unlit=True,
    )
    run_state.spawned_objects.append(
        SpawnedObject(
            entity=entity,
            entity_kind="powerup",
            color_name="magnet",
            model_name=POWERUP_MODEL_NAME,
            collision_radius=4.0,
            score_value=0,
            band_index=0,
            base_x=entity.x,
            base_y=entity.y,
            base_z=entity.z,
            base_scale=Vec3(1.2, 1.2, 1.2),
            spawn_time=monotonic(),
            powerup_kind=POWERUP_MAGNET_KIND,
        ),
    )
    schedule_next_powerup_spawn(
        run_state=run_state,
        rng=rng,
        gameplay_settings=gameplay_settings,
        now=monotonic(),
    )


def update_powerup_spawning(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    # R0913: explicit spawn inputs.
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    movement_settings: MovementSettings,
    gameplay_settings: GameplayTuningSettings,
    now: float,
) -> None:
    """Spawn powerups on an independent timer."""
    if run_state.next_powerup_spawn_at <= 0.0:
        schedule_next_powerup_spawn(
            run_state=run_state,
            rng=rng,
            gameplay_settings=gameplay_settings,
            now=now,
        )
        spawn_powerup(
            run_state=run_state,
            player_y=player_y,
            rng=rng,
            fall_settings=fall_settings,
            movement_settings=movement_settings,
            gameplay_settings=gameplay_settings,
        )
        return
    if now < run_state.next_powerup_spawn_at:
        return
    spawn_powerup(
        run_state=run_state,
        player_y=player_y,
        rng=rng,
        fall_settings=fall_settings,
        movement_settings=movement_settings,
        gameplay_settings=gameplay_settings,
    )
