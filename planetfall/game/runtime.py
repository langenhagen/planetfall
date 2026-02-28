"""Ursina runtime for an endless third-person falling game."""

# pylint: disable=too-many-lines
# C0302: large runtime keeps loop cohesive.

import importlib
from contextlib import suppress
from functools import lru_cache
from math import sin
from pathlib import Path
from random import Random
from time import monotonic
from typing import Any, Protocol, cast

import ursina
import ursina.shaders as ursina_shaders
from ursina import (
    Audio,
    Entity,
    Text,
    Vec2,
    Vec3,
    application,
    destroy,
    lerp_exponential_decay,
    mouse,
    window,
)
from ursina.main import Ursina

from planetfall.game.config import (
    FallSettings,
    GameplayTuningSettings,
    GameSettings,
    MovementSettings,
)
from planetfall.game.runtime_audio import (
    BOOST_LOOP_FADE_SECONDS,
    BOOST_LOOP_VOLUME,
    build_music_playlist,
    play_coin_pickup_sfx,
    play_obstacle_hit_sfx,
    resolve_boost_loop_clip,
    start_music_track,
)
from planetfall.game.runtime_backdrop import (
    create_space_backdrop,
    update_atmosphere_for_depth,
)
from planetfall.game.runtime_camera import (
    apply_camera_post_process,
    configure_camera,
    configure_mouse_capture,
    create_camera_orbit_rig,
    update_camera_tracking,
)
from planetfall.game.runtime_colors import resolve_color, rgba_color
from planetfall.game.runtime_controls import (
    clamp_to_play_area,
    compute_control_axes,
    compute_fall_speed,
    compute_look_angles,
    compute_smoothed_lateral_speed,
    compute_zoom_distance,
    lerp_scalar,
    rotate_planar_velocity_by_yaw,
    should_despawn_object,
    should_spawn_next_band,
)
from planetfall.game.runtime_entities import (
    configure_lighting,
    create_player_visual_state,
    mark_lit_shadowed,
    spawn_player_avatar,
)
from planetfall.game.runtime_postfx import next_post_process_option, toggle_render_mode
from planetfall.game.runtime_state import (
    BackdropState,
    CameraState,
    FallingRunState,
    LightingRig,
    MotionState,
    OrbitRig,
    PlayerVisualState,
    SpawnedObject,
)
from planetfall.game.runtime_ui import (
    create_controls_hint,
    create_pause_text,
    create_status_text,
    update_status_text,
)
from planetfall.game.scene import (
    BAND_SPACING,
    COIN_PATTERN_COUNT,
    COIN_SCORE_VALUE,
    FallingBlueprint,
    build_fall_band_blueprints,
)

PLAYER_COLLISION_RADIUS = 0.95
RUN_RANDOM_SEED = 20260224
ASTEROID_MODEL_NAME = "models/asteroids/Asteroid_1.obj"
ASTEROID_MODEL_VARIANTS: tuple[str, ...] = (
    "models/asteroids/Asteroid_1.obj",
    "models/asteroids/Rocky_Asteroid_2.obj",
    "models/asteroids/Rocky_Asteroid_3.obj",
    "models/asteroids/Rocky_Asteroid_4.obj",
    "models/asteroids/Rocky_Asteroid_5.obj",
    "models/asteroids/Rocky_Asteroid_6.obj",
)
ASTEROID_DIFFUSE_TEXTURE_BY_MODEL: dict[str, str] = {
    "models/asteroids/Asteroid_1.obj": (
        "models/asteroids/Textures_Asteroid_1/Asteroid_1_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_2.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_2/Rocky_Asteroid_2_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_3.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_3/Rocky_Asteroid_3_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_4.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_4/Rocky_Asteroid_4_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_5.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_5/Rocky_Asteroid_5_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_6.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_6/Rocky_Asteroid_6_Diffuse_1K.png"
    ),
}
ASTEROID_SCALE_MIN = 0.6
ASTEROID_SCALE_MAX = 2.5
COIN_PATTERN_SWITCH_SECONDS = 40.0
RANDOM_YAW_INTERVAL_SECONDS = 45.0
RANDOM_YAW_INTERVAL_JITTER = 0.35
RANDOM_YAW_MIN_DELTA = 25.0
SCROLL_DIRECTION_BY_KEY = {
    "scroll up": 1,
    "scroll down": -1,
    "gamepad dpad up": 1,
    "gamepad dpad down": -1,
}
RESTART_KEYS = {"r"}
TOGGLE_CONTROLS_KEYS = {"u"}
RECENTER_CAMERA_KEYS = {"c", "gamepad dpad left"}
PAUSE_KEYS = {"p", "gamepad start"}
POST_PROCESS_CYCLE_KEYS = {"t"}
RENDER_MODE_TOGGLE_KEYS = {"y"}
ANIMATION_CULL_DISTANCE = 170.0
OBSTACLE_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 3.0
COIN_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 2.0
COIN_COLLECT_ANIMATION_SECONDS = 0.18
MIN_ENTITY_SCALE = 0.02
BOOST_DIVE_THRESHOLD = 0.05

