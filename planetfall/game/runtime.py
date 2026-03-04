"""Ursina runtime for an endless third-person falling game.

Coordinates the main loop and re-exports runtime helpers used by tests.
"""

# pylint: disable=too-many-lines
# C0302: large runtime keeps loop cohesive.

from dataclasses import replace
from math import atan2, degrees, sin
from pathlib import Path
from random import Random, SystemRandom
from time import monotonic
from typing import Any, cast

import ursina
import ursina.shaders as ursina_shaders
from ursina import (
    Audio,
    Entity,
    Text,
    Vec2,
    Vec3,
    application,
    lerp_exponential_decay,
    mouse,
    window,
)
from ursina.main import Ursina

from planetfall.game.config import (
    FallSettings,
    GameSettings,
    MovementSettings,
)
from planetfall.game.runtime_animation import animate_spawned_objects
from planetfall.game.runtime_audio import (
    BOOST_LOOP_FADE_SECONDS,
    BOOST_LOOP_VOLUME,
    build_music_playlist,
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
from planetfall.game.runtime_collisions import (
    apply_obstacle_recovery,
    cleanup_passed_objects,
    destroy_spawned_objects,
    process_collisions,
)
from planetfall.game.runtime_colors import rgba_color
from planetfall.game.runtime_controls import (
    clamp_to_play_area,
    compute_control_axes,
    compute_fall_speed,
    compute_look_angles,
    compute_smoothed_lateral_speed,
    compute_zoom_distance,
    lerp_scalar,
    rotate_planar_velocity_by_yaw,
)
from planetfall.game.runtime_entities import (
    configure_lighting,
    create_player_visual_state,
    spawn_player_avatar,
)
from planetfall.game.runtime_fx import create_hit_flash
from planetfall.game.runtime_perf import PerfTracker
from planetfall.game.runtime_postfx import next_post_process_option, toggle_render_mode
from planetfall.game.runtime_random import deterministic_probability_hit
from planetfall.game.runtime_spawn import (
    spawn_bands_ahead,
    spawn_entity_from_blueprint,
    update_powerup_spawning,
)
from planetfall.game.runtime_spawn_obstacles import (
    ASTEROID_DIFFUSE_TEXTURE_BY_MODEL,
    ASTEROID_MODEL_NAME,
    ASTEROID_MODEL_VARIANTS,
    choose_asteroid_variant,
)
from planetfall.game.runtime_spawn_powerups import (
    POWERUP_MAGNET_KIND,
    POWERUP_MODEL_NAME,
)
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
from planetfall.game.scene import BAND_SPACING, COIN_PATTERN_COUNT

__all__ = [
    "ASTEROID_DIFFUSE_TEXTURE_BY_MODEL",
    "ASTEROID_MODEL_NAME",
    "ASTEROID_MODEL_VARIANTS",
    "POWERUP_MAGNET_KIND",
    "POWERUP_MODEL_NAME",
    "SpawnedObject",
    "animate_spawned_objects",
    "apply_obstacle_recovery",
    "choose_asteroid_variant",
    "deterministic_probability_hit",
    "process_collisions",
    "spawn_entity_from_blueprint",
]

COIN_PATTERN_SWITCH_METERS = 3600.0
RANDOM_YAW_INTERVAL_SECONDS = 45.0
RANDOM_YAW_INTERVAL_JITTER = 0.35
RANDOM_YAW_MIN_DELTA = 25.0
AUTO_YAW_INPUT_EPSILON = 0.02
SCROLL_DIRECTION_BY_KEY = {
    "scroll up": 1,
    "scroll down": -1,
    "gamepad dpad up": 1,
    "gamepad dpad down": -1,
}
RESTART_KEYS = {"r"}
TOGGLE_CONTROLS_KEYS = {"u"}
RECENTER_CAMERA_KEYS = {"c", "gamepad dpad left"}
TOGGLE_AUTO_YAW_KEYS = {"v", "gamepad dpad right"}
PAUSE_KEYS = {"p", "gamepad start"}
POST_PROCESS_CYCLE_KEYS = {"t"}
RENDER_MODE_TOGGLE_KEYS = {"y"}
BOOST_DIVE_THRESHOLD = 0.05

CAMERA_POST_PROCESS_OPTIONS: tuple[tuple[str, object | None], ...] = (
    ("Off", None),
    ("SSAO", cast("object", ursina_shaders.ssao_shader)),
    (
        "Vertical Blur",
        cast("object", ursina_shaders.camera_vertical_blur_shader),
    ),
)


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
    shield_active: bool,
) -> None:
    """Animate player visuals based on speed and steering."""
    runtime_time = monotonic()
    speed_factor = max(0.0, min(1.0, (fall_speed - 10.0) / 32.0))
    lateral_factor = max(
        0.0,
        min(
            1.0,
            (abs(motion_state.horizontal_speed) + abs(motion_state.depth_speed)) / 26.0,
        ),
    )

    player_visual_state.shield_bubble.enabled = shield_active
    if shield_active:
        player_visual_state.shield_bubble.scale = Vec3(3.5, 3.5, 3.5)
        player_visual_state.shield_bubble.color = rgba_color(
            0.15,
            0.88,
            1.0,
            0.2,
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


def initialize_run_state(
    run_state: FallingRunState,
    fall_settings: FallSettings,
) -> None:
    """Reset run-state values to initial defaults."""
    run_state.score = 0
    run_state.collected_coins = 0
    run_state.reset_count = 0
    run_state.is_paused = False
    run_state.deepest_y = 0.0
    run_state.next_band_index = 0
    run_state.next_band_y = fall_settings.initial_spawn_y
    run_state.last_hit_time = 0.0
    run_state.coin_pattern_index = 0
    run_state.coin_pattern_start_y = fall_settings.initial_spawn_y
    run_state.auto_yaw_enabled = False
    run_state.magnet_expires_at = 0.0
    run_state.shield_expires_at = 0.0
    run_state.coin_multiplier_expires_at = 0.0
    run_state.coin_multiplier_factor = 1.0


def update_coin_pattern_timer(
    run_state: FallingRunState,
    *,
    player_y: float,
) -> None:
    """Advance the active coin pattern based on distance fallen."""
    if (run_state.coin_pattern_start_y - player_y) < COIN_PATTERN_SWITCH_METERS:
        return
    run_state.coin_pattern_start_y = player_y
    run_state.coin_pattern_index = (
        run_state.coin_pattern_index + 1
    ) % COIN_PATTERN_COUNT


def resolve_camera_band_progress(
    *,
    player_y: float,
    fall_settings: FallSettings,
    y_offset: float,
) -> float:
    """Return fractional band index for smooth camera alignment."""
    band_offset: float = (
        fall_settings.initial_spawn_y - (player_y + y_offset)
    ) / BAND_SPACING
    return band_offset


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


YAW_DELTA_LIMIT = 180.0
YAW_ALIGNMENT_EPSILON = 0.01


def _normalize_yaw_delta(delta: float) -> float:
    """Normalize yaw delta into the [-180, 180] range."""
    while delta > YAW_DELTA_LIMIT:
        delta -= YAW_DELTA_LIMIT * 2.0
    while delta < -YAW_DELTA_LIMIT:
        delta += YAW_DELTA_LIMIT * 2.0
    return delta


def _resolve_coin_road_target(
    *,
    run_state: FallingRunState,
    ahead_min: float,
    ahead_max: float,
) -> Vec3 | None:
    """Return the average coin position in the lookahead band."""
    coin_positions: list[Vec3] = []
    for spawned in run_state.spawned_objects:
        if spawned.entity_kind != "coin":
            continue
        if spawned.entity.y > ahead_max or spawned.entity.y < ahead_min:
            continue
        coin_positions.append(spawned.entity.position)

    if not coin_positions:
        return None

    avg_x = sum(pos.x for pos in coin_positions) / len(coin_positions)
    avg_z = sum(pos.z for pos in coin_positions) / len(coin_positions)
    avg_y = sum(pos.y for pos in coin_positions) / len(coin_positions)
    return Vec3(avg_x, avg_y, avg_z)


def resolve_auto_yaw_axis(
    *,
    run_state: FallingRunState,
    player_position: Vec3,
    fall_settings: FallSettings,
    camera_state: CameraState,
    yaw_turn_speed: float,
) -> float:
    """Return a yaw axis that follows the next coin road."""
    ahead_min = player_position.y - (fall_settings.spawn_ahead_distance * 0.8)
    ahead_max = player_position.y - (fall_settings.spawn_ahead_distance * 0.2)
    average_target = _resolve_coin_road_target(
        run_state=run_state,
        ahead_min=ahead_min,
        ahead_max=ahead_max,
    )
    if average_target is None:
        return 0.0

    delta_x = average_target.x - player_position.x
    delta_z = average_target.z - player_position.z
    if abs(delta_x) <= YAW_ALIGNMENT_EPSILON and abs(delta_z) <= YAW_ALIGNMENT_EPSILON:
        return 0.0

    target_yaw = degrees(atan2(delta_x, delta_z))
    yaw_delta = _normalize_yaw_delta(target_yaw - camera_state.yaw_angle)
    yaw_divisor = float(max(1.0, yaw_turn_speed))
    return max(-1.0, min(1.0, yaw_delta / yaw_divisor))


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
    hit_flash = create_hit_flash()
    run_seed = settings.run_seed
    # S311: non-crypto RNG; B311: gameplay seed.
    randomizer = Random(  # noqa: S311  # nosec B311
        SystemRandom().randint(0, 2**32 - 1) if run_seed is None else run_seed,
    )
    camera_state = CameraState(
        yaw_angle=0.0,
        pitch_angle=settings.camera.start_pitch,
        distance=settings.camera.distance,
    )
    motion_state = MotionState()
    run_state = FallingRunState()
    perf_tracker = PerfTracker(enabled=settings.perf_log_enabled)
    initialize_run_state(run_state, settings.fall)
    post_process_index = 0
    apply_camera_post_process(CAMERA_POST_PROCESS_OPTIONS[post_process_index][1])
    music_playlist = build_music_playlist()
    boost_clip_name = resolve_boost_loop_clip()

    def reset_run() -> None:
        nonlocal music_track_path
        destroy_spawned_objects(run_state.spawned_objects)
        initialize_run_state(run_state, settings.fall)
        if run_seed is not None:
            randomizer.seed(run_seed)
        player.position = Vec3(0.0, 0.0, 0.0)
        player.rotation = Vec3(0.0, 0.0, 0.0)
        motion_state.horizontal_speed = 0.0
        motion_state.depth_speed = 0.0
        motion_state.yaw_turn_speed = 0.0
        camera_state.yaw_angle = 0.0
        camera_state.pitch_angle = settings.camera.start_pitch
        camera_state.distance = settings.camera.distance
        camera_state.yaw_follow_angle = 0.0
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
            shield_active=False,
        )
        update_status_text(run_state, status_text)
        hit_flash.enabled = False
        hit_flash.color = rgba_color(1.0, 1.0, 1.0, 0.0)

    reset_run()

    # C901: too-complex; per-frame flow.
    # PLR0912: too-many-branches; per-frame flow keeps explicit phases.
    # pylint: disable=too-many-branches
    def controller_update() -> None:  # noqa: C901, PLR0912, PLR0915
        nonlocal music_track_path
        held = cast("dict[str, float]", getattr(ursina, "held_keys", {}))
        mouse_velocity = cast("Vec3", getattr(mouse, "velocity", Vec3(0.0, 0.0, 0.0)))
        x_axis, z_axis, dive_axis, yaw_turn_axis, look_velocity = compute_control_axes(
            held,
            mouse_velocity,
        )
        yaw_input_active = abs(yaw_turn_axis) > AUTO_YAW_INPUT_EPSILON
        if run_state.auto_yaw_enabled and not yaw_input_active:
            yaw_turn_axis = resolve_auto_yaw_axis(
                run_state=run_state,
                player_position=player.position,
                fall_settings=settings.fall,
                camera_state=camera_state,
                yaw_turn_speed=settings.movement.yaw_turn_speed,
            )
        else:
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
                band_progress=resolve_camera_band_progress(
                    player_y=player.y,
                    fall_settings=settings.fall,
                    y_offset=settings.camera.yaw_lookahead_depth,
                ),
                yaw_follow_strength=(
                    settings.camera.yaw_follow_strength
                    if run_state.auto_yaw_enabled
                    else 0.0
                ),
                yaw_input_active=yaw_input_active,
                dt=0.0,
            )
            player.rotation_y = camera_state.yaw_angle
            hit_flash.enabled = False
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
                band_progress=resolve_camera_band_progress(
                    player_y=player.y,
                    fall_settings=settings.fall,
                    y_offset=settings.camera.yaw_lookahead_depth,
                ),
                yaw_follow_strength=(
                    settings.camera.yaw_follow_strength
                    if run_state.auto_yaw_enabled
                    else 0.0
                ),
                yaw_input_active=yaw_input_active,
                dt=dt,
            )
            update_status_text(run_state, status_text)
            hit_flash.enabled = False
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

        update_coin_pattern_timer(run_state, player_y=player.y)

        update_powerup_spawning(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
            movement_settings=settings.movement,
            gameplay_settings=settings.gameplay,
            now=monotonic(),
        )

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
        animation_start = monotonic()
        animate_spawned_objects(
            run_state,
            settings.gameplay,
            dt,
            player.y,
            player.position,
            perf_tracker=perf_tracker,
        )
        perf_tracker.record("animate", monotonic() - animation_start)
        perf_tracker.set_gauge("spawned", float(len(run_state.spawned_objects)))
        dt_unscaled = cast("float", getattr(ursina.time, "dt_unscaled", dt))
        if dt_unscaled > 0.0:
            perf_tracker.record_sample("fps", 1.0 / dt_unscaled)
        fps_counter = getattr(window, "fps_counter", None)
        if fps_counter is not None:
            fps_text = cast("str", getattr(fps_counter, "text", ""))
            if fps_text.isdigit():
                perf_tracker.record_sample("fps_ursina", float(fps_text))
        collision_start = monotonic()
        process_collisions(
            player=player,
            motion_state=motion_state,
            run_state=run_state,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
            hit_flash=hit_flash,
            perf_tracker=perf_tracker,
        )
        perf_tracker.record("collisions", monotonic() - collision_start)
        cleanup_passed_objects(
            run_state=run_state,
            player_y=player.y,
            cleanup_above_distance=settings.fall.cleanup_above_distance,
        )
        perf_tracker.maybe_report()

        update_camera_tracking(
            player=player,
            orbit_rig=orbit_rig,
            camera_state=camera_state,
            camera_settings=settings.camera,
            look_velocity=Vec3(0.0, 0.0, 0.0),
            band_progress=resolve_camera_band_progress(
                player_y=player.y,
                fall_settings=settings.fall,
                y_offset=settings.camera.yaw_lookahead_depth,
            ),
            yaw_follow_strength=(
                settings.camera.yaw_follow_strength
                if run_state.auto_yaw_enabled
                else 0.0
            ),
            yaw_input_active=yaw_input_active,
            dt=dt,
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
            shield_active=run_state.shield_expires_at > monotonic(),
        )
        update_status_text(run_state, status_text)
        hit_flash_alpha = 0.0
        if run_state.hit_flash_expires_at > 0.0:
            flash_remaining = max(0.0, run_state.hit_flash_expires_at - monotonic())
            flash_duration = settings.gameplay.obstacle_hit_cooldown_seconds
            if flash_remaining > 0.0 and flash_duration > 0.0:
                hit_flash_alpha = min(0.45, flash_remaining / flash_duration)
        hit_flash.enabled = hit_flash_alpha > 0.0
        if hit_flash.enabled:
            hit_flash.color = rgba_color(1.0, 1.0, 1.0, hit_flash_alpha)

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

        if key in TOGGLE_AUTO_YAW_KEYS:
            run_state.auto_yaw_enabled = not run_state.auto_yaw_enabled

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
    if active_settings.run_seed is None:
        run_seed = SystemRandom().randint(0, 2**32 - 1)
        # T201: visible run seed for replay/debugging.
        print(f"Run seed: {run_seed}")  # noqa: T201
        active_settings = replace(active_settings, run_seed=run_seed)
    else:
        # T201: visible run seed for replay/debugging.
        print(f"Run seed: {active_settings.run_seed}")  # noqa: T201
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
