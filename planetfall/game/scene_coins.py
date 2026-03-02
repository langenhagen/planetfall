"""Coin pattern blueprints for the falling course."""

from math import cos, sin, tau
from random import Random

from planetfall.game import scene_base as base


def coin_chain_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a short straight chain of coins along the path."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)

    blueprints = [
        base.coin_blueprint(
            name="coin_chain_lead",
            x_pos=center.x - (direction.x * base.COIN_CHAIN_FORWARD_OFFSET),
            y_pos=y_position + 0.4,
            z_pos=center.z - (direction.z * base.COIN_CHAIN_FORWARD_OFFSET),
        ),
        base.coin_blueprint(
            name="coin_chain_center",
            x_pos=center.x,
            y_pos=y_position + 0.4,
            z_pos=center.z,
        ),
        base.coin_blueprint(
            name="coin_chain_tail",
            x_pos=center.x + (direction.x * base.COIN_CHAIN_FORWARD_OFFSET),
            y_pos=y_position + 0.4,
            z_pos=center.z + (direction.z * base.COIN_CHAIN_FORWARD_OFFSET),
        ),
    ]

    if band_index % 2 == 0:
        blueprints.append(
            base.coin_blueprint(
                name="coin_chain_side",
                x_pos=center.x + (side.x * base.COIN_CHAIN_SIDE_OFFSET),
                y_pos=y_position + 0.65,
                z_pos=center.z + (side.z * base.COIN_CHAIN_SIDE_OFFSET),
            ),
        )

    return tuple(blueprints)


def coin_road_wave_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a wave that moves across the full road width."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []

    for index, lane in enumerate(base.LANE_POSITIONS):
        forward = (index - 2) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.55)
        phase = base.lane_phase_value(band_index, lane) + (index * 0.25)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_road_wave_{index}",
                x_pos=center.x + (side.x * lane) + (direction.x * forward),
                y_pos=y_position + 0.5,
                z_pos=center.z + (side.z * lane) + (direction.z * forward),
                motion_kind="lane_wave",
                motion_amplitude=base.COIN_CHAIN_SIDE_OFFSET * 0.75,
                motion_frequency=1.15,
                motion_phase=phase,
            ),
        )

    return tuple(blueprints)


def coin_road_orbit_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a slow orbiting sweep along the road centerline."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(7):
        forward = (index - 3) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.55)
        phase = base.lane_phase_value(band_index, 0.0) + (index * 0.38)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_road_orbit_{index}",
                x_pos=center.x + (direction.x * forward),
                y_pos=y_position + 0.5,
                z_pos=center.z + (direction.z * forward),
                motion_kind="lane_orbit",
                motion_amplitude=base.COIN_CHAIN_SIDE_OFFSET * 1.15,
                motion_frequency=0.85,
                motion_phase=phase,
            ),
        )

    return tuple(blueprints)


def coin_road_slalom_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a slalom that snakes across the road and lifts."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(9):
        forward = (index - 4) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.5)
        phase = base.lane_phase_value(band_index, 0.0) + (index * 0.42)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_road_slalom_{index}",
                x_pos=center.x + (direction.x * forward),
                y_pos=y_position + 0.5,
                z_pos=center.z + (direction.z * forward),
                motion_kind="lane_slalom",
                motion_amplitude=base.COIN_CHAIN_SIDE_OFFSET * 1.25,
                motion_frequency=1.05,
                motion_phase=phase,
            ),
        )

    return tuple(blueprints)


def coin_wave_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a shallow lateral wave of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    offsets = (
        -base.COIN_CHAIN_FORWARD_OFFSET,
        0.0,
        base.COIN_CHAIN_FORWARD_OFFSET,
    )
    blueprints: list[base.FallingBlueprint] = []

    for index, forward_offset in enumerate(offsets):
        lateral = (index - 1) * (base.COIN_CHAIN_SIDE_OFFSET * 0.75)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_wave_{index}",
                x_pos=center.x + (direction.x * forward_offset) + (side.x * lateral),
                y_pos=y_position + 0.45,
                z_pos=center.z + (direction.z * forward_offset) + (side.z * lateral),
            ),
        )

    return tuple(blueprints)


