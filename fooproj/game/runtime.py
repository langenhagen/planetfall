"""Ursina runtime for an endless third-person falling game."""

import importlib
from contextlib import suppress
from dataclasses import dataclass, field
from math import cos, sin, tau
from pathlib import Path
from random import Random
from time import monotonic
from typing import TYPE_CHECKING, cast

import ursina
import ursina.color as color_module
import ursina.shaders as ursina_shaders
from ursina import (
    AmbientLight,
    DirectionalLight,
    Entity,
    Text,
    Vec2,
    Vec3,
    application,
    camera,
    destroy,
    lerp_exponential_decay,
    mouse,
    scene,
    window,
)
from ursina.main import Ursina

from .config import CameraSettings, FallSettings, GameSettings, MovementSettings
from .scene import BAND_SPACING, FallingBlueprint, build_fall_band_blueprints

if TYPE_CHECKING:
    from ursina.color import Color


LIT_SHADER = cast("object", ursina_shaders.lit_with_shadows_shader)
GAMEPAD_DEADZONE = 0.08
GAMEPAD_LOOK_SENSITIVITY = 0.012
PLAYER_COLLISION_RADIUS = 0.95
OBSTACLE_HIT_COOLDOWN_SECONDS = 0.45
RUN_RANDOM_SEED = 20260224
PLANET_APPROACH_DEPTH = 1600.0
STARFIELD_COUNT = 48
STARFIELD_RADIUS = 74.0
SCROLL_DIRECTION_BY_KEY = {
    "scroll up": 1,
    "scroll down": -1,
    "gamepad dpad up": 1,
    "gamepad dpad down": -1,
}
RESTART_KEYS = {"r", "gamepad start"}
TOGGLE_CONTROLS_KEYS = {"u", "gamepad y"}
RECENTER_CAMERA_KEYS = {"c", "gamepad dpad left"}


@dataclass(slots=True)
class OrbitRig:
    """Camera yaw/pitch pivot entities for third-person orbit motion."""

    yaw_pivot: Entity
    pitch_pivot: Entity


@dataclass(slots=True)
class CameraState:
    """Mutable camera state for orbit look and zoom behavior."""

    yaw_angle: float
    pitch_angle: float
    distance: float


@dataclass(slots=True)
class MotionState:
    """Mutable player movement speeds for gentle acceleration/deceleration."""

    horizontal_speed: float = 0.0
    depth_speed: float = 0.0


@dataclass(slots=True)
class SpawnedObject:
    """Runtime state for one spawned world object."""

    entity: Entity
    entity_kind: str
    collision_radius: float
    score_value: int
    spin_speed: float = 0.0


@dataclass(slots=True)
class FallingRunState:
    """Mutable run-state values tracked across gameplay frames."""

    max_health: int
    score: int = 0
    collected_orbs: int = 0
    health: int = 0
    deepest_y: float = 0.0
    next_band_index: int = 0
    next_band_y: float = 0.0
    is_game_over: bool = False
    last_hit_time: float = 0.0
    spawned_objects: list[SpawnedObject] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LightingRig:
    """Runtime references for lighting entities that change with depth."""

    key_light: DirectionalLight
    ambient_light: AmbientLight


@dataclass(frozen=True, slots=True)
class BackdropState:
    """Runtime references for starfield and planetfall backdrop entities."""

    sky: Entity
    stars: tuple[Entity, ...]
    planet: Entity
    atmosphere_shell: Entity


def resolve_color(color_name: str) -> Color:
    """Resolve a color name from Ursina's built-in color palette."""
    return cast("Color", getattr(color_module, color_name, color_module.white))


def rgba_color(red: float, green: float, blue: float, alpha: float = 1.0) -> Color:
    """Create a color using Ursina's runtime rgba helper."""
    rgba_factory = getattr(color_module, "rgba")  # noqa: B009  # B009: getattr-with-constant
    return cast("Color", rgba_factory(red, green, blue, alpha))


