"""Ursina runtime bootstrap functions."""

import importlib
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, cast

import ursina
import ursina.color as color_module
import ursina.shaders as ursina_shaders
from ursina import (
    AmbientLight,
    DirectionalLight,
    Entity,
    Sky,
    Text,
    Vec2,
    Vec3,
    application,
    camera,
    lerp_exponential_decay,
    mouse,
    scene,
    window,
)
from ursina.main import Ursina

from .config import CameraSettings, GameSettings, MovementSettings
from .scene import EntityBlueprint, starter_scene_blueprints

if TYPE_CHECKING:
    from ursina.color import Color


LIT_SHADER = cast("object", ursina_shaders.lit_with_shadows_shader)
CAR_IMPACT_RADIUS = 1.75
CAR_MODEL_FILE = (
    Path(__file__).resolve().parents[2] / "assets" / "De_Tomaso_P72_2020.obj"
)
CAR_BASE_TEXTURE_FILE = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "De_Tomaso_Textures"
    / "Detomasop72_Base_Color.png"
)
CAR_BASE_TEXTURE_PATH = "assets/De_Tomaso_Textures/Detomasop72_Base_Color.png"
CAR_TARGET_LENGTH = 4.8
BOUNCE_DAMPING = 0.35
MIN_BOUNCE_SPEED = 0.25
MIN_IMPACT_SPEED = 0.1
NORMALIZE_EPSILON = 0.0001
GROUND_FRICTION = 0.97
SCROLL_DIRECTION_BY_KEY = {
    "scroll up": 1,
    "scroll down": -1,
    "gamepad dpad up": 1,
    "gamepad dpad down": -1,
}
CAMERA_TOGGLE_KEYS = {"c", "gamepad dpad left"}
CHASE_CAMERA_HEIGHT_OFFSET = 0.75
CHASE_CAMERA_LOOK_AHEAD = 3.6
CHASE_CAMERA_FOLLOW_SPEED = 8.5
GAMEPAD_DEADZONE = 0.08
GAMEPAD_LOOK_SENSITIVITY = 0.012
RUMBLE_COOLDOWN_SECONDS = 0.12
FORWARD_MAX_SPEED_MULTIPLIER = 3.0
FORWARD_ACCELERATION_RATE = 9.0
FORWARD_DECELERATION_RATE = 11.0
FORWARD_BRAKE_RATE = 16.0


@dataclass(slots=True)
class OrbitControlState:
    """Mutable orbit camera state used across input frames."""

    yaw_angle: float
    pitch_angle: float
    camera_distance: float
    chase_camera_enabled: bool = False
    forward_speed: float = 0.0


@dataclass(frozen=True, slots=True)
class OrbitRig:
    """Holds yaw and pitch pivot entities for camera orbit."""

    yaw_pivot: Entity
    pitch_pivot: Entity


@dataclass(slots=True)
class DynamicProp:
    """Simple dynamic prop state for lightweight physics interactions."""

    entity: Entity
    velocity: Vec3
    radius: float
    mass: float


def resolve_color(color_name: str) -> Color:
    """Resolve a color name from Ursina's built-in color palette."""
    return cast("Color", getattr(color_module, color_name, color_module.white))


def mark_lit_shadowed(entity: Entity) -> Entity:
    """Apply the project-default lit shader and shadow camera mask."""
    entity.shader = LIT_SHADER
    entity.show(0b0001)
    return entity


def side_label(x_pos: float) -> str:
    """Return stable left/right labels from signed x positions."""
    return "left" if x_pos < 0.0 else "right"


def wheel_label(x_pos: float, z_pos: float) -> str:
    """Return stable wheel labels from wheel-local positions."""
    axle_label = "front" if z_pos > 0.0 else "rear"
    return f"{axle_label}_{side_label(x_pos)}"


def get_frame_dt() -> float:
    """Read frame delta from Ursina's dynamic runtime module."""
    # Ursina exposes frame delta via dynamic module attributes.
    # B009: getattr-with-constant; ursina.time.dt is dynamic at runtime.
    return cast("float", getattr(getattr(ursina, "time"), "dt", 0.0))  # noqa: B009