def coin_fan_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a fan-shaped spread of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(5):
        spread = (index - 2) * (base.COIN_CHAIN_SIDE_OFFSET * 0.75)
        forward = (index - 2) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.35)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_fan_{index}",
                x_pos=center.x + (side.x * spread) + (direction.x * forward),
                y_pos=y_position + 0.55,
                z_pos=center.z + (side.z * spread) + (direction.z * forward),
            ),
        )

    return tuple(blueprints)


def coin_ribbon_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a ribbon-like curve of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []
    offsets = (-2, -1, 0, 1, 2)

    for index, step in enumerate(offsets):
        forward = step * (base.COIN_CHAIN_FORWARD_OFFSET * 0.65)
        arc_phase = (index / max(1, len(offsets) - 1)) * tau * 0.35
        lateral = sin(arc_phase + (band_index * 0.2)) * (
            base.COIN_CHAIN_SIDE_OFFSET * 0.7
        )
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_ribbon_{index}",
                x_pos=center.x + (direction.x * forward) + (side.x * lateral),
                y_pos=y_position + 0.5,
                z_pos=center.z + (direction.z * forward) + (side.z * lateral),
            ),
        )

    return tuple(blueprints)


def coin_wide_bridge_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a wide cross-road bridge of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(20):
        # S311: non-crypto RNG; B311: deterministic gameplay variation.
        rng = Random((band_index * 173) + (index * 29) + 77)  # noqa: S311  # nosec B311
        lateral = rng.uniform(-0.95, 0.95) * base.MAX_COIN_ABS
        forward = rng.uniform(-1.4, 1.4) * base.COIN_CHAIN_FORWARD_OFFSET
        vertical = rng.uniform(-0.2, 0.2)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_wide_bridge_{index}",
                x_pos=center.x + (side.x * lateral) + (direction.x * forward),
                y_pos=y_position + 0.5 + vertical,
                z_pos=center.z + (side.z * lateral) + (direction.z * forward),
            ),
        )

    return tuple(blueprints)


def coin_wide_arc_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a wide arc of coins across the tunnel."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(18):
        # S311: non-crypto RNG; B311: deterministic gameplay variation.
        rng = Random(  # noqa: S311  # nosec B311
            (band_index * 197) + (index * 41) + 121,
        )
        lateral = rng.uniform(-1.05, 1.05) * base.MAX_COIN_ABS
        forward = rng.uniform(-1.8, 1.8) * base.COIN_CHAIN_FORWARD_OFFSET
        vertical = rng.uniform(-0.25, 0.25)
        arc_bias = cos((index / 18) * tau) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.45)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_wide_arc_{index}",
                x_pos=center.x + (side.x * lateral) + (direction.x * forward),
                y_pos=y_position + 0.6 + vertical,
                z_pos=center.z
                + (side.z * lateral)
                + (direction.z * (forward + arc_bias)),
            ),
        )

    return tuple(blueprints)


def coin_grid_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a compact grid of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    forward_offsets = (
        -base.COIN_CHAIN_FORWARD_OFFSET * 0.85,
        base.COIN_CHAIN_FORWARD_OFFSET * 0.85,
    )
    side_offsets = (
        -base.COIN_CHAIN_SIDE_OFFSET * 0.75,
        0.0,
        base.COIN_CHAIN_SIDE_OFFSET * 0.75,
    )
    blueprints: list[base.FallingBlueprint] = []

    for row_index, forward in enumerate(forward_offsets):
        for col_index, lateral in enumerate(side_offsets):
            blueprints.append(
                base.coin_blueprint(
                    name=f"coin_grid_{row_index}_{col_index}",
                    x_pos=center.x + (direction.x * forward) + (side.x * lateral),
                    y_pos=y_position + 0.45 + (row_index * 0.08),
                    z_pos=center.z + (direction.z * forward) + (side.z * lateral),
                ),
            )

    return tuple(blueprints)


