"""Ursina runtime for an endless third-person falling game."""

import importlib
from contextlib import suppress
from functools import lru_cache
from math import cos, sin, tau
from pathlib import Path
from random import Random
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol, cast

import ursina
import ursina.color as color_module
import ursina.shaders as ursina_shaders
from ursina import (
    AmbientLight,
    Audio,
    DirectionalLight,
    Entity,
    Shader,
    Text,
    Vec2,
    Vec3,
    application,
    camera,
    destroy,
    lerp_exponential_decay,
    load_texture,
    mouse,
    scene,
    window,
)
from ursina.main import Ursina

from .config import (
    CameraSettings,
    FallSettings,
    GameplayTuningSettings,
    GameSettings,
    MovementSettings,
)
from .runtime_controls import (
    clamp_to_play_area,
    compute_control_axes,
    compute_fall_speed,
    compute_look_angles,
    compute_smoothed_lateral_speed,
    compute_zoom_distance,
    lerp_scalar,
    rotate_planar_velocity_by_yaw,
    should_despawn_object,
    should_spawn_next_band,
)
from .runtime_postfx import next_post_process_option, toggle_render_mode
from .runtime_state import (
    BackdropState,
    CameraState,
    FallingRunState,
    LightingRig,
    MotionState,
    OrbitRig,
    PlayerVisualState,
    SpawnedObject,
)
from .runtime_ui import (
    create_controls_hint,
    create_pause_text,
    create_status_text,
    update_status_text,
)
from .scene import (
    BAND_SPACING,
    COIN_SCORE_VALUE,
    FallingBlueprint,
    build_fall_band_blueprints,
)

if TYPE_CHECKING:
    from ursina.color import Color


LIT_SHADER = cast("object", ursina_shaders.lit_with_shadows_shader)
PLAYER_COLLISION_RADIUS = 0.95
RUN_RANDOM_SEED = 20260224
PLANET_APPROACH_DEPTH = 1600.0
STARFIELD_COUNT = 36
STARFIELD_RADIUS = 74.0
NEBULA_COUNT = 4
MOTION_MOTE_COUNT = 24
MOTION_MOTE_VERTICAL_SPAN = 72.0
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
SPACE_SKY_DIR = ASSETS_DIR / "sky" / "NightSkyHDRI009_4K"
SPACE_SKY_TEXTURE_CANDIDATES = (
    "NightSkyHDRI009_4K_TONEMAPPED.jpg",
    "NightSkyHDRI009.png",
    "NightSkyHDRI009_4K_HDR.exr",
)
SKY_BLEND_HOLD_SECONDS = 24.0
SKY_BLEND_DURATION_SECONDS = 6.0
ASTEROID_MODEL_NAME = "models/asteroids/Asteroid_1.obj"
ASTEROID_MODEL_VARIANTS: tuple[str, ...] = (
    "models/asteroids/Asteroid_1.obj",
    "models/asteroids/Rocky_Asteroid_2.obj",
    "models/asteroids/Rocky_Asteroid_3.obj",
    "models/asteroids/Rocky_Asteroid_4.obj",
    "models/asteroids/Rocky_Asteroid_5.obj",
    "models/asteroids/Rocky_Asteroid_6.obj",
)
ASTEROID_DIFFUSE_TEXTURE_BY_MODEL: dict[str, str] = {
    "models/asteroids/Asteroid_1.obj": (
        "models/asteroids/Textures_Asteroid_1/Asteroid_1_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_2.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_2/Rocky_Asteroid_2_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_3.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_3/Rocky_Asteroid_3_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_4.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_4/Rocky_Asteroid_4_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_5.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_5/Rocky_Asteroid_5_Diffuse_1K.png"
    ),
    "models/asteroids/Rocky_Asteroid_6.obj": (
        "models/asteroids/Textures_Rocky_Asteroid_6/Rocky_Asteroid_6_Diffuse_1K.png"
    ),
}
ASTEROID_SCALE_MIN = 0.6
ASTEROID_SCALE_MAX = 2.5
COIN_SFX_NAMES = ("audio/sfx/345297_6212127-lq.mp3",)
IMPACT_SFX_NAMES = ("audio/sfx/explosionCrunch_000.ogg",)
SCROLL_DIRECTION_BY_KEY = {
    "scroll up": 1,
    "scroll down": -1,
    "gamepad dpad up": 1,
    "gamepad dpad down": -1,
}
RESTART_KEYS = {"r"}
TOGGLE_CONTROLS_KEYS = {"u"}
RECENTER_CAMERA_KEYS = {"c", "gamepad dpad left"}
PAUSE_KEYS = {"p", "gamepad start"}
POST_PROCESS_CYCLE_KEYS = {"t"}
RENDER_MODE_TOGGLE_KEYS = {"y"}
ANIMATION_CULL_DISTANCE = 170.0
OBSTACLE_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 3.0
COIN_ANIMATION_CULL_DISTANCE = ANIMATION_CULL_DISTANCE * 2.0
COIN_COLLECT_ANIMATION_SECONDS = 0.18

CAMERA_POST_PROCESS_OPTIONS: tuple[tuple[str, object | None], ...] = (
    ("Off", None),
    ("SSAO", cast("object", ursina_shaders.ssao_shader)),
    (
        "Vertical Blur",
        cast("object", ursina_shaders.camera_vertical_blur_shader),
    ),
)

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


class GamepadVibrateCallable(Protocol):
    """Callable protocol for Ursina's optional gamepad vibrate hook."""

    def __call__(self, **_kwargs: float) -> object:
        """Trigger gamepad vibration with motor intensities and duration."""


@lru_cache(maxsize=32)
def resolve_color(color_name: str) -> Color:
    """Resolve a color name from Ursina's built-in color palette."""
    return cast("Color", getattr(color_module, color_name, color_module.white))


