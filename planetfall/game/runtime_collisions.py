"""Collision and recovery handling for runtime entities.

Owns collision resolution, recovery penalties, and cleanup of passed entities.
"""

from time import monotonic
from typing import TYPE_CHECKING

from ursina import Entity, Vec3, destroy

from planetfall.game.runtime_audio import (
    play_coin_pickup_sfx,
    play_obstacle_hit_sfx,
    play_powerup_pickup_sfx,
)
from planetfall.game.runtime_controls import should_despawn_object
from planetfall.game.runtime_fx import trigger_impact_rumble

if TYPE_CHECKING:
    from planetfall.game.config import FallSettings, GameplayTuningSettings
    from planetfall.game.runtime_state import (
        FallingRunState,
        MotionState,
        SpawnedObject,
    )

PLAYER_COLLISION_RADIUS = 0.95
COIN_COLLECT_ANIMATION_SECONDS = 0.18
POWERUP_MAGNET_KIND = "magnet"


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


def process_collisions(
    *,
    player: Entity,
    motion_state: MotionState,
    run_state: FallingRunState,
    fall_settings: FallSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Handle collisions with coins and obstacles for score and reset behavior."""
    now = monotonic()
    survivors: list[SpawnedObject] = []

    for spawned in run_state.spawned_objects:
        if spawned.collision_radius <= 0.0:
            survivors.append(spawned)
            continue

        hit_radius = PLAYER_COLLISION_RADIUS + spawned.collision_radius
        delta_y = spawned.entity.y - player.y
        if abs(delta_y) > hit_radius:
            survivors.append(spawned)
            continue

        delta = spawned.entity.position - player.position
        distance_squared = (
            (delta.x * delta.x) + (delta.y * delta.y) + (delta.z * delta.z)
        )
        if distance_squared > (hit_radius * hit_radius):
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "coin":
            spawned.is_collecting = True
            spawned.collect_started_at = now
            spawned.collect_duration = COIN_COLLECT_ANIMATION_SECONDS
            spawned.collect_start_position = Vec3(
                spawned.entity.position.x,
                spawned.entity.position.y,
                spawned.entity.position.z,
            )
            spawned.collision_radius = 0.0
            run_state.collected_coins += 1
            run_state.score += spawned.score_value
            play_coin_pickup_sfx()
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "obstacle":
            if (
                now - run_state.last_hit_time
                < gameplay_settings.obstacle_hit_cooldown_seconds
            ):
                survivors.append(spawned)
                continue

            destroy_entity_tree(spawned.entity)
            run_state.last_hit_time = now
            run_state.reset_count += 1
            run_state.score = max(
                0,
                run_state.score - fall_settings.recovery_score_penalty,
            )
            play_obstacle_hit_sfx()
            trigger_impact_rumble(intensity=0.65)
            apply_obstacle_recovery(
                player=player,
                motion_state=motion_state,
                recovery_height=fall_settings.recovery_height,
            )
            continue

        if spawned.entity_kind == "powerup":
            if spawned.powerup_kind == POWERUP_MAGNET_KIND:
                run_state.magnet_expires_at = (
                    now + gameplay_settings.magnet_duration_seconds
                )
                run_state.score += 5
                play_powerup_pickup_sfx()
            destroy_entity_tree(spawned.entity)
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
