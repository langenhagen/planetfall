"""Runtime entity spawning helpers.

Owns asteroid model selection, rainbow color helpers, blueprint-to-entity
spawning, and band/powerup spawn orchestration.
"""

from math import sin, tau
from time import monotonic
from typing import TYPE_CHECKING, cast

from ursina import Entity, Vec3

from planetfall.game.runtime_colors import resolve_color, rgba_color
from planetfall.game.runtime_controls import should_spawn_next_band
from planetfall.game.runtime_entities import mark_lit_shadowed
from planetfall.game.runtime_random import (
    deterministic_probability_hit,
    discrete_value_in_range,
    signed_speed_from_seed,
)
from planetfall.game.runtime_state import SpawnedObject
from planetfall.game.scene import (
    BAND_SPACING,
    COIN_SCORE_VALUE,
    build_fall_band_blueprints,
)
from planetfall.game.scene_base import MAX_COIN_ABS

if TYPE_CHECKING:
    from random import Random

    from planetfall.game.config import (
        FallSettings,
        GameplayTuningSettings,
        MovementSettings,
    )
    from planetfall.game.runtime_state import FallingRunState
    from planetfall.game.scene import FallingBlueprint

ASTEROID_MODEL_NAME = "models/asteroids/Asteroid_1.bam"
ASTEROID_MODEL_VARIANTS: tuple[str, ...] = (
    "models/asteroids/Asteroid_1.bam",
    "models/asteroids/Rocky_Asteroid_2.bam",
    "models/asteroids/Rocky_Asteroid_3.bam",
    "models/asteroids/Rocky_Asteroid_4.bam",
    "models/asteroids/Rocky_Asteroid_5.bam",
    "models/asteroids/Rocky_Asteroid_6.bam",
)
ASTEROID_DIFFUSE_TEXTURE_BY_MODEL: dict[str, str] = {
    "models/asteroids/Asteroid_1.bam": (
        "models/asteroids/Textures_Asteroid_1/Asteroid_1_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_2.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_2/Rocky_Asteroid_2_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_3.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_3/Rocky_Asteroid_3_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_4.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_4/Rocky_Asteroid_4_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_5.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_5/Rocky_Asteroid_5_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_6.bam": (
        "models/asteroids/Textures_Rocky_Asteroid_6/Rocky_Asteroid_6_Diffuse_1K.png"
    ),
}
ASTEROID_SCALE_MIN = 0.6
ASTEROID_SCALE_MAX = 2.5

POWERUP_MODEL_NAME = "icosphere"
POWERUP_MAGNET_KIND = "magnet"
POWERUP_BASE_COLOR = rgba_color(1.0, 0.35, 0.9, 1.0)
POWERUP_HALO_COLOR = rgba_color(0.95, 0.2, 0.8, 0.22)


def rainbow_lane_rgb(lane_x: float) -> tuple[float, float, float]:
    """Return a bright rainbow color based on lateral lane position."""
    lane_span = max(0.01, MAX_COIN_ABS)
    clamped_x = max(-lane_span, min(lane_span, lane_x))
    phase = (clamped_x + lane_span) / (lane_span * 2.0)
    red = 0.5 + (0.5 * sin((tau * phase) + 0.0))
    green = 0.5 + (0.5 * sin((tau * phase) + 2.094))
    blue = 0.5 + (0.5 * sin((tau * phase) + 4.188))
    return red, green, blue


def rainbow_wave_rgb(
    *,
    lane_x: float,
    band_index: int,
    runtime_time: float,
) -> tuple[float, float, float]:
    """Return a rainbow color that ripples along the road."""
    lane_span = max(0.01, MAX_COIN_ABS)
    clamped_x = max(-lane_span, min(lane_span, lane_x))
    lane_phase = (clamped_x + lane_span) / (lane_span * 2.0)
    wave_phase = (band_index * 0.18) + (lane_phase * 1.6) + (runtime_time * 0.6)
    red = 0.5 + (0.5 * sin((tau * wave_phase) + 0.0))
    green = 0.5 + (0.5 * sin((tau * wave_phase) + 2.094))
    blue = 0.5 + (0.5 * sin((tau * wave_phase) + 4.188))
    return red, green, blue


def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid model and diffuse texture by seed."""
    variant_index = variation_seed % len(ASTEROID_MODEL_VARIANTS)
    model_name = ASTEROID_MODEL_VARIANTS[variant_index]
    return model_name, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name]


def spawn_entity_from_blueprint(  # noqa: C901, PLR0912, PLR0915
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    # R0912: branching follows entity kind and variant setup.
    # R0914: locals keep spawn tuning explicit per entity.
    # R0915: setup stages are intentionally verbose for clarity.
    *,
    blueprint: FallingBlueprint,
    band_index: int,
    blueprint_index: int,
    gameplay_settings: GameplayTuningSettings,
) -> SpawnedObject:
    # R0914/R0915: setup is data-heavy.
    """Spawn one band blueprint as an Ursina entity and runtime record."""
    variation_seed = (band_index * 41) + (blueprint_index * 17)
    spawn_model = blueprint.model
    spawn_texture: str | None = None
    if blueprint.entity_kind == "obstacle" and blueprint.model == ASTEROID_MODEL_NAME:
        spawn_model, spawn_texture = choose_asteroid_variant(variation_seed)

    entity_name = (
        f"fall_band_{band_index}_"
        f"{blueprint.entity_kind}_"
        f"{blueprint.name}_"
        f"{blueprint_index}"
    )
    entity = Entity(
        name=entity_name,
        model=spawn_model,
        color=resolve_color(blueprint.color_name),
        scale=Vec3(blueprint.scale.x, blueprint.scale.y, blueprint.scale.z),
        position=Vec3(
            blueprint.position.x,
            blueprint.position.y,
            blueprint.position.z,
        ),
    )
    if spawn_texture is not None:
        entity.texture = spawn_texture

    base_scale = Vec3(entity.scale.x, entity.scale.y, entity.scale.z)

    spin_speed_x = 0.0
    spin_speed_y = 0.0
    spin_speed_z = 0.0
    bob_amplitude = 0.0
    bob_frequency = 0.0
    pulse_amplitude = 0.0
    pulse_frequency = 0.0
    drift_speed_x = 0.0
    drift_speed_z = 0.0
    fade_duration = gameplay_settings.spawn_fade_duration_seconds

    target_color = resolve_color(blueprint.color_name)

    if blueprint.entity_kind == "coin":
        entity.unlit = True
        entity.texture = None
        if blueprint.color_name == "rainbow":
            rainbow_red, rainbow_green, rainbow_blue = rainbow_lane_rgb(
                blueprint.position.x,
            )
        elif blueprint.color_name == "rainbow_wave":
            rainbow_red, rainbow_green, rainbow_blue = rainbow_wave_rgb(
                lane_x=blueprint.position.x,
                band_index=band_index,
                runtime_time=monotonic(),
            )
        else:
            rainbow_red = 1.0
            rainbow_green = 0.92
            rainbow_blue = 0.22
        target_color = rgba_color(rainbow_red, rainbow_green, rainbow_blue, 1.0)
        is_high_value_coin = blueprint.score_value > COIN_SCORE_VALUE
        should_render_coin_halo = deterministic_probability_hit(
            seed=variation_seed + 13,
            probability=gameplay_settings.high_value_coin_halo_chance,
        )
        if is_high_value_coin:
            target_color = rgba_color(
                min(1.0, rainbow_red * 1.08),
                min(1.0, rainbow_green * 1.08),
                min(1.0, rainbow_blue * 1.08),
                1.0,
            )
            if should_render_coin_halo:
                Entity(
                    parent=entity,
                    name=f"{entity_name}_coin_halo",
                    model=spawn_model,
                    scale=Vec3(1.18, 1.18, 1.18),
                    color=rgba_color(
                        min(1.0, rainbow_red * 1.1),
                        min(1.0, rainbow_green * 1.1),
                        min(1.0, rainbow_blue * 1.1),
                        0.18,
                    ),
                    unlit=True,
                )
        spin_speed_x = 0.0
        spin_speed_y = (88.0 + ((blueprint_index % 4) * 16.0)) * 0.3
        spin_speed_z = 0.0
        entity.rotation_x = -6.0 + ((blueprint_index % 5) * 3.0)
        entity.rotation_y = ((band_index * 26.0) + (blueprint_index * 32.0)) % 360.0
        entity.rotation_z = -4.0 + ((blueprint_index % 4) * 2.5)
        bob_amplitude = 0.08 + ((variation_seed % 4) * 0.03)
        bob_frequency = 2.5 + ((variation_seed % 5) * 0.36)
        pulse_amplitude = 0.08 + ((variation_seed % 3) * 0.03)
        pulse_frequency = 4.2 + ((variation_seed % 4) * 0.48)
    else:
        mark_lit_shadowed(entity)
        should_spin = False
        if blueprint.entity_kind == "obstacle":
            should_spin = deterministic_probability_hit(
                seed=variation_seed + 3,
                probability=0.7,
            )
            if blueprint.model == ASTEROID_MODEL_NAME:
                target_color = resolve_color("white")
                entity.unlit = False
                entity.rotation_x = (variation_seed * 37) % 360
                entity.rotation_y = (variation_seed * 53) % 360
                entity.rotation_z = (variation_seed * 29) % 360
                scale_multiplier = discrete_value_in_range(
                    seed=variation_seed + 53,
                    variant_count=11,
                    minimum=ASTEROID_SCALE_MIN,
                    maximum=ASTEROID_SCALE_MAX,
                )
                entity.scale = Vec3(
                    entity.scale.x * scale_multiplier,
                    entity.scale.y * scale_multiplier,
                    entity.scale.z * scale_multiplier,
                )
                base_scale = Vec3(entity.scale.x, entity.scale.y, entity.scale.z)
                if should_spin:
                    should_drift = deterministic_probability_hit(
                        seed=variation_seed + 71,
                        probability=0.3,
                    )
                    if should_drift:
                        drift_speed_x = signed_speed_from_seed(
                            seed=variation_seed + 73,
                            variant_count=13,
                            minimum_magnitude=0.8,
                            maximum_magnitude=2.2,
                        )
                        drift_speed_z = signed_speed_from_seed(
                            seed=variation_seed + 79,
                            variant_count=9,
                            minimum_magnitude=0.2,
                            maximum_magnitude=0.9,
                        )
            if should_spin:
                spin_speed_x = signed_speed_from_seed(
                    seed=variation_seed + 5,
                    variant_count=gameplay_settings.obstacle_spin_variants + 6,
                    minimum_magnitude=gameplay_settings.obstacle_spin_speed_min,
                    maximum_magnitude=gameplay_settings.obstacle_spin_speed_max,
                )
                spin_speed_y = signed_speed_from_seed(
                    seed=variation_seed + 11,
                    variant_count=gameplay_settings.obstacle_spin_variants + 10,
                    minimum_magnitude=gameplay_settings.obstacle_spin_speed_min,
                    maximum_magnitude=gameplay_settings.obstacle_spin_speed_max,
                )
                spin_speed_z = signed_speed_from_seed(
                    seed=variation_seed + 19,
                    variant_count=gameplay_settings.obstacle_rock_variants + 10,
                    minimum_magnitude=abs(gameplay_settings.obstacle_rock_speed_min),
                    maximum_magnitude=abs(gameplay_settings.obstacle_rock_speed_max),
                )
        else:
            spin_speed_x = 0.0
            spin_speed_y = 6.0 + ((variation_seed % 5) * 2.5)
            spin_speed_z = 0.0

    target_rgba = (
        cast("float", target_color.r),
        cast("float", target_color.g),
        cast("float", target_color.b),
        cast("float", target_color.a),
    )
    entity.color = rgba_color(target_rgba[0], target_rgba[1], target_rgba[2], 0.0)

    return SpawnedObject(
        entity=entity,
        entity_kind=blueprint.entity_kind,
        color_name=blueprint.color_name,
        model_name=spawn_model,
        collision_radius=blueprint.collision_radius,
        score_value=blueprint.score_value,
        band_index=band_index,
        spin_speed_x=spin_speed_x,
        spin_speed_y=spin_speed_y,
        spin_speed_z=spin_speed_z,
        bob_amplitude=bob_amplitude,
        bob_frequency=bob_frequency,
        pulse_amplitude=pulse_amplitude,
        pulse_frequency=pulse_frequency,
        base_x=entity.x,
        base_y=entity.y,
        base_z=entity.z,
        drift_speed_x=drift_speed_x,
        drift_speed_z=drift_speed_z,
        drift_progress=0.0,
        base_scale=base_scale,
        motion_kind=blueprint.motion_kind,
        motion_amplitude=blueprint.motion_amplitude,
        motion_frequency=blueprint.motion_frequency,
        motion_phase=blueprint.motion_phase,
        spawn_time=monotonic(),
        fade_duration=fade_duration,
        target_rgba=target_rgba,
    )


def schedule_next_powerup_spawn(
    *,
    run_state: FallingRunState,
    rng: Random,
    gameplay_settings: GameplayTuningSettings,
    now: float,
) -> None:
    """Schedule the next powerup spawn time."""
    jitter = rng.uniform(
        -gameplay_settings.powerup_spawn_jitter_seconds,
        gameplay_settings.powerup_spawn_jitter_seconds,
    )
    interval = max(4.0, gameplay_settings.powerup_spawn_interval_seconds + jitter)
    run_state.next_powerup_spawn_at = now + interval


def spawn_powerup(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    # R0913: explicit spawn inputs.
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    movement_settings: MovementSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Spawn a single magnet powerup ahead of the player."""
    spawn_y = player_y - (fall_settings.spawn_ahead_distance * 0.35)
    max_radius = movement_settings.play_area_radius * 0.6
    spawn_x = rng.uniform(-max_radius, max_radius)
    spawn_z = rng.uniform(-max_radius, max_radius)
    entity_name = f"powerup_magnet_{int(spawn_y)}"
    entity = Entity(
        name=entity_name,
        model=POWERUP_MODEL_NAME,
        color=POWERUP_BASE_COLOR,
        scale=Vec3(1.2, 1.2, 1.2),
        position=Vec3(spawn_x, spawn_y, spawn_z),
    )
    entity.unlit = True
    Entity(
        parent=entity,
        name=f"{entity_name}_halo",
        model=POWERUP_MODEL_NAME,
        scale=Vec3(1.85, 1.85, 1.85),
        color=POWERUP_HALO_COLOR,
        unlit=True,
    )
    run_state.spawned_objects.append(
        SpawnedObject(
            entity=entity,
            entity_kind="powerup",
            color_name="magnet",
            model_name=POWERUP_MODEL_NAME,
            collision_radius=4.0,
            score_value=0,
            band_index=0,
            base_x=entity.x,
            base_y=entity.y,
            base_z=entity.z,
            base_scale=Vec3(1.2, 1.2, 1.2),
            spawn_time=monotonic(),
            powerup_kind=POWERUP_MAGNET_KIND,
        ),
    )
    schedule_next_powerup_spawn(
        run_state=run_state,
        rng=rng,
        gameplay_settings=gameplay_settings,
        now=monotonic(),
    )


def update_powerup_spawning(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
    # R0913: explicit spawn inputs.
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    movement_settings: MovementSettings,
    gameplay_settings: GameplayTuningSettings,
    now: float,
) -> None:
    """Spawn powerups on an independent timer."""
    if run_state.next_powerup_spawn_at <= 0.0:
        schedule_next_powerup_spawn(
            run_state=run_state,
            rng=rng,
            gameplay_settings=gameplay_settings,
            now=now,
        )
        spawn_powerup(
            run_state=run_state,
            player_y=player_y,
            rng=rng,
            fall_settings=fall_settings,
            movement_settings=movement_settings,
            gameplay_settings=gameplay_settings,
        )
        return
    if now < run_state.next_powerup_spawn_at:
        return
    spawn_powerup(
        run_state=run_state,
        player_y=player_y,
        rng=rng,
        fall_settings=fall_settings,
        movement_settings=movement_settings,
        gameplay_settings=gameplay_settings,
    )


def spawn_bands_ahead(
    *,
    run_state: FallingRunState,
    player_y: float,
    rng: Random,
    fall_settings: FallSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Spawn new obstacle/coin bands until the ahead window is filled."""
    while should_spawn_next_band(
        next_band_y=run_state.next_band_y,
        player_y=player_y,
        spawn_ahead_distance=fall_settings.spawn_ahead_distance,
    ):
        blueprints = build_fall_band_blueprints(
            band_index=run_state.next_band_index,
            y_position=run_state.next_band_y,
            rng=rng,
            coin_pattern_index=run_state.coin_pattern_index,
        )
        for blueprint_index, blueprint in enumerate(blueprints):
            run_state.spawned_objects.append(
                spawn_entity_from_blueprint(
                    blueprint=blueprint,
                    band_index=run_state.next_band_index,
                    blueprint_index=blueprint_index,
                    gameplay_settings=gameplay_settings,
                ),
            )

        run_state.next_band_index += 1
        run_state.next_band_y -= BAND_SPACING