def spawn_entity(blueprint: EntityBlueprint) -> Entity:
    """Spawn one entity from a scene blueprint and return it."""
    # Stable names make runtime inspection in Ursina's entity list easier.
    entity_name = (
        f"world_{blueprint.model}_"
        f"{round(blueprint.position.x)}_"
        f"{round(blueprint.position.z)}"
    )
    entity = Entity(
        name=entity_name,
        model=blueprint.model,
        color=resolve_color(blueprint.color_name),
        scale=Vec3(blueprint.scale.x, blueprint.scale.y, blueprint.scale.z),
        position=Vec3(blueprint.position.x, blueprint.position.y, blueprint.position.z),
    )
    return mark_lit_shadowed(entity)


def configure_window(settings: GameSettings) -> None:
    """Apply top-level window settings."""
    window.title = settings.window_title
    window.borderless = settings.borderless
    window.fullscreen = settings.fullscreen


# PLR0913 / pylint R0913,R0917: explicit geometry parameters keep
# primitive car part callsites readable and easy to tweak.
# pylint: disable=too-many-arguments,too-many-positional-arguments
def add_car_part(  # noqa: PLR0913
    parent: Entity,
    name: str,
    model: str,
    color_value: Color,
    scale: Vec3,
    position: Vec3,
    rotation: Vec3 | None = None,
) -> Entity:
    """Create one shaded part for the player car prefab."""
    part = Entity(
        parent=parent,
        name=name,
        model=model,
        color=color_value,
        scale=scale,
        position=position,
    )
    if rotation is not None:
        part.rotation = rotation
    return mark_lit_shadowed(part)


# pylint: enable=too-many-arguments,too-many-positional-arguments


