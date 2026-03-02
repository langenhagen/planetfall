"""Procedural blueprint helpers for the endless falling course."""

from dataclasses import replace
from typing import TYPE_CHECKING

from planetfall.game import scene_base as base
from planetfall.game.scene_coins import (
    bonus_coin_arc_blueprints,
    coin_chain_blueprints,
    coin_double_spiral_blueprints,
    coin_fan_blueprints,
    coin_grid_blueprints,
    coin_orbit_blueprints,
    coin_ribbon_blueprints,
    coin_road_orbit_blueprints,
    coin_road_slalom_blueprints,
    coin_road_wave_blueprints,
    coin_spiral_blueprints,
    coin_wave_blueprints,
    coin_wide_arc_blueprints,
    coin_wide_bridge_blueprints,
    coin_zigzag_blueprints,
)
from planetfall.game.scene_obstacles import (
    checker_wall_pattern_blueprints,
    chicane_pattern_blueprints,
    comet_pattern_blueprints,
    extra_asteroid_blueprints,
    gate_pattern_blueprints,
    orbit_cluster_pattern_blueprints,
    ring_gap_pattern_blueprints,
    scatter_pattern_blueprints,
    slalom_pattern_blueprints,
    spiral_pattern_blueprints,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from random import Random
else:  # pragma: no cover - runtime fallback for deferred annotations.
    Random = object

TUNNEL_WIDTH_SCALE = base.TUNNEL_WIDTH_SCALE
LANE_POSITIONS = base.LANE_POSITIONS
BAND_SPACING = base.BAND_SPACING
COIN_SCORE_VALUE = base.COIN_SCORE_VALUE
HIGH_VALUE_COIN_SCORE_VALUE = base.HIGH_VALUE_COIN_SCORE_VALUE
MAX_COLLIDABLE_ABS = base.MAX_COLLIDABLE_ABS
MAX_COIN_ABS = base.MAX_COIN_ABS
OBSTACLE_DENSITY_MULTIPLIER = base.OBSTACLE_DENSITY_MULTIPLIER
COIN_PATTERN_COUNT = base.COIN_PATTERN_COUNT
OBSTACLE_PATTERN_COUNT = base.OBSTACLE_PATTERN_COUNT
PATTERN_GATE = base.PATTERN_GATE
PATTERN_SLALOM = base.PATTERN_SLALOM
PATTERN_CHICANE = base.PATTERN_CHICANE
PATTERN_RING_GAP = base.PATTERN_RING_GAP
PATTERN_COMET = base.PATTERN_COMET
PATTERN_CHECKER = base.PATTERN_CHECKER
PATTERN_SPIRAL = base.PATTERN_SPIRAL
PATTERN_ORBIT = base.PATTERN_ORBIT
PATTERN_SCATTER = base.PATTERN_SCATTER
PATH_DIRECTION_EPSILON = base.PATH_DIRECTION_EPSILON
RING_GAP_ANGLE_THRESHOLD = base.RING_GAP_ANGLE_THRESHOLD
BONUS_ARC_SIDE_SPLIT = base.BONUS_ARC_SIDE_SPLIT
OBSTACLE_MODEL_NAME = base.OBSTACLE_MODEL_NAME
COIN_MODEL_NAME = base.COIN_MODEL_NAME
COIN_CHAIN_FORWARD_OFFSET = base.COIN_CHAIN_FORWARD_OFFSET
COIN_CHAIN_SIDE_OFFSET = base.COIN_CHAIN_SIDE_OFFSET
Vec3 = base.Vec3
FallingBlueprint = base.FallingBlueprint


def build_fall_band_blueprints(
    *,
    band_index: int,
    y_position: float,
    rng: Random,
    coin_pattern_index: int = 0,
) -> tuple[base.FallingBlueprint, ...]:
    """Build one designed band with chained coins and structured obstacles."""
    blueprints: list[base.FallingBlueprint] = []
    coin_pattern = coin_pattern_index % COIN_PATTERN_COUNT
    # Enable/disable coin patterns by commenting/uncommenting entries.
    # The selection rotates by index (see update_coin_pattern_timer), not random.
    # Keep COIN_PATTERN_COUNT in scene_base.py in sync with the active list.
    coin_pattern_builders: list[
        Callable[[float, int], tuple[base.FallingBlueprint, ...]],
    ] = [
        lambda y_pos, band: coin_chain_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_road_wave_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_road_orbit_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_road_slalom_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_chain_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_wave_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_fan_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_ribbon_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_grid_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_orbit_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_zigzag_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_spiral_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_double_spiral_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_wide_bridge_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        lambda y_pos, band: coin_wide_arc_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
    ]
    coin_builder = coin_pattern_builders[coin_pattern % len(coin_pattern_builders)]
    blueprints.extend(coin_builder(y_position, band_index))

    pattern = band_index % OBSTACLE_PATTERN_COUNT
    obstacle_patterns: dict[
        int,
        Callable[[float, int], tuple[base.FallingBlueprint, ...]],
    ] = {
        PATTERN_GATE: lambda y_pos, band: gate_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_SLALOM: lambda y_pos, band: slalom_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_CHICANE: lambda y_pos, band: chicane_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_RING_GAP: lambda y_pos, band: ring_gap_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_COMET: lambda y_pos, band: comet_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_CHECKER: lambda y_pos, band: checker_wall_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_SPIRAL: lambda y_pos, band: spiral_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
        PATTERN_ORBIT: lambda y_pos, band: orbit_cluster_pattern_blueprints(
            y_position=y_pos,
            band_index=band,
        ),
    }
    if (obstacle_builder := obstacle_patterns.get(pattern)) is None:
        blueprints.extend(
            scatter_pattern_blueprints(y_position=y_position, band_index=band_index),
        )
    else:
        blueprints.extend(obstacle_builder(y_position, band_index))

    if band_index % 7 == 0:
        blueprints.extend(
            bonus_coin_arc_blueprints(
                y_position=y_position,
                band_index=band_index,
                rng=rng,
            ),
        )

    coin_color_cycle = ("yellow", "rainbow", "rainbow_wave")
    coin_color = coin_color_cycle[coin_pattern % len(coin_color_cycle)]
    blueprints = _apply_coin_color_pattern(blueprints, coin_color)

    if band_index % 4 == 0:
        blueprints.extend(
            extra_asteroid_blueprints(y_position=y_position, band_index=band_index),
        )

    return tuple(_apply_obstacle_density(blueprints, rng))


def _apply_coin_color_pattern(
    blueprints: list[base.FallingBlueprint],
    color_name: str,
) -> list[base.FallingBlueprint]:
    if not blueprints:
        return blueprints
    return [
        (
            replace(blueprint, color_name=color_name)
            if blueprint.entity_kind == "coin"
            else blueprint
        )
        for blueprint in blueprints
    ]


def _apply_obstacle_density(
    blueprints: list[base.FallingBlueprint],
    rng: Random,
) -> list[base.FallingBlueprint]:
    obstacles = [
        blueprint for blueprint in blueprints if blueprint.entity_kind == "obstacle"
    ]
    if not obstacles:
        return blueprints

    reduced: list[base.FallingBlueprint] = []
    for blueprint in blueprints:
        if blueprint.entity_kind != "obstacle":
            reduced.append(blueprint)
            continue
        if rng.random() < OBSTACLE_DENSITY_MULTIPLIER:
            reduced.append(blueprint)

    if not any(blueprint.entity_kind == "obstacle" for blueprint in reduced):
        reduced.append(obstacles[0])

    return reduced