def mark_lit_shadowed(entity: Entity) -> Entity:
    """Apply the project-default lit shader and shadow camera mask."""
    entity.shader = LIT_SHADER
    entity.show(0b0001)
    return entity


def get_frame_dt() -> float:
    """Read frame delta from Ursina's dynamic runtime module."""
    # Ursina exposes frame delta via dynamic module attributes.
    # B009: getattr-with-constant; ursina.time.dt is dynamic at runtime.
    return cast("float", getattr(getattr(ursina, "time"), "dt", 0.0))  # noqa: B009


def apply_deadzone(value: float, deadzone: float = GAMEPAD_DEADZONE) -> float:
    """Clamp tiny analog controller drift to zero."""
    if abs(value) < deadzone:
        return 0.0
    return value


def dominant_axis(primary: float, secondary: float) -> float:
    """Return the stronger of two axis sources by absolute value."""
    return primary if abs(primary) >= abs(secondary) else secondary


def compute_keyboard_axes(held: dict[str, float]) -> tuple[float, float, float]:
    """Map keyboard state to horizontal and fall-speed control axes."""
    x_axis = (
        held.get("right arrow", 0.0)
        + held.get("d", 0.0)
        - held.get("left arrow", 0.0)
        - held.get("a", 0.0)
    )
    z_axis = (
        held.get("up arrow", 0.0)
        + held.get("w", 0.0)
        - held.get("down arrow", 0.0)
        - held.get("s", 0.0)
    )
    dive_axis = held.get("space", 0.0) - max(
        held.get("left shift", 0.0),
        held.get("right shift", 0.0),
    )
    return x_axis, z_axis, dive_axis


def compute_gamepad_axes(
    held: dict[str, float],
) -> tuple[float, float, float, float, float]:
    """Map gamepad sticks, triggers, and shoulders to gameplay axes."""
    shoulder_axis = held.get("gamepad right shoulder", 0.0) - held.get(
        "gamepad left shoulder",
        0.0,
    )
    stick_x = apply_deadzone(held.get("gamepad left stick x", 0.0))
    stick_y = apply_deadzone(held.get("gamepad left stick y", 0.0))
    x_axis = dominant_axis(stick_x, shoulder_axis)
    z_axis = -stick_y
    dive_axis = apply_deadzone(
        held.get("gamepad right trigger", 0.0) - held.get("gamepad left trigger", 0.0),
    )
    look_x = apply_deadzone(held.get("gamepad right stick x", 0.0))
    look_y = apply_deadzone(held.get("gamepad right stick y", 0.0))
    return (
        x_axis,
        z_axis,
        dive_axis,
        look_x * GAMEPAD_LOOK_SENSITIVITY,
        look_y * GAMEPAD_LOOK_SENSITIVITY,
    )


def compute_control_axes(
    held: dict[str, float],
    mouse_velocity: Vec3,
) -> tuple[float, float, float, Vec3]:
    """Combine keyboard, gamepad, and mouse into one control vector set."""
    keyboard_x, keyboard_z, keyboard_dive = compute_keyboard_axes(held)
    gamepad_x, gamepad_z, gamepad_dive, gamepad_look_x, gamepad_look_y = (
        compute_gamepad_axes(held)
    )
    return (
        dominant_axis(keyboard_x, gamepad_x),
        dominant_axis(keyboard_z, gamepad_z),
        dominant_axis(keyboard_dive, gamepad_dive),
        Vec3(
            dominant_axis(mouse_velocity.x, gamepad_look_x),
            dominant_axis(mouse_velocity.y, gamepad_look_y),
            0.0,
        ),
    )


def clamp_to_play_area(
    x_value: float,
    z_value: float,
    play_area_radius: float,
) -> tuple[float, float]:
    """Clamp x/z movement to a circular play area."""
    radial_distance = (x_value**2 + z_value**2) ** 0.5
    if radial_distance <= play_area_radius or radial_distance == 0.0:
        return x_value, z_value

    scale = play_area_radius / radial_distance
    return x_value * scale, z_value * scale