def spawn_primitive_player() -> Entity:
    """Create a richer low-poly sports car as the player entity."""
    car = Entity(name="player_car_primitive_root", position=Vec3(0.0, 0.48, 0.0))

    # Car body: base shell, mid shell, nose, rear deck.
    add_car_part(
        parent=car,
        name="car_body_base",
        model="cube",
        color_value=color_module.orange,
        scale=Vec3(2.3, 0.46, 4.6),
        position=Vec3(0.0, -0.02, 0.0),
    )
    add_car_part(
        parent=car,
        name="car_body_mid",
        model="cube",
        color_value=color_module.orange,
        scale=Vec3(2.18, 0.44, 3.55),
        position=Vec3(0.0, 0.33, -0.02),
    )
    add_car_part(
        parent=car,
        name="car_body_nose",
        model="cube",
        color_value=color_module.orange,
        scale=Vec3(2.1, 0.36, 1.65),
        position=Vec3(0.0, 0.31, 1.55),
        rotation=Vec3(2.0, 0.0, 0.0),
    )
    add_car_part(
        parent=car,
        name="car_body_rear",
        model="cube",
        color_value=color_module.orange,
        scale=Vec3(2.02, 0.32, 1.2),
        position=Vec3(0.0, 0.31, -1.8),
        rotation=Vec3(-2.0, 0.0, 0.0),
    )

    # Cabin and glass.
    add_car_part(
        parent=car,
        name="car_cabin_shell",
        model="cube",
        color_value=color_module.azure,
        scale=Vec3(1.7, 0.42, 2.2),
        position=Vec3(0.0, 0.68, -0.28),
    )
    add_car_part(
        parent=car,
        name="car_cabin_roof",
        model="cube",
        color_value=color_module.azure,
        scale=Vec3(1.35, 0.2, 1.45),
        position=Vec3(0.0, 0.95, -0.28),
    )
    add_car_part(
        parent=car,
        name="car_windshield_front",
        model="cube",
        color_value=color_module.light_gray,
        scale=Vec3(1.26, 0.18, 0.08),
        position=Vec3(0.0, 0.83, 0.58),
        rotation=Vec3(32.0, 0.0, 0.0),
    )
    add_car_part(
        parent=car,
        name="car_windshield_rear",
        model="cube",
        color_value=color_module.light_gray,
        scale=Vec3(1.16, 0.17, 0.08),
        position=Vec3(0.0, 0.81, -1.02),
        rotation=Vec3(-30.0, 0.0, 0.0),
    )

    # Bumpers.
    add_car_part(
        parent=car,
        name="car_bumper_front",
        model="cube",
        color_value=color_module.dark_gray,
        scale=Vec3(2.22, 0.18, 0.34),
        position=Vec3(0.0, -0.03, 2.28),
    )
    add_car_part(
        parent=car,
        name="car_bumper_rear",
        model="cube",
        color_value=color_module.dark_gray,
        scale=Vec3(2.14, 0.18, 0.34),
        position=Vec3(0.0, -0.03, -2.28),
    )

    # Side skirts.
    for x_pos in (-1.04, 1.04):
        side_name = side_label(x_pos)
        add_car_part(
            parent=car,
            name=f"car_skirt_{side_name}",
            model="cube",
            color_value=color_module.dark_gray,
            scale=Vec3(0.11, 0.19, 2.85),
            position=Vec3(x_pos, -0.03, 0.02),
        )

    # Front headlights and rear lights.
    for x_pos in (-0.72, 0.72):
        side_name = side_label(x_pos)
        add_car_part(
            parent=car,
            name=f"car_headlight_{side_name}",
            model="sphere",
            color_value=color_module.yellow,
            scale=Vec3(0.24, 0.24, 0.24),
            position=Vec3(x_pos, 0.15, 2.24),
        )
        add_car_part(
            parent=car,
            name=f"car_taillight_{side_name}",
            model="sphere",
            color_value=color_module.red,
            scale=Vec3(0.22, 0.22, 0.22),
            position=Vec3(x_pos, 0.18, -2.23),
        )

    # Mirrors.
    for x_pos in (-1.05, 1.05):
        side_name = side_label(x_pos)
        add_car_part(
            parent=car,
            name=f"car_mirror_arm_{side_name}",
            model="cube",
            color_value=color_module.gray,
            scale=Vec3(0.09, 0.18, 0.09),
            position=Vec3(x_pos, 0.61, 0.46),
        )
        add_car_part(
            parent=car,
            name=f"car_mirror_cap_{side_name}",
            model="cube",
            color_value=color_module.light_gray,
            scale=Vec3(0.16, 0.07, 0.2),
            position=Vec3(x_pos * 1.02, 0.67, 0.46),
        )

    # Rear spoiler.
    for x_pos in (-0.56, 0.56):
        side_name = side_label(x_pos)
        add_car_part(
            parent=car,
            name=f"car_spoiler_post_{side_name}",
            model="cube",
            color_value=color_module.dark_gray,
            scale=Vec3(0.12, 0.32, 0.12),
            position=Vec3(x_pos, 0.62, -1.96),
        )
    add_car_part(
        parent=car,
        name="car_spoiler_wing",
        model="cube",
        color_value=color_module.dark_gray,
        scale=Vec3(1.42, 0.08, 0.28),
        position=Vec3(0.0, 0.74, -1.96),
    )

    # Wheels, hubs, and wheel bars.
    wheel_offsets = ((-1.12, 1.55), (1.12, 1.55), (-1.12, -1.55), (1.12, -1.55))
    for x_pos, z_pos in wheel_offsets:
        wheel_name = wheel_label(x_pos, z_pos)
        add_car_part(
            parent=car,
            name=f"car_wheel_tire_{wheel_name}",
            model="sphere",
            color_value=color_module.black,
            scale=Vec3(0.62, 0.62, 0.62),
            position=Vec3(x_pos, -0.22, z_pos),
        )
        add_car_part(
            parent=car,
            name=f"car_wheel_hub_{wheel_name}",
            model="sphere",
            color_value=color_module.light_gray,
            scale=Vec3(0.28, 0.28, 0.28),
            position=Vec3(x_pos, -0.22, z_pos),
        )
        add_car_part(
            parent=car,
            name=f"car_wheel_bar_{wheel_name}",
            model="cube",
            color_value=color_module.dark_gray,
            scale=Vec3(0.72, 0.12, 0.16),
            position=Vec3(x_pos, -0.22, z_pos),
        )

    return car


