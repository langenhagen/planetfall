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
    from planetfall.game.runtime_perf import PerfTracker
    from planetfall.game.runtime_state import FallingRunState, SpawnedObject

ANIMATION_CULL_DISTANCE = 170.0
OBSTACLE_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 3.0
COIN_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 2.0
MIN_ENTITY_SCALE = 0.02
MOTION_KIND_NONE = 0
MOTION_KIND_WAVE = 1
MOTION_KIND_ORBIT = 2
MOTION_KIND_SLALOM = 3


class CoinBatchScratch:
    """Reusable scratch buffers for coin batch animation math."""

    def __init__(self, size: int) -> None:
        """Allocate reusable arrays for the given coin batch size."""
        self.size = size
        self.positions: NDArray[np.float64] = np.empty((size, 3), dtype=np.float64)
        self.base_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.base_y: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.base_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.motion_frequency: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.motion_phase: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.motion_amplitude: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.bob_frequency: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.bob_amplitude: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pulse_frequency: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pulse_amplitude: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.motion_kind_index: NDArray[np.int8] = np.empty(size, dtype=np.int8)
        self.has_motion: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.is_wave: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.is_orbit: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.is_slalom: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.motion_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.wave_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.orbit_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.slalom_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.bob_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.pulse_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.magnet_in_range_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.magnet_not_in_range: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.magnet_distance_array: NDArray[np.float64] = np.empty(
            size,
            dtype=np.float64,
        )
        self.magnet_delta_array: NDArray[np.float64] = np.empty(
            (size, 3),
            dtype=np.float64,
        )
        self.new_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.new_y: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.new_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pulse_scale: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pull_strength: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pull_distance: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.pull_positive_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.pull_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)


class ObstacleBatchScratch:
    """Reusable scratch buffers for obstacle batch animation math."""

    def __init__(self, size: int) -> None:
        """Allocate reusable arrays for the given obstacle batch size."""
        self.size = size
        self.spin_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.spin_y: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.spin_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.drift_speed_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.drift_speed_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.drift_progress: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.drift_blend: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.base_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.base_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.drift_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.apply_mask: NDArray[np.bool_] = np.empty(size, dtype=bool)
        self.new_x: NDArray[np.float64] = np.empty(size, dtype=np.float64)
        self.new_z: NDArray[np.float64] = np.empty(size, dtype=np.float64)


_coin_scratch: CoinBatchScratch | None = None
_obstacle_scratch: ObstacleBatchScratch | None = None


def _get_coin_scratch(size: int) -> CoinBatchScratch:
    global _coin_scratch
    if _coin_scratch is None or _coin_scratch.size != size:
        _coin_scratch = CoinBatchScratch(size)
    return _coin_scratch