def lerp_scalar(start_value: float, end_value: float, factor: float) -> float:
    """Linearly interpolate between two scalar values."""
    return start_value + ((end_value - start_value) * factor)


def lerp_rgb_color(
    start_rgb: tuple[int, int, int],
    end_rgb: tuple[int, int, int],
    factor: float,
) -> Color:
    """Interpolate between two rgb tuples and return a color value."""
    clamped_factor = max(0.0, min(1.0, factor))
    red = round(lerp_scalar(float(start_rgb[0]), float(end_rgb[0]), clamped_factor))
    green = round(lerp_scalar(float(start_rgb[1]), float(end_rgb[1]), clamped_factor))
    blue = round(lerp_scalar(float(start_rgb[2]), float(end_rgb[2]), clamped_factor))
    return rgba_color(red / 255.0, green / 255.0, blue / 255.0, 1.0)


def compute_smoothed_lateral_speed(
    *,
    current_speed: float,
    axis_input: float,
    max_speed: float,
    acceleration_rate: float,
    deceleration_rate: float,
    dt: float,
) -> float:
    """Smooth horizontal speed changes for gentle acceleration/deceleration."""
    if dt <= 0.0:
        return current_speed

    target_speed = axis_input * max_speed
    if target_speed == 0.0:
        response_rate = deceleration_rate
    elif abs(target_speed) > abs(current_speed):
        response_rate = acceleration_rate
    else:
        response_rate = deceleration_rate

    if target_speed != 0.0 and (target_speed * current_speed) < 0.0:
        response_rate = max(response_rate, deceleration_rate * 1.25)

    return cast(
        "float",
        lerp_exponential_decay(current_speed, target_speed, dt * response_rate),
    )


def compute_fall_speed(
    *,
    base_speed: float,
    dive_axis: float,
    boost_multiplier: float,
    brake_multiplier: float,
) -> float:
    """Compute effective fall speed from dive and brake input."""
    if dive_axis >= 0.0:
        return base_speed * (1.0 + (dive_axis * boost_multiplier))

    speed = base_speed * (1.0 + (dive_axis * brake_multiplier))
    return max(base_speed * 0.2, speed)


def compute_look_angles(
    *,
    yaw_angle: float,
    pitch_angle: float,
    look_velocity: Vec3,
    mouse_look_speed: float,
    min_pitch: float,
    max_pitch: float,
) -> tuple[float, float]:
    """Update camera yaw/pitch from look input and clamp pitch limits."""
    next_yaw = yaw_angle + (look_velocity.x * mouse_look_speed)
    next_pitch = pitch_angle + (look_velocity.y * mouse_look_speed)
    next_pitch = max(min_pitch, min(max_pitch, next_pitch))
    return next_yaw, next_pitch


def compute_zoom_distance(
    *,
    current_distance: float,
    scroll_direction: int,
    min_distance: float,
    max_distance: float,
    zoom_step: float,
) -> float:
    """Adjust and clamp camera zoom distance from scroll input."""
    next_distance = current_distance - (scroll_direction * zoom_step)
    return max(min_distance, min(max_distance, next_distance))


def should_spawn_next_band(
    *,
    next_band_y: float,
    player_y: float,
    spawn_ahead_distance: float,
) -> bool:
    """Return whether more content should be spawned below the player."""
    return next_band_y > (player_y - spawn_ahead_distance)


def should_despawn_object(
    *,
    object_y: float,
    player_y: float,
    cleanup_above_distance: float,
) -> bool:
    """Return whether an entity is far above the player and should be removed."""
    return object_y > (player_y + cleanup_above_distance)


def configure_window(settings: GameSettings) -> None:
    """Apply top-level window settings."""
    window.title = settings.window_title
    window.borderless = settings.borderless
    window.fullscreen = settings.fullscreen