def normalize_loaded_car_model(model: object) -> None:
    """Scale and center imported car mesh to a consistent gameplay size."""
    get_tight_bounds = getattr(model, "getTightBounds", None)
    set_scale = getattr(model, "setScale", None)
    set_pos = getattr(model, "setPos", None)
    if not callable(get_tight_bounds):
        return
    if not callable(set_scale) or not callable(set_pos):
        return

    bounds = cast("tuple[Vec3, Vec3] | None", get_tight_bounds())
    if bounds is None:
        return

    min_point, max_point = bounds
    size_x = float(max_point.x - min_point.x)
    size_z = float(max_point.z - min_point.z)
    base_length = max(size_x, size_z)
    if base_length <= 0.0:
        return

    scale_factor = CAR_TARGET_LENGTH / base_length
    set_scale(scale_factor)
    set_pos(
        -(float(min_point.x) + size_x * 0.5) * scale_factor,
        -float(min_point.y) * scale_factor,
        -(float(min_point.z) + size_z * 0.5) * scale_factor,
    )


def spawn_imported_player() -> Entity | None:
    """Try to spawn imported car model and return None on load failure."""
    if not CAR_MODEL_FILE.exists():
        return None

    loader = getattr(getattr(application, "base", None), "loader", None)
    if loader is None:
        return None

    with suppress(Exception):
        model = loader.loadModel(str(CAR_MODEL_FILE))
        is_empty_callable = getattr(model, "isEmpty", None)
        is_empty = bool(is_empty_callable()) if callable(is_empty_callable) else False
        if is_empty:
            return None

        # Imported OBJ has inverted winding in this asset pack.
        panda3d_core = importlib.import_module("panda3d.core")
        cull_face_attrib = getattr(panda3d_core, "CullFaceAttrib", None)
        if cull_face_attrib is not None:
            model.setAttrib(cull_face_attrib.makeReverse())

        normalize_loaded_car_model(model)

        car = Entity(
            name="player_car_imported_root",
            model=model,
            position=Vec3(0.0, 0.0, 0.0),
        )
        if CAR_BASE_TEXTURE_FILE.exists():
            car.texture = CAR_BASE_TEXTURE_PATH
        return mark_lit_shadowed(car)

    return None


def spawn_player() -> Entity:
    """Spawn the external car model when available, else use fallback."""
    imported_player = spawn_imported_player()
    if imported_player is not None:
        return imported_player
    return spawn_primitive_player()


def compute_prop_mass(scale: Vec3) -> float:
    """Approximate prop mass from visual volume."""
    volume = max(0.1, float(scale.x) * float(scale.y) * float(scale.z))
    return max(0.6, volume)


def blueprint_to_dynamic_prop(
    entity: Entity,
    blueprint: EntityBlueprint,
) -> DynamicProp:
    """Create dynamic-physics state for a spawned scene entity."""
    scale = Vec3(blueprint.scale.x, blueprint.scale.y, blueprint.scale.z)
    radius = max(scale.x, scale.z) * 0.5
    return DynamicProp(
        entity=entity,
        velocity=Vec3(0.0, 0.0, 0.0),
        radius=radius,
        mass=compute_prop_mass(scale),
    )


def configure_camera() -> None:
    """Set up the camera for third-person orbit controls."""
    camera.parent = scene
    camera.rotation = Vec3(0.0, 0.0, 0.0)


