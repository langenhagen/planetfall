"""Backdrop helpers for sky and atmosphere presentation."""

import importlib
from math import cos, sin, tau
from pathlib import Path
from random import Random
from time import monotonic
from typing import cast

import ursina.color as color_module
from ursina import Entity, Shader, Vec3, load_texture

from planetfall.game.runtime_assets import ASSETS_DIR
from planetfall.game.runtime_colors import lerp_rgb_color, rgba_color
from planetfall.game.runtime_controls import lerp_scalar
from planetfall.game.runtime_state import BackdropState, LightingRig

SKY_BLEND_HOLD_SECONDS = 24.0
SKY_BLEND_DURATION_SECONDS = 6.0
SKY_BLEND_MIN_TEXTURES = 2
PLANET_APPROACH_DEPTH = 1600.0
MOTION_MOTE_COUNT = 24
MOTION_MOTE_VERTICAL_SPAN = 72.0
SPACE_PARTICLE_COUNT = 96
SPACE_PARTICLE_RADIUS_MIN = 2.0
SPACE_PARTICLE_RADIUS_MAX = 6.0
SPACE_PARTICLE_DEPTH_SPAN = 120.0
SPACE_PARTICLE_START_OFFSET = -100.0
SPACE_PARTICLE_SCALE_MIN = 0.006
SPACE_PARTICLE_SCALE_MAX = 0.02
SPACE_PARTICLE_SWIRL_RATE = 0.08
SPACE_PARTICLE_DRIFT_RATE = 14.0

SKY_BLEND_SHADER = Shader(
    name="sky_blend_shader",
    language=Shader.GLSL,
    fragment="""
#version 430

in vec2 uv;
out vec4 color;

uniform sampler2D p3d_Texture0;
uniform sampler2D secondary_texture;
uniform float blend_factor;

void main() {
    vec4 primary = texture(p3d_Texture0, uv);
    vec4 secondary = texture(secondary_texture, uv);
    color = vec4(mix(primary.rgb, secondary.rgb, blend_factor), 1.0);
}
""",
    default_input={
        "blend_factor": 0.0,
    },
)


def resolve_space_sky_texture_paths() -> tuple[Path, ...]:
    """Resolve all available sky textures for timed cross-fade cycling."""
    resolved: list[Path] = []

    for extension in ("*.txo",):
        resolved.extend(
            sorted(
                Path(path)
                for path in Path(ASSETS_DIR / "sky").glob(extension)
                if path.is_file()
            ),
        )

    seen: set[Path] = set()
    deduped: list[Path] = []
    for texture_path in resolved:
        if texture_path in seen:
            continue
        seen.add(texture_path)
        deduped.append(texture_path)
    return tuple(deduped)


def initialize_sky_texture_blend_state(
    sky_entity: Entity,
) -> None:
    # W0212: store blend state on sky entity.
    # pylint: disable=protected-access
    """Prepare shader inputs and runtime state for sky texture cross-fading."""
    texture_paths = resolve_space_sky_texture_paths()
    if not texture_paths:
        return

    texture_assets = [
        path.relative_to(Path(ASSETS_DIR)).as_posix() for path in texture_paths
    ]
    preloaded_textures = tuple(
        load_texture(texture_asset) for texture_asset in texture_assets
    )
    # SLF001: private access; store blend state.
    sky_entity._sky_blend_assets = tuple(texture_assets)  # noqa: SLF001
    sky_entity._sky_blend_textures = preloaded_textures  # noqa: SLF001
    sky_entity._sky_blend_current = 0  # noqa: SLF001
    sky_entity._sky_blend_next = 1 if len(texture_assets) > 1 else 0  # noqa: SLF001
    sky_entity._sky_blend_cycle_start = monotonic()  # noqa: SLF001

    sky_entity.texture = texture_assets[0]
    if len(texture_assets) > 1:
        sky_entity.shader = SKY_BLEND_SHADER
        sky_entity.set_shader_input("secondary_texture", preloaded_textures[1])
        sky_entity.set_shader_input("blend_factor", 0.0)