def add_avatar_part(
    *,
    parent: Entity,
    name: str,
    model: str,
    color_name: str,
    scale: Vec3,
    position: Vec3,
) -> Entity:
    """Create one named avatar part for scene-inspector readability."""
    part = Entity(
        parent=parent,
        name=name,
        model=model,
        color=resolve_color(color_name),
        scale=scale,
        position=position,
    )
    return mark_lit_shadowed(part)


def spawn_player_avatar() -> Entity:
    """Spawn a stylized falling character visible in third-person view."""
    avatar = Entity(name="player_faller_root", position=Vec3(0.0, 0.0, 0.0))

    add_avatar_part(
        parent=avatar,
        name="player_torso",
        model="cube",
        color_name="azure",
        scale=Vec3(1.15, 1.55, 0.8),
        position=Vec3(0.0, 0.0, 0.0),
    )
    add_avatar_part(
        parent=avatar,
        name="player_head",
        model="sphere",
        color_name="peach",
        scale=Vec3(0.78, 0.78, 0.78),
        position=Vec3(0.0, 1.12, 0.0),
    )
    add_avatar_part(
        parent=avatar,
        name="player_pack",
        model="cube",
        color_name="dark_gray",
        scale=Vec3(0.88, 0.92, 0.32),
        position=Vec3(0.0, 0.2, -0.56),
    )

    for side_name, side_x in (("left", -0.86), ("right", 0.86)):
        add_avatar_part(
            parent=avatar,
            name=f"player_arm_{side_name}",
            model="cube",
            color_name="orange",
            scale=Vec3(0.34, 1.18, 0.34),
            position=Vec3(side_x, -0.06, 0.0),
        )

    for side_name, side_x in (("left", -0.34), ("right", 0.34)):
        add_avatar_part(
            parent=avatar,
            name=f"player_leg_{side_name}",
            model="cube",
            color_name="navy",
            scale=Vec3(0.38, 1.02, 0.38),
            position=Vec3(side_x, -1.18, 0.0),
        )

    return avatar


def configure_camera() -> None:
    """Set up base camera parent and transform defaults."""
    camera.parent = scene
    camera.rotation = Vec3(0.0, 0.0, 0.0)


def create_camera_orbit_rig(settings: GameSettings) -> OrbitRig:
    """Create yaw and pitch pivots used for stable orbit controls."""
    yaw_pivot = Entity(name="camera_yaw_pivot", parent=scene)
    pitch_pivot = Entity(name="camera_pitch_pivot", parent=yaw_pivot)
    camera.parent = pitch_pivot
    camera.position = Vec3(0.0, 0.0, -settings.camera.distance)
    camera.rotation = Vec3(0.0, 0.0, 0.0)
    return OrbitRig(yaw_pivot=yaw_pivot, pitch_pivot=pitch_pivot)


def configure_mouse_capture() -> None:
    """Capture the mouse cursor for camera look controls."""
    mouse.locked = True
    mouse.visible = False


def create_controls_hint() -> Text:
    """Render controls help text and return its entity."""
    return Text(
        name="controls_hint_text",
        text=(
            "Steer: arrows or WASD (up = up-screen)\n"
            "Dive faster: space / R2\n"
            "Air brake: shift / L2\n"
            "Pad steer: left stick + L1/R1\n"
            "Look: mouse / right stick\n"
            "Zoom: mouse wheel / dpad up-down\n"
            "Recenter: c / dpad left\n"
            "Restart: r / start\n"
            "UI: u"
        ),
        x=-0.86,
        y=0.47,
        scale=0.9,
        background=True,
    )


def create_status_text() -> Text:
    """Create top-left run status text entity."""
    return Text(
        name="run_status_text",
        text="",
        x=-0.86,
        y=0.42,
        scale=1.05,
    )


def create_game_over_text() -> Text:
    """Create centered game-over text shown when shields are depleted."""
    return Text(
        name="game_over_text",
        text="Run Over\nPress R or Start to dive again",
        origin=(0.0, 0.0),
        scale=2.0,
        background=True,
        enabled=False,
    )