def _get_obstacle_scratch(size: int) -> ObstacleBatchScratch:
    global _obstacle_scratch
    if _obstacle_scratch is None or _obstacle_scratch.size != size:
        _obstacle_scratch = ObstacleBatchScratch(size)
    return _obstacle_scratch


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
    perf_tracker: PerfTracker | None = None,
) -> None:
    if not coins:
        return

    batch_start = monotonic() if perf_tracker and perf_tracker.enabled else 0.0

    coin_count = len(coins)
    scratch = _get_coin_scratch(coin_count)
    positions = scratch.positions
    base_x = scratch.base_x
    base_y = scratch.base_y
    base_z = scratch.base_z
    motion_frequency = scratch.motion_frequency
    motion_phase = scratch.motion_phase
    motion_amplitude = scratch.motion_amplitude
    bob_frequency = scratch.bob_frequency
    bob_amplitude = scratch.bob_amplitude
    pulse_frequency = scratch.pulse_frequency
    pulse_amplitude = scratch.pulse_amplitude
    motion_kind_index = scratch.motion_kind_index
    for index, coin in enumerate(coins):
        positions[index, 0] = coin.entity.x
        positions[index, 1] = coin.entity.y
        positions[index, 2] = coin.entity.z
        base_x[index] = coin.base_x
        base_y[index] = coin.base_y
        base_z[index] = coin.base_z
        motion_frequency[index] = coin.motion_frequency
        motion_phase[index] = coin.motion_phase
        motion_amplitude[index] = coin.motion_amplitude
        bob_frequency[index] = coin.bob_frequency
        bob_amplitude[index] = coin.bob_amplitude
        pulse_frequency[index] = coin.pulse_frequency
        pulse_amplitude[index] = coin.pulse_amplitude
        motion_kind_index[index] = coin.motion_kind_index

    has_motion = scratch.has_motion
    is_wave = scratch.is_wave
    is_orbit = scratch.is_orbit
    is_slalom = scratch.is_slalom
    np.not_equal(motion_kind_index, MOTION_KIND_NONE, out=has_motion)
    np.equal(motion_kind_index, MOTION_KIND_WAVE, out=is_wave)
    np.equal(motion_kind_index, MOTION_KIND_ORBIT, out=is_orbit)
    np.equal(motion_kind_index, MOTION_KIND_SLALOM, out=is_slalom)

    magnet_in_range_mask = scratch.magnet_in_range_mask
    magnet_distance_array = scratch.magnet_distance_array
    magnet_delta_array = scratch.magnet_delta_array
    magnet_in_range_mask.fill(False)
    if magnet_active:
        player_vec = np.array(
            [player_position.x, player_position.y, player_position.z],
            dtype=np.float64,
        )
        np.subtract(player_vec, positions, out=magnet_delta_array)
        magnet_distance_array[:] = np.linalg.norm(magnet_delta_array, axis=1)
        np.maximum(magnet_distance_array, 0.01, out=magnet_distance_array)
        np.less_equal(
            magnet_distance_array,
            gameplay_settings.magnet_radius,
            out=magnet_in_range_mask,
        )
    else:
        magnet_distance_array.fill(0.0)

    new_x = scratch.new_x
    new_y = scratch.new_y
    new_z = scratch.new_z
    np.copyto(new_x, positions[:, 0])
    np.copyto(new_y, positions[:, 1])
    np.copyto(new_z, positions[:, 2])

    motion_mask = scratch.motion_mask
    wave_mask = scratch.wave_mask
    orbit_mask = scratch.orbit_mask
    slalom_mask = scratch.slalom_mask
    bob_mask = scratch.bob_mask
    pulse_mask = scratch.pulse_mask
    np.logical_not(magnet_in_range_mask, out=scratch.magnet_not_in_range)
    np.logical_and(has_motion, scratch.magnet_not_in_range, out=motion_mask)
    np.logical_and(motion_mask, is_wave, out=wave_mask)
    if np.any(wave_mask):
        wave_phase_array = (runtime_time * motion_frequency[wave_mask]) + (
            motion_phase[wave_mask]
        )
        sway_array = np.sin(wave_phase_array) * motion_amplitude[wave_mask]
        new_x[wave_mask] = base_x[wave_mask] + sway_array

    np.logical_and(motion_mask, is_orbit, out=orbit_mask)
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

    np.logical_and(motion_mask, is_slalom, out=slalom_mask)
    if np.any(slalom_mask):
        slalom_phase_array = (runtime_time * motion_frequency[slalom_mask]) + (
            motion_phase[slalom_mask]
        )
        sway_array = np.sin(slalom_phase_array) * motion_amplitude[slalom_mask]
        lift_array = np.cos(slalom_phase_array) * (motion_amplitude[slalom_mask] * 0.18)
        new_x[slalom_mask] = base_x[slalom_mask] + sway_array
        new_y[slalom_mask] = base_y[slalom_mask] + lift_array

    np.greater(bob_amplitude, 0.0, out=bob_mask)
    if np.any(bob_mask):
        bob_phase_array: NDArray[np.float64] = (
            runtime_time * bob_frequency[bob_mask]
        ) + (pulse_frequency[bob_mask])
        bob_offset_array: NDArray[np.float64] = (
            np.sin(bob_phase_array) * bob_amplitude[bob_mask]
        )
        new_y[bob_mask] = base_y[bob_mask] + bob_offset_array

    pulse_scale = scratch.pulse_scale
    pulse_scale.fill(1.0)
    np.greater(pulse_amplitude, 0.0, out=pulse_mask)
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
        pull_strength_array = scratch.pull_strength
        pull_distance_array = scratch.pull_distance
        pull_positive_mask = scratch.pull_positive_mask
        pull_mask = scratch.pull_mask
        np.divide(magnet_distance_array, magnet_radius, out=pull_strength_array)
        np.subtract(1.0, pull_strength_array, out=pull_strength_array)
        pull_distance_array[:] = magnet_strength * pull_strength_array * dt
        np.minimum(pull_distance_array, magnet_distance_array, out=pull_distance_array)
        np.greater(pull_distance_array, 0.0, out=pull_positive_mask)
        np.logical_and(magnet_in_range_mask, pull_positive_mask, out=pull_mask)
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
    if perf_tracker and perf_tracker.enabled:
        perf_tracker.record("coin_batch", monotonic() - batch_start)


