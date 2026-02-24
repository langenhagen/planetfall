"""Procedural blueprint helpers for the endless falling course."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random
else:  # pragma: no cover - runtime fallback for deferred annotations.
    Random = object

LANE_POSITIONS = (-6.0, -3.0, 0.0, 3.0, 6.0)
BAND_SPACING = 18.0
FRAME_RADIUS = 11.0
COIN_SCORE_VALUE = 10


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


def band_y_position(
    *,
    start_y: float,
    band_index: int,
    spacing: float = BAND_SPACING,
) -> float:
    """Convert a sequential band index into a world-space y position."""
    return start_y - (band_index * spacing)


def build_fall_band_blueprints(
    *,
    band_index: int,
    y_position: float,
    rng: Random,
) -> tuple[FallingBlueprint, ...]:
    """Build one procedural band containing obstacles, coins, and decor."""
    blueprints: list[FallingBlueprint] = []
    blueprints.extend(_frame_blueprints(y_position=y_position))

    pattern = band_index % 4
    if pattern == 0:
        blueprints.extend(_gate_pattern_blueprints(y_position=y_position, rng=rng))
    elif pattern == 1:
        blueprints.extend(_slice_pattern_blueprints(y_position=y_position, rng=rng))
    elif pattern == 2:
        blueprints.extend(_slalom_pattern_blueprints(y_position=y_position, rng=rng))
    else:
        blueprints.extend(_coin_rain_blueprints(y_position=y_position, rng=rng))

    return tuple(blueprints)


def _frame_blueprints(*, y_position: float) -> tuple[FallingBlueprint, ...]:
    return (
        FallingBlueprint(
            name="frame_wall_left",
            entity_kind="decor",
            model="cube",
            color_name="dark_gray",
            scale=Vec3(0.65, 10.0, 24.0),
            position=Vec3(-FRAME_RADIUS, y_position, 0.0),
        ),
        FallingBlueprint(
            name="frame_wall_right",
            entity_kind="decor",
            model="cube",
            color_name="dark_gray",
            scale=Vec3(0.65, 10.0, 24.0),
            position=Vec3(FRAME_RADIUS, y_position, 0.0),
        ),
        FallingBlueprint(
            name="frame_wall_front",
            entity_kind="decor",
            model="cube",
            color_name="smoke",
            scale=Vec3(24.0, 10.0, 0.65),
            position=Vec3(0.0, y_position, -FRAME_RADIUS),
        ),
        FallingBlueprint(
            name="frame_wall_back",
            entity_kind="decor",
            model="cube",
            color_name="smoke",
            scale=Vec3(24.0, 10.0, 0.65),
            position=Vec3(0.0, y_position, FRAME_RADIUS),
        ),
    )


def _obstacle_blueprint(
    *,
    name: str,
    x_pos: float,
    y_pos: float,
    z_pos: float,
    scale: Vec3,
) -> FallingBlueprint:
    return FallingBlueprint(
        name=name,
        entity_kind="obstacle",
        model="cube",
        color_name="orange",
        scale=scale,
        position=Vec3(x_pos, y_pos, z_pos),
        collision_radius=max(scale.x, scale.y, scale.z) * 0.45,
    )


def _coin_blueprint(
    *, name: str, x_pos: float, y_pos: float, z_pos: float
) -> FallingBlueprint:
    return FallingBlueprint(
        name=name,
        entity_kind="coin",
        model="sphere",
        color_name="yellow",
        scale=Vec3(0.72, 0.72, 0.72),
        position=Vec3(x_pos, y_pos, z_pos),
        collision_radius=0.45,
        score_value=COIN_SCORE_VALUE,
    )


def _gate_pattern_blueprints(
    *, y_position: float, rng: Random
) -> tuple[FallingBlueprint, ...]:
    safe_lane_x = rng.choice(LANE_POSITIONS)
    blueprints: list[FallingBlueprint] = []

    for lane_x in LANE_POSITIONS:
        if lane_x == safe_lane_x:
            continue
        blueprints.append(
            _obstacle_blueprint(
                name=f"gate_obstacle_{int(lane_x)}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=0.0,
                scale=Vec3(2.4, 2.4, 2.4),
            ),
        )

    for coin_index, lane_z in enumerate((-4.0, 0.0, 4.0)):
        blueprints.append(
            _coin_blueprint(
                name=f"gate_coin_{coin_index}",
                x_pos=safe_lane_x,
                y_pos=y_position + 0.35,
                z_pos=lane_z,
            ),
        )

    return tuple(blueprints)


def _slice_pattern_blueprints(
    *, y_position: float, rng: Random
) -> tuple[FallingBlueprint, ...]:
    safe_lane_z = rng.choice(LANE_POSITIONS)
    blueprints: list[FallingBlueprint] = []

    for lane_z in LANE_POSITIONS:
        if lane_z == safe_lane_z:
            continue
        blueprints.append(
            _obstacle_blueprint(
                name=f"slice_obstacle_{int(lane_z)}",
                x_pos=0.0,
                y_pos=y_position,
                z_pos=lane_z,
                scale=Vec3(2.2, 2.2, 2.2),
            ),
        )

    for coin_index, lane_x in enumerate((-3.0, 0.0, 3.0)):
        blueprints.append(
            _coin_blueprint(
                name=f"slice_coin_{coin_index}",
                x_pos=lane_x,
                y_pos=y_position + 0.35,
                z_pos=safe_lane_z,
            ),
        )

    return tuple(blueprints)


def _slalom_pattern_blueprints(
    *, y_position: float, rng: Random
) -> tuple[FallingBlueprint, ...]:
    lane_count = len(LANE_POSITIONS)
    start_index = rng.randrange(lane_count)
    blueprints: list[FallingBlueprint] = []

    for step_index, lane_x in enumerate(LANE_POSITIONS):
        lane_z = LANE_POSITIONS[(start_index + step_index) % lane_count]
        blueprints.append(
            _obstacle_blueprint(
                name=f"slalom_obstacle_{step_index}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=lane_z,
                scale=Vec3(1.8, 1.8, 1.8),
            ),
        )

    for step_index, lane_x in enumerate(LANE_POSITIONS):
        lane_z = LANE_POSITIONS[(start_index + step_index + 2) % lane_count]
        blueprints.append(
            _coin_blueprint(
                name=f"slalom_coin_{step_index}",
                x_pos=lane_x,
                y_pos=y_position + 0.35,
                z_pos=lane_z,
            ),
        )

    return tuple(blueprints)


def _coin_rain_blueprints(
    *, y_position: float, rng: Random
) -> tuple[FallingBlueprint, ...]:
    blueprints: list[FallingBlueprint] = []
    corner_obstacles = ((-6.0, -6.0), (-6.0, 6.0), (6.0, -6.0), (6.0, 6.0))
    for obstacle_index, (x_pos, z_pos) in enumerate(corner_obstacles):
        blueprints.append(
            _obstacle_blueprint(
                name=f"coin_rain_corner_{obstacle_index}",
                x_pos=x_pos,
                y_pos=y_position,
                z_pos=z_pos,
                scale=Vec3(1.9, 1.9, 1.9),
            ),
        )

    coin_index = 0
    for lane_x in LANE_POSITIONS:
        for lane_z in (-6.0, 0.0, 6.0):
            blueprints.append(
                _coin_blueprint(
                    name=f"coin_rain_coin_{coin_index}",
                    x_pos=lane_x,
                    y_pos=y_position + 0.35,
                    z_pos=lane_z,
                ),
            )
            coin_index += 1

    if rng.random() < 0.6:
        blueprints.append(
            _obstacle_blueprint(
                name="coin_rain_center",
                x_pos=0.0,
                y_pos=y_position,
                z_pos=0.0,
                scale=Vec3(2.2, 2.2, 2.2),
            ),
        )

    return tuple(blueprints)