CAMERA_POST_PROCESS_OPTIONS: tuple[tuple[str, object | None], ...] = (
    ("Off", None),
    ("SSAO", cast("object", ursina_shaders.ssao_shader)),
    (
        "Vertical Blur",
        cast("object", ursina_shaders.camera_vertical_blur_shader),
    ),
)


class GamepadVibrateCallable(Protocol):  # pylint: disable=too-few-public-methods
    # R0903: protocol is single-call hook.
    """Callable protocol for Ursina's optional gamepad vibrate hook."""

    def __call__(self, **_kwargs: float) -> object:
        """Trigger gamepad vibration with motor intensities and duration."""


def get_frame_dt() -> float:
    """Read frame delta from Ursina's dynamic runtime module."""
    # Ursina exposes frame delta via dynamic module attributes.
    # B009: getattr-with-constant; Ursina sets dt.
    frame_dt = getattr(
        ursina.time,
        "dt",
        0.0,
    )
    return cast("float", frame_dt)


@lru_cache(maxsize=2048)
def deterministic_probability_hit(*, seed: int, probability: float) -> bool:
    """Return deterministic pseudo-random chance hit from integer seed."""
    clamped_probability = max(0.0, min(1.0, probability))
    if clamped_probability <= 0.0:
        return False
    if clamped_probability >= 1.0:
        return True

    hashed_seed = (seed * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    return (hashed_seed / 0x80000000) < clamped_probability


@lru_cache(maxsize=2048)
def discrete_value_in_range(
    *,
    seed: int,
    variant_count: int,
    minimum: float,
    maximum: float,
) -> float:
    """Map an integer seed to one of N evenly spaced values in a range."""
    if variant_count <= 1:
        return minimum

    clamped_variant_count = max(2, variant_count)
    variant_index = seed % clamped_variant_count
    interpolation = variant_index / (clamped_variant_count - 1)
    return minimum + ((maximum - minimum) * interpolation)


@lru_cache(maxsize=2048)
def signed_speed_from_seed(
    *,
    seed: int,
    variant_count: int,
    minimum_magnitude: float,
    maximum_magnitude: float,
) -> float:
    """Generate deterministic signed speed with bidirectional variance."""
    magnitude = discrete_value_in_range(
        seed=seed,
        variant_count=variant_count,
        minimum=minimum_magnitude,
        maximum=maximum_magnitude,
    )
    direction = -1.0 if seed % 2 == 0 else 1.0
    return magnitude * direction


@lru_cache(maxsize=256)
def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid model and diffuse texture by seed."""
    variant_index = variation_seed % len(ASTEROID_MODEL_VARIANTS)
    model_name = ASTEROID_MODEL_VARIANTS[variant_index]
    return model_name, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name]


def configure_window(settings: GameSettings) -> None:
    """Apply top-level window settings."""
    window.title = settings.window_title
    window.borderless = settings.borderless
    window.fullscreen = settings.fullscreen
    window.entity_counter.enabled = False
    window.collider_counter.enabled = False


# PLR0913: too-many-arguments; explicit parts.


def update_player_visual_state(
    *,
    player_visual_state: PlayerVisualState,
    motion_state: MotionState,
    fall_speed: float,
) -> None:
    """Animate player aura and contrails based on speed and steering."""
    runtime_time = monotonic()
    speed_factor = max(0.0, min(1.0, (fall_speed - 10.0) / 32.0))
    lateral_factor = max(
        0.0,
        min(
            1.0,
            (abs(motion_state.horizontal_speed) + abs(motion_state.depth_speed)) / 26.0,
        ),
    )

    aura_scale = lerp_scalar(1.65, 2.25, speed_factor)
    player_visual_state.aura.scale = Vec3(aura_scale, aura_scale * 1.08, aura_scale)
    player_visual_state.aura.color = rgba_color(
        lerp_scalar(0.26, 0.62, speed_factor),
        lerp_scalar(0.65, 0.86, speed_factor),
        1.0,
        lerp_scalar(0.12, 0.24, speed_factor),
    )

    trail_width = lerp_scalar(0.08, 0.14, speed_factor)
    trail_length = lerp_scalar(1.9, 3.8, speed_factor)
    for trail_index, contrail in enumerate(player_visual_state.contrails):
        sway_sign = -1.0 if trail_index == 0 else 1.0
        sway = sin((runtime_time * 7.4) + (trail_index * 1.7)) * 0.08
        contrail.position = Vec3(
            sway_sign * (0.2 + (lateral_factor * 0.06)),
            -1.5 - (speed_factor * 0.16),
            -0.62 + sway,
        )
        contrail.scale = Vec3(trail_width, trail_length, trail_width)
        contrail.color = rgba_color(
            lerp_scalar(0.38, 0.8, speed_factor),
            lerp_scalar(0.74, 0.95, speed_factor),
            1.0,
            lerp_scalar(0.2, 0.52, speed_factor),
        )


# C901: too-complex; PLR0915: too-many-statements.
def spawn_entity_from_blueprint(  # noqa: C901, PLR0915
    # pylint: disable=too-many-locals,too-many-statements
    *,
    blueprint: FallingBlueprint,
    band_index: int,
    blueprint_index: int,
    gameplay_settings: GameplayTuningSettings,
) -> SpawnedObject:
    # R0914/R0915: setup is data-heavy.
    """Spawn one band blueprint as an Ursina entity and runtime record."""
    variation_seed = (band_index * 41) + (blueprint_index * 17)
    spawn_model = blueprint.model
    spawn_texture: str | None = None
    if blueprint.entity_kind == "obstacle" and blueprint.model == ASTEROID_MODEL_NAME:
        spawn_model, spawn_texture = choose_asteroid_variant(variation_seed)

    entity_name = (
        f"fall_band_{band_index}_"
        f"{blueprint.entity_kind}_"
        f"{blueprint.name}_"
        f"{blueprint_index}"
    )
    entity = Entity(
        name=entity_name,
        model=spawn_model,
        color=resolve_color(blueprint.color_name),
        scale=Vec3(blueprint.scale.x, blueprint.scale.y, blueprint.scale.z),
        position=Vec3(
            blueprint.position.x,
            blueprint.position.y,
            blueprint.position.z,
        ),
    )
    if spawn_texture is not None:
        entity.texture = spawn_texture

    base_scale = Vec3(entity.scale.x, entity.scale.y, entity.scale.z)

    spin_speed_x = 0.0
    spin_speed_y = 0.0
    spin_speed_z = 0.0
    bob_amplitude = 0.0
    bob_frequency = 0.0
    pulse_amplitude = 0.0
    pulse_frequency = 0.0
    drift_speed_x = 0.0
    drift_speed_z = 0.0
    fade_duration = gameplay_settings.spawn_fade_duration_seconds

    target_color = resolve_color(blueprint.color_name)

    if blueprint.entity_kind == "coin":
        mark_lit_shadowed(entity)
        entity.unlit = False
        entity.texture = None
        target_color = rgba_color(1.0, 0.92, 0.22, 1.0)
        is_high_value_coin = blueprint.score_value > COIN_SCORE_VALUE
        should_render_coin_halo = deterministic_probability_hit(
            seed=variation_seed + 13,
            probability=gameplay_settings.high_value_coin_halo_chance,
        )
        if is_high_value_coin:
            target_color = rgba_color(1.0, 0.84, 0.18, 1.0)
            if should_render_coin_halo:
                Entity(
                    parent=entity,
                    name=f"{entity_name}_coin_halo",
                    model=spawn_model,
                    scale=Vec3(1.18, 1.18, 1.18),
                    color=rgba_color(1.0, 0.92, 0.3, 0.18),
                    unlit=True,
                )
        spin_speed_x = 0.0
        spin_speed_y = (88.0 + ((blueprint_index % 4) * 16.0)) * 0.3
        spin_speed_z = 0.0
        entity.rotation_x = -6.0 + ((blueprint_index % 5) * 3.0)
        entity.rotation_y = ((band_index * 26.0) + (blueprint_index * 32.0)) % 360.0
        entity.rotation_z = -4.0 + ((blueprint_index % 4) * 2.5)
        bob_amplitude = 0.08 + ((variation_seed % 4) * 0.03)
        bob_frequency = 2.5 + ((variation_seed % 5) * 0.36)
        pulse_amplitude = 0.08 + ((variation_seed % 3) * 0.03)
        pulse_frequency = 4.2 + ((variation_seed % 4) * 0.48)
    else:
        mark_lit_shadowed(entity)
        if blueprint.entity_kind == "obstacle":
            should_spin = deterministic_probability_hit(
                seed=variation_seed + 3,
                probability=0.7,
            )
            if blueprint.model == ASTEROID_MODEL_NAME:
                target_color = resolve_color("white")
                entity.unlit = True
                entity.rotation_x = (variation_seed * 37) % 360
                entity.rotation_y = (variation_seed * 53) % 360
                entity.rotation_z = (variation_seed * 29) % 360
                scale_multiplier = discrete_value_in_range(
                    seed=variation_seed + 53,
                    variant_count=11,
                    minimum=ASTEROID_SCALE_MIN,
                    maximum=ASTEROID_SCALE_MAX,
                )
                entity.scale = Vec3(
                    entity.scale.x * scale_multiplier,
                    entity.scale.y * scale_multiplier,
                    entity.scale.z * scale_multiplier,
                )
                base_scale = Vec3(entity.scale.x, entity.scale.y, entity.scale.z)
                if should_spin:
                    should_drift = deterministic_probability_hit(
                        seed=variation_seed + 71,
                        probability=0.3,
                    )
                    if should_drift:
                        drift_speed_x = signed_speed_from_seed(
                            seed=variation_seed + 73,
                            variant_count=13,
                            minimum_magnitude=0.8,
                            maximum_magnitude=2.2,
                        )
                        drift_speed_z = signed_speed_from_seed(
                            seed=variation_seed + 79,
                            variant_count=9,
                            minimum_magnitude=0.2,
                            maximum_magnitude=0.9,
                        )
            if should_spin:
                spin_speed_x = signed_speed_from_seed(
                    seed=variation_seed + 5,
                    variant_count=gameplay_settings.obstacle_spin_variants + 6,
                    minimum_magnitude=gameplay_settings.obstacle_spin_speed_min,
                    maximum_magnitude=gameplay_settings.obstacle_spin_speed_max,
                )
                spin_speed_y = signed_speed_from_seed(
                    seed=variation_seed + 11,
                    variant_count=gameplay_settings.obstacle_spin_variants + 10,
                    minimum_magnitude=gameplay_settings.obstacle_spin_speed_min,
                    maximum_magnitude=gameplay_settings.obstacle_spin_speed_max,
                )
                spin_speed_z = signed_speed_from_seed(
                    seed=variation_seed + 19,
                    variant_count=gameplay_settings.obstacle_rock_variants + 10,
                    minimum_magnitude=abs(gameplay_settings.obstacle_rock_speed_min),
                    maximum_magnitude=abs(gameplay_settings.obstacle_rock_speed_max),
                )
        else:
            spin_speed_x = 0.0
            spin_speed_y = 6.0 + ((variation_seed % 5) * 2.5)
            spin_speed_z = 0.0

    target_rgba = (
        cast("float", target_color.r),
        cast("float", target_color.g),
        cast("float", target_color.b),
        cast("float", target_color.a),
    )
    entity.color = rgba_color(target_rgba[0], target_rgba[1], target_rgba[2], 0.0)

    return SpawnedObject(
        entity=entity,
        entity_kind=blueprint.entity_kind,
        model_name=spawn_model,
        collision_radius=blueprint.collision_radius,
        score_value=blueprint.score_value,
        spin_speed_x=spin_speed_x,
        spin_speed_y=spin_speed_y,
        spin_speed_z=spin_speed_z,
        bob_amplitude=bob_amplitude,
        bob_frequency=bob_frequency,
        pulse_amplitude=pulse_amplitude,
        pulse_frequency=pulse_frequency,
        base_x=entity.x,
        base_y=entity.y,
        base_z=entity.z,
        drift_speed_x=drift_speed_x,
        drift_speed_z=drift_speed_z,
        drift_progress=0.0,
        base_scale=base_scale,
        spawn_time=monotonic(),
        fade_duration=fade_duration,
        target_rgba=target_rgba,
    )


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


def initialize_run_state(
    run_state: FallingRunState,
    fall_settings: FallSettings,
) -> None:
    """Reset run-state values to initial defaults."""
    run_state.score = 0
    run_state.collected_orbs = 0
    run_state.reset_count = 0
    run_state.is_paused = False
    run_state.deepest_y = 0.0
    run_state.next_band_index = 0
    run_state.next_band_y = fall_settings.initial_spawn_y
    run_state.last_hit_time = 0.0
    run_state.coin_pattern_index = 0
    run_state.coin_pattern_started_at = monotonic()


def update_coin_pattern_timer(run_state: FallingRunState) -> None:
    """Advance the active coin pattern on a fixed interval."""
    now = monotonic()
    if now - run_state.coin_pattern_started_at < COIN_PATTERN_SWITCH_SECONDS:
        return
    run_state.coin_pattern_started_at = now
    run_state.coin_pattern_index = (
        run_state.coin_pattern_index + 1
    ) % COIN_PATTERN_COUNT


def start_next_music_track(
    *,
    current_track: Audio | None,
    playlist: list[Path],
) -> tuple[Audio | None, Path | None]:
    """Start the next music track when none is playing."""
    if current_track is not None and current_track.playing:
        return current_track, None

    if not playlist:
        playlist.extend(build_music_playlist())
        if not playlist:
            return None, None

    next_path = playlist.pop(0)
    return start_music_track(next_path), next_path


def resume_music_after_pause(
    *,
    music_playlist: list[Path],
    track_path: Path | None,
) -> tuple[Audio | None, Path | None]:
    """Resume music playback by restarting a track."""
    if track_path is not None:
        return start_music_track(track_path), track_path

    return start_next_music_track(current_track=None, playlist=music_playlist)


def schedule_random_yaw(run_state: FallingRunState) -> None:
    """Schedule the next randomized camera yaw change."""
    # S311: non-crypto RNG; B311: gameplay randomness.
    random_jitter = Random().random()  # noqa: S311  # nosec B311
    jitter = (random_jitter - 0.5) * 2.0 * RANDOM_YAW_INTERVAL_JITTER
    interval = max(10.0, RANDOM_YAW_INTERVAL_SECONDS * (1.0 + jitter))
    run_state.random_yaw_next_at = monotonic() + interval


def maybe_update_random_yaw(
    run_state: FallingRunState,
    *,
    camera_state: CameraState,
    yaw_turn_axis: float,
    settings: GameSettings,
) -> float:
    """Return yaw axis override when random yaw should steer the camera."""
    now = monotonic()
    if run_state.random_yaw_next_at <= 0.0:
        schedule_random_yaw(run_state)
        return yaw_turn_axis

    if run_state.random_yaw_target is None and now >= run_state.random_yaw_next_at:
        max_angle = settings.movement.yaw_turn_speed * 0.9
        delta_range = max(
            RANDOM_YAW_MIN_DELTA,
            min(160.0, max_angle),
        )
        # S311: non-crypto RNG; B311: gameplay randomness.
        delta = Random().uniform(  # noqa: S311  # nosec B311
            delta_range,
            min(175.0, delta_range * 1.6),
        )
        if Random().random() < 0.5:  # noqa: S311, PLR2004  # nosec B311
            delta *= -1.0
        run_state.random_yaw_target = camera_state.yaw_angle + delta
        schedule_random_yaw(run_state)

    if run_state.random_yaw_target is None:
        return yaw_turn_axis

    if abs(yaw_turn_axis) > 0.02:  # noqa: PLR2004
        run_state.random_yaw_target = None
        return yaw_turn_axis

    random_yaw_target = run_state.random_yaw_target
    if random_yaw_target is None:
        return yaw_turn_axis
    yaw_delta: float = random_yaw_target - camera_state.yaw_angle
    if abs(yaw_delta) <= 1.0:
        run_state.random_yaw_target = None
        return yaw_turn_axis

    yaw_divisor = float(max(1.0, settings.movement.yaw_turn_speed))
    return max(-1.0, min(1.0, yaw_delta / yaw_divisor))


def destroy_entity_tree(entity: Entity) -> None:
    """Destroy an entity and any child entities to avoid scene leaks."""
    for child in list(entity.children):
        destroy_entity_tree(cast("Entity", child))
    destroy(entity)


def destroy_spawned_objects(spawned_objects: list[SpawnedObject]) -> None:
    """Destroy spawned entities and clear the container in-place."""
    for spawned in spawned_objects:
        destroy_entity_tree(spawned.entity)
    spawned_objects.clear()


def spawn_bands_ahead(
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Spawn new obstacle/coin bands until the ahead window is filled."""
    while should_spawn_next_band(
        next_band_y=run_state.next_band_y,
        player_y=player_y,
        spawn_ahead_distance=fall_settings.spawn_ahead_distance,
    ):
        blueprints = build_fall_band_blueprints(
            band_index=run_state.next_band_index,
            y_position=run_state.next_band_y,
            rng=rng,
            coin_pattern_index=run_state.coin_pattern_index,
        )
        for blueprint_index, blueprint in enumerate(blueprints):
            run_state.spawned_objects.append(
                spawn_entity_from_blueprint(
                    blueprint=blueprint,
                    band_index=run_state.next_band_index,
                    blueprint_index=blueprint_index,
                    gameplay_settings=gameplay_settings,
                ),
            )

        run_state.next_band_index += 1
        run_state.next_band_y -= BAND_SPACING


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
            run_state.collected_orbs += 1
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

        destroy_entity_tree(spawned.entity)

    run_state.spawned_objects = survivors


# C901: too-complex; PLR0912: too-many-branches; PLR0915: too-many-statements.
def animate_spawned_objects(  # noqa: C901, PLR0912, PLR0915
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    run_state: FallingRunState,
    dt: float,
    player_y: float,
    player_position: Vec3,
) -> None:
    # R0912/R0914/R0915: frame loop.
    """Animate collectibles and obstacles for richer motion language."""
    runtime_time = monotonic()
    survivors: list[SpawnedObject] = []
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

        if spawned.entity_kind == "coin":
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


# PLR0913: too-many-arguments; explicit inputs.
def apply_player_movement(  # noqa: PLR0913
    # pylint: disable=too-many-arguments,too-many-locals
    *,
    player: Entity,
    motion_state: MotionState,
    movement_settings: MovementSettings,
    fall_settings: FallSettings,
    camera_yaw_degrees: float,
    x_axis: float,
    z_axis: float,
    dive_axis: float,
    dt: float,
) -> float:
    # R0913/R0914: explicit motion inputs.
    """Move the player avatar and return effective vertical fall speed."""
    fall_speed: float = compute_fall_speed(
        base_speed=fall_settings.base_speed,
        dive_axis=dive_axis,
        boost_multiplier=fall_settings.boost_multiplier,
        brake_multiplier=fall_settings.brake_multiplier,
    )

    motion_state.horizontal_speed = compute_smoothed_lateral_speed(
        current_speed=motion_state.horizontal_speed,
        axis_input=x_axis,
        max_speed=movement_settings.horizontal_speed,
        acceleration_rate=movement_settings.horizontal_accel_rate,
        deceleration_rate=movement_settings.horizontal_decel_rate,
        dt=dt,
    )
    motion_state.depth_speed = compute_smoothed_lateral_speed(
        current_speed=motion_state.depth_speed,
        axis_input=z_axis,
        max_speed=movement_settings.depth_speed,
        acceleration_rate=movement_settings.depth_accel_rate,
        deceleration_rate=movement_settings.depth_decel_rate,
        dt=dt,
    )

    world_x_speed, world_z_speed = rotate_planar_velocity_by_yaw(
        right_speed=motion_state.horizontal_speed,
        forward_speed=motion_state.depth_speed,
        yaw_degrees=camera_yaw_degrees,
    )

    player.y -= fall_speed * dt
    player.x += world_x_speed * dt
    player.z += world_z_speed * dt
    player.x, player.z = clamp_to_play_area(
        player.x,
        player.z,
        movement_settings.play_area_radius,
    )

    normalized_horizontal = 0.0
    if movement_settings.horizontal_speed > 0.0:
        normalized_horizontal = (
            motion_state.horizontal_speed / movement_settings.horizontal_speed
        )

    normalized_depth = 0.0
    if movement_settings.depth_speed > 0.0:
        normalized_depth = motion_state.depth_speed / movement_settings.depth_speed

    target_roll = normalized_horizontal * movement_settings.tilt_degrees
    target_pitch = normalized_depth * movement_settings.tilt_degrees * 0.7
    player.rotation_z = cast(
        "float",
        lerp_exponential_decay(player.rotation_z, target_roll, dt * 9.0),
    )
    player.rotation_x = cast(
        "float",
        lerp_exponential_decay(player.rotation_x, target_pitch, dt * 9.0),
    )
    return fall_speed


# C901: too-complex; PLR0913: too-many-arguments; PLR0915: too-many-statements.
def install_game_controller(  # noqa: C901, PLR0913, PLR0915
    # pylint: disable=too-many-arguments,too-many-locals,too-many-statements
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    settings: GameSettings,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
    player_visual_state: PlayerVisualState,
    controls_hint: Text,
    status_text: Text,
    pause_text: Text,
) -> Entity:
    # R0913/R0914/R0915: controller glue.
    """Attach per-frame gameplay update and input handlers."""
    music_state: dict[str, Audio | None] = {"track": None}
    music_track_path: Path | None = None
    boost_state: dict[str, Audio | None] = {"track": None}
    controller = Entity(name="fall_game_controller")
    # S311: non-crypto RNG; B311: gameplay seed.
    randomizer = Random(RUN_RANDOM_SEED)  # noqa: S311  # nosec B311
    camera_state = CameraState(
        yaw_angle=0.0,
        pitch_angle=settings.camera.start_pitch,
        distance=settings.camera.distance,
    )
    motion_state = MotionState()
    run_state = FallingRunState()
    initialize_run_state(run_state, settings.fall)
    post_process_index = 0
    apply_camera_post_process(CAMERA_POST_PROCESS_OPTIONS[post_process_index][1])
    music_playlist = build_music_playlist()
    boost_clip_name = resolve_boost_loop_clip()

    def reset_run() -> None:
        nonlocal music_track_path
        destroy_spawned_objects(run_state.spawned_objects)
        initialize_run_state(run_state, settings.fall)
        randomizer.seed(RUN_RANDOM_SEED)
        player.position = Vec3(0.0, 0.0, 0.0)
        player.rotation = Vec3(0.0, 0.0, 0.0)
        motion_state.horizontal_speed = 0.0
        motion_state.depth_speed = 0.0
        motion_state.yaw_turn_speed = 0.0
        camera_state.yaw_angle = 0.0
        camera_state.pitch_angle = settings.camera.start_pitch
        camera_state.distance = settings.camera.distance
        apply_camera_post_process(CAMERA_POST_PROCESS_OPTIONS[post_process_index][1])
        pause_text.enabled = False
        run_state.random_yaw_target = None
        schedule_random_yaw(run_state)
        music_track_path = None
        if music_state["track"] is not None:
            music_state["track"].play()
        if boost_state["track"] is not None:
            boost_state["track"].stop()
        spawn_bands_ahead(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
            fall_speed=settings.fall.base_speed,
        )
        update_player_visual_state(
            player_visual_state=player_visual_state,
            motion_state=motion_state,
            fall_speed=settings.fall.base_speed,
        )
        update_status_text(run_state, status_text)

    reset_run()

    # C901: too-complex; per-frame flow.
    def controller_update() -> None:  # noqa: C901, PLR0915
        nonlocal music_track_path
        held = cast("dict[str, float]", getattr(ursina, "held_keys", {}))
        mouse_velocity = cast("Vec3", getattr(mouse, "velocity", Vec3(0.0, 0.0, 0.0)))
        x_axis, z_axis, dive_axis, yaw_turn_axis, look_velocity = compute_control_axes(
            held,
            mouse_velocity,
        )
        yaw_turn_axis = maybe_update_random_yaw(
            run_state,
            camera_state=camera_state,
            yaw_turn_axis=yaw_turn_axis,
            settings=settings,
        )

        if not run_state.is_paused:
            music_state["track"], music_track_path = start_next_music_track(
                current_track=music_state["track"],
                playlist=music_playlist,
            )

        dt = get_frame_dt()
        if dt <= 0.0:
            update_camera_tracking(
                player=player,
                orbit_rig=orbit_rig,
                camera_state=camera_state,
                camera_settings=settings.camera,
                look_velocity=look_velocity,
            )
            player.rotation_y = camera_state.yaw_angle
            return

        if run_state.is_paused:
            if music_state["track"] is not None and music_state["track"].playing:
                music_state["track"].pause()
            if boost_state["track"] is not None and boost_state["track"].playing:
                boost_state["track"].pause()
            motion_state.yaw_turn_speed = compute_smoothed_lateral_speed(
                current_speed=motion_state.yaw_turn_speed,
                axis_input=0.0,
                max_speed=settings.movement.yaw_turn_speed,
                acceleration_rate=settings.movement.yaw_turn_accel_rate,
                deceleration_rate=settings.movement.yaw_turn_decel_rate,
                dt=dt,
            )
            camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
                yaw_angle=camera_state.yaw_angle,
                pitch_angle=camera_state.pitch_angle,
                look_velocity=look_velocity,
                mouse_look_speed=settings.camera.mouse_look_speed,
                min_pitch=settings.camera.min_pitch,
                max_pitch=settings.camera.max_pitch,
            )
            player.rotation_y = camera_state.yaw_angle
            update_camera_tracking(
                player=player,
                orbit_rig=orbit_rig,
                camera_state=camera_state,
                camera_settings=settings.camera,
                look_velocity=Vec3(0.0, 0.0, 0.0),
            )
            update_status_text(run_state, status_text)
            return

        camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
            yaw_angle=camera_state.yaw_angle,
            pitch_angle=camera_state.pitch_angle,
            look_velocity=look_velocity,
            mouse_look_speed=settings.camera.mouse_look_speed,
            min_pitch=settings.camera.min_pitch,
            max_pitch=settings.camera.max_pitch,
        )

        motion_state.yaw_turn_speed = compute_smoothed_lateral_speed(
            current_speed=motion_state.yaw_turn_speed,
            axis_input=yaw_turn_axis,
            max_speed=settings.movement.yaw_turn_speed,
            acceleration_rate=settings.movement.yaw_turn_accel_rate,
            deceleration_rate=settings.movement.yaw_turn_decel_rate,
            dt=dt,
        )
        camera_state.yaw_angle += motion_state.yaw_turn_speed * dt
        player.rotation_y = camera_state.yaw_angle

        fall_speed = apply_player_movement(
            player=player,
            motion_state=motion_state,
            movement_settings=settings.movement,
            fall_settings=settings.fall,
            camera_yaw_degrees=camera_state.yaw_angle,
            x_axis=x_axis,
            z_axis=z_axis,
            dive_axis=dive_axis,
            dt=dt,
        )
        run_state.deepest_y = min(run_state.deepest_y, player.y)

        update_coin_pattern_timer(run_state)

        if boost_clip_name is not None and dive_axis > BOOST_DIVE_THRESHOLD:
            if boost_state["track"] is None or not boost_state["track"].playing:
                audio_factory: Any = Audio
                boost_state["track"] = audio_factory(
                    boost_clip_name,
                    loop=True,
                    autoplay=True,
                    volume=BOOST_LOOP_VOLUME,
                )
            else:
                boost_track = cast("Any", boost_state["track"])
                boost_track.volume = BOOST_LOOP_VOLUME
        elif boost_state["track"] is not None and boost_state["track"].playing:
            fade_speed = BOOST_LOOP_VOLUME / max(0.01, BOOST_LOOP_FADE_SECONDS)
            boost_track = cast("Any", boost_state["track"])
            boost_track.volume = max(
                0.0,
                boost_track.volume - (fade_speed * dt),
            )
            if boost_track.volume <= 0.0:
                boost_track.pause()

        spawn_bands_ahead(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        if music_state["track"] is None and music_playlist:
            music_state["track"] = start_music_track(music_playlist.pop(0))
        animate_spawned_objects(run_state, dt, player.y, player.position)
        process_collisions(
            player=player,
            motion_state=motion_state,
            run_state=run_state,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        cleanup_passed_objects(
            run_state=run_state,
            player_y=player.y,
            cleanup_above_distance=settings.fall.cleanup_above_distance,
        )

        update_camera_tracking(
            player=player,
            orbit_rig=orbit_rig,
            camera_state=camera_state,
            camera_settings=settings.camera,
            look_velocity=Vec3(0.0, 0.0, 0.0),
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
            fall_speed=fall_speed,
        )
        update_player_visual_state(
            player_visual_state=player_visual_state,
            motion_state=motion_state,
            fall_speed=fall_speed,
        )
        update_status_text(run_state, status_text)

    # C901: too-complex; input branching.
    def controller_input(key: str) -> None:  # noqa: C901
        # C901: complex; input branching.
        nonlocal post_process_index, music_track_path

        if key == "escape":
            application.quit()
            return

        if key in TOGGLE_CONTROLS_KEYS:
            controls_hint.enabled = not controls_hint.enabled

        if key in POST_PROCESS_CYCLE_KEYS:
            post_process_index, _, post_shader = next_post_process_option(
                current_index=post_process_index,
                options=CAMERA_POST_PROCESS_OPTIONS,
            )
            apply_camera_post_process(post_shader)
            update_status_text(run_state, status_text)
            return

        if key in RENDER_MODE_TOGGLE_KEYS:
            current_mode = cast("str", getattr(window, "render_mode", "default"))
            next_mode = toggle_render_mode(current_mode)
            window.render_mode = next_mode
            update_status_text(run_state, status_text)
            return

        if key in PAUSE_KEYS:
            run_state.is_paused = not run_state.is_paused
            pause_text.enabled = run_state.is_paused
            if run_state.is_paused:
                if music_state["track"] is not None:
                    music_state["track"].pause()
            else:
                music_state["track"], music_track_path = resume_music_after_pause(
                    music_playlist=music_playlist,
                    track_path=music_track_path,
                )
            return

        if key in RESTART_KEYS:
            reset_run()
            return

        if key in RECENTER_CAMERA_KEYS:
            camera_state.yaw_angle = 0.0
            camera_state.pitch_angle = settings.camera.start_pitch

        scroll_direction = SCROLL_DIRECTION_BY_KEY.get(key)
        if scroll_direction is None:
            return

        camera_state.distance = compute_zoom_distance(
            current_distance=camera_state.distance,
            scroll_direction=scroll_direction,
            min_distance=settings.camera.min_distance,
            max_distance=settings.camera.max_distance,
            zoom_step=settings.camera.zoom_step,
        )

    controller.update = controller_update
    controller.input = controller_input
    return controller


def run_game(settings: GameSettings | None = None) -> None:
    """Run the endless third-person falling game."""
    active_settings = GameSettings() if settings is None else settings
    app = cast(
        "object",
        Ursina(
            title=active_settings.window_title,
            development_mode=active_settings.development_mode,
            size=(
                Vec2(
                    active_settings.window_size[0],
                    active_settings.window_size[1],
                )
                if active_settings.window_size is not None
                else None
            ),
        ),
    )
    application.asset_folder = Path(__file__).resolve().parents[2]

    configure_window(active_settings)

    player = spawn_player_avatar()
    player_visual_state = create_player_visual_state(player)
    configure_camera()
    orbit_rig = create_camera_orbit_rig(active_settings)
    configure_mouse_capture()
    controls_hint = create_controls_hint()
    status_text = create_status_text()
    pause_text = create_pause_text()
    lighting_rig = configure_lighting(player)
    backdrop_state = create_space_backdrop()
    install_game_controller(
        player=player,
        orbit_rig=orbit_rig,
        settings=active_settings,
        lighting_rig=lighting_rig,
        backdrop_state=backdrop_state,
        player_visual_state=player_visual_state,
        controls_hint=controls_hint,
        status_text=status_text,
        pause_text=pause_text,
    )

    # Ursina's app proxy is typed as object here, so dynamic access is needed.
    app_proxy = cast("Any", app)
    app_proxy.run()