def rgba_color(red: float, green: float, blue: float, alpha: float = 1.0) -> Color:
    """Create a color using Ursina's runtime rgba helper."""
    # B009: getattr-with-constant; Ursina exposes color helpers dynamically.
    rgba_factory = getattr(color_module, "rgba")  # noqa: B009
    return cast("Color", rgba_factory(red, green, blue, alpha))


def mark_lit_shadowed(entity: Entity) -> Entity:
    """Apply the project-default lit shader without shadow casting."""
    entity.shader = LIT_SHADER
    return entity


def get_frame_dt() -> float:
    """Read frame delta from Ursina's dynamic runtime module."""
    # Ursina exposes frame delta via dynamic module attributes.
    # B009: getattr-with-constant; ursina.time.dt is dynamic at runtime.
    return cast("float", getattr(getattr(ursina, "time"), "dt", 0.0))  # noqa: B009


def lerp_rgb_color(
    start_rgb: tuple[int, int, int],
    end_rgb: tuple[int, int, int],
    factor: float,
) -> Color:
    """Interpolate between two rgb tuples and return a color value."""
    clamped_factor = max(0.0, min(1.0, factor))
    red = round(lerp_scalar(float(start_rgb[0]), float(end_rgb[0]), clamped_factor))
    green = round(lerp_scalar(float(start_rgb[1]), float(end_rgb[1]), clamped_factor))
    blue = round(lerp_scalar(float(start_rgb[2]), float(end_rgb[2]), clamped_factor))
    return rgba_color(red / 255.0, green / 255.0, blue / 255.0, 1.0)


