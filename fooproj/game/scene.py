"""Scene blueprints for the Ursina driving sandbox world."""

from dataclasses import dataclass
from math import cos, radians, sin

COURSE_RADIUS = 44.0


@dataclass(frozen=True, slots=True)
class Vec3:
    """Simple 3D vector data container."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class EntityBlueprint:
    """Data-only description for spawning an Ursina entity."""

    model: str
    color_name: str
    scale: Vec3
    position: Vec3
    is_dynamic: bool = True


def starter_scene_blueprints() -> tuple[EntityBlueprint, ...]:
    """Return entities for an obstacle-focused sandbox race arena."""
    blueprints: list[EntityBlueprint] = []
    blueprints.extend(_ground_layers())
    blueprints.extend(_round_course_tiles())
    blueprints.extend(_course_obstacles())
    blueprints.extend(_trackside_houses())
    blueprints.extend(_trackside_trees())
    blueprints.extend(_perimeter_columns())
    blueprints.extend(_cardinal_landmarks())
    return tuple(blueprints)


def _ground_layers() -> list[EntityBlueprint]:
    """Create layered ground colors so the world reads like a track area."""
    return [
        EntityBlueprint(
            model="plane",
            color_name="olive",
            scale=Vec3(320.0, 1.0, 320.0),
            position=Vec3(0.0, 0.0, 0.0),
            is_dynamic=False,
        ),
        EntityBlueprint(
            model="plane",
            color_name="green",
            scale=Vec3(200.0, 1.0, 200.0),
            position=Vec3(0.0, 0.02, 0.0),
            is_dynamic=False,
        ),
        EntityBlueprint(
            model="plane",
            color_name="lime",
            scale=Vec3(78.0, 1.0, 78.0),
            position=Vec3(0.0, 0.04, 0.0),
            is_dynamic=False,
        ),
    ]


def _round_course_tiles() -> list[EntityBlueprint]:
    """Create a wide circular driving loop with colored curb markers."""
    tiles: list[EntityBlueprint] = []
    segments = 72
    road_tile_scale = Vec3(4.8, 0.16, 4.8)

    for segment_index in range(segments):
        angle = (360.0 / segments) * segment_index
        x_pos = sin(radians(angle)) * COURSE_RADIUS
        z_pos = cos(radians(angle)) * COURSE_RADIUS

        tiles.append(
            EntityBlueprint(
                model="cube",
                color_name="dark_gray",
                scale=road_tile_scale,
                position=Vec3(x_pos, road_tile_scale.y * 0.5, z_pos),
                is_dynamic=False,
            ),
        )

        if segment_index % 2 == 0:
            curb_color = "red" if (segment_index // 2) % 2 == 0 else "white"
            for curb_radius in (COURSE_RADIUS - 5.2, COURSE_RADIUS + 5.2):
                curb_x = sin(radians(angle)) * curb_radius
                curb_z = cos(radians(angle)) * curb_radius
                tiles.append(
                    EntityBlueprint(
                        model="cube",
                        color_name=curb_color,
                        scale=Vec3(1.4, 0.22, 1.4),
                        position=Vec3(curb_x, 0.11, curb_z),
                        is_dynamic=False,
                    ),
                )

    for stripe_index in range(-3, 4):
        tiles.append(
            EntityBlueprint(
                model="cube",
                color_name="smoke",
                scale=Vec3(1.1, 0.18, 3.2),
                position=Vec3(stripe_index * 1.4, 0.1, COURSE_RADIUS),
                is_dynamic=False,
            ),
        )

    return tiles


def _course_obstacles() -> list[EntityBlueprint]:
    """Place dynamic obstacles around the loop for dodge-heavy gameplay."""
    obstacles: list[EntityBlueprint] = []
    lane_offsets = (-2.6, 0.0, 2.6)
    colors = ("orange", "yellow", "azure", "magenta", "cyan", "violet")

    for obstacle_index, angle in enumerate(range(12, 360, 24)):
        lane_offset = lane_offsets[obstacle_index % len(lane_offsets)]
        obstacle_radius = COURSE_RADIUS + lane_offset
        x_pos = sin(radians(float(angle))) * obstacle_radius
        z_pos = cos(radians(float(angle))) * obstacle_radius
        model_name = "sphere" if obstacle_index % 2 else "cube"
        scale = Vec3(1.5, 1.5, 1.5) if model_name == "sphere" else Vec3(1.8, 1.8, 1.8)

        obstacles.append(
            EntityBlueprint(
                model=model_name,
                color_name=colors[obstacle_index % len(colors)],
                scale=scale,
                position=Vec3(x_pos, scale.y * 0.5, z_pos),
            ),
        )

    for angle in range(0, 360, 45):
        x_pos = sin(radians(float(angle))) * 16.0
        z_pos = cos(radians(float(angle))) * 16.0
        obstacles.append(
            EntityBlueprint(
                model="sphere",
                color_name="yellow",
                scale=Vec3(1.35, 1.35, 1.35),
                position=Vec3(x_pos, 0.675, z_pos),
            ),
        )

    return obstacles


def _perimeter_columns() -> list[EntityBlueprint]:
    """Create a large boundary ring of heavy columns."""
    columns: list[EntityBlueprint] = []
    colors = ("cyan", "magenta", "yellow", "lime")
    color_index = 0
    edge = 122.0

    for step in range(-96, 97, 24):
        edge_positions = (
            (float(step), edge),
            (float(step), -edge),
            (edge, float(step)),
            (-edge, float(step)),
        )
        for x_pos, z_pos in edge_positions:
            columns.append(
                EntityBlueprint(
                    model="cube",
                    color_name=colors[color_index % len(colors)],
                    scale=Vec3(2.4, 6.2, 2.4),
                    position=Vec3(x_pos, 3.1, z_pos),
                    is_dynamic=False,
                ),
            )
            color_index += 1

    return columns


def _trackside_houses() -> list[EntityBlueprint]:
    """Place static house-like structures around the outer course area."""
    houses: list[EntityBlueprint] = []
    home_positions = (
        Vec3(72.0, 0.0, 66.0),
        Vec3(-76.0, 0.0, 58.0),
        Vec3(74.0, 0.0, -62.0),
        Vec3(-71.0, 0.0, -68.0),
        Vec3(0.0, 0.0, 98.0),
        Vec3(0.0, 0.0, -98.0),
    )
    wall_colors = ("peach", "smoke", "light_gray")

    for house_index, base in enumerate(home_positions):
        wall_color = wall_colors[house_index % len(wall_colors)]
        houses.append(
            EntityBlueprint(
                model="cube",
                color_name=wall_color,
                scale=Vec3(9.0, 4.6, 9.0),
                position=Vec3(base.x, 2.3, base.z),
                is_dynamic=False,
            ),
        )
        houses.append(
            EntityBlueprint(
                model="cube",
                color_name="brown",
                scale=Vec3(9.4, 1.1, 9.4),
                position=Vec3(base.x, 4.95, base.z),
                is_dynamic=False,
            ),
        )
        houses.append(
            EntityBlueprint(
                model="cube",
                color_name="dark_gray",
                scale=Vec3(1.4, 2.5, 0.4),
                position=Vec3(base.x, 1.25, base.z + 4.7),
                is_dynamic=False,
            ),
        )

    return houses


def _trackside_trees() -> list[EntityBlueprint]:
    """Place static tree clusters to improve depth and silhouette variety."""
    trees: list[EntityBlueprint] = []
    canopy_colors = ("green", "lime")

    for tree_index, angle in enumerate(range(0, 360, 30)):
        radius = 84.0 if tree_index % 2 == 0 else 102.0
        x_pos = sin(radians(float(angle))) * radius
        z_pos = cos(radians(float(angle))) * radius
        canopy_color = canopy_colors[tree_index % len(canopy_colors)]

        trees.append(
            EntityBlueprint(
                model="cube",
                color_name="brown",
                scale=Vec3(0.8, 3.2, 0.8),
                position=Vec3(x_pos, 1.6, z_pos),
                is_dynamic=False,
            ),
        )
        trees.append(
            EntityBlueprint(
                model="sphere",
                color_name=canopy_color,
                scale=Vec3(3.4, 3.4, 3.4),
                position=Vec3(x_pos, 4.4, z_pos),
                is_dynamic=False,
            ),
        )
        trees.append(
            EntityBlueprint(
                model="sphere",
                color_name=canopy_color,
                scale=Vec3(2.6, 2.6, 2.6),
                position=Vec3(x_pos + 1.2, 5.6, z_pos),
                is_dynamic=False,
            ),
        )
        trees.append(
            EntityBlueprint(
                model="sphere",
                color_name=canopy_color,
                scale=Vec3(2.6, 2.6, 2.6),
                position=Vec3(x_pos - 1.2, 5.6, z_pos),
                is_dynamic=False,
            ),
        )

    return trees


def _cardinal_landmarks() -> list[EntityBlueprint]:
    """Create distant large landmarks to emphasize world scale."""
    landmarks: list[EntityBlueprint] = []
    layout = (
        ("cube", "orange", Vec3(9.0, 16.0, 9.0), Vec3(0.0, 8.0, 118.0)),
        ("cube", "azure", Vec3(9.0, 16.0, 9.0), Vec3(0.0, 8.0, -118.0)),
        ("cube", "yellow", Vec3(9.0, 16.0, 9.0), Vec3(118.0, 8.0, 0.0)),
        ("cube", "violet", Vec3(9.0, 16.0, 9.0), Vec3(-118.0, 8.0, 0.0)),
        ("sphere", "lime", Vec3(7.0, 7.0, 7.0), Vec3(82.0, 3.5, 82.0)),
        ("sphere", "magenta", Vec3(7.0, 7.0, 7.0), Vec3(-82.0, 3.5, 82.0)),
        ("sphere", "cyan", Vec3(7.0, 7.0, 7.0), Vec3(82.0, 3.5, -82.0)),
        ("sphere", "red", Vec3(7.0, 7.0, 7.0), Vec3(-82.0, 3.5, -82.0)),
    )

    for model_name, color_name, scale, position in layout:
        landmarks.append(
            EntityBlueprint(
                model=model_name,
                color_name=color_name,
                scale=scale,
                position=position,
                is_dynamic=False,
            ),
        )

    return landmarks