def configure_lighting(focus_entity: Entity) -> LightingRig:
    """Create one sun light and ambient fill with stable shadow bounds."""
    sun_direction = Vec3(0.75, -1.2, -0.45).normalized()
    key_light = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(3072, 3072))
    key_light.color = color_module.white
    key_light.look_at(sun_direction)

    ambient_light = AmbientLight()
    ambient_light.color = color_module.rgba(0.24, 0.26, 0.31, 1.0)

    scene.set_shader_input("shadow_color", color_module.black66)
    scene.set_shader_input("shadow_blur", 0.0008)
    scene.set_shader_input("shadow_bias", 0.0005)
    scene.set_shader_input("shadow_samples", 3)

    shadow_bounds = Entity(
        name="shadow_bounds_focus",
        parent=focus_entity,
        model="cube",
        position=Vec3(0.0, -20.0, 0.0),
        scale=Vec3(64.0, 84.0, 64.0),
        color=color_module.clear,
        unlit=True,
    )
    key_light.update_bounds(shadow_bounds)

    shadow_controller = Entity(name="shadow_bounds_controller")

    def update_shadow_bounds() -> None:
        key_light.update_bounds(shadow_bounds)

    shadow_controller.update = update_shadow_bounds

    return LightingRig(key_light=key_light, ambient_light=ambient_light)


def create_space_backdrop() -> BackdropState:
    """Create stars and a distant planet to sell the planetfall fantasy."""
    sky_module = importlib.import_module("ursina.prefabs.sky")
    sky_factory = cast("type[Entity]", sky_module.Sky)
    sky_entity = sky_factory()
    stars: list[Entity] = []

    for star_index in range(STARFIELD_COUNT):
        angle = (tau / STARFIELD_COUNT) * star_index
        radius = STARFIELD_RADIUS + ((star_index % 7) * 4.5)
        star_y = 48.0 + ((star_index % 9) * 12.0)
        if star_index % 2:
            star_y *= 0.55
        stars.append(
            Entity(
                name=f"space_star_{star_index}",
                model="sphere",
                scale=Vec3(0.18, 0.18, 0.18),
                position=Vec3(cos(angle) * radius, star_y, sin(angle) * radius),
                color=color_module.rgba(1.0, 1.0, 1.0, 1.0),
                unlit=True,
            ),
        )

    planet = Entity(
        name="planet_surface",
        model="sphere",
        color=rgba_color(34 / 255.0, 60 / 255.0, 94 / 255.0, 1.0),
        scale=Vec3(980.0, 980.0, 980.0),
        position=Vec3(0.0, -1900.0, 0.0),
        unlit=True,
    )
    atmosphere_shell = Entity(
        parent=planet,
        name="planet_atmosphere_shell",
        model="sphere",
        color=color_module.rgba(0.26, 0.5, 0.86, 0.18),
        scale=Vec3(1.08, 1.08, 1.08),
        position=Vec3(0.0, 0.0, 0.0),
        unlit=True,
    )

    return BackdropState(
        sky=sky_entity,
        stars=tuple(stars),
        planet=planet,
        atmosphere_shell=atmosphere_shell,
    )


def update_atmosphere_for_depth(
    *,
    player: Entity,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
) -> None:
    """Shift sky and light colors from cold space to warm atmosphere."""
    depth = max(0.0, -player.y)
    progress = max(0.0, min(1.0, depth / PLANET_APPROACH_DEPTH))

    backdrop_state.sky.color = lerp_rgb_color((7, 10, 24), (145, 186, 214), progress)
    lighting_rig.ambient_light.color = color_module.rgba(
        lerp_scalar(0.12, 0.38, progress),
        lerp_scalar(0.15, 0.42, progress),
        lerp_scalar(0.24, 0.48, progress),
        1.0,
    )
    lighting_rig.key_light.color = color_module.rgba(
        lerp_scalar(0.65, 1.0, progress),
        lerp_scalar(0.72, 0.95, progress),
        lerp_scalar(0.82, 0.9, progress),
        1.0,
    )

    star_alpha = max(0.0, 1.0 - (progress * 1.35))
    for star in backdrop_state.stars:
        star.color = color_module.rgba(1.0, 1.0, 1.0, star_alpha)

    backdrop_state.planet.color = lerp_rgb_color((34, 60, 94), (78, 133, 99), progress)
    backdrop_state.atmosphere_shell.color = color_module.rgba(
        0.26,
        0.5,
        0.86,
        lerp_scalar(0.14, 0.5, progress),
    )
    backdrop_state.planet.x = player.x * 0.35
    backdrop_state.planet.z = player.z * 0.35
    backdrop_state.planet.y = -1900.0 + (progress * 620.0)


