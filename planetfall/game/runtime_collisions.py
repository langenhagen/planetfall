"""Collision and recovery handling for runtime entities.

Owns collision resolution, recovery penalties, and cleanup of passed entities.
"""

from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

import numpy as np
from ursina import Entity, Vec3, destroy

from planetfall.game.runtime_audio import (
    play_coin_pickup_sfx,
    play_obstacle_hit_sfx,
    play_powerup_pickup_sfx,
)
from planetfall.game.runtime_controls import should_despawn_object
from planetfall.game.runtime_fx import create_hit_flash, trigger_impact_rumble
from planetfall.game.runtime_spawn_powerups import (
    POWERUP_MAGNET_KIND,
    POWERUP_MULTIPLIER_KIND,
    POWERUP_SHIELD_KIND,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from planetfall.game.config import FallSettings, GameplayTuningSettings
    from planetfall.game.runtime_state import (
        FallingRunState,
        MotionState,
        SpawnedObject,
    )

PLAYER_COLLISION_RADIUS = 0.95
COIN_COLLECT_ANIMATION_SECONDS = 0.18


@dataclass(slots=True)
class CollisionContext:
    """Shared state used while resolving collisions for this frame."""

    player: Entity
    motion_state: MotionState
    run_state: FallingRunState
    fall_settings: FallSettings
    gameplay_settings: GameplayTuningSettings
    now: float
    hit_flash: Entity | None


def _compute_collision_hits(
    *,
    player_position: Vec3,
    player_radius: float,
    spawned_objects: list[SpawnedObject],
) -> NDArray[np.bool_]:
    """Return a boolean mask for which objects intersect the player."""
    positions = np.array(
        [
            (
                spawned.entity.x,
                spawned.entity.y,
                spawned.entity.z,
                spawned.collision_radius,
            )
            for spawned in spawned_objects
        ],
        dtype=np.float32,
    )
    player_vec = np.array(
        [player_position.x, player_position.y, player_position.z],
        dtype=np.float32,
    )
    deltas = positions[:, :3] - player_vec
    hit_radius = player_radius + positions[:, 3]
    distance_squared: NDArray[np.floating] = np.einsum("ij,ij->i", deltas, deltas)
    hit_distance: NDArray[np.floating] = hit_radius * hit_radius
    return np.asarray(distance_squared <= hit_distance, dtype=np.bool_)


def _handle_coin_collision(
    *,
    spawned: SpawnedObject,
    ctx: CollisionContext,
) -> None:
    spawned.is_collecting = True
    spawned.collect_started_at = ctx.now
    spawned.collect_duration = COIN_COLLECT_ANIMATION_SECONDS
    spawned.collect_start_position = Vec3(
        spawned.entity.position.x,
        spawned.entity.position.y,
        spawned.entity.position.z,
    )
    spawned.collision_radius = 0.0
    ctx.run_state.collected_coins += 1
    coin_multiplier_active = ctx.run_state.coin_multiplier_expires_at > ctx.now
    if coin_multiplier_active:
        ctx.run_state.score += int(
            spawned.score_value * ctx.run_state.coin_multiplier_factor,
        )
    else:
        ctx.run_state.score += spawned.score_value
    play_coin_pickup_sfx()


def apply_obstacle_recovery(
    *,
    player: Entity,
    motion_state: MotionState,
    recovery_height: float,
) -> None:
    """Move the player upward after an obstacle hit and damp momentum."""
    player.y += recovery_height
    motion_state.horizontal_speed *= 0.2
    motion_state.depth_speed *= 0.2


def destroy_entity_tree(entity: Entity) -> None:
    """Destroy an entity and any child entities to avoid scene leaks."""
    for child in list(entity.children):
        destroy_entity_tree(child)
    destroy(entity)


def _handle_obstacle_collision(
    *,
    spawned: SpawnedObject,
    ctx: CollisionContext,
) -> bool:
    if (
        ctx.now - ctx.run_state.last_hit_time
        < ctx.gameplay_settings.obstacle_hit_cooldown_seconds
    ):
        return False

    if ctx.run_state.shield_expires_at > ctx.now:
        destroy_entity_tree(spawned.entity)
        play_obstacle_hit_sfx()
        trigger_impact_rumble(intensity=0.35)
        return True

    destroy_entity_tree(spawned.entity)
    ctx.run_state.last_hit_time = ctx.now
    ctx.run_state.hit_flash_expires_at = max(
        ctx.run_state.hit_flash_expires_at,
        ctx.now + ctx.gameplay_settings.obstacle_hit_cooldown_seconds,
    )
    hit_flash = ctx.hit_flash
    if hit_flash is None:
        hit_flash = create_hit_flash()
        ctx.hit_flash = hit_flash
    hit_flash.enabled = True
    ctx.run_state.reset_count += 1
    ctx.run_state.score = max(
        0,
        ctx.run_state.score - ctx.fall_settings.recovery_score_penalty,
    )
    play_obstacle_hit_sfx()
    trigger_impact_rumble(intensity=0.65)
    apply_obstacle_recovery(
        player=ctx.player,
        motion_state=ctx.motion_state,
        recovery_height=ctx.fall_settings.recovery_height,
    )
    return True


def _handle_powerup_collision(
    *,
    spawned: SpawnedObject,
    ctx: CollisionContext,
) -> None:
    if spawned.powerup_kind == POWERUP_MAGNET_KIND:
        ctx.run_state.magnet_expires_at = (
            ctx.now + ctx.gameplay_settings.magnet_duration_seconds
        )
        ctx.run_state.score += 5
        play_powerup_pickup_sfx()
    elif spawned.powerup_kind == POWERUP_SHIELD_KIND:
        ctx.run_state.shield_expires_at = (
            ctx.now + ctx.gameplay_settings.shield_duration_seconds
        )
        ctx.run_state.score += 10
        play_powerup_pickup_sfx()
    elif spawned.powerup_kind == POWERUP_MULTIPLIER_KIND:
        ctx.run_state.coin_multiplier_expires_at = (
            ctx.now + ctx.gameplay_settings.coin_multiplier_duration_seconds
        )
        ctx.run_state.coin_multiplier_factor = (
            ctx.gameplay_settings.coin_multiplier_factor
        )
        ctx.run_state.score += 10
        play_powerup_pickup_sfx()
    destroy_entity_tree(spawned.entity)


def _should_handle_collision(
    *,
    spawned: SpawnedObject,
    index: int,
    hits: NDArray[np.bool_],
) -> bool:
    if spawned.collision_radius <= 0.0:
        return False
    return bool(hits[index])


# PLR0913: too-many-arguments; explicit runtime inputs.
def process_collisions(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    player: Entity,
    motion_state: MotionState,
    run_state: FallingRunState,
    fall_settings: FallSettings,
    gameplay_settings: GameplayTuningSettings,
    hit_flash: Entity | None = None,
) -> None:
    """Handle collisions with coins and obstacles for score and reset behavior."""
    now = monotonic()
    ctx = CollisionContext(
        player=player,
        motion_state=motion_state,
        run_state=run_state,
        fall_settings=fall_settings,
        gameplay_settings=gameplay_settings,
        now=now,
        hit_flash=hit_flash,
    )
    survivors: list[SpawnedObject] = []
    spawned_objects = run_state.spawned_objects
    if not spawned_objects:
        run_state.spawned_objects = survivors
        return

    hits = _compute_collision_hits(
        player_position=player.position,
        player_radius=PLAYER_COLLISION_RADIUS,
        spawned_objects=spawned_objects,
    )

    for index, spawned in enumerate(spawned_objects):
        if not _should_handle_collision(
            spawned=spawned,
            index=index,
            hits=hits,
        ):
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "coin":
            _handle_coin_collision(spawned=spawned, ctx=ctx)
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "obstacle":
            if not _handle_obstacle_collision(spawned=spawned, ctx=ctx):
                survivors.append(spawned)
            continue

        if spawned.entity_kind == "powerup":
            _handle_powerup_collision(spawned=spawned, ctx=ctx)
            continue

        destroy_entity_tree(spawned.entity)

    run_state.spawned_objects = survivors


def destroy_spawned_objects(spawned_objects: list[SpawnedObject]) -> None:
    """Destroy spawned entities and clear the container in-place."""
    for spawned in spawned_objects:
        destroy_entity_tree(spawned.entity)
    spawned_objects.clear()


def cleanup_passed_objects(
    *,
    run_state: FallingRunState,
    player_y: float,
    cleanup_above_distance: float,
) -> None:
    """Destroy objects that are far above the player after being passed."""
    survivors: list[SpawnedObject] = []
    for spawned in run_state.spawned_objects:
        if should_despawn_object(
            object_y=spawned.entity.y,
            player_y=player_y,
            cleanup_above_distance=cleanup_above_distance,
        ):
            destroy_entity_tree(spawned.entity)
            continue
        survivors.append(spawned)

    run_state.spawned_objects = survivors