@lru_cache(maxsize=2048)
def deterministic_probability_hit(*, seed: int, probability: float) -> bool:
    """Return deterministic pseudo-random chance hit from integer seed."""
    clamped_probability = max(0.0, min(1.0, probability))
    if clamped_probability <= 0.0:
        return False
    if clamped_probability >= 1.0:
        return True

    hashed_seed = (seed * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    return (hashed_seed / 0x80000000) < clamped_probability


@lru_cache(maxsize=2048)
def discrete_value_in_range(
    *,
    seed: int,
    variant_count: int,
    minimum: float,
    maximum: float,
) -> float:
    """Map an integer seed to one of N evenly spaced values in a range."""
    if variant_count <= 1:
        return minimum

    clamped_variant_count = max(2, variant_count)
    variant_index = seed % clamped_variant_count
    interpolation = variant_index / (clamped_variant_count - 1)
    return minimum + ((maximum - minimum) * interpolation)


@lru_cache(maxsize=2048)
def signed_speed_from_seed(
    *,
    seed: int,
    variant_count: int,
    minimum_magnitude: float,
    maximum_magnitude: float,
) -> float:
    """Generate deterministic signed speed with bidirectional variance."""
    magnitude = discrete_value_in_range(
        seed=seed,
        variant_count=variant_count,
        minimum=minimum_magnitude,
        maximum=maximum_magnitude,
    )
    direction = -1.0 if seed % 2 == 0 else 1.0
    return magnitude * direction


@lru_cache(maxsize=256)
def choose_asteroid_variant(variation_seed: int) -> tuple[str, str]:
    """Select deterministic asteroid model and diffuse texture by seed."""
    variant_index = variation_seed % len(ASTEROID_MODEL_VARIANTS)
    model_name = ASTEROID_MODEL_VARIANTS[variant_index]
    return model_name, ASTEROID_DIFFUSE_TEXTURE_BY_MODEL[model_name]


def configure_window(settings: GameSettings) -> None:
    """Apply top-level window settings."""
    window.title = settings.window_title
    window.borderless = settings.borderless
    window.fullscreen = settings.fullscreen
    window.entity_counter.enabled = False
    window.collider_counter.enabled = False


def add_avatar_part(
    *,
    parent: Entity,
    name: str,
    model: str,
    color_name: str,
    scale: Vec3,
    position: Vec3,
) -> Entity:
    """Create one named avatar part for scene-inspector readability."""
    part = Entity(
        parent=parent,
        name=name,
        model=model,
        color=resolve_color(color_name),
        scale=scale,
        position=position,
    )
    return mark_lit_shadowed(part)


def spawn_player_avatar() -> Entity:
    """Spawn a stylized falling character visible in third-person view."""
    avatar = Entity(name="player_faller_root", position=Vec3(0.0, 0.0, 0.0))

    add_avatar_part(
        parent=avatar,
        name="player_torso",
        model="cube",
        color_name="azure",
        scale=Vec3(1.15, 1.55, 0.8),
        position=Vec3(0.0, 0.0, 0.0),
    )
    add_avatar_part(
        parent=avatar,
        name="player_head",
        model="sphere",
        color_name="peach",
        scale=Vec3(0.78, 0.78, 0.78),
        position=Vec3(0.0, 1.12, 0.0),
    )
    add_avatar_part(
        parent=avatar,
        name="player_pack",
        model="cube",
        color_name="dark_gray",
        scale=Vec3(0.88, 0.92, 0.32),
        position=Vec3(0.0, 0.2, -0.56),
    )

    for side_name, side_x in (("left", -0.86), ("right", 0.86)):
        add_avatar_part(
            parent=avatar,
            name=f"player_arm_{side_name}",
            model="cube",
            color_name="orange",
            scale=Vec3(0.34, 1.18, 0.34),
            position=Vec3(side_x, -0.06, 0.0),
        )

    for side_name, side_x in (("left", -0.34), ("right", 0.34)):
        add_avatar_part(
            parent=avatar,
            name=f"player_leg_{side_name}",
            model="cube",
            color_name="navy",
            scale=Vec3(0.38, 1.02, 0.38),
            position=Vec3(side_x, -1.18, 0.0),
        )

    return avatar


def create_player_visual_state(player: Entity) -> PlayerVisualState:
    """Attach contrails and aura entities to enrich player visuals."""
    aura = Entity(
        parent=player,
        name="player_plasma_aura",
        model="sphere",
        position=Vec3(0.0, -0.2, 0.0),
        scale=Vec3(1.75, 1.95, 1.75),
        color=rgba_color(0.3, 0.72, 1.0, 0.16),
        unlit=True,
    )
    contrails = (
        Entity(
            parent=player,
            name="player_contrail_left",
            model="cube",
            position=Vec3(-0.22, -1.45, -0.62),
            scale=Vec3(0.1, 2.4, 0.1),
            color=rgba_color(0.45, 0.89, 1.0, 0.28),
            unlit=True,
        ),
        Entity(
            parent=player,
            name="player_contrail_right",
            model="cube",
            position=Vec3(0.22, -1.45, -0.62),
            scale=Vec3(0.1, 2.4, 0.1),
            color=rgba_color(0.45, 0.89, 1.0, 0.28),
            unlit=True,
        ),
    )
    return PlayerVisualState(contrails=contrails, aura=aura)


def update_player_visual_state(
    *,
    player_visual_state: PlayerVisualState,
    motion_state: MotionState,
    fall_speed: float,
) -> None:
    """Animate player aura and contrails based on speed and steering."""
    runtime_time = monotonic()
    speed_factor = max(0.0, min(1.0, (fall_speed - 10.0) / 32.0))
    lateral_factor = max(
        0.0,
        min(
            1.0,
            (abs(motion_state.horizontal_speed) + abs(motion_state.depth_speed)) / 26.0,
        ),
    )

    aura_scale = lerp_scalar(1.65, 2.25, speed_factor)
    player_visual_state.aura.scale = Vec3(aura_scale, aura_scale * 1.08, aura_scale)
    player_visual_state.aura.color = rgba_color(
        lerp_scalar(0.26, 0.62, speed_factor),
        lerp_scalar(0.65, 0.86, speed_factor),
        1.0,
        lerp_scalar(0.12, 0.24, speed_factor),
    )

    trail_width = lerp_scalar(0.08, 0.14, speed_factor)
    trail_length = lerp_scalar(1.9, 3.8, speed_factor)
    for trail_index, contrail in enumerate(player_visual_state.contrails):
        sway_sign = -1.0 if trail_index == 0 else 1.0
        sway = sin((runtime_time * 7.4) + (trail_index * 1.7)) * 0.08
        contrail.position = Vec3(
            sway_sign * (0.2 + (lateral_factor * 0.06)),
            -1.5 - (speed_factor * 0.16),
            -0.62 + sway,
        )
        contrail.scale = Vec3(trail_width, trail_length, trail_width)
        contrail.color = rgba_color(
            lerp_scalar(0.38, 0.8, speed_factor),
            lerp_scalar(0.74, 0.95, speed_factor),
            1.0,
            lerp_scalar(0.2, 0.52, speed_factor),
        )


def configure_camera() -> None:
    """Set up base camera parent and transform defaults."""
    camera.parent = scene
    camera.rotation = Vec3(0.0, 0.0, 0.0)


def apply_camera_post_process(shader: object | None) -> None:
    """Apply one camera post process shader, or fully disable post process."""
    if shader is None:
        filter_manager = getattr(camera, "filter_manager", None)
        if filter_manager is not None:
            with suppress(Exception):
                filter_manager.cleanup()
        filter_quad = getattr(camera, "filter_quad", None)
        if filter_quad is not None:
            with suppress(Exception):
                filter_quad.removeNode()
        camera.filter_manager = None
        camera.filter_quad = None
        camera._shader = None
        return

    camera.shader = shader


def create_camera_orbit_rig(settings: GameSettings) -> OrbitRig:
    """Create yaw and pitch pivots used for stable orbit controls."""
    yaw_pivot = Entity(name="camera_yaw_pivot", parent=scene)
    pitch_pivot = Entity(name="camera_pitch_pivot", parent=yaw_pivot)
    camera.parent = pitch_pivot
    camera.position = Vec3(0.0, 0.0, -settings.camera.distance)
    camera.rotation = Vec3(0.0, 0.0, 0.0)
    return OrbitRig(yaw_pivot=yaw_pivot, pitch_pivot=pitch_pivot)


def configure_mouse_capture() -> None:
    """Capture the mouse cursor for camera look controls."""
    mouse.locked = True
    mouse.visible = False


def configure_lighting(focus_entity: Entity) -> LightingRig:
    """Create one sun light and ambient fill without drop shadows."""
    sun_direction = Vec3(0.75, -1.2, -0.45).normalized()
    key_light = DirectionalLight(shadows=False)
    key_light.color = color_module.white
    key_light.look_at(sun_direction)

    ambient_light = AmbientLight()
    ambient_light.color = color_module.rgba(0.24, 0.26, 0.31, 1.0)

    _ = focus_entity

    return LightingRig(key_light=key_light, ambient_light=ambient_light)


def create_space_backdrop() -> BackdropState:
    """Create HDRI sky plus layered ambience for deep-space descent."""
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

    depth_overlay = Entity(
        parent=camera.ui,
        name="depth_color_overlay",
        model="quad",
        z=1.0,
        scale=Vec2(2.2, 1.3),
        color=rgba_color(0.04, 0.08, 0.18, 0.0),
        unlit=True,
    )

    return BackdropState(
        sky=sky_entity,
        motion_motes=tuple(motion_motes),
        depth_overlay=depth_overlay,
    )


def resolve_space_sky_texture_path() -> Path | None:
    """Resolve a custom sky texture path from the NightSkyHDRI asset folder."""
    for file_name in SPACE_SKY_TEXTURE_CANDIDATES:
        candidate = SPACE_SKY_DIR / file_name
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=8)
def resolve_music_paths() -> tuple[Path, ...]:
    """Resolve all available background music tracks."""
    music_dir = ASSETS_DIR / "audio" / "music"
    if not music_dir.exists():
        return ()
    return tuple(sorted(path for path in music_dir.glob("*.mp3") if path.is_file()))


