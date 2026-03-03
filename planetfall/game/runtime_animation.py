"""Per-frame animation for spawned runtime objects.

Owns culling thresholds and animation logic for coins, obstacles, and powerups.
"""

from math import sin
from time import monotonic
from typing import TYPE_CHECKING

import numpy as np
from ursina import Vec3

from planetfall.game.runtime_collisions import destroy_entity_tree
from planetfall.game.runtime_colors import rgba_color
from planetfall.game.runtime_spawn_coins import rainbow_wave_rgb

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from planetfall.game.config import GameplayTuningSettings
    from planetfall.game.runtime_state import FallingRunState, SpawnedObject

ANIMATION_CULL_DISTANCE = 170.0
OBSTACLE_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 3.0
COIN_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 2.0
MIN_ENTITY_SCALE = 0.02


# C901/PLR0912/PLR0913/PLR0915: vectorized batch keeps logic consolidated.
def _update_coin_batch(  # noqa: C901, PLR0912, PLR0913, PLR0915
    # pylint: disable=too-many-arguments,too-many-locals
    # pylint: disable=too-many-branches,too-many-statements
    coins: list[SpawnedObject],
    *,
    runtime_time: float,
    dt: float,
    player_position: Vec3,
    gameplay_settings: GameplayTuningSettings,
    magnet_active: bool,
    wave_cache: dict[tuple[int, float], tuple[float, float, float]],
) -> None:
    if not coins:
        return

    positions: NDArray[np.float64] = np.array(
        [(coin.entity.x, coin.entity.y, coin.entity.z) for coin in coins],
        dtype=np.float64,
    )
    base_x: NDArray[np.float64] = np.array(
        [coin.base_x for coin in coins],
        dtype=np.float64,
    )
    base_y: NDArray[np.float64] = np.array(
        [coin.base_y for coin in coins],
        dtype=np.float64,
    )
    base_z: NDArray[np.float64] = np.array(
        [coin.base_z for coin in coins],
        dtype=np.float64,
    )
    motion_frequency: NDArray[np.float64] = np.array(
        [coin.motion_frequency for coin in coins],
        dtype=np.float64,
    )
    motion_phase: NDArray[np.float64] = np.array(
        [coin.motion_phase for coin in coins],
        dtype=np.float64,
    )
    motion_amplitude: NDArray[np.float64] = np.array(
        [coin.motion_amplitude for coin in coins],
        dtype=np.float64,
    )
    bob_frequency: NDArray[np.float64] = np.array(
        [coin.bob_frequency for coin in coins],
        dtype=np.float64,
    )
    bob_amplitude: NDArray[np.float64] = np.array(
        [coin.bob_amplitude for coin in coins],
        dtype=np.float64,
    )
    pulse_frequency: NDArray[np.float64] = np.array(
        [coin.pulse_frequency for coin in coins],
        dtype=np.float64,
    )
    pulse_amplitude: NDArray[np.float64] = np.array(
        [coin.pulse_amplitude for coin in coins],
        dtype=np.float64,
    )

    motion_kind = [coin.motion_kind for coin in coins]
    has_motion: NDArray[np.bool_] = np.array(
        [bool(kind) for kind in motion_kind],
        dtype=bool,
    )
    is_wave: NDArray[np.bool_] = np.array(
        [kind == "lane_wave" for kind in motion_kind],
        dtype=bool,
    )
    is_orbit: NDArray[np.bool_] = np.array(
        [kind == "lane_orbit" for kind in motion_kind],
        dtype=bool,
    )
    is_slalom: NDArray[np.bool_] = np.array(
        [kind == "lane_slalom" for kind in motion_kind],
        dtype=bool,
    )

    magnet_in_range_mask: NDArray[np.bool_] = np.zeros(len(coins), dtype=bool)
    magnet_distance_array: NDArray[np.float64] = np.zeros(
        len(coins),
        dtype=np.float64,
    )
    magnet_delta_array: NDArray[np.float64] = np.zeros_like(positions)
    if magnet_active:
        player_vec = np.array(
            [player_position.x, player_position.y, player_position.z],
            dtype=np.float64,
        )
        magnet_delta_array = player_vec - positions
        magnet_distance_array = np.linalg.norm(magnet_delta_array, axis=1)
        magnet_distance_array = np.maximum(magnet_distance_array, 0.01)
        magnet_in_range_mask = magnet_distance_array <= gameplay_settings.magnet_radius

    new_x: NDArray[np.float64] = positions[:, 0].copy()
    new_y: NDArray[np.float64] = positions[:, 1].copy()
    new_z: NDArray[np.float64] = positions[:, 2].copy()

    motion_mask = has_motion & ~magnet_in_range_mask
    wave_mask = motion_mask & is_wave
    if np.any(wave_mask):
        wave_phase_array = (runtime_time * motion_frequency[wave_mask]) + (
            motion_phase[wave_mask]
        )
        sway_array = np.sin(wave_phase_array) * motion_amplitude[wave_mask]
        new_x[wave_mask] = base_x[wave_mask] + sway_array

    orbit_mask = motion_mask & is_orbit
    if np.any(orbit_mask):
        orbit_phase_array = (runtime_time * motion_frequency[orbit_mask]) + (
            motion_phase[orbit_mask]
        )
        new_x[orbit_mask] = base_x[orbit_mask] + (
            np.cos(orbit_phase_array) * motion_amplitude[orbit_mask]
        )
        new_z[orbit_mask] = base_z[orbit_mask] + (
            np.sin(orbit_phase_array) * motion_amplitude[orbit_mask]
        )

    slalom_mask = motion_mask & is_slalom
    if np.any(slalom_mask):
        slalom_phase_array = (runtime_time * motion_frequency[slalom_mask]) + (
            motion_phase[slalom_mask]
        )
        sway_array = np.sin(slalom_phase_array) * motion_amplitude[slalom_mask]
        lift_array = np.cos(slalom_phase_array) * (motion_amplitude[slalom_mask] * 0.18)
        new_x[slalom_mask] = base_x[slalom_mask] + sway_array
        new_y[slalom_mask] = base_y[slalom_mask] + lift_array

    bob_mask = bob_amplitude > 0.0
    if np.any(bob_mask):
        bob_phase_array: NDArray[np.float64] = (
            runtime_time * bob_frequency[bob_mask]
        ) + (pulse_frequency[bob_mask])
        bob_offset_array: NDArray[np.float64] = (
            np.sin(bob_phase_array) * bob_amplitude[bob_mask]
        )
        new_y[bob_mask] = base_y[bob_mask] + bob_offset_array

    pulse_scale: NDArray[np.float64] = np.ones(len(coins), dtype=np.float64)
    pulse_mask = pulse_amplitude > 0.0
    if np.any(pulse_mask):
        pulse_phase_array: NDArray[np.float64] = (
            runtime_time * pulse_frequency[pulse_mask]
        ) + (bob_frequency[pulse_mask])
        pulse_scale[pulse_mask] = 1.0 + (
            np.sin(pulse_phase_array) * pulse_amplitude[pulse_mask]
        )

    if magnet_active and np.any(magnet_in_range_mask):
        magnet_radius = gameplay_settings.magnet_radius
        magnet_strength = gameplay_settings.magnet_strength
        pull_strength_array: NDArray[np.float64] = 1.0 - (
            magnet_distance_array / magnet_radius
        )
        pull_distance_array = magnet_strength * pull_strength_array * dt
        pull_distance_array = np.minimum(
            pull_distance_array,
            magnet_distance_array,
        )
        pull_mask = magnet_in_range_mask & (pull_distance_array > 0.0)
        if np.any(pull_mask):
            normalized_delta_array: NDArray[np.float64] = (
                magnet_delta_array[pull_mask]
                / magnet_distance_array[pull_mask][:, None]
            )
            pull_step_array: NDArray[np.float64] = (
                normalized_delta_array * pull_distance_array[pull_mask][:, None]
            )
            new_x[pull_mask] += pull_step_array[:, 0]
            new_y[pull_mask] += pull_step_array[:, 1]
            new_z[pull_mask] += pull_step_array[:, 2]

    for index, spawned in enumerate(coins):
        spawned.entity.position = Vec3(
            float(new_x[index]),
            float(new_y[index]),
            float(new_z[index]),
        )
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
        if spawned.model_name not in {"sphere", "icosphere"}:
            spawned.entity.rotation_y += spawned.spin_speed_y * dt
        if spawned.pulse_amplitude > 0.0:
            pulse_value = pulse_scale[index]
            spawned.entity.scale = Vec3(
                max(MIN_ENTITY_SCALE, spawned.base_scale.x * pulse_value),
                max(MIN_ENTITY_SCALE, spawned.base_scale.y * pulse_value),
                max(MIN_ENTITY_SCALE, spawned.base_scale.z * pulse_value),
            )
        if magnet_active and bool(magnet_in_range_mask[index]):
            spawned.entity.rotation_y += 140.0 * dt
            spawned.entity.scale = Vec3(
                max(MIN_ENTITY_SCALE, spawned.base_scale.x * 1.12),
                max(MIN_ENTITY_SCALE, spawned.base_scale.y * 1.12),
                max(MIN_ENTITY_SCALE, spawned.base_scale.z * 1.12),
            )


