"""Procedural blueprint helpers for the endless falling course."""

from dataclasses import dataclass
from functools import lru_cache
from math import atan2, cos, sin, sqrt, tau
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random
else:  # pragma: no cover - runtime fallback for deferred annotations.
    Random = object

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
COIN_PATTERN_COUNT = 5
OBSTACLE_PATTERN_COUNT = 7
PATTERN_GATE = 0
PATTERN_SLALOM = 1
PATTERN_CHICANE = 2  # Pattern index for alternating dual-row gates.
PATTERN_RING_GAP = 3  # Pattern index for ring obstacle with one open sector.
PATTERN_COMET = 4
PATTERN_CHECKER = 5
PATTERN_SPIRAL = 6
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


def build_fall_band_blueprints(
    *,
    band_index: int,
    y_position: float,
    rng: Random,
    coin_pattern_index: int = 0,
) -> tuple[FallingBlueprint, ...]:
    """Build one designed band with chained coins and structured obstacles."""
    blueprints: list[FallingBlueprint] = []
    coin_pattern = coin_pattern_index % COIN_PATTERN_COUNT
    if coin_pattern == 0:
        blueprints.extend(
            _coin_chain_blueprints(y_position=y_position, band_index=band_index),
        )
    elif coin_pattern == 1:
        blueprints.extend(
            _coin_wave_blueprints(y_position=y_position, band_index=band_index),
        )
    elif coin_pattern == 2:
        blueprints.extend(
            _coin_fan_blueprints(y_position=y_position, band_index=band_index),
        )
    elif coin_pattern == 3:
        blueprints.extend(
            _coin_ribbon_blueprints(y_position=y_position, band_index=band_index),
        )
    else:
        blueprints.extend(
            _coin_grid_blueprints(y_position=y_position, band_index=band_index),
        )

    pattern = band_index % OBSTACLE_PATTERN_COUNT
    if pattern == PATTERN_GATE:
        blueprints.extend(
            _gate_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == PATTERN_SLALOM:
        blueprints.extend(
            _slalom_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == PATTERN_CHICANE:
        blueprints.extend(
            _chicane_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == PATTERN_RING_GAP:
        blueprints.extend(
            _ring_gap_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == PATTERN_COMET:
        blueprints.extend(
            _comet_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == PATTERN_CHECKER:
        blueprints.extend(
            _checker_wall_pattern_blueprints(
                y_position=y_position,
                band_index=band_index,
            ),
        )
    else:
        blueprints.extend(
            _spiral_pattern_blueprints(y_position=y_position, band_index=band_index),
        )

    if band_index % 7 == 0:
        blueprints.extend(
            _bonus_coin_arc_blueprints(
                y_position=y_position,
                band_index=band_index,
                rng=rng,
            ),
        )

    if band_index % 4 == 0:
        blueprints.extend(
            _extra_asteroid_blueprints(y_position=y_position, band_index=band_index),
        )

    return tuple(_apply_obstacle_density(blueprints, rng))


@lru_cache(maxsize=1024)
def _path_center(band_index: int) -> Vec3:
    angle = band_index * 0.37
    radius = (4.2 + (sin(band_index * 0.19) * 1.6)) * TUNNEL_WIDTH_SCALE
    return Vec3(cos(angle) * radius, 0.0, sin(angle * 0.87) * radius)


@lru_cache(maxsize=1024)
def _path_direction(band_index: int) -> Vec3:
    previous_point = _path_center(band_index - 1)
    next_point = _path_center(band_index + 1)
    delta_x = next_point.x - previous_point.x
    delta_z = next_point.z - previous_point.z
    length = sqrt((delta_x * delta_x) + (delta_z * delta_z))
    if length <= PATH_DIRECTION_EPSILON:
        return Vec3(1.0, 0.0, 0.0)
    return Vec3(delta_x / length, 0.0, delta_z / length)


def _lane_snap(value: float) -> float:
    return min(LANE_POSITIONS, key=lambda lane_value: abs(lane_value - value))


def _clamp_collidable_axis(value: float) -> float:
    return max(-MAX_COLLIDABLE_ABS, min(MAX_COLLIDABLE_ABS, value))


def _clamp_coin_axis(value: float) -> float:
    return max(-MAX_COIN_ABS, min(MAX_COIN_ABS, value))


def _angular_distance(angle_a: float, angle_b: float) -> float:
    delta = abs((angle_a - angle_b) % tau)
    return min(delta, tau - delta)


def _obstacle_blueprint(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    scale: Vec3,
    color_name: str = "orange",
) -> FallingBlueprint:
    # R0913: explicit placement inputs.
    return FallingBlueprint(
        name=name,
        entity_kind="obstacle",
        model=OBSTACLE_MODEL_NAME,
        color_name=color_name,
        scale=scale,
        position=Vec3(
            _clamp_collidable_axis(x_pos),
            y_pos,
            _clamp_collidable_axis(z_pos),
        ),
        collision_radius=max(scale.x, scale.y, scale.z) * 0.55,
    )


def _apply_obstacle_density(
    blueprints: list[FallingBlueprint],
    rng: Random,
) -> list[FallingBlueprint]:
    obstacles = [
        blueprint for blueprint in blueprints if blueprint.entity_kind == "obstacle"
    ]
    if not obstacles:
        return blueprints

    reduced: list[FallingBlueprint] = []
    for blueprint in blueprints:
        if blueprint.entity_kind != "obstacle":
            reduced.append(blueprint)
            continue
        if rng.random() < OBSTACLE_DENSITY_MULTIPLIER:
            reduced.append(blueprint)

    if not any(blueprint.entity_kind == "obstacle" for blueprint in reduced):
        reduced.append(obstacles[0])

    return reduced


def _coin_blueprint(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    score_value: int = COIN_SCORE_VALUE,
    color_name: str = "yellow",
) -> FallingBlueprint:
    # R0913: explicit placement inputs.
    return FallingBlueprint(
        name=name,
        entity_kind="coin",
        model=COIN_MODEL_NAME,
        color_name=color_name,
        scale=Vec3(0.72, 0.72, 0.72),
        position=Vec3(
            _clamp_coin_axis(x_pos),
            y_pos,
            _clamp_coin_axis(z_pos),
        ),
        collision_radius=2.5,
        score_value=score_value,
    )


def _extra_asteroid_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    """Add extra in-lane asteroid hazards to increase field density."""
    center = _path_center(band_index)
    first_lane = LANE_POSITIONS[(band_index + 1) % len(LANE_POSITIONS)]
    second_lane = LANE_POSITIONS[(band_index + 3) % len(LANE_POSITIONS)]
    return (
        _obstacle_blueprint(
            name="extra_asteroid_a",
            x_pos=first_lane if band_index % 8 != 0 else second_lane,
            y_pos=y_position,
            z_pos=_lane_snap(center.z + (2.2 * TUNNEL_WIDTH_SCALE)),
            scale=Vec3(1.45, 1.45, 1.45),
            color_name="orange",
        ),
    )


def _coin_chain_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    direction = _path_direction(band_index)
    side = Vec3(-direction.z, 0.0, direction.x)

    blueprints = [
        _coin_blueprint(
            name="coin_chain_lead",
            x_pos=center.x - (direction.x * COIN_CHAIN_FORWARD_OFFSET),
            y_pos=y_position + 0.4,
            z_pos=center.z - (direction.z * COIN_CHAIN_FORWARD_OFFSET),
        ),
        _coin_blueprint(
            name="coin_chain_center",
            x_pos=center.x,
            y_pos=y_position + 0.4,
            z_pos=center.z,
        ),
        _coin_blueprint(
            name="coin_chain_tail",
            x_pos=center.x + (direction.x * COIN_CHAIN_FORWARD_OFFSET),
            y_pos=y_position + 0.4,
            z_pos=center.z + (direction.z * COIN_CHAIN_FORWARD_OFFSET),
        ),
    ]

    if band_index % 2 == 0:
        blueprints.append(
            _coin_blueprint(
                name="coin_chain_side",
                x_pos=center.x + (side.x * COIN_CHAIN_SIDE_OFFSET),
                y_pos=y_position + 0.65,
                z_pos=center.z + (side.z * COIN_CHAIN_SIDE_OFFSET),
            ),
        )

    return tuple(blueprints)


def _coin_wave_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    direction = _path_direction(band_index)
    side = Vec3(-direction.z, 0.0, direction.x)
    offsets = (-COIN_CHAIN_FORWARD_OFFSET, 0.0, COIN_CHAIN_FORWARD_OFFSET)
    blueprints: list[FallingBlueprint] = []

    for index, forward_offset in enumerate(offsets):
        lateral = (index - 1) * (COIN_CHAIN_SIDE_OFFSET * 0.75)
        blueprints.append(
            _coin_blueprint(
                name=f"coin_wave_{index}",
                x_pos=center.x + (direction.x * forward_offset) + (side.x * lateral),
                y_pos=y_position + 0.45,
                z_pos=center.z + (direction.z * forward_offset) + (side.z * lateral),
            ),
        )

    return tuple(blueprints)


def _coin_fan_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    direction = _path_direction(band_index)
    side = Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[FallingBlueprint] = []

    for index in range(5):
        spread = (index - 2) * (COIN_CHAIN_SIDE_OFFSET * 0.75)
        forward = (index - 2) * (COIN_CHAIN_FORWARD_OFFSET * 0.35)
        blueprints.append(
            _coin_blueprint(
                name=f"coin_fan_{index}",
                x_pos=center.x + (side.x * spread) + (direction.x * forward),
                y_pos=y_position + 0.55,
                z_pos=center.z + (side.z * spread) + (direction.z * forward),
            ),
        )

    return tuple(blueprints)


def _coin_ribbon_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    direction = _path_direction(band_index)
    side = Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[FallingBlueprint] = []
    offsets = (-2, -1, 0, 1, 2)

    for index, step in enumerate(offsets):
        forward = step * (COIN_CHAIN_FORWARD_OFFSET * 0.65)
        arc_phase = (index / max(1, len(offsets) - 1)) * tau * 0.35
        lateral = sin(arc_phase + (band_index * 0.2)) * (COIN_CHAIN_SIDE_OFFSET * 0.7)
        blueprints.append(
            _coin_blueprint(
                name=f"coin_ribbon_{index}",
                x_pos=center.x + (direction.x * forward) + (side.x * lateral),
                y_pos=y_position + 0.5,
                z_pos=center.z + (direction.z * forward) + (side.z * lateral),
            ),
        )

    return tuple(blueprints)


def _coin_grid_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    direction = _path_direction(band_index)
    side = Vec3(-direction.z, 0.0, direction.x)
    forward_offsets = (
        -COIN_CHAIN_FORWARD_OFFSET * 0.85,
        COIN_CHAIN_FORWARD_OFFSET * 0.85,
    )
    side_offsets = (
        -COIN_CHAIN_SIDE_OFFSET * 0.75,
        0.0,
        COIN_CHAIN_SIDE_OFFSET * 0.75,
    )
    blueprints: list[FallingBlueprint] = []

    for row_index, forward in enumerate(forward_offsets):
        for col_index, lateral in enumerate(side_offsets):
            blueprints.append(
                _coin_blueprint(
                    name=f"coin_grid_{row_index}_{col_index}",
                    x_pos=center.x + (direction.x * forward) + (side.x * lateral),
                    y_pos=y_position + 0.45 + (row_index * 0.08),
                    z_pos=center.z + (direction.z * forward) + (side.z * lateral),
                ),
            )

    return tuple(blueprints)


def _gate_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    path_center = _path_center(band_index)
    safe_lane_x = _lane_snap(path_center.x)
    row_z = _lane_snap(path_center.z * 0.45)
    blueprints: list[FallingBlueprint] = []

    for lane_x in LANE_POSITIONS:
        if lane_x == safe_lane_x:
            continue
        blueprints.append(
            _obstacle_blueprint(
                name=f"gate_block_{int(lane_x)}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=row_z,
                scale=Vec3(2.3, 2.3, 2.3),
                color_name="orange",
            ),
        )

    return tuple(blueprints)


def _slalom_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    shift = band_index % len(LANE_POSITIONS)
    safe_lane_x = _lane_snap(_path_center(band_index).x)
    blueprints: list[FallingBlueprint] = []

    for index, lane_x in enumerate(LANE_POSITIONS):
        lane_z = LANE_POSITIONS[(index + shift) % len(LANE_POSITIONS)]
        if lane_x == safe_lane_x:
            continue
        blueprints.append(
            _obstacle_blueprint(
                name=f"slalom_block_{index}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=lane_z,
                scale=Vec3(1.9, 1.9, 1.9),
                color_name="red",
            ),
        )

    return tuple(blueprints)


def _chicane_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    path_center = _path_center(band_index)
    row_a_z = _lane_snap(path_center.z + (2.4 * TUNNEL_WIDTH_SCALE))
    row_b_z = _lane_snap(path_center.z - (2.4 * TUNNEL_WIDTH_SCALE))
    open_a = _lane_snap(path_center.x - (3.0 * TUNNEL_WIDTH_SCALE))
    open_b = _lane_snap(path_center.x + (3.0 * TUNNEL_WIDTH_SCALE))
    blueprints: list[FallingBlueprint] = []

    for lane_x in LANE_POSITIONS:
        if lane_x != open_a:
            blueprints.append(
                _obstacle_blueprint(
                    name=f"chicane_row_a_{int(lane_x)}",
                    x_pos=lane_x,
                    y_pos=y_position,
                    z_pos=row_a_z,
                    scale=Vec3(2.0, 2.0, 2.0),
                    color_name="violet",
                ),
            )
        if lane_x != open_b:
            blueprints.append(
                _obstacle_blueprint(
                    name=f"chicane_row_b_{int(lane_x)}",
                    x_pos=lane_x,
                    y_pos=y_position,
                    z_pos=row_b_z,
                    scale=Vec3(2.0, 2.0, 2.0),
                    color_name="azure",
                ),
            )

    return tuple(blueprints)


def _ring_gap_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    path_center = _path_center(band_index)
    gap_angle = atan2(path_center.z, path_center.x)
    blueprints: list[FallingBlueprint] = []

    for index in range(10):
        angle = (tau / 10.0) * index
        if _angular_distance(angle, gap_angle) < RING_GAP_ANGLE_THRESHOLD:
            continue
        blueprints.append(
            _obstacle_blueprint(
                name=f"ring_block_{index}",
                x_pos=cos(angle) * (5.8 * TUNNEL_WIDTH_SCALE),
                y_pos=y_position,
                z_pos=sin(angle) * (5.8 * TUNNEL_WIDTH_SCALE),
                scale=Vec3(1.6, 1.6, 1.6),
                color_name="magenta",
            ),
        )

    return tuple(blueprints)


def _comet_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    base_angle = band_index * 0.35
    blueprints: list[FallingBlueprint] = []

    for index in range(4):
        angle = base_angle + (index * 0.58)
        blueprints.append(
            _obstacle_blueprint(
                name=f"comet_block_{index}",
                x_pos=cos(angle) * (5.5 * TUNNEL_WIDTH_SCALE),
                y_pos=y_position,
                z_pos=sin(angle) * (5.5 * TUNNEL_WIDTH_SCALE),
                scale=Vec3(1.8, 1.8, 1.8),
                color_name="brown",
            ),
        )

    return tuple(blueprints)


def _checker_wall_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    path_center = _path_center(band_index)
    row_a_z = _lane_snap(path_center.z + (1.8 * TUNNEL_WIDTH_SCALE))
    row_b_z = _lane_snap(path_center.z - (1.8 * TUNNEL_WIDTH_SCALE))
    blueprints: list[FallingBlueprint] = []

    for index, lane_x in enumerate(LANE_POSITIONS):
        if index % 2 == 0:
            row_z = row_a_z
            color_name = "lime"
            suffix = "a"
        else:
            row_z = row_b_z
            color_name = "turquoise"
            suffix = "b"
        blueprints.append(
            _obstacle_blueprint(
                name=f"checker_block_{suffix}_{index}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=row_z,
                scale=Vec3(1.9, 1.9, 1.9),
                color_name=color_name,
            ),
        )

    return tuple(blueprints)


def _spiral_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    base_angle = band_index * 0.32
    base_radius = 2.8 * TUNNEL_WIDTH_SCALE
    blueprints: list[FallingBlueprint] = []

    for index in range(6):
        angle = base_angle + (index * 0.75)
        radius = base_radius + (index * 0.4 * TUNNEL_WIDTH_SCALE)
        blueprints.append(
            _obstacle_blueprint(
                name=f"spiral_block_{index}",
                x_pos=cos(angle) * radius,
                y_pos=y_position,
                z_pos=sin(angle) * radius,
                scale=Vec3(1.7, 1.7, 1.7),
                color_name="pink",
            ),
        )

    return tuple(blueprints)


def _bonus_coin_arc_blueprints(
    *,
    y_position: float,
    band_index: int,
    rng: Random,
) -> tuple[FallingBlueprint, ...]:
    center = _path_center(band_index)
    side_sign = -1.0 if rng.random() < BONUS_ARC_SIDE_SPLIT else 1.0
    blueprints: list[FallingBlueprint] = []

    for index in range(3):
        lift = (index - 1) * (0.95 * TUNNEL_WIDTH_SCALE)
        blueprints.append(
            _coin_blueprint(
                name=f"bonus_arc_coin_{index}",
                x_pos=center.x
                + (side_sign * ((2.0 + (index * 0.6)) * TUNNEL_WIDTH_SCALE)),
                y_pos=y_position + 0.9,
                z_pos=center.z + lift,
                score_value=HIGH_VALUE_COIN_SCORE_VALUE,
                color_name="gold",
            ),
        )

    return tuple(blueprints)
