"""Obstacle pattern blueprints for the falling course."""

from math import atan2, cos, sin, tau

from planetfall.game import scene_base as base


def gate_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a blocked gate with one safe lane."""
    path_center = base.path_center(band_index)
    safe_lane_x = base.lane_snap(path_center.x)
    row_z = base.lane_snap(path_center.z * 0.45)
    blueprints: list[base.FallingBlueprint] = []

    for lane_x in base.LANE_POSITIONS:
        if lane_x == safe_lane_x:
            continue
        blueprints.append(
            base.obstacle_blueprint(
                name=f"gate_block_{int(lane_x)}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=row_z,
                scale=base.Vec3(2.3, 2.3, 2.3),
                color_name="orange",
            ),
        )

    return tuple(blueprints)


def slalom_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place alternating obstacles to create a slalom."""
    shift = band_index % len(base.LANE_POSITIONS)
    safe_lane_x = base.lane_snap(base.path_center(band_index).x)
    blueprints: list[base.FallingBlueprint] = []

    for index, lane_x in enumerate(base.LANE_POSITIONS):
        lane_z = base.LANE_POSITIONS[(index + shift) % len(base.LANE_POSITIONS)]
        if lane_x == safe_lane_x:
            continue
        blueprints.append(
            base.obstacle_blueprint(
                name=f"slalom_block_{index}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=lane_z,
                scale=base.Vec3(1.9, 1.9, 1.9),
                color_name="red",
            ),
        )

    return tuple(blueprints)


def chicane_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a two-row chicane with offset openings."""
    path_center = base.path_center(band_index)
    row_a_z = base.lane_snap(path_center.z + (2.4 * base.TUNNEL_WIDTH_SCALE))
    row_b_z = base.lane_snap(path_center.z - (2.4 * base.TUNNEL_WIDTH_SCALE))
    open_a = base.lane_snap(path_center.x - (3.0 * base.TUNNEL_WIDTH_SCALE))
    open_b = base.lane_snap(path_center.x + (3.0 * base.TUNNEL_WIDTH_SCALE))
    blueprints: list[base.FallingBlueprint] = []

    for lane_x in base.LANE_POSITIONS:
        if lane_x != open_a:
            blueprints.append(
                base.obstacle_blueprint(
                    name=f"chicane_row_a_{int(lane_x)}",
                    x_pos=lane_x,
                    y_pos=y_position,
                    z_pos=row_a_z,
                    scale=base.Vec3(2.0, 2.0, 2.0),
                    color_name="violet",
                ),
            )
        if lane_x != open_b:
            blueprints.append(
                base.obstacle_blueprint(
                    name=f"chicane_row_b_{int(lane_x)}",
                    x_pos=lane_x,
                    y_pos=y_position,
                    z_pos=row_b_z,
                    scale=base.Vec3(2.0, 2.0, 2.0),
                    color_name="azure",
                ),
            )

    return tuple(blueprints)


def ring_gap_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a ring with one angular gap."""
    path_center = base.path_center(band_index)
    gap_angle = atan2(path_center.z, path_center.x)
    blueprints: list[base.FallingBlueprint] = []

    for index in range(10):
        angle = (tau / 10.0) * index
        if base.angular_distance(angle, gap_angle) < base.RING_GAP_ANGLE_THRESHOLD:
            continue
        blueprints.append(
            base.obstacle_blueprint(
                name=f"ring_block_{index}",
                x_pos=cos(angle) * (5.8 * base.TUNNEL_WIDTH_SCALE),
                y_pos=y_position,
                z_pos=sin(angle) * (5.8 * base.TUNNEL_WIDTH_SCALE),
                scale=base.Vec3(1.6, 1.6, 1.6),
                color_name="magenta",
            ),
        )

    return tuple(blueprints)


