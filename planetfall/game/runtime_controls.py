"""Control and movement helper functions for runtime systems."""

from math import cos, radians, sin
from typing import cast

from ursina import Vec3, lerp_exponential_decay

GAMEPAD_DEADZONE = 0.08
GAMEPAD_LOOK_SENSITIVITY = 0.012


def apply_deadzone(value: float, deadzone: float = GAMEPAD_DEADZONE) -> float:
    """Clamp tiny analog controller drift to zero."""
    if abs(value) < deadzone:
        return 0.0
    return value


def dominant_axis(primary: float, secondary: float) -> float:
    """Return the stronger of two axis sources by absolute value."""
    return primary if abs(primary) >= abs(secondary) else secondary


def compute_keyboard_axes(
    held: dict[str, float],
) -> tuple[float, float, float, float]:
    """Map keyboard state to movement, dive, and yaw-turn axes."""
    keyboard_yaw_axis = (
        held.get("e", 0.0)
        + held.get("page down", 0.0)
        - held.get("q", 0.0)
        - held.get("page up", 0.0)
    )
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
    return x_axis, z_axis, dive_axis, keyboard_yaw_axis


def compute_gamepad_axes(
    held: dict[str, float],
) -> tuple[float, float, float, float, float, float]:
    """Map gamepad sticks/triggers and shoulders to control axes."""
    shoulder_yaw_axis = held.get("gamepad right shoulder", 0.0) - held.get(
        "gamepad left shoulder",
        0.0,
    )
    stick_x = apply_deadzone(held.get("gamepad left stick x", 0.0))
    stick_y = apply_deadzone(held.get("gamepad left stick y", 0.0))
    x_axis = stick_x
    z_axis = stick_y
    dive_axis = apply_deadzone(
        held.get("gamepad right trigger", 0.0) - held.get("gamepad left trigger", 0.0),
    )
    look_x = apply_deadzone(held.get("gamepad right stick x", 0.0))
    look_y = apply_deadzone(held.get("gamepad right stick y", 0.0))
    return (
        x_axis,
        z_axis,
        dive_axis,
        shoulder_yaw_axis,
        look_x * GAMEPAD_LOOK_SENSITIVITY,
        look_y * GAMEPAD_LOOK_SENSITIVITY,
    )


def compute_control_axes(
    held: dict[str, float],
    mouse_velocity: Vec3,
) -> tuple[float, float, float, float, Vec3]:
    """Combine keyboard, gamepad, and mouse into one control vector set."""
    keyboard_x, keyboard_z, keyboard_dive, keyboard_yaw = compute_keyboard_axes(held)
    gamepad_x, gamepad_z, gamepad_dive, gamepad_yaw, gamepad_look_x, gamepad_look_y = (
        compute_gamepad_axes(held)
    )
    return (
        dominant_axis(keyboard_x, gamepad_x),
        dominant_axis(keyboard_z, gamepad_z),
        dominant_axis(keyboard_dive, gamepad_dive),
        dominant_axis(keyboard_yaw, gamepad_yaw),
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


def rotate_planar_velocity_by_yaw(
    *,
    right_speed: float,
    forward_speed: float,
    yaw_degrees: float,
) -> tuple[float, float]:
    """Convert camera-relative planar speed into world-space x/z speed."""
    yaw_radians = radians(yaw_degrees)
    right_x = cos(yaw_radians)
    right_z = -sin(yaw_radians)
    forward_x = sin(yaw_radians)
    forward_z = cos(yaw_radians)
    return (
        (right_speed * right_x) + (forward_speed * forward_x),
        (right_speed * right_z) + (forward_speed * forward_z),
    )


def lerp_scalar(start_value: float, end_value: float, factor: float) -> float:
    """Linearly interpolate between two scalar values."""
    return start_value + ((end_value - start_value) * factor)


# PLR0913: too-many-arguments; explicit inputs.
def compute_smoothed_lateral_speed(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    current_speed: float,
    axis_input: float,
    max_speed: float,
    acceleration_rate: float,
    deceleration_rate: float,
    dt: float,
) -> float:
    # R0913: explicit tuning inputs.
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


# PLR0913: too-many-arguments; explicit inputs.
def compute_look_angles(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    yaw_angle: float,
    pitch_angle: float,
    look_velocity: Vec3,
    mouse_look_speed: float,
    min_pitch: float,
    max_pitch: float,
) -> tuple[float, float]:
    # R0913: explicit tuning inputs.
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
