"""Per-frame animation for spawned runtime objects.

Owns culling thresholds and animation logic for coins, obstacles, and powerups.
"""

from math import cos, sin
from time import monotonic
from typing import TYPE_CHECKING

from ursina import Vec3

from planetfall.game.runtime_collisions import destroy_entity_tree
from planetfall.game.runtime_colors import rgba_color
from planetfall.game.runtime_spawn import rainbow_wave_rgb

if TYPE_CHECKING:
    from planetfall.game.config import GameplayTuningSettings
    from planetfall.game.runtime_state import FallingRunState, SpawnedObject

ANIMATION_CULL_DISTANCE = 170.0
OBSTACLE_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 3.0
COIN_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 2.0
MIN_ENTITY_SCALE = 0.02


def animate_spawned_objects(  # noqa: C901, PLR0912, PLR0915
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    run_state: FallingRunState,
    gameplay_settings: GameplayTuningSettings,
    dt: float,
    player_y: float,
    player_position: Vec3,
) -> None:
    # R0912/R0914/R0915: frame loop.
    """Animate collectibles and obstacles for richer motion language."""
    runtime_time = monotonic()
    survivors: list[SpawnedObject] = []
    magnet_active = run_state.magnet_expires_at > runtime_time
    wave_cache: dict[tuple[int, float], tuple[float, float, float]] = {}
    for spawned in run_state.spawned_objects:
        if spawned.entity_kind == "coin" and spawned.is_collecting:
            collect_duration = max(0.001, spawned.collect_duration)
            collect_progress = max(
                0.0,
                min(
                    1.0,
                    (runtime_time - spawned.collect_started_at) / collect_duration,
                ),
            )
            # Keep transforms invertible; a zero-scale frame can trigger
            # Panda's has_mat() assertion in render/cull internals.
            if collect_progress >= 1.0:
                destroy_entity_tree(spawned.entity)
                continue

            collect_ease = 1.0 - ((1.0 - collect_progress) ** 3)
            collect_target = Vec3(
                player_position.x,
                player_position.y + 0.45,
                player_position.z,
            )
            spawned.entity.position = spawned.collect_start_position + (
                (collect_target - spawned.collect_start_position) * collect_ease
            )
            collect_scale = max(0.0, 1.0 - collect_progress)
            spawned.entity.scale = Vec3(
                max(MIN_ENTITY_SCALE, spawned.base_scale.x * collect_scale),
                max(MIN_ENTITY_SCALE, spawned.base_scale.y * collect_scale),
                max(MIN_ENTITY_SCALE, spawned.base_scale.z * collect_scale),
            )

            survivors.append(spawned)
            continue

        if spawned.fade_duration > 0.0:
            target_red, target_green, target_blue, target_alpha = spawned.target_rgba
            elapsed = runtime_time - spawned.spawn_time
            if elapsed >= spawned.fade_duration:
                spawned.entity.color = rgba_color(
                    target_red,
                    target_green,
                    target_blue,
                    target_alpha,
                )
                spawned.fade_duration = 0.0
            else:
                fade_progress = max(0.0, min(1.0, elapsed / spawned.fade_duration))
                alpha_blend = 0.35 + (fade_progress * 0.65)
                spawned.entity.color = rgba_color(
                    target_red,
                    target_green,
                    target_blue,
                    target_alpha * alpha_blend,
                )

        cull_distance = (
            COIN_ANIMATION_CULL_DISTANCE
            if spawned.entity_kind == "coin"
            else (
                OBSTACLE_ANIMATION_CULL_DISTANCE
                if spawned.entity_kind == "obstacle"
                else ANIMATION_CULL_DISTANCE
            )
        )
        if abs(spawned.entity.y - player_y) > cull_distance:
            if spawned.drift_speed_x != 0.0 or spawned.drift_speed_z != 0.0:
                spawned.drift_blend = 0.0
            survivors.append(spawned)
            continue

        is_sphere_model = spawned.model_name in {"sphere", "icosphere"}

        if spawned.entity_kind == "powerup":
            spawned.entity.rotation_y += 60.0 * dt
            pulse_scale = 1.0 + (sin(runtime_time * 3.2) * 0.08)
            spawned.entity.scale = Vec3(
                spawned.base_scale.x * pulse_scale,
                spawned.base_scale.y * pulse_scale,
                spawned.base_scale.z * pulse_scale,
            )
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "coin":
            magnet_in_range = False
            magnet_offset = Vec3(0.0, 0.0, 0.0)
            magnet_distance = 0.0
            magnet_radius = gameplay_settings.magnet_radius
            if magnet_active:
                magnet_offset = player_position - spawned.entity.position
                magnet_distance = max(0.01, magnet_offset.length())
                magnet_in_range = magnet_distance <= magnet_radius
            if (
                spawned.motion_kind
                and not spawned.is_collecting
                and not magnet_in_range
            ):
                if spawned.motion_kind == "lane_wave":
                    sway = sin(
                        (runtime_time * spawned.motion_frequency)
                        + spawned.motion_phase,
                    )
                    spawned.entity.x = spawned.base_x + (
                        sway * spawned.motion_amplitude
                    )
                elif spawned.motion_kind == "lane_orbit":
                    orbit_phase = (
                        runtime_time * spawned.motion_frequency
                    ) + spawned.motion_phase
                    spawned.entity.x = spawned.base_x + (
                        cos(orbit_phase) * spawned.motion_amplitude
                    )
                    spawned.entity.z = spawned.base_z + (
                        sin(orbit_phase) * spawned.motion_amplitude
                    )
                elif spawned.motion_kind == "lane_slalom":
                    slalom_phase = (
                        runtime_time * spawned.motion_frequency
                    ) + spawned.motion_phase
                    sway = sin(slalom_phase)
                    lift = cos(slalom_phase) * (spawned.motion_amplitude * 0.18)
                    spawned.entity.x = spawned.base_x + (
                        sway * spawned.motion_amplitude
                    )
                    spawned.entity.y = spawned.base_y + lift
            if spawned.color_name == "rainbow_wave":
                cache_key = (spawned.band_index, spawned.base_x)
                cached = wave_cache.get(cache_key)
                if cached is None:
                    cached = rainbow_wave_rgb(
                        lane_x=spawned.base_x,
                        band_index=spawned.band_index,
                        runtime_time=runtime_time,
                    )
                    wave_cache[cache_key] = cached
                wave_red, wave_green, wave_blue = cached
                spawned.target_rgba = (
                    wave_red,
                    wave_green,
                    wave_blue,
                    spawned.target_rgba[3],
                )
                spawned.entity.color = rgba_color(
                    wave_red,
                    wave_green,
                    wave_blue,
                    spawned.entity.color.a,
                )
            if not is_sphere_model:
                spawned.entity.rotation_y += spawned.spin_speed_y * dt
            if spawned.bob_amplitude > 0.0:
                spawned.entity.y = spawned.base_y + (
                    sin(
                        (runtime_time * spawned.bob_frequency)
                        + spawned.pulse_frequency,
                    )
                    * spawned.bob_amplitude
                )
            if spawned.pulse_amplitude > 0.0:
                pulse_scale = 1.0 + (
                    sin(
                        (runtime_time * spawned.pulse_frequency)
                        + spawned.bob_frequency,
                    )
                    * spawned.pulse_amplitude
                )
                spawned.entity.scale = Vec3(
                    max(MIN_ENTITY_SCALE, spawned.base_scale.x * pulse_scale),
                    max(MIN_ENTITY_SCALE, spawned.base_scale.y * pulse_scale),
                    max(MIN_ENTITY_SCALE, spawned.base_scale.z * pulse_scale),
                )
            if magnet_active:
                magnet_strength = gameplay_settings.magnet_strength
                if magnet_in_range:
                    pull_strength = 1.0 - (magnet_distance / magnet_radius)
                    pull_distance = magnet_strength * pull_strength * dt
                    pull_distance = min(pull_distance, magnet_distance)
                    spawned.entity.position += (
                        magnet_offset.normalized() * pull_distance
                    )
                    spawned.entity.rotation_y += 140.0 * dt
                    spawned.entity.scale = Vec3(
                        max(MIN_ENTITY_SCALE, spawned.base_scale.x * 1.12),
                        max(MIN_ENTITY_SCALE, spawned.base_scale.y * 1.12),
                        max(MIN_ENTITY_SCALE, spawned.base_scale.z * 1.12),
                    )
            survivors.append(spawned)
            continue

        if not is_sphere_model:
            spawned.entity.rotation_x += spawned.spin_speed_x * dt
            spawned.entity.rotation_y += spawned.spin_speed_y * dt
            spawned.entity.rotation_z += spawned.spin_speed_z * dt
            if spawned.drift_speed_x != 0.0 or spawned.drift_speed_z != 0.0:
                spawned.drift_blend = min(1.0, spawned.drift_blend + (dt * 1.6))
                blended_dt = dt * spawned.drift_blend
                spawned.drift_progress += blended_dt
                spawned.entity.x = spawned.base_x + (
                    spawned.drift_progress * spawned.drift_speed_x
                )
                spawned.entity.z = spawned.base_z + (
                    spawned.drift_progress * spawned.drift_speed_z
                )

        survivors.append(spawned)

    run_state.spawned_objects = survivors