def _update_obstacle_batch(
    obstacles: list[SpawnedObject],
    *,
    dt: float,
    perf_tracker: PerfTracker | None = None,
) -> None:
    # R0914: batch math uses many intermediate arrays.
    # pylint: disable=too-many-locals
    if not obstacles:
        return

    batch_start = monotonic() if perf_tracker and perf_tracker.enabled else 0.0

    obstacle_count = len(obstacles)
    scratch = _get_obstacle_scratch(obstacle_count)
    spin_x = scratch.spin_x
    spin_y = scratch.spin_y
    spin_z = scratch.spin_z
    drift_speed_x = scratch.drift_speed_x
    drift_speed_z = scratch.drift_speed_z
    drift_progress = scratch.drift_progress
    drift_blend = scratch.drift_blend
    base_x = scratch.base_x
    base_z = scratch.base_z
    for index, obj in enumerate(obstacles):
        spin_x[index] = obj.spin_speed_x
        spin_y[index] = obj.spin_speed_y
        spin_z[index] = obj.spin_speed_z
        drift_speed_x[index] = obj.drift_speed_x
        drift_speed_z[index] = obj.drift_speed_z
        drift_progress[index] = obj.drift_progress
        drift_blend[index] = obj.drift_blend
        base_x[index] = obj.base_x
        base_z[index] = obj.base_z

    spin_x *= dt
    spin_y *= dt
    spin_z *= dt

    drift_mask = scratch.drift_mask
    apply_mask = scratch.apply_mask
    new_x = scratch.new_x
    new_z = scratch.new_z
    np.logical_or(drift_speed_x != 0.0, drift_speed_z != 0.0, out=drift_mask)
    np.copyto(apply_mask, drift_mask)
    np.copyto(new_x, base_x)
    np.copyto(new_z, base_z)
    if np.any(apply_mask):
        np.add(drift_blend[apply_mask], (dt * 1.6), out=drift_blend[apply_mask])
        np.minimum(drift_blend[apply_mask], 1.0, out=drift_blend[apply_mask])
        blended_dt = drift_blend[apply_mask] * dt
        drift_progress[apply_mask] = drift_progress[apply_mask] + blended_dt
        new_x[apply_mask] = base_x[apply_mask] + (
            drift_progress[apply_mask] * drift_speed_x[apply_mask]
        )
        new_z[apply_mask] = base_z[apply_mask] + (
            drift_progress[apply_mask] * drift_speed_z[apply_mask]
        )

    for index, spawned in enumerate(obstacles):
        spawned.entity.rotation_x += float(spin_x[index])
        spawned.entity.rotation_y += float(spin_y[index])
        spawned.entity.rotation_z += float(spin_z[index])
        if apply_mask[index]:
            spawned.drift_blend = float(drift_blend[index])
            spawned.drift_progress = float(drift_progress[index])
            spawned.entity.x = float(new_x[index])
            spawned.entity.z = float(new_z[index])
    if perf_tracker and perf_tracker.enabled:
        perf_tracker.record("obstacle_batch", monotonic() - batch_start)


def animate_spawned_objects(  # noqa: C901, PLR0912, PLR0915
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    run_state: FallingRunState,
    gameplay_settings: GameplayTuningSettings,
    dt: float,
    player_y: float,
    player_position: Vec3,
    perf_tracker: PerfTracker | None = None,
) -> None:
    # R0912/R0914/R0915: frame loop.
    """Animate collectibles and obstacles for richer motion language."""
    runtime_time = monotonic()
    survivors: list[SpawnedObject] = []
    magnet_active = run_state.magnet_expires_at > runtime_time
    multiplier_active = run_state.coin_multiplier_expires_at > runtime_time
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
            if spawned.powerup_kind == "shield":
                pulse_scale *= 1.06
            elif spawned.powerup_kind == "multiplier":
                pulse_scale *= 1.1
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
    if perf_tracker and perf_tracker.enabled:
        perf_tracker.set_gauge("coins", len(coin_batch))
        perf_tracker.set_gauge("obstacles", len(obstacle_batch))
    _update_coin_batch(
        coin_batch,
        runtime_time=runtime_time,
        dt=dt,
        player_position=player_position,
        gameplay_settings=gameplay_settings,
        magnet_active=magnet_active,
        wave_cache=wave_cache,
        perf_tracker=perf_tracker,
    )
    if multiplier_active:
        for spawned in coin_batch:
            spawned.entity.scale = Vec3(
                max(MIN_ENTITY_SCALE, spawned.base_scale.x * 1.6),
                max(MIN_ENTITY_SCALE, spawned.base_scale.y * 1.6),
                max(MIN_ENTITY_SCALE, spawned.base_scale.z * 1.6),
            )
    if not multiplier_active and run_state.coin_multiplier_factor != 1.0:
        run_state.coin_multiplier_factor = 1.0
    _update_obstacle_batch(
        obstacle_batch,
        dt=dt,
        perf_tracker=perf_tracker,
    )