def build_music_playlist() -> list[Path]:
    """Build a shuffled playlist of all available music tracks."""
    playlist = list(resolve_music_paths())
    Random().shuffle(playlist)  # noqa: S311  # nosec B311 - non-crypto shuffle.
    return playlist


def start_music_track(track_path: Path) -> Audio:
    """Start a single background music track (non-looping)."""
    relative_track = track_path.relative_to(ASSETS_DIR.parent).as_posix()
    audio_factory: Any = Audio
    return audio_factory(
        relative_track,
        loop=False,
        autoplay=True,
        auto_destroy=True,
        volume=0.6,
    )


def advance_music_playlist(
    *,
    current_track: Audio | None,
    playlist: list[Path],
) -> Audio | None:
    """Advance to the next track when the current one finishes."""
    if current_track is not None and current_track.playing:
        return current_track

    if not playlist:
        playlist.extend(build_music_playlist())
        if not playlist:
            return None

    return start_music_track(playlist.pop(0))


def resolve_space_sky_texture_paths() -> tuple[Path, ...]:
    """Resolve all available sky textures for timed cross-fade cycling."""
    resolved: list[Path] = []

    for extension in ("*.png", "*.jpg", "*.jpeg", "*.exr"):
        resolved.extend(
            sorted(
                path for path in (ASSETS_DIR / "sky").glob(extension) if path.is_file()
            ),
        )

    fallback_texture = resolve_space_sky_texture_path()
    if fallback_texture is not None and fallback_texture not in resolved:
        resolved.append(fallback_texture)

    seen: set[Path] = set()
    deduped: list[Path] = []
    for texture_path in resolved:
        if texture_path in seen:
            continue
        seen.add(texture_path)
        deduped.append(texture_path)
    return tuple(deduped)


def initialize_sky_texture_blend_state(sky_entity: Entity) -> None:
    """Prepare shader inputs and runtime state for sky texture cross-fading."""
    texture_paths = resolve_space_sky_texture_paths()
    if not texture_paths:
        return

    texture_assets = [path.relative_to(ASSETS_DIR).as_posix() for path in texture_paths]
    preloaded_textures = tuple(
        load_texture(texture_asset) for texture_asset in texture_assets
    )
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


def update_sky_texture_blend(sky_entity: Entity, runtime_time: float) -> None:
    """Advance timed sky blending so textures smoothly cycle for inspection."""
    texture_assets = cast(
        "tuple[str, ...]",
        getattr(sky_entity, "_sky_blend_assets", ()),
    )
    preloaded_textures = cast(
        "tuple[object, ...]",
        getattr(sky_entity, "_sky_blend_textures", ()),
    )
    if len(texture_assets) < 2:
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

    sky_entity._sky_blend_cycle_start = cycle_start  # noqa: SLF001
    sky_entity._sky_blend_current = current_index  # noqa: SLF001
    sky_entity._sky_blend_next = next_index  # noqa: SLF001
    sky_entity.set_shader_input("blend_factor", blend_factor)


def update_atmosphere_for_depth(
    *,
    player: Entity,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
    fall_speed: float,
) -> None:
    """Shift sky, stars, and atmosphere effects while descending."""
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

    backdrop_state.depth_overlay.color = rgba_color(0.0, 0.0, 0.0, 0.0)


def spawn_entity_from_blueprint(
    *,
    blueprint: FallingBlueprint,
    band_index: int,
    blueprint_index: int,
    gameplay_settings: GameplayTuningSettings,
) -> SpawnedObject:
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
        mark_lit_shadowed(entity)
        entity.unlit = False
        entity.texture = None
        target_color = rgba_color(1.0, 0.92, 0.22, 1.0)
        is_high_value_coin = blueprint.score_value > COIN_SCORE_VALUE
        should_render_coin_halo = deterministic_probability_hit(
            seed=variation_seed + 13,
            probability=gameplay_settings.high_value_coin_halo_chance,
        )
        if is_high_value_coin:
            target_color = rgba_color(1.0, 0.84, 0.18, 1.0)
            if should_render_coin_halo:
                Entity(
                    parent=entity,
                    name=f"{entity_name}_coin_halo",
                    model=spawn_model,
                    scale=Vec3(1.18, 1.18, 1.18),
                    color=rgba_color(1.0, 0.92, 0.3, 0.18),
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
        if blueprint.entity_kind == "obstacle":
            should_spin = deterministic_probability_hit(
                seed=variation_seed + 3,
                probability=0.7,
            )
            if blueprint.model == ASTEROID_MODEL_NAME:
                target_color = resolve_color("white")
                entity.unlit = True
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
        model_name=spawn_model,
        collision_radius=blueprint.collision_radius,
        score_value=blueprint.score_value,
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
        spawn_time=monotonic(),
        fade_duration=fade_duration,
        target_rgba=target_rgba,
    )


def trigger_impact_rumble(intensity: float) -> None:
    """Trigger brief gamepad rumble on obstacle impact, if available."""
    vibrate = resolve_gamepad_vibrate_callable()
    if vibrate is None:
        return

    with suppress(Exception):
        vibrate(
            low_freq_motor=max(0.2, min(1.0, intensity)),
            high_freq_motor=max(0.2, min(1.0, intensity + 0.1)),
            duration=0.09,
        )


@lru_cache(maxsize=1)
def resolve_gamepad_vibrate_callable() -> GamepadVibrateCallable | None:
    """Resolve and cache the optional Ursina gamepad vibrate callable."""
    with suppress(Exception):
        gamepad_module = importlib.import_module("ursina.gamepad")
        if not hasattr(gamepad_module, "vibrate"):
            return None
        vibrate = gamepad_module.vibrate
        if callable(vibrate):
            return cast("GamepadVibrateCallable", vibrate)
    return None


def play_sfx_clip(*, clip_name: str, volume: float, pitch: float) -> None:
    """Play one-shot sound effect with runtime-set volume and pitch."""
    audio_factory: Any = Audio
    audio_factory(clip_name, volume=volume, pitch=pitch, auto_destroy=True)