def _update_obstacle_batch(
    obstacles: list[SpawnedObject],
    *,
    dt: float,
) -> None:
    # R0914: batch math uses many intermediate arrays.
    # pylint: disable=too-many-locals
    if not obstacles:
        return

    spin_x = np.array([obj.spin_speed_x for obj in obstacles], dtype=np.float64)
    spin_y = np.array([obj.spin_speed_y for obj in obstacles], dtype=np.float64)
    spin_z = np.array([obj.spin_speed_z for obj in obstacles], dtype=np.float64)
    drift_speed_x = np.array([obj.drift_speed_x for obj in obstacles], dtype=np.float64)
    drift_speed_z = np.array([obj.drift_speed_z for obj in obstacles], dtype=np.float64)
    is_sphere = np.array(
        [obj.model_name in {"sphere", "icosphere"} for obj in obstacles],
        dtype=bool,
    )
    drift_progress = np.array(
        [obj.drift_progress for obj in obstacles],
        dtype=np.float64,
    )
    drift_blend = np.array(
        [obj.drift_blend for obj in obstacles],
        dtype=np.float64,
    )
    base_x = np.array([obj.base_x for obj in obstacles], dtype=np.float64)
    base_z = np.array([obj.base_z for obj in obstacles], dtype=np.float64)

    spin_x *= dt
    spin_y *= dt
    spin_z *= dt

    drift_mask = (drift_speed_x != 0.0) | (drift_speed_z != 0.0)
    apply_mask = drift_mask & ~is_sphere
    new_x = base_x.copy()
    new_z = base_z.copy()
    if np.any(apply_mask):
        drift_blend[apply_mask] = np.minimum(
            1.0,
            drift_blend[apply_mask] + (dt * 1.6),
        )
        blended_dt = drift_blend[apply_mask] * dt
        drift_progress[apply_mask] = drift_progress[apply_mask] + blended_dt
        new_x[apply_mask] = base_x[apply_mask] + (
            drift_progress[apply_mask] * drift_speed_x[apply_mask]
        )
        new_z[apply_mask] = base_z[apply_mask] + (
            drift_progress[apply_mask] * drift_speed_z[apply_mask]
        )

    for index, spawned in enumerate(obstacles):
        if is_sphere[index]:
            continue
        spawned.entity.rotation_x += float(spin_x[index])
        spawned.entity.rotation_y += float(spin_y[index])
        spawned.entity.rotation_z += float(spin_z[index])
        if apply_mask[index]:
            spawned.drift_blend = float(drift_blend[index])
            spawned.drift_progress = float(drift_progress[index])
            spawned.entity.x = float(new_x[index])
            spawned.entity.z = float(new_z[index])


def animate_spawned_objects(  # noqa: C901, PLR0915
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
    coin_batch: list[SpawnedObject] = []
    obstacle_batch: list[SpawnedObject] = []
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
            coin_batch.append(spawned)
            survivors.append(spawned)
            continue

        if not is_sphere_model:
            obstacle_batch.append(spawned)
            survivors.append(spawned)
            continue

        survivors.append(spawned)

    run_state.spawned_objects = survivors
    _update_coin_batch(
        coin_batch,
        runtime_time=runtime_time,
        dt=dt,
        player_position=player_position,
        gameplay_settings=gameplay_settings,
        magnet_active=magnet_active,
        wave_cache=wave_cache,
    )
    _update_obstacle_batch(obstacle_batch, dt=dt)