def create_camera_orbit_rig(settings: GameSettings) -> OrbitRig:
    """Create yaw/pitch pivots used for stable camera orbit."""
    yaw_pivot = Entity(name="camera_yaw_pivot", parent=scene)
    pitch_pivot = Entity(name="camera_pitch_pivot", parent=yaw_pivot)
    camera.parent = pitch_pivot
    camera.position = Vec3(0.0, 0.0, -settings.camera.distance)
    camera.rotation = Vec3(0.0, 0.0, 0.0)
    return OrbitRig(yaw_pivot=yaw_pivot, pitch_pivot=pitch_pivot)


def configure_mouse_capture() -> None:
    """Capture the mouse cursor for look controls."""
    mouse.locked = True
    mouse.visible = False


def create_controls_hint() -> Text:
    """Render controls help text and return its entity."""
    return Text(
        name="controls_hint_text",
        text=(
            "Move: arrow keys (forward/back + strafe)\n"
            "Turn: page up/down + mouse (captured)\n"
            "Zoom: mouse wheel\n"
            "Camera: c / gamepad dpad left (orbit/chase)\n"
            "UI: u toggle controls\n"
            "Zoom pad: gamepad dpad up/down\n"
            "Controller: R2/L2 gas-brake, L1/R1 strafe, LS steer, RS look"
        ),
        x=-0.86,
        y=0.47,
        scale=0.9,
        background=True,
    )


def configure_lighting(focus_entity: Entity) -> None:
    """Create one shadow-casting sun light and stable local shadow bounds."""
    sun_direction = Vec3(0.8, -1.2, -0.5).normalized()
    key_light = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(4096, 4096))
    key_light.color = color_module.white
    key_light.look_at(sun_direction)

    ambient_light = AmbientLight()
    ambient_light.color = color_module.rgba(0.22, 0.24, 0.28, 1.0)

    scene.set_shader_input("shadow_color", color_module.black66)
    scene.set_shader_input("shadow_blur", 0.0008)
    scene.set_shader_input("shadow_bias", 0.0005)
    scene.set_shader_input("shadow_samples", 3)

    shadow_bounds = Entity(
        name="shadow_bounds_focus",
        parent=focus_entity,
        model="cube",
        position=Vec3(0.0, 0.0, 0.0),
        scale=Vec3(38.0, 20.0, 38.0),
        color=color_module.clear,
        unlit=True,
    )
    key_light.update_bounds(shadow_bounds)

    shadow_controller = Entity(name="shadow_bounds_controller")

    def update_shadow_bounds() -> None:
        key_light.update_bounds(shadow_bounds)

    shadow_controller.update = update_shadow_bounds


def compute_keyboard_axes(held: dict[str, float]) -> tuple[float, float, float]:
    """Compute movement axes from the current held-key mapping."""
    forward_amount = held.get("up arrow", 0.0) - held.get("down arrow", 0.0)
    strafe_amount = held.get("right arrow", 0.0) - held.get("left arrow", 0.0)
    turn_amount = held.get("page down", 0.0) - held.get("page up", 0.0)
    return forward_amount, strafe_amount, turn_amount


def apply_deadzone(value: float, deadzone: float = GAMEPAD_DEADZONE) -> float:
    """Clamp small analog stick/trigger noise to zero."""
    if abs(value) < deadzone:
        return 0.0
    return value


def compute_gamepad_axes(
    held: dict[str, float],
) -> tuple[float, float, float, float, float]:
    """Map gamepad triggers/sticks to movement and camera look inputs."""
    forward_amount = apply_deadzone(
        held.get("gamepad right trigger", 0.0) - held.get("gamepad left trigger", 0.0),
    )
    strafe_amount = held.get("gamepad right shoulder", 0.0) - held.get(
        "gamepad left shoulder",
        0.0,
    )
    turn_amount = apply_deadzone(held.get("gamepad left stick x", 0.0))
    look_x = apply_deadzone(held.get("gamepad right stick x", 0.0))
    look_y = apply_deadzone(held.get("gamepad right stick y", 0.0))
    return (
        forward_amount,
        strafe_amount,
        turn_amount,
        look_x * GAMEPAD_LOOK_SENSITIVITY,
        look_y * GAMEPAD_LOOK_SENSITIVITY,
    )