def play_coin_pickup_sfx() -> None:
    """Play the configured coin pickup sound effect."""
    with suppress(Exception):
        coin_path = resolve_sfx_path(
            preferred_names=COIN_SFX_NAMES,
            fallback_pattern="coin*.ogg",
        )
        if coin_path is not None:
            play_sfx_clip(clip_name=coin_path.name, volume=0.7, pitch=1.0)
            return
        play_sfx_clip(clip_name="sine", volume=1.0, pitch=2.0)


def play_obstacle_hit_sfx() -> None:
    """Play the configured obstacle impact sound effect."""
    with suppress(Exception):
        impact_path = resolve_sfx_path(
            preferred_names=IMPACT_SFX_NAMES,
            fallback_pattern="*impact*.ogg",
        )
        if impact_path is not None:
            play_sfx_clip(clip_name=impact_path.name, volume=0.75, pitch=1.0)
            return
        play_sfx_clip(clip_name="sine", volume=1.0, pitch=1.0)


@lru_cache(maxsize=8)
def resolve_sfx_path(
    *,
    preferred_names: tuple[str, ...],
    fallback_pattern: str,
) -> Path | None:
    """Resolve an audio file path from preferred names or a fallback glob."""
    for file_name in preferred_names:
        candidate = ASSETS_DIR / file_name
        if candidate.exists():
            return candidate

    fallback_matches = sorted(ASSETS_DIR.glob(fallback_pattern))
    if fallback_matches:
        return fallback_matches[0]

    return None


def initialize_run_state(
    run_state: FallingRunState,
    fall_settings: FallSettings,
) -> None:
    """Reset run-state values to initial defaults."""
    run_state.score = 0
    run_state.collected_orbs = 0
    run_state.reset_count = 0
    run_state.is_paused = False
    run_state.deepest_y = 0.0
    run_state.next_band_index = 0
    run_state.next_band_y = fall_settings.initial_spawn_y
    run_state.last_hit_time = 0.0


def destroy_entity_tree(entity: Entity) -> None:
    """Destroy an entity and any child entities to avoid scene leaks."""
    for child in list(entity.children):
        destroy_entity_tree(cast("Entity", child))
    destroy(entity)


def destroy_spawned_objects(spawned_objects: list[SpawnedObject]) -> None:
    """Destroy spawned entities and clear the container in-place."""
    for spawned in spawned_objects:
        destroy_entity_tree(spawned.entity)
    spawned_objects.clear()


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


def cleanup_passed_objects(
    *,
    run_state: FallingRunState,
    player_y: float,
    cleanup_above_distance: float,
) -> None:
    """Destroy objects that are far above the player after being passed."""
    survivors: list[SpawnedObject] = []
    for spawned in run_state.spawned_objects:
        if should_despawn_object(
            object_y=spawned.entity.y,
            player_y=player_y,
            cleanup_above_distance=cleanup_above_distance,
        ):
            destroy_entity_tree(spawned.entity)
            continue
        survivors.append(spawned)

    run_state.spawned_objects = survivors


def apply_obstacle_recovery(
    *,
    player: Entity,
    motion_state: MotionState,
    recovery_height: float,
) -> None:
    """Move the player upward after an obstacle hit and damp momentum."""
    player.y += recovery_height
    motion_state.horizontal_speed *= 0.2
    motion_state.depth_speed *= 0.2


def process_collisions(
    *,
    player: Entity,
    motion_state: MotionState,
    run_state: FallingRunState,
    fall_settings: FallSettings,
    gameplay_settings: GameplayTuningSettings,
) -> None:
    """Handle collisions with coins and obstacles for score and reset behavior."""
    now = monotonic()
    survivors: list[SpawnedObject] = []

    for spawned in run_state.spawned_objects:
        if spawned.collision_radius <= 0.0:
            survivors.append(spawned)
            continue

        hit_radius = PLAYER_COLLISION_RADIUS + spawned.collision_radius
        delta_y = spawned.entity.y - player.y
        if abs(delta_y) > hit_radius:
            survivors.append(spawned)
            continue

        delta = spawned.entity.position - player.position
        distance_squared = (
            (delta.x * delta.x) + (delta.y * delta.y) + (delta.z * delta.z)
        )
        if distance_squared > (hit_radius * hit_radius):
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "coin":
            spawned.is_collecting = True
            spawned.collect_started_at = now
            spawned.collect_duration = COIN_COLLECT_ANIMATION_SECONDS
            spawned.collect_start_position = Vec3(
                spawned.entity.position.x,
                spawned.entity.position.y,
                spawned.entity.position.z,
            )
            spawned.collision_radius = 0.0
            run_state.collected_orbs += 1
            run_state.score += spawned.score_value
            play_coin_pickup_sfx()
            survivors.append(spawned)
            continue

        if spawned.entity_kind == "obstacle":
            if (
                now - run_state.last_hit_time
                < gameplay_settings.obstacle_hit_cooldown_seconds
            ):
                survivors.append(spawned)
                continue

            destroy_entity_tree(spawned.entity)
            run_state.last_hit_time = now
            run_state.reset_count += 1
            run_state.score = max(
                0,
                run_state.score - fall_settings.recovery_score_penalty,
            )
            play_obstacle_hit_sfx()
            trigger_impact_rumble(intensity=0.65)
            apply_obstacle_recovery(
                player=player,
                motion_state=motion_state,
                recovery_height=fall_settings.recovery_height,
            )
            continue

        destroy_entity_tree(spawned.entity)

    run_state.spawned_objects = survivors