# R0914: keep explicit particle tuning locals.
def create_space_backdrop() -> BackdropState:  # pylint: disable=too-many-locals
    """Create HDRI sky plus light atmospheric motion cues."""
    sky_module = importlib.import_module("ursina.prefabs.sky")
    sky_factory = cast("type[Entity]", sky_module.Sky)
    sky_entity = sky_factory()
    initialize_sky_texture_blend_state(sky_entity)

    motion_motes = [
        Entity(
            name=f"atmo_mote_{mote_index}",
            model="cube",
            position=Vec3(0.0, 0.0, 0.0),
            scale=Vec3(0.06, 2.0, 0.06),
            color=rgba_color(0.74, 0.92, 1.0, 0.2),
            unlit=True,
        )
        for mote_index in range(MOTION_MOTE_COUNT)
    ]

    space_particles: list[Entity] = []
    for particle_index in range(SPACE_PARTICLE_COUNT):
        ratio = particle_index / max(1, SPACE_PARTICLE_COUNT - 1)
        # S311: non-crypto RNG; B311: gameplay variance.
        rng = Random(12_345 + particle_index)  # noqa: S311  # nosec B311
        radius = lerp_scalar(
            SPACE_PARTICLE_RADIUS_MIN,
            SPACE_PARTICLE_RADIUS_MAX,
            rng.random(),
        )
        scale = lerp_scalar(
            SPACE_PARTICLE_SCALE_MIN,
            SPACE_PARTICLE_SCALE_MAX,
            rng.random(),
        )
        depth_offset = rng.uniform(0.0, SPACE_PARTICLE_DEPTH_SPAN)
        phase = rng.uniform(0.0, tau * 2.0)
        wobble_rate = rng.uniform(0.4, 1.4)
        wobble_amp = rng.uniform(0.2, 1.4)
        drift_bias = rng.uniform(-2.2, 2.2)
        particle = Entity(
            name=f"space_particle_{particle_index}",
            model="sphere",
            position=Vec3(0.0, 0.0, 0.0),
            scale=Vec3(scale, scale, scale),
            color=rgba_color(0.98, 0.99, 1.0, 0.55),
            unlit=True,
        )
        # W0212: store per-particle phase data on the entity.
        # pylint: disable=protected-access
        particle._space_phase = phase + (ratio * tau * 2.0)  # noqa: SLF001
        particle._space_radius = radius  # noqa: SLF001
        particle._space_depth_offset = depth_offset  # noqa: SLF001
        particle._space_scale = scale  # noqa: SLF001
        particle._space_swirl_rate = SPACE_PARTICLE_SWIRL_RATE  # noqa: SLF001
        particle._space_drift_rate = SPACE_PARTICLE_DRIFT_RATE  # noqa: SLF001
        particle._space_wobble_rate = wobble_rate  # noqa: SLF001
        particle._space_wobble_amp = wobble_amp  # noqa: SLF001
        particle._space_drift_bias = drift_bias  # noqa: SLF001
        space_particles.append(particle)

    return BackdropState(
        sky=sky_entity,
        motion_motes=tuple(motion_motes),
        space_particles=tuple(space_particles),
    )


def update_sky_texture_blend(
    sky_entity: Entity,
    runtime_time: float,
) -> None:
    # W0212: update blend state on sky entity.
    # pylint: disable=protected-access
    """Advance timed sky blending so textures smoothly cycle."""
    texture_assets = cast(
        "tuple[str, ...]",
        getattr(sky_entity, "_sky_blend_assets", ()),
    )
    preloaded_textures = cast(
        "tuple[object, ...]",
        getattr(sky_entity, "_sky_blend_textures", ()),
    )
    if len(texture_assets) < SKY_BLEND_MIN_TEXTURES:
        return

    cycle_start = cast(
        "float",
        getattr(sky_entity, "_sky_blend_cycle_start", runtime_time),
    )
    current_index = cast("int", getattr(sky_entity, "_sky_blend_current", 0))
    next_index = cast("int", getattr(sky_entity, "_sky_blend_next", 1))
    full_cycle = SKY_BLEND_HOLD_SECONDS + SKY_BLEND_DURATION_SECONDS
    cycle_elapsed = runtime_time - cycle_start

    while cycle_elapsed >= full_cycle:
        current_index = next_index
        next_index = (next_index + 1) % len(texture_assets)
        sky_entity.texture = texture_assets[current_index]
        sky_entity.set_shader_input("secondary_texture", preloaded_textures[next_index])
        cycle_start += full_cycle
        cycle_elapsed = runtime_time - cycle_start

    if cycle_elapsed <= SKY_BLEND_HOLD_SECONDS:
        blend_factor = 0.0
    else:
        blend_factor = min(
            1.0,
            (cycle_elapsed - SKY_BLEND_HOLD_SECONDS) / SKY_BLEND_DURATION_SECONDS,
        )

    # SLF001: private access; update blend state.
    sky_entity._sky_blend_cycle_start = cycle_start  # noqa: SLF001
    sky_entity._sky_blend_current = current_index  # noqa: SLF001
    sky_entity._sky_blend_next = next_index  # noqa: SLF001
    sky_entity.set_shader_input("blend_factor", blend_factor)