def spawn_entity_from_blueprint(
    *,
    blueprint: FallingBlueprint,
    band_index: int,
    blueprint_index: int,
) -> SpawnedObject:
    """Spawn one band blueprint as an Ursina entity and runtime record."""
    entity_name = (
        f"fall_band_{band_index}_"
        f"{blueprint.entity_kind}_"
        f"{blueprint.name}_"
        f"{blueprint_index}"
    )
    entity = Entity(
        name=entity_name,
        model=blueprint.model,
        color=resolve_color(blueprint.color_name),
        scale=Vec3(blueprint.scale.x, blueprint.scale.y, blueprint.scale.z),
        position=Vec3(
            blueprint.position.x,
            blueprint.position.y,
            blueprint.position.z,
        ),
    )
    if blueprint.entity_kind == "coin":
        entity.unlit = True
    else:
        mark_lit_shadowed(entity)

    return SpawnedObject(
        entity=entity,
        entity_kind=blueprint.entity_kind,
        collision_radius=blueprint.collision_radius,
        score_value=blueprint.score_value,
        spin_speed=240.0 if blueprint.entity_kind == "coin" else 0.0,
    )


def trigger_impact_rumble(intensity: float) -> None:
    """Trigger brief gamepad rumble on obstacle impact, if available."""
    with suppress(Exception):
        gamepad_module = importlib.import_module("ursina.gamepad")
        vibrate = getattr(gamepad_module, "vibrate", None)
        if callable(vibrate):
            vibrate(
                low_freq_motor=max(0.2, min(1.0, intensity)),
                high_freq_motor=max(0.2, min(1.0, intensity + 0.1)),
                duration=0.09,
            )


def initialize_run_state(
    run_state: FallingRunState, fall_settings: FallSettings
) -> None:
    """Reset run-state values to initial defaults."""
    run_state.score = 0
    run_state.collected_orbs = 0
    run_state.health = run_state.max_health
    run_state.deepest_y = 0.0
    run_state.next_band_index = 0
    run_state.next_band_y = fall_settings.initial_spawn_y
    run_state.is_game_over = False
    run_state.last_hit_time = 0.0


def destroy_spawned_objects(spawned_objects: list[SpawnedObject]) -> None:
    """Destroy spawned entities and clear the container in-place."""
    for spawned in spawned_objects:
        destroy(spawned.entity)
    spawned_objects.clear()


