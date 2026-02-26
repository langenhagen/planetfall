"""Procedural blueprint helpers for the endless falling course."""

from dataclasses import dataclass
from functools import lru_cache
from math import atan2, cos, sin, sqrt, tau
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random
else:  # pragma: no cover - runtime fallback for deferred annotations.
    Random = object

TUNNEL_WIDTH_SCALE = 1.5  # Master width multiplier for lanes and formations.
LANE_POSITIONS = (
    -6.0 * TUNNEL_WIDTH_SCALE,
    -3.0 * TUNNEL_WIDTH_SCALE,
    0.0,
    3.0 * TUNNEL_WIDTH_SCALE,
    6.0 * TUNNEL_WIDTH_SCALE,
)
BAND_SPACING = 18.0  # Vertical distance between generated gameplay bands.
COIN_SCORE_VALUE = 10  # Standard coin value.
HIGH_VALUE_COIN_SCORE_VALUE = 25  # Bonus coin value (halo-highlighted).
MAX_COLLIDABLE_ABS = 6.0 * TUNNEL_WIDTH_SCALE  # Clamp for obstacle/coin placement.
DECOR_RING_RADIUS = 10.5 * TUNNEL_WIDTH_SCALE  # Radius for non-collidable ambience.
PATTERN_CHICANE = 2  # Pattern index for alternating dual-row gates.
PATTERN_RING_GAP = 3  # Pattern index for ring obstacle with one open sector.
# Small-length guard to avoid divide-by-zero normalization.
PATH_DIRECTION_EPSILON = 1e-4
RING_GAP_ANGLE_THRESHOLD = 0.52  # Angular width of the safe opening in ring patterns.
BONUS_ARC_SIDE_SPLIT = 0.5  # 50/50 chance for bonus arc on left or right side.


@dataclass(frozen=True, slots=True)
class Vec3:
    """Simple 3D vector data container."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class FallingBlueprint:
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
) -> tuple[FallingBlueprint, ...]:
    """Build one designed band with chained coins and structured obstacles."""
    blueprints: list[FallingBlueprint] = []
    blueprints.extend(
        _decor_shards_blueprints(y_position=y_position, band_index=band_index),
    )
    blueprints.extend(
        _coin_chain_blueprints(y_position=y_position, band_index=band_index),
    )

    pattern = band_index % 5
    if pattern == 0:
        blueprints.extend(
            _gate_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    elif pattern == 1:
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
    else:
        blueprints.extend(
            _comet_pattern_blueprints(y_position=y_position, band_index=band_index),
        )

    if band_index % 7 == 0:
        blueprints.extend(
            _bonus_coin_arc_blueprints(
                y_position=y_position,
                band_index=band_index,
                rng=rng,
            ),
        )

    return tuple(blueprints)


@lru_cache(maxsize=1024)
def _path_center(band_index: int) -> Vec3:
    angle = band_index * 0.37
    radius = (3.6 + (sin(band_index * 0.19) * 1.2)) * TUNNEL_WIDTH_SCALE
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


def _angular_distance(angle_a: float, angle_b: float) -> float:
    delta = abs((angle_a - angle_b) % tau)
    return min(delta, tau - delta)


def _obstacle_blueprint(
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    scale: Vec3,
    color_name: str = "orange",
) -> FallingBlueprint:
    return FallingBlueprint(
        name=name,
        entity_kind="obstacle",
        model="cube",
        color_name=color_name,
        scale=scale,
        position=Vec3(
            _clamp_collidable_axis(x_pos),
            y_pos,
            _clamp_collidable_axis(z_pos),
        ),
        collision_radius=max(scale.x, scale.y, scale.z) * 0.45,
    )


def _coin_blueprint(
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    score_value: int = COIN_SCORE_VALUE,
    color_name: str = "yellow",
) -> FallingBlueprint:
    return FallingBlueprint(
        name=name,
        entity_kind="coin",
        model="sphere",
        color_name=color_name,
        scale=Vec3(0.72, 0.72, 0.72),
        position=Vec3(
            _clamp_collidable_axis(x_pos),
            y_pos,
            _clamp_collidable_axis(z_pos),
        ),
        collision_radius=0.45,
        score_value=score_value,
    )


def _decor_shards_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[FallingBlueprint, ...]:
    first_angle = (band_index * 0.23) % tau
    second_angle = (first_angle + (tau * 0.5)) % tau
    return (
        FallingBlueprint(
            name="decor_shard_primary",
            entity_kind="decor",
            model="cube",
            color_name="dark_gray",
            scale=Vec3(1.4, 0.45, 1.9),
            position=Vec3(
                cos(first_angle) * DECOR_RING_RADIUS,
                y_position + 0.55,
                sin(first_angle) * DECOR_RING_RADIUS,
            ),
        ),
        FallingBlueprint(
            name="decor_shard_secondary",
            entity_kind="decor",
            model="sphere",
            color_name="smoke",
            scale=Vec3(1.2, 1.2, 1.2),
            position=Vec3(
                cos(second_angle) * DECOR_RING_RADIUS,
                y_position - 0.35,
                sin(second_angle) * DECOR_RING_RADIUS,
            ),
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
            x_pos=center.x - (direction.x * 1.2 * TUNNEL_WIDTH_SCALE),
            y_pos=y_position + 0.4,
            z_pos=center.z - (direction.z * 1.2 * TUNNEL_WIDTH_SCALE),
        ),
        _coin_blueprint(
            name="coin_chain_center",
            x_pos=center.x,
            y_pos=y_position + 0.4,
            z_pos=center.z,
        ),
        _coin_blueprint(
            name="coin_chain_tail",
            x_pos=center.x + (direction.x * 1.2 * TUNNEL_WIDTH_SCALE),
            y_pos=y_position + 0.4,
            z_pos=center.z + (direction.z * 1.2 * TUNNEL_WIDTH_SCALE),
        ),
    ]

    if band_index % 2 == 0:
        blueprints.append(
            _coin_blueprint(
                name="coin_chain_side",
                x_pos=center.x + (side.x * 1.05 * TUNNEL_WIDTH_SCALE),
                y_pos=y_position + 0.65,
                z_pos=center.z + (side.z * 1.05 * TUNNEL_WIDTH_SCALE),
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