# R0914: keep explicit atmosphere/particle tuning locals.
def update_atmosphere_for_depth(  # pylint: disable=too-many-locals
    *,
    player: Entity,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
    fall_speed: float,
) -> None:
    """Shift sky tone and atmosphere cues while descending."""
    depth = max(0.0, -player.y)
    progress = max(0.0, min(1.0, depth / PLANET_APPROACH_DEPTH))
    runtime_time = monotonic()
    update_sky_texture_blend(backdrop_state.sky, runtime_time)

    backdrop_state.sky.color = lerp_rgb_color((7, 10, 24), (145, 186, 214), progress)
    lighting_rig.ambient_light.color = color_module.rgba(
        0.28,
        0.28,
        0.28,
        1.0,
    )
    lighting_rig.key_light.color = color_module.rgba(
        0.98,
        0.98,
        0.98,
        1.0,
    )

    speed_factor = max(0.0, min(1.0, (fall_speed - 12.0) / 34.0))
    mote_thickness = lerp_scalar(0.05, 0.09, speed_factor)
    mote_length = lerp_scalar(1.8, 3.6, speed_factor)
    for mote_index, mote in enumerate(backdrop_state.motion_motes):
        angle = ((mote_index / MOTION_MOTE_COUNT) * tau) + (runtime_time * 0.18)
        radius = 7.4 + ((mote_index % 7) * 0.82)
        travel = (
            (runtime_time * max(10.0, fall_speed * 0.95)) + (mote_index * 3.7)
        ) % MOTION_MOTE_VERTICAL_SPAN
        mote.position = Vec3(
            player.x + (cos(angle) * radius),
            player.y - 34.0 + travel,
            player.z + (sin(angle) * radius),
        )
        mote.rotation_y = (angle * 57.2958) + 90.0
        mote.scale = Vec3(mote_thickness, mote_length, mote_thickness)
        mote.color = rgba_color(
            lerp_scalar(0.58, 0.92, progress),
            lerp_scalar(0.75, 0.94, progress),
            1.0,
            lerp_scalar(0.08, 0.32, speed_factor),
        )

    if backdrop_state.space_particles:
        # W0212: read per-particle phase data from the entity.
        # pylint: disable=protected-access
        for particle in backdrop_state.space_particles:
            phase = cast("float", getattr(particle, "_space_phase", 0.0))
            radius = cast("float", getattr(particle, "_space_radius", 0.0))
            depth_offset = cast(
                "float",
                getattr(particle, "_space_depth_offset", 0.0),
            )
            scale = cast("float", getattr(particle, "_space_scale", 0.1))
            swirl_rate = cast(
                "float",
                getattr(particle, "_space_swirl_rate", SPACE_PARTICLE_SWIRL_RATE),
            )
            drift_rate = cast(
                "float",
                getattr(particle, "_space_drift_rate", SPACE_PARTICLE_DRIFT_RATE),
            )
            wobble_rate = cast(
                "float",
                getattr(particle, "_space_wobble_rate", 1.0),
            )
            wobble_amp = cast(
                "float",
                getattr(particle, "_space_wobble_amp", 0.0),
            )
            drift_bias = cast(
                "float",
                getattr(particle, "_space_drift_bias", 0.0),
            )
            wobble = sin((runtime_time * wobble_rate) + phase) * wobble_amp
            angle = phase + (runtime_time * swirl_rate) + (wobble * 0.18)
            depth = ((runtime_time * drift_rate) + depth_offset) % (
                SPACE_PARTICLE_DEPTH_SPAN
            )
            particle.position = Vec3(
                player.x + (cos(angle) * (radius + wobble)),
                player.y + SPACE_PARTICLE_START_OFFSET + depth,
                player.z + (sin(angle) * (radius + wobble)) + drift_bias,
            )
            particle.scale = Vec3(scale, scale, scale)
            particle.color = rgba_color(
                lerp_scalar(0.88, 0.98, progress),
                lerp_scalar(0.94, 1.0, progress),
                1.0,
                lerp_scalar(0.32, 0.6, speed_factor),
            )