def animate_spawned_objects(
    run_state: FallingRunState,
    dt: float,
    player_y: float,
    player_position: Vec3,
) -> None:
    """Animate collectibles and obstacles for richer motion language."""
    runtime_time = monotonic()
    survivors: list[SpawnedObject] = []
    for spawned in run_state.spawned_objects:
        if spawned.entity_kind == "coin" and spawned.is_collecting:
            collect_duration = max(0.001, spawned.collect_duration)
            collect_progress = max(
                0.0,
                min(
                    1.0,
                    (runtime_time - spawned.collect_started_at) / collect_duration,
                ),
            )
            # Keep transforms invertible; a zero-scale frame can trigger
            # Panda's has_mat() assertion in render/cull internals.
            if collect_progress >= 1.0:
                destroy_entity_tree(spawned.entity)
                continue

            collect_ease = 1.0 - ((1.0 - collect_progress) ** 3)
            collect_target = Vec3(
                player_position.x,
                player_position.y + 0.45,
                player_position.z,
            )
            spawned.entity.position = spawned.collect_start_position + (
                (collect_target - spawned.collect_start_position) * collect_ease
            )
            collect_scale = max(0.0, 1.0 - collect_progress)
            spawned.entity.scale = Vec3(
                spawned.base_scale.x * collect_scale,
                spawned.base_scale.y * collect_scale,
                spawned.base_scale.z * collect_scale,
            )

            survivors.append(spawned)
            continue

        if spawned.fade_duration > 0.0:
            target_red, target_green, target_blue, target_alpha = spawned.target_rgba
            elapsed = runtime_time - spawned.spawn_time
            if elapsed >= spawned.fade_duration:
                spawned.entity.color = rgba_color(
                    target_red,
                    target_green,
                    target_blue,
                    target_alpha,
                )
                spawned.fade_duration = 0.0
            else:
                fade_progress = max(0.0, min(1.0, elapsed / spawned.fade_duration))
                alpha_blend = 0.35 + (fade_progress * 0.65)
                spawned.entity.color = rgba_color(
                    target_red,
                    target_green,
                    target_blue,
                    target_alpha * alpha_blend,
                )

        cull_distance = (
            COIN_ANIMATION_CULL_DISTANCE
            if spawned.entity_kind == "coin"
            else (
                OBSTACLE_ANIMATION_CULL_DISTANCE
                if spawned.entity_kind == "obstacle"
                else ANIMATION_CULL_DISTANCE
            )
        )
        if abs(spawned.entity.y - player_y) > cull_distance:
            if spawned.drift_speed_x != 0.0 or spawned.drift_speed_z != 0.0:
                spawned.drift_blend = 0.0
            survivors.append(spawned)
            continue

        is_sphere_model = spawned.model_name in {"sphere", "icosphere"}

        if spawned.entity_kind == "coin":
            if not is_sphere_model:
                spawned.entity.rotation_y += spawned.spin_speed_y * dt
            if spawned.bob_amplitude > 0.0:
                spawned.entity.y = spawned.base_y + (
                    sin(
                        (runtime_time * spawned.bob_frequency)
                        + spawned.pulse_frequency,
                    )
                    * spawned.bob_amplitude
                )
            if spawned.pulse_amplitude > 0.0:
                pulse_scale = 1.0 + (
                    sin(
                        (runtime_time * spawned.pulse_frequency)
                        + spawned.bob_frequency,
                    )
                    * spawned.pulse_amplitude
                )
                spawned.entity.scale = Vec3(
                    spawned.base_scale.x * pulse_scale,
                    spawned.base_scale.y * pulse_scale,
                    spawned.base_scale.z * pulse_scale,
                )
            survivors.append(spawned)
            continue

        if not is_sphere_model:
            spawned.entity.rotation_x += spawned.spin_speed_x * dt
            spawned.entity.rotation_y += spawned.spin_speed_y * dt
            spawned.entity.rotation_z += spawned.spin_speed_z * dt
            if spawned.drift_speed_x != 0.0 or spawned.drift_speed_z != 0.0:
                spawned.drift_blend = min(1.0, spawned.drift_blend + (dt * 1.6))
                blended_dt = dt * spawned.drift_blend
                spawned.drift_progress += blended_dt
                spawned.entity.x = spawned.base_x + (
                    spawned.drift_progress * spawned.drift_speed_x
                )
                spawned.entity.z = spawned.base_z + (
                    spawned.drift_progress * spawned.drift_speed_z
                )

        survivors.append(spawned)

    run_state.spawned_objects = survivors


def update_camera_tracking(
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    camera_state: CameraState,
    camera_settings: CameraSettings,
    look_velocity: Vec3,
) -> None:
    """Update orbit camera pivots and zoom using current look input."""
    camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
        yaw_angle=camera_state.yaw_angle,
        pitch_angle=camera_state.pitch_angle,
        look_velocity=look_velocity,
        mouse_look_speed=camera_settings.mouse_look_speed,
        min_pitch=camera_settings.min_pitch,
        max_pitch=camera_settings.max_pitch,
    )

    orbit_rig.yaw_pivot.world_position = player.world_position + Vec3(
        0.0,
        camera_settings.height,
        0.0,
    )
    orbit_rig.yaw_pivot.rotation = Vec3(0.0, camera_state.yaw_angle, 0.0)
    orbit_rig.pitch_pivot.rotation = Vec3(camera_state.pitch_angle, 0.0, 0.0)
    camera.position = Vec3(0.0, 0.0, -camera_state.distance)
    camera.rotation_z = 0.0