def spawn_bands_ahead(
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
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
        )
        for blueprint_index, blueprint in enumerate(blueprints):
            run_state.spawned_objects.append(
                spawn_entity_from_blueprint(
                    blueprint=blueprint,
                    band_index=run_state.next_band_index,
                    blueprint_index=blueprint_index,
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
            destroy(spawned.entity)
            continue
        survivors.append(spawned)

    run_state.spawned_objects = survivors


def process_collisions(*, player: Entity, run_state: FallingRunState) -> None:
    """Handle collisions with coins and obstacles for score and health."""
    now = monotonic()
    survivors: list[SpawnedObject] = []

    for spawned in run_state.spawned_objects:
        if spawned.collision_radius <= 0.0:
            survivors.append(spawned)
            continue

        distance = (spawned.entity.position - player.position).length()
        hit_radius = PLAYER_COLLISION_RADIUS + spawned.collision_radius
        if distance > hit_radius:
            survivors.append(spawned)
            continue

        destroy(spawned.entity)
        if spawned.entity_kind == "coin":
            run_state.collected_orbs += 1
            run_state.score += spawned.score_value
            continue

        if spawned.entity_kind != "obstacle":
            continue

        if now - run_state.last_hit_time < OBSTACLE_HIT_COOLDOWN_SECONDS:
            continue

        run_state.last_hit_time = now
        run_state.health -= 1
        run_state.score = max(0, run_state.score - 35)
        trigger_impact_rumble(intensity=0.65)

    run_state.spawned_objects = survivors


def spin_coin_entities(run_state: FallingRunState, dt: float) -> None:
    """Apply simple spin animation to collectible orbs."""
    for spawned in run_state.spawned_objects:
        if spawned.entity_kind != "coin":
            continue
        spawned.entity.rotation_y += spawned.spin_speed * dt


def depth_zone_label(depth: float) -> str:
    """Return a readable biome label for the current descent depth."""
    if depth < 420.0:
        return "Deep Space"
    if depth < 980.0:
        return "Upper Atmosphere"
    return "Planetfall"


def update_status_text(run_state: FallingRunState, status_text: Text) -> None:
    """Render current score, depth, and shield status into the HUD."""
    depth = max(0.0, -run_state.deepest_y)
    status_text.text = (
        f"Score: {run_state.score}\n"
        f"Orbs: {run_state.collected_orbs}\n"
        f"Depth: {depth:.0f} m\n"
        f"Zone: {depth_zone_label(depth)}\n"
        f"Shields: {max(0, run_state.health)}"
    )


def update_camera_tracking(
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    camera_state: CameraState,
    camera_settings: CameraSettings,
    look_velocity: Vec3,
) -> None:
    """Update orbit camera pivots and zoom using current look input."""
    camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
        yaw_angle=camera_state.yaw_angle,
        pitch_angle=camera_state.pitch_angle,
        look_velocity=look_velocity,
        mouse_look_speed=camera_settings.mouse_look_speed,
        min_pitch=camera_settings.min_pitch,
        max_pitch=camera_settings.max_pitch,
    )

    orbit_rig.yaw_pivot.world_position = player.world_position + Vec3(
        0.0,
        camera_settings.height,
        0.0,
    )
    orbit_rig.yaw_pivot.rotation = Vec3(0.0, camera_state.yaw_angle, 0.0)
    orbit_rig.pitch_pivot.rotation = Vec3(camera_state.pitch_angle, 0.0, 0.0)
    camera.position = Vec3(0.0, 0.0, -camera_state.distance)
    camera.rotation_z = 0.0


def apply_player_movement(
    *,
    player: Entity,
    motion_state: MotionState,
    movement_settings: MovementSettings,
    fall_settings: FallSettings,
    x_axis: float,
    z_axis: float,
    dive_axis: float,
    dt: float,
) -> float:
    """Move the player avatar and return effective vertical fall speed."""
    fall_speed = compute_fall_speed(
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

    player.y -= fall_speed * dt
    player.x += motion_state.horizontal_speed * dt
    player.z += motion_state.depth_speed * dt
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

    target_roll = -normalized_horizontal * movement_settings.tilt_degrees
    target_pitch = normalized_depth * movement_settings.tilt_degrees * 0.7
    player.rotation_z = cast(
        "float",
        lerp_exponential_decay(player.rotation_z, target_roll, dt * 9.0),
    )
    player.rotation_x = cast(
        "float",
        lerp_exponential_decay(player.rotation_x, target_pitch, dt * 9.0),
    )
    player.rotation_y = cast(
        "float",
        lerp_exponential_decay(
            player.rotation_y, normalized_horizontal * 22.0, dt * 6.0
        ),
    )
    return fall_speed


def install_game_controller(
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    settings: GameSettings,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
    controls_hint: Text,
    status_text: Text,
    game_over_text: Text,
) -> Entity:
    """Attach per-frame gameplay update and input handlers."""
    controller = Entity(name="fall_game_controller")
    randomizer = Random(RUN_RANDOM_SEED)
    camera_state = CameraState(
        yaw_angle=0.0,
        pitch_angle=settings.camera.start_pitch,
        distance=settings.camera.distance,
    )
    motion_state = MotionState()
    run_state = FallingRunState(max_health=settings.max_health)
    initialize_run_state(run_state, settings.fall)

    def reset_run() -> None:
        destroy_spawned_objects(run_state.spawned_objects)
        initialize_run_state(run_state, settings.fall)
        randomizer.seed(RUN_RANDOM_SEED)
        player.position = Vec3(0.0, 0.0, 0.0)
        player.rotation = Vec3(0.0, 0.0, 0.0)
        motion_state.horizontal_speed = 0.0
        motion_state.depth_speed = 0.0
        camera_state.yaw_angle = 0.0
        camera_state.pitch_angle = settings.camera.start_pitch
        camera_state.distance = settings.camera.distance
        game_over_text.enabled = False
        spawn_bands_ahead(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
        )
        update_status_text(run_state, status_text)

    reset_run()

    def controller_update() -> None:
        held = cast("dict[str, float]", getattr(ursina, "held_keys", {}))
        mouse_velocity = cast("Vec3", getattr(mouse, "velocity", Vec3(0.0, 0.0, 0.0)))
        x_axis, z_axis, dive_axis, look_velocity = compute_control_axes(
            held,
            mouse_velocity,
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
            return

        if not run_state.is_game_over:
            apply_player_movement(
                player=player,
                motion_state=motion_state,
                movement_settings=settings.movement,
                fall_settings=settings.fall,
                x_axis=x_axis,
                z_axis=z_axis,
                dive_axis=dive_axis,
                dt=dt,
            )
            run_state.deepest_y = min(run_state.deepest_y, player.y)

            spawn_bands_ahead(
                run_state=run_state,
                player_y=player.y,
                rng=randomizer,
                fall_settings=settings.fall,
            )
            spin_coin_entities(run_state, dt)
            process_collisions(player=player, run_state=run_state)
            cleanup_passed_objects(
                run_state=run_state,
                player_y=player.y,
                cleanup_above_distance=settings.fall.cleanup_above_distance,
            )

            if run_state.health <= 0:
                run_state.is_game_over = True
                game_over_text.enabled = True

        update_camera_tracking(
            player=player,
            orbit_rig=orbit_rig,
            camera_state=camera_state,
            camera_settings=settings.camera,
            look_velocity=look_velocity,
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
        )
        update_status_text(run_state, status_text)

    def controller_input(key: str) -> None:
        if key == "escape":
            application.quit()
            return

        if key in TOGGLE_CONTROLS_KEYS:
            controls_hint.enabled = not controls_hint.enabled

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
    app = cast("object", Ursina(development_mode=active_settings.development_mode))
    application.asset_folder = Path(__file__).resolve().parents[2]

    configure_window(active_settings)

    player = spawn_player_avatar()
    configure_camera()
    orbit_rig = create_camera_orbit_rig(active_settings)
    configure_mouse_capture()
    controls_hint = create_controls_hint()
    status_text = create_status_text()
    game_over_text = create_game_over_text()
    lighting_rig = configure_lighting(player)
    backdrop_state = create_space_backdrop()
    install_game_controller(
        player=player,
        orbit_rig=orbit_rig,
        settings=active_settings,
        lighting_rig=lighting_rig,
        backdrop_state=backdrop_state,
        controls_hint=controls_hint,
        status_text=status_text,
        game_over_text=game_over_text,
    )

    # Ursina's app proxy is typed as object here, so dynamic access is needed.
    run_callable = getattr(app, "run")  # noqa: B009  # B009: getattr-with-constant
    run_callable()