def dominant_axis(primary: float, secondary: float) -> float:
    """Return the stronger of two axis sources by absolute value."""
    return primary if abs(primary) >= abs(secondary) else secondary


def compute_control_axes(
    held: dict[str, float],
    mouse_velocity: Vec3,
) -> tuple[float, float, float, Vec3]:
    """Combine keyboard, gamepad, and mouse into one control vector set."""
    keyboard_forward, keyboard_strafe, keyboard_turn = compute_keyboard_axes(held)
    gamepad_forward, gamepad_strafe, gamepad_turn, gamepad_look_x, gamepad_look_y = (
        compute_gamepad_axes(held)
    )
    return (
        dominant_axis(keyboard_forward, gamepad_forward),
        dominant_axis(keyboard_strafe, gamepad_strafe),
        dominant_axis(keyboard_turn, gamepad_turn),
        Vec3(
            dominant_axis(mouse_velocity.x, gamepad_look_x),
            dominant_axis(mouse_velocity.y, gamepad_look_y),
            0.0,
        ),
    )


def compute_look_angles(
    yaw_angle: float,
    pitch_angle: float,
    mouse_velocity: Vec3,
    mouse_look_speed: float,
) -> tuple[float, float]:
    """Update yaw and pitch from mouse input and clamp pitch."""
    next_yaw = yaw_angle + (mouse_velocity.x * mouse_look_speed)
    next_pitch = pitch_angle + (mouse_velocity.y * mouse_look_speed)
    next_pitch = max(-90.0, min(90.0, next_pitch))
    return next_yaw, next_pitch


def compute_zoom_distance(
    current_distance: float,
    scroll_direction: int,
    min_distance: float,
    max_distance: float | None,
    zoom_step: float,
) -> float:
    """Adjust and clamp camera zoom distance from scroll input."""
    next_distance = current_distance - (scroll_direction * zoom_step)
    if max_distance is None:
        return max(min_distance, next_distance)

    return max(min_distance, min(max_distance, next_distance))


def compute_smoothed_forward_speed(
    current_speed: float,
    forward_input: float,
    max_speed: float,
    dt: float,
) -> float:
    """Compute smooth forward speed from digital/analog acceleration input."""
    if dt <= 0.0:
        return current_speed

    target_speed = forward_input * max_speed
    if target_speed == 0.0:
        response_rate = FORWARD_DECELERATION_RATE
    elif current_speed == 0.0 or (target_speed * current_speed) > 0.0:
        if abs(target_speed) >= abs(current_speed):
            response_rate = FORWARD_ACCELERATION_RATE
        else:
            response_rate = FORWARD_DECELERATION_RATE
    else:
        response_rate = FORWARD_BRAKE_RATE

    return cast(
        "float",
        lerp_exponential_decay(current_speed, target_speed, dt * response_rate),
    )


def compute_player_velocity(
    current_position: Vec3,
    previous_position: Vec3,
    dt: float,
) -> Vec3:
    """Compute frame velocity from two positions and a delta time."""
    if dt <= 0.0:
        return Vec3(0.0, 0.0, 0.0)

    inverse_dt = 1.0 / dt
    return Vec3(
        (current_position.x - previous_position.x) * inverse_dt,
        (current_position.y - previous_position.y) * inverse_dt,
        (current_position.z - previous_position.z) * inverse_dt,
    )


def trigger_impact_rumble(player_speed: float) -> None:
    """Trigger brief gamepad rumble on impact, if a controller exists."""
    if player_speed <= MIN_IMPACT_SPEED:
        return

    rumble_strength = max(0.2, min(0.9, player_speed / 18.0))
    with suppress(Exception):
        gamepad_module = importlib.import_module("ursina.gamepad")
        vibrate = getattr(gamepad_module, "vibrate", None)
        if callable(vibrate):
            vibrate(
                low_freq_motor=rumble_strength,
                high_freq_motor=min(1.0, (rumble_strength * 0.8) + 0.1),
                duration=0.08,
            )