def apply_player_movement(
    *,
    player: Entity,
    motion_state: MotionState,
    movement_settings: MovementSettings,
    fall_settings: FallSettings,
    camera_yaw_degrees: float,
    x_axis: float,
    z_axis: float,
    dive_axis: float,
    dt: float,
) -> float:
    """Move the player avatar and return effective vertical fall speed."""
    fall_speed: float = compute_fall_speed(
        base_speed=fall_settings.base_speed,
        dive_axis=dive_axis,
        boost_multiplier=fall_settings.boost_multiplier,
        brake_multiplier=fall_settings.brake_multiplier,
    )

    motion_state.horizontal_speed = compute_smoothed_lateral_speed(
        current_speed=motion_state.horizontal_speed,
        axis_input=x_axis,
        max_speed=movement_settings.horizontal_speed,
        acceleration_rate=movement_settings.horizontal_accel_rate,
        deceleration_rate=movement_settings.horizontal_decel_rate,
        dt=dt,
    )
    motion_state.depth_speed = compute_smoothed_lateral_speed(
        current_speed=motion_state.depth_speed,
        axis_input=z_axis,
        max_speed=movement_settings.depth_speed,
        acceleration_rate=movement_settings.depth_accel_rate,
        deceleration_rate=movement_settings.depth_decel_rate,
        dt=dt,
    )

    world_x_speed, world_z_speed = rotate_planar_velocity_by_yaw(
        right_speed=motion_state.horizontal_speed,
        forward_speed=motion_state.depth_speed,
        yaw_degrees=camera_yaw_degrees,
    )

    player.y -= fall_speed * dt
    player.x += world_x_speed * dt
    player.z += world_z_speed * dt
    player.x, player.z = clamp_to_play_area(
        player.x,
        player.z,
        movement_settings.play_area_radius,
    )

    normalized_horizontal = 0.0
    if movement_settings.horizontal_speed > 0.0:
        normalized_horizontal = (
            motion_state.horizontal_speed / movement_settings.horizontal_speed
        )

    normalized_depth = 0.0
    if movement_settings.depth_speed > 0.0:
        normalized_depth = motion_state.depth_speed / movement_settings.depth_speed

    target_roll = normalized_horizontal * movement_settings.tilt_degrees
    target_pitch = normalized_depth * movement_settings.tilt_degrees * 0.7
    player.rotation_z = cast(
        "float",
        lerp_exponential_decay(player.rotation_z, target_roll, dt * 9.0),
    )
    player.rotation_x = cast(
        "float",
        lerp_exponential_decay(player.rotation_x, target_pitch, dt * 9.0),
    )
    return fall_speed