def comet_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a curved comet trail of obstacles."""
    base_angle = band_index * 0.35
    blueprints: list[base.FallingBlueprint] = []

    for index in range(4):
        angle = base_angle + (index * 0.58)
        blueprints.append(
            base.obstacle_blueprint(
                name=f"comet_block_{index}",
                x_pos=cos(angle) * (5.5 * base.TUNNEL_WIDTH_SCALE),
                y_pos=y_position,
                z_pos=sin(angle) * (5.5 * base.TUNNEL_WIDTH_SCALE),
                scale=base.Vec3(1.8, 1.8, 1.8),
                color_name="brown",
            ),
        )

    return tuple(blueprints)


def checker_wall_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a checker wall across alternating rows."""
    path_center = base.path_center(band_index)
    row_a_z = base.lane_snap(path_center.z + (1.8 * base.TUNNEL_WIDTH_SCALE))
    row_b_z = base.lane_snap(path_center.z - (1.8 * base.TUNNEL_WIDTH_SCALE))
    blueprints: list[base.FallingBlueprint] = []

    for index, lane_x in enumerate(base.LANE_POSITIONS):
        if index % 2 == 0:
            row_z = row_a_z
            color_name = "lime"
            suffix = "a"
        else:
            row_z = row_b_z
            color_name = "turquoise"
            suffix = "b"
        blueprints.append(
            base.obstacle_blueprint(
                name=f"checker_block_{suffix}_{index}",
                x_pos=lane_x,
                y_pos=y_position,
                z_pos=row_z,
                scale=base.Vec3(1.9, 1.9, 1.9),
                color_name=color_name,
            ),
        )

    return tuple(blueprints)


def spiral_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a spiral of obstacles."""
    base_angle = band_index * 0.32
    base_radius = 2.8 * base.TUNNEL_WIDTH_SCALE
    blueprints: list[base.FallingBlueprint] = []

    for index in range(6):
        angle = base_angle + (index * 0.75)
        radius = base_radius + (index * 0.4 * base.TUNNEL_WIDTH_SCALE)
        blueprints.append(
            base.obstacle_blueprint(
                name=f"spiral_block_{index}",
                x_pos=cos(angle) * radius,
                y_pos=y_position,
                z_pos=sin(angle) * radius,
                scale=base.Vec3(1.7, 1.7, 1.7),
                color_name="pink",
            ),
        )

    return tuple(blueprints)


def orbit_cluster_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place an orbiting cluster of obstacles."""
    center = base.path_center(band_index)
    count = 7
    base_radius = 2.4 * base.TUNNEL_WIDTH_SCALE
    blueprints: list[base.FallingBlueprint] = []

    for index in range(count):
        angle = ((tau / count) * index) + (band_index * 0.27)
        radius = base_radius + (
            sin((band_index * 0.33) + (index * 1.4)) * (0.6 * base.TUNNEL_WIDTH_SCALE)
        )
        scale = 1.5 + (0.2 * sin((band_index * 0.41) + index))
        blueprints.append(
            base.obstacle_blueprint(
                name=f"orbit_block_{index}",
                x_pos=center.x + (cos(angle) * radius),
                y_pos=y_position,
                z_pos=center.z + (sin(angle) * radius),
                scale=base.Vec3(scale, scale, scale),
                color_name="azure",
            ),
        )

    return tuple(blueprints)


def scatter_pattern_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Place a chaotic scatter of obstacles."""
    center = base.path_center(band_index)
    blueprints: list[base.FallingBlueprint] = []
    colors = ("orange", "yellow", "red", "cyan", "lime", "violet")

    for index in range(6):
        angle = (band_index * 0.37) + (index * 1.91)
        radius = (
            1.8 + ((sin((band_index * 0.53) + (index * 2.1)) + 1.0) * 0.5 * 3.4)
        ) * base.TUNNEL_WIDTH_SCALE
        scale = 1.35 + ((sin((band_index * 0.61) + index) + 1.0) * 0.5 * 0.6)
        blueprints.append(
            base.obstacle_blueprint(
                name=f"scatter_block_{index}",
                x_pos=center.x + (cos(angle) * radius),
                y_pos=y_position,
                z_pos=center.z + (sin(angle) * radius),
                scale=base.Vec3(scale, scale, scale),
                color_name=colors[index % len(colors)],
            ),
        )

    return tuple(blueprints)


def extra_asteroid_blueprints(
    *,
    y_position: float,
    band_index: int,
) -> tuple[base.FallingBlueprint, ...]:
    """Add extra in-lane asteroid hazards to increase field density."""
    center = base.path_center(band_index)
    first_lane = base.LANE_POSITIONS[(band_index + 1) % len(base.LANE_POSITIONS)]
    second_lane = base.LANE_POSITIONS[(band_index + 3) % len(base.LANE_POSITIONS)]
    return (
        base.obstacle_blueprint(
            name="extra_asteroid_a",
            x_pos=first_lane if band_index % 8 != 0 else second_lane,
            y_pos=y_position,
            z_pos=base.lane_snap(center.z + (2.2 * base.TUNNEL_WIDTH_SCALE)),
            scale=base.Vec3(1.45, 1.45, 1.45),
            color_name="orange",
        ),
    )