def resolve_ground_contact(
    position_y: float,
    velocity_y: float,
    radius: float,
) -> tuple[float, float]:
    """Clamp a prop above ground and bounce vertical velocity."""
    if position_y >= radius:
        return position_y, velocity_y

    next_y = radius
    next_velocity_y = velocity_y
    if velocity_y < 0.0:
        next_velocity_y = -velocity_y * BOUNCE_DAMPING
        if abs(next_velocity_y) < MIN_BOUNCE_SPEED:
            next_velocity_y = 0.0

    return next_y, next_velocity_y


def install_prop_physics_controller(player: Entity, props: list[DynamicProp]) -> Entity:
    """Attach simple prop physics and player impact responses."""
    controller = Entity(name="prop_physics_controller")
    previous_player_position = Vec3(player.position)
    last_rumble_time = 0.0

    def controller_update() -> None:
        nonlocal previous_player_position, last_rumble_time

        dt = get_frame_dt()
        player_velocity = compute_player_velocity(
            player.position,
            previous_player_position,
            dt,
        )
        previous_player_position = Vec3(player.position)

        for prop in props:
            prop.velocity.y -= 9.81 * dt

            to_prop = prop.entity.position - player.position
            distance = to_prop.length()
            impact_radius = CAR_IMPACT_RADIUS + prop.radius
            player_speed = player_velocity.length()
            if distance < impact_radius and player_speed > MIN_IMPACT_SPEED:
                push_dir = (
                    to_prop.normalized()
                    if distance > NORMALIZE_EPSILON
                    else player.forward
                )
                penetration = impact_radius - distance
                if penetration > 0.0:
                    prop.entity.position += push_dir * (penetration * 0.4)
                prop.velocity += push_dir * (player_speed * (0.8 / prop.mass))
                prop.velocity.y = max(prop.velocity.y, 1.6)

                now = monotonic()
                if now - last_rumble_time >= RUMBLE_COOLDOWN_SECONDS:
                    trigger_impact_rumble(player_speed)
                    last_rumble_time = now

            prop.entity.position += prop.velocity * dt

            next_y, next_velocity_y = resolve_ground_contact(
                prop.entity.y,
                prop.velocity.y,
                prop.radius,
            )
            prop.entity.y = next_y
            prop.velocity.y = next_velocity_y
            if next_y <= prop.radius + 0.001:
                prop.velocity.x *= GROUND_FRICTION
                prop.velocity.z *= GROUND_FRICTION

    controller.update = controller_update
    return controller


def install_movement_controller(
    player: Entity,
    orbit_rig: OrbitRig,
    settings: GameSettings,
    controls_hint: Text,
) -> Entity:
    """Attach per-frame movement handling to a controller entity."""
    controller = Entity(name="player_input_controller")
    control_state = OrbitControlState(
        yaw_angle=player.rotation_y,
        pitch_angle=18.0,
        camera_distance=settings.camera.distance,
    )

    def controller_update() -> None:
        apply_player_input(
            player,
            orbit_rig,
            settings.movement,
            settings.camera,
            control_state,
        )

    def controller_input(key: str) -> None:
        if key == "escape":
            application.quit()

        if key == "u":
            controls_hint.enabled = not controls_hint.enabled

        if key in CAMERA_TOGGLE_KEYS:
            control_state.chase_camera_enabled = not control_state.chase_camera_enabled
            if control_state.chase_camera_enabled:
                camera.parent = scene
            else:
                camera.parent = orbit_rig.pitch_pivot
                camera.position = Vec3(0.0, 0.0, -control_state.camera_distance)
                camera.rotation = Vec3(0.0, 0.0, 0.0)

        scroll_direction = SCROLL_DIRECTION_BY_KEY.get(key)
        if scroll_direction is None:
            return

        control_state.camera_distance = compute_zoom_distance(
            control_state.camera_distance,
            scroll_direction=scroll_direction,
            min_distance=settings.camera.min_distance,
            max_distance=settings.camera.max_distance,
            zoom_step=settings.camera.zoom_step,
        )

    controller.update = controller_update
    controller.input = controller_input
    return controller


