"""Shared scene constants and blueprint helpers for patterns."""

from dataclasses import dataclass
from functools import lru_cache
from math import cos, sin, sqrt, tau

TUNNEL_WIDTH_SCALE = 3.8  # Master width multiplier for lanes and formations.
LANE_POSITIONS = (
    -7.5 * TUNNEL_WIDTH_SCALE,
    -3.75 * TUNNEL_WIDTH_SCALE,
    0.0,
    3.75 * TUNNEL_WIDTH_SCALE,
    7.5 * TUNNEL_WIDTH_SCALE,
)
BAND_SPACING = 20.0  # Vertical distance between generated gameplay bands.
COIN_SCORE_VALUE = 10  # Standard coin value.
HIGH_VALUE_COIN_SCORE_VALUE = 25  # Bonus coin value (halo-highlighted).
MAX_COLLIDABLE_ABS = 6.0 * TUNNEL_WIDTH_SCALE  # Clamp for obstacle/coin placement.
MAX_COIN_ABS = 5.0 * TUNNEL_WIDTH_SCALE  # Keep coin lanes slightly tighter.
OBSTACLE_DENSITY_MULTIPLIER = 0.9  # Reduce asteroid count by ~10%.
COIN_PATTERN_COUNT = 11
OBSTACLE_PATTERN_COUNT = 9
PATTERN_GATE = 0
PATTERN_SLALOM = 1
PATTERN_CHICANE = 2  # Pattern index for alternating dual-row gates.
PATTERN_RING_GAP = 3  # Pattern index for ring obstacle with one open sector.
PATTERN_COMET = 4
PATTERN_CHECKER = 5
PATTERN_SPIRAL = 6
PATTERN_ORBIT = 7
PATTERN_SCATTER = 8
# Small-length guard to avoid divide-by-zero normalization.
PATH_DIRECTION_EPSILON = 1e-4
RING_GAP_ANGLE_THRESHOLD = 0.52  # Angular width of the safe opening in ring patterns.
BONUS_ARC_SIDE_SPLIT = 0.5  # 50/50 chance for bonus arc on left or right side.
OBSTACLE_MODEL_NAME = "models/asteroids/Asteroid_1.obj"  # Asteroid hazards.
COIN_MODEL_NAME = "models/coins/coin.obj"  # Asset-backed coin pickup model.
COIN_CHAIN_FORWARD_OFFSET = 2.2  # Forward/back spacing within coin pickup line.
COIN_CHAIN_SIDE_OFFSET = 1.9  # Side coin offset for optional fourth pickup.


@dataclass(frozen=True, slots=True)
class Vec3:
    """Simple 3D vector data container."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class FallingBlueprint:  # pylint: disable=too-many-instance-attributes
    # R0902: blueprint bundles related fields.
    """Data-only description for spawning one falling-course entity."""

    name: str
    entity_kind: str
    model: str
    color_name: str
    scale: Vec3
    position: Vec3
    collision_radius: float = 0.0
    score_value: int = 0


@lru_cache(maxsize=1024)
def path_center(band_index: int) -> Vec3:
    """Return the center point for a given band index."""
    angle = band_index * 0.37
    radius = (4.2 + (sin(band_index * 0.19) * 1.6)) * TUNNEL_WIDTH_SCALE
    return Vec3(cos(angle) * radius, 0.0, sin(angle * 0.87) * radius)


@lru_cache(maxsize=1024)
def path_direction(band_index: int) -> Vec3:
    """Return the normalized direction vector of the path."""
    previous_point = path_center(band_index - 1)
    next_point = path_center(band_index + 1)
    delta_x = next_point.x - previous_point.x
    delta_z = next_point.z - previous_point.z
    length = sqrt((delta_x * delta_x) + (delta_z * delta_z))
    if length <= PATH_DIRECTION_EPSILON:
        return Vec3(1.0, 0.0, 0.0)
    return Vec3(delta_x / length, 0.0, delta_z / length)


def lane_snap(value: float) -> float:
    """Snap a value to the nearest lane coordinate."""
    return min(LANE_POSITIONS, key=lambda lane_value: abs(lane_value - value))


def clamp_collidable_axis(value: float) -> float:
    """Clamp obstacle positions to the collidable bounds."""
    return max(-MAX_COLLIDABLE_ABS, min(MAX_COLLIDABLE_ABS, value))


def clamp_coin_axis(value: float) -> float:
    """Clamp coin positions to the coin bounds."""
    return max(-MAX_COIN_ABS, min(MAX_COIN_ABS, value))


def angular_distance(angle_a: float, angle_b: float) -> float:
    """Compute the shortest distance between two angles."""
    delta = abs((angle_a - angle_b) % tau)
    return min(delta, tau - delta)


def obstacle_blueprint(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    scale: Vec3,
    color_name: str = "orange",
) -> FallingBlueprint:
    """Create a blueprint for an obstacle entity."""
    # R0913: explicit placement inputs.
    return FallingBlueprint(
        name=name,
        entity_kind="obstacle",
        model=OBSTACLE_MODEL_NAME,
        color_name=color_name,
        scale=scale,
        position=Vec3(
            clamp_collidable_axis(x_pos),
            y_pos,
            clamp_collidable_axis(z_pos),
        ),
        collision_radius=max(scale.x, scale.y, scale.z) * 0.55,
    )


def coin_blueprint(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    score_value: int = COIN_SCORE_VALUE,
    color_name: str = "yellow",
) -> FallingBlueprint:
    """Create a blueprint for a coin entity."""
    # R0913: explicit placement inputs.
    return FallingBlueprint(
        name=name,
        entity_kind="coin",
        model=COIN_MODEL_NAME,
        color_name=color_name,
        scale=Vec3(0.72, 0.72, 0.72),
        position=Vec3(
            clamp_coin_axis(x_pos),
            y_pos,
            clamp_coin_axis(z_pos),
        ),
        collision_radius=2.5,
        score_value=score_value,
    )