def install_game_controller(
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    settings: GameSettings,
    lighting_rig: LightingRig,
    backdrop_state: BackdropState,
    player_visual_state: PlayerVisualState,
    controls_hint: Text,
    status_text: Text,
    pause_text: Text,
) -> Entity:
    """Attach per-frame gameplay update and input handlers."""
    music_state: dict[str, Audio | None] = {"track": None}
    controller = Entity(name="fall_game_controller")
    randomizer = Random(RUN_RANDOM_SEED)  # noqa: S311  # nosec B311
    camera_state = CameraState(
        yaw_angle=0.0,
        pitch_angle=settings.camera.start_pitch,
        distance=settings.camera.distance,
    )
    motion_state = MotionState()
    run_state = FallingRunState()
    initialize_run_state(run_state, settings.fall)
    post_process_index = 0
    apply_camera_post_process(CAMERA_POST_PROCESS_OPTIONS[post_process_index][1])
    music_playlist = build_music_playlist()

    def reset_run() -> None:
        destroy_spawned_objects(run_state.spawned_objects)
        initialize_run_state(run_state, settings.fall)
        randomizer.seed(RUN_RANDOM_SEED)
        player.position = Vec3(0.0, 0.0, 0.0)
        player.rotation = Vec3(0.0, 0.0, 0.0)
        motion_state.horizontal_speed = 0.0
        motion_state.depth_speed = 0.0
        motion_state.yaw_turn_speed = 0.0
        camera_state.yaw_angle = 0.0
        camera_state.pitch_angle = settings.camera.start_pitch
        camera_state.distance = settings.camera.distance
        apply_camera_post_process(CAMERA_POST_PROCESS_OPTIONS[post_process_index][1])
        pause_text.enabled = False
        if music_state["track"] is not None:
            music_state["track"].play()
        spawn_bands_ahead(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
            fall_speed=settings.fall.base_speed,
        )
        update_player_visual_state(
            player_visual_state=player_visual_state,
            motion_state=motion_state,
            fall_speed=settings.fall.base_speed,
        )
        update_status_text(run_state, status_text)

    reset_run()

    def controller_update() -> None:
        held = cast("dict[str, float]", getattr(ursina, "held_keys", {}))
        mouse_velocity = cast("Vec3", getattr(mouse, "velocity", Vec3(0.0, 0.0, 0.0)))
        x_axis, z_axis, dive_axis, yaw_turn_axis, look_velocity = compute_control_axes(
            held,
            mouse_velocity,
        )

        if not run_state.is_paused:
            music_state["track"] = advance_music_playlist(
                current_track=music_state["track"],
                playlist=music_playlist,
            )

        dt = get_frame_dt()
        if dt <= 0.0:
            update_camera_tracking(
                player=player,
                orbit_rig=orbit_rig,
                camera_state=camera_state,
                camera_settings=settings.camera,
                look_velocity=look_velocity,
            )
            player.rotation_y = camera_state.yaw_angle
            return

        if run_state.is_paused:
            if music_state["track"] is not None and music_state["track"].playing:
                music_state["track"].pause()
            motion_state.yaw_turn_speed = compute_smoothed_lateral_speed(
                current_speed=motion_state.yaw_turn_speed,
                axis_input=0.0,
                max_speed=settings.movement.yaw_turn_speed,
                acceleration_rate=settings.movement.yaw_turn_accel_rate,
                deceleration_rate=settings.movement.yaw_turn_decel_rate,
                dt=dt,
            )
            camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
                yaw_angle=camera_state.yaw_angle,
                pitch_angle=camera_state.pitch_angle,
                look_velocity=look_velocity,
                mouse_look_speed=settings.camera.mouse_look_speed,
                min_pitch=settings.camera.min_pitch,
                max_pitch=settings.camera.max_pitch,
            )
            player.rotation_y = camera_state.yaw_angle
            update_camera_tracking(
                player=player,
                orbit_rig=orbit_rig,
                camera_state=camera_state,
                camera_settings=settings.camera,
                look_velocity=Vec3(0.0, 0.0, 0.0),
            )
            update_status_text(run_state, status_text)
            return

        camera_state.yaw_angle, camera_state.pitch_angle = compute_look_angles(
            yaw_angle=camera_state.yaw_angle,
            pitch_angle=camera_state.pitch_angle,
            look_velocity=look_velocity,
            mouse_look_speed=settings.camera.mouse_look_speed,
            min_pitch=settings.camera.min_pitch,
            max_pitch=settings.camera.max_pitch,
        )

        motion_state.yaw_turn_speed = compute_smoothed_lateral_speed(
            current_speed=motion_state.yaw_turn_speed,
            axis_input=yaw_turn_axis,
            max_speed=settings.movement.yaw_turn_speed,
            acceleration_rate=settings.movement.yaw_turn_accel_rate,
            deceleration_rate=settings.movement.yaw_turn_decel_rate,
            dt=dt,
        )
        camera_state.yaw_angle += motion_state.yaw_turn_speed * dt
        player.rotation_y = camera_state.yaw_angle

        fall_speed = apply_player_movement(
            player=player,
            motion_state=motion_state,
            movement_settings=settings.movement,
            fall_settings=settings.fall,
            camera_yaw_degrees=camera_state.yaw_angle,
            x_axis=x_axis,
            z_axis=z_axis,
            dive_axis=dive_axis,
            dt=dt,
        )
        run_state.deepest_y = min(run_state.deepest_y, player.y)

        spawn_bands_ahead(
            run_state=run_state,
            player_y=player.y,
            rng=randomizer,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        if music_state["track"] is None and music_playlist:
            music_state["track"] = start_music_track(music_playlist.pop(0))
        animate_spawned_objects(run_state, dt, player.y, player.position)
        process_collisions(
            player=player,
            motion_state=motion_state,
            run_state=run_state,
            fall_settings=settings.fall,
            gameplay_settings=settings.gameplay,
        )
        cleanup_passed_objects(
            run_state=run_state,
            player_y=player.y,
            cleanup_above_distance=settings.fall.cleanup_above_distance,
        )

        update_camera_tracking(
            player=player,
            orbit_rig=orbit_rig,
            camera_state=camera_state,
            camera_settings=settings.camera,
            look_velocity=Vec3(0.0, 0.0, 0.0),
        )
        update_atmosphere_for_depth(
            player=player,
            lighting_rig=lighting_rig,
            backdrop_state=backdrop_state,
            fall_speed=fall_speed,
        )
        update_player_visual_state(
            player_visual_state=player_visual_state,
            motion_state=motion_state,
            fall_speed=fall_speed,
        )
        update_status_text(run_state, status_text)

    def controller_input(key: str) -> None:
        nonlocal post_process_index

        if key == "escape":
            application.quit()
            return

        if key in TOGGLE_CONTROLS_KEYS:
            controls_hint.enabled = not controls_hint.enabled

        if key in POST_PROCESS_CYCLE_KEYS:
            post_process_index, _, post_shader = next_post_process_option(
                current_index=post_process_index,
                options=CAMERA_POST_PROCESS_OPTIONS,
            )
            apply_camera_post_process(post_shader)
            update_status_text(run_state, status_text)
            return

        if key in RENDER_MODE_TOGGLE_KEYS:
            current_mode = cast("str", getattr(window, "render_mode", "default"))
            next_mode = toggle_render_mode(current_mode)
            window.render_mode = next_mode
            update_status_text(run_state, status_text)
            return

        if key in PAUSE_KEYS:
            run_state.is_paused = not run_state.is_paused
            pause_text.enabled = run_state.is_paused
            if music_state["track"] is not None:
                if run_state.is_paused:
                    music_state["track"].pause()
                else:
                    music_state["track"].play()
            return

        if key in RESTART_KEYS:
            reset_run()
            return

        if key in RECENTER_CAMERA_KEYS:
            camera_state.yaw_angle = 0.0
            camera_state.pitch_angle = settings.camera.start_pitch

        scroll_direction = SCROLL_DIRECTION_BY_KEY.get(key)
        if scroll_direction is None:
            return

        camera_state.distance = compute_zoom_distance(
            current_distance=camera_state.distance,
            scroll_direction=scroll_direction,
            min_distance=settings.camera.min_distance,
            max_distance=settings.camera.max_distance,
            zoom_step=settings.camera.zoom_step,
        )

    controller.update = controller_update
    controller.input = controller_input
    return controller


def run_game(settings: GameSettings | None = None) -> None:
    """Run the endless third-person falling game."""
    active_settings = GameSettings() if settings is None else settings
    app = cast(
        "object",
        Ursina(
            title=active_settings.window_title,
            development_mode=active_settings.development_mode,
            size=(
                Vec2(
                    active_settings.window_size[0],
                    active_settings.window_size[1],
                )
                if active_settings.window_size is not None
                else None
            ),
        ),
    )
    application.asset_folder = Path(__file__).resolve().parents[2]

    configure_window(active_settings)

    player = spawn_player_avatar()
    player_visual_state = create_player_visual_state(player)
    configure_camera()
    orbit_rig = create_camera_orbit_rig(active_settings)
    configure_mouse_capture()
    controls_hint = create_controls_hint()
    status_text = create_status_text()
    pause_text = create_pause_text()
    lighting_rig = configure_lighting(player)
    backdrop_state = create_space_backdrop()
    install_game_controller(
        player=player,
        orbit_rig=orbit_rig,
        settings=active_settings,
        lighting_rig=lighting_rig,
        backdrop_state=backdrop_state,
        player_visual_state=player_visual_state,
        controls_hint=controls_hint,
        status_text=status_text,
        pause_text=pause_text,
    )

    # Ursina's app proxy is typed as object here, so dynamic access is needed.
    run_callable = getattr(app, "run")  # noqa: B009  # B009: getattr-with-constant
    run_callable()