def coin_orbit_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a ring orbit of coins."""
    center = base.path_center(band_index)
    radius = 2.6 * base.TUNNEL_WIDTH_SCALE
    count = 8
    blueprints: list[base.FallingBlueprint] = []

    for index in range(count):
        angle = ((tau / count) * index) + (band_index * 0.18)
        lift = 0.45 + (0.08 if index % 2 == 0 else 0.0)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_orbit_{index}",
                x_pos=center.x + (cos(angle) * radius),
                y_pos=y_position + lift,
                z_pos=center.z + (sin(angle) * radius),
            ),
        )

    return tuple(blueprints)


def coin_zigzag_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a zigzagging line of coins."""
    center = base.path_center(band_index)
    direction = base.path_direction(band_index)
    side = base.Vec3(-direction.z, 0.0, direction.x)
    blueprints: list[base.FallingBlueprint] = []
    count = 7

    for index in range(count):
        forward = (index - 3) * (base.COIN_CHAIN_FORWARD_OFFSET * 0.55)
        lateral = (1.0 if index % 2 == 0 else -1.0) * (
            base.COIN_CHAIN_SIDE_OFFSET * 1.1
        )
        lift = 0.45 + (abs(index - 3) * 0.03)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_zigzag_{index}",
                x_pos=center.x + (direction.x * forward) + (side.x * lateral),
                y_pos=y_position + lift,
                z_pos=center.z + (direction.z * forward) + (side.z * lateral),
            ),
        )

    return tuple(blueprints)


def coin_spiral_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place an outward spiral of coins."""
    center = base.path_center(band_index)
    base_angle = band_index * 0.24
    radius_start = 0.8 * base.TUNNEL_WIDTH_SCALE
    radius_step = 0.55 * base.TUNNEL_WIDTH_SCALE
    blueprints: list[base.FallingBlueprint] = []
    count = 9

    for index in range(count):
        radius = radius_start + (index * radius_step)
        angle = base_angle + (index * 0.72)
        lift = 0.45 + (index * 0.04)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_spiral_{index}",
                x_pos=center.x + (cos(angle) * radius),
                y_pos=y_position + lift,
                z_pos=center.z + (sin(angle) * radius),
            ),
        )

    return tuple(blueprints)


def coin_double_spiral_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a double-arm spiral of coins."""
    center = base.path_center(band_index)
    base_angle = band_index * 0.21
    radius_start = 1.0 * base.TUNNEL_WIDTH_SCALE
    radius_step = 0.45 * base.TUNNEL_WIDTH_SCALE
    blueprints: list[base.FallingBlueprint] = []
    count = 10

    for index in range(count):
        arm_angle = base_angle + (index * 0.68)
        if index % 2 == 1:
            arm_angle += tau * 0.5
        radius = radius_start + (index * radius_step)
        lift = 0.45 + ((index % 3) * 0.05)
        blueprints.append(
            base.coin_blueprint(
                name=f"coin_double_spiral_{index}",
                x_pos=center.x + (cos(arm_angle) * radius),
                y_pos=y_position + lift,
                z_pos=center.z + (sin(arm_angle) * radius),
            ),
        )

    return tuple(blueprints)


def bonus_coin_arc_blueprints(
    *,
    y_position: float,
    band_index: int,
    rng: Random,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a bonus arc of high-value coins."""
    center = base.path_center(band_index)
    side_sign = -1.0 if rng.random() < base.BONUS_ARC_SIDE_SPLIT else 1.0
    blueprints: list[base.FallingBlueprint] = []

    for index in range(3):
        lift = (index - 1) * (0.95 * base.TUNNEL_WIDTH_SCALE)
        blueprints.append(
            base.coin_blueprint(
                name=f"bonus_arc_coin_{index}",
                x_pos=center.x
                + (side_sign * ((2.0 + (index * 0.6)) * base.TUNNEL_WIDTH_SCALE)),
                y_pos=y_position + 0.9,
                z_pos=center.z + lift,
                score_value=base.HIGH_VALUE_COIN_SCORE_VALUE,
                color_name="gold",
            ),
        )

    return tuple(blueprints)