def apply_player_input(
    player: Entity,
    orbit_rig: OrbitRig,
    movement_settings: MovementSettings,
    camera_settings: CameraSettings,
    control_state: OrbitControlState,
) -> None:
    """Apply keyboard movement and rotation to the player."""
    held = cast("dict[str, float]", getattr(ursina, "held_keys", {}))
    mouse_velocity = cast("Vec3", getattr(mouse, "velocity", Vec3(0.0, 0.0, 0.0)))
    forward_amount, strafe_amount, turn_amount, look_velocity = compute_control_axes(
        held,
        mouse_velocity,
    )

    dt = get_frame_dt()
    max_forward_speed = movement_settings.move_speed * FORWARD_MAX_SPEED_MULTIPLIER
    control_state.forward_speed = compute_smoothed_forward_speed(
        control_state.forward_speed,
        forward_amount,
        max_forward_speed,
        dt,
    )
    player.position += player.forward * (control_state.forward_speed * dt)
    player.position += player.right * (
        strafe_amount * movement_settings.move_speed * dt
    )
    player.rotation_y += turn_amount * movement_settings.turn_speed * dt

    if control_state.chase_camera_enabled:
        target_position = (
            player.world_position
            - (player.forward * control_state.camera_distance)
            + Vec3(0.0, camera_settings.height + CHASE_CAMERA_HEIGHT_OFFSET, 0.0)
        )
        camera.world_position = cast(
            "Vec3",
            lerp_exponential_decay(
                camera.world_position,
                target_position,
                dt * CHASE_CAMERA_FOLLOW_SPEED,
            ),
        )
        camera.look_at(
            player.world_position
            + (player.forward * CHASE_CAMERA_LOOK_AHEAD)
            + Vec3(0.0, camera_settings.height * 0.5, 0.0),
        )
        camera.rotation_z = 0.0
        return

    control_state.yaw_angle, control_state.pitch_angle = compute_look_angles(
        control_state.yaw_angle,
        control_state.pitch_angle,
        look_velocity,
        camera_settings.mouse_look_speed,
    )

    orbit_rig.yaw_pivot.world_position = player.world_position + Vec3(
        0.0,
        camera_settings.height,
        0.0,
    )
    orbit_rig.yaw_pivot.rotation = Vec3(0.0, control_state.yaw_angle, 0.0)
    orbit_rig.pitch_pivot.rotation = Vec3(control_state.pitch_angle, 0.0, 0.0)
    camera.position = Vec3(0.0, 0.0, -control_state.camera_distance)
    camera.rotation_z = 0.0


def spawn_world_entities() -> list[DynamicProp]:
    """Spawn static scene entities and return dynamic-physics props."""
    dynamic_props: list[DynamicProp] = []
    for blueprint in starter_scene_blueprints():
        entity = spawn_entity(blueprint)
        if blueprint.is_dynamic:
            dynamic_props.append(blueprint_to_dynamic_prop(entity, blueprint))
    return dynamic_props


def run_game(settings: GameSettings | None = None) -> None:
    """Run the Ursina starter sandbox."""
    active_settings = GameSettings() if settings is None else settings
    app = cast("object", Ursina(development_mode=active_settings.development_mode))
    application.asset_folder = Path(__file__).resolve().parents[2]

    configure_window(active_settings)

    dynamic_props = spawn_world_entities()

    player = spawn_player()
    configure_camera()
    orbit_rig = create_camera_orbit_rig(active_settings)
    configure_mouse_capture()
    controls_hint = create_controls_hint()
    configure_lighting(player)
    install_movement_controller(player, orbit_rig, active_settings, controls_hint)
    install_prop_physics_controller(player, dynamic_props)

    Sky()
    # Ursina's app proxy is typed as object here, so dynamic access is needed.
    run_callable = getattr(app, "run")  # noqa: B009  # B009: getattr-with-constant
    run_callable()
