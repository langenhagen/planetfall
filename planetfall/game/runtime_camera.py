"""Camera setup and tracking helpers for the runtime."""

from contextlib import suppress
from math import atan2, degrees
from typing import TYPE_CHECKING

from ursina import Entity, Vec3, camera, lerp_exponential_decay, mouse
from ursina import scene as scene_root

from planetfall.game.runtime_controls import compute_look_angles
from planetfall.game.runtime_state import CameraState, OrbitRig
from planetfall.game.scene_base import path_center, path_direction

PATH_EPSILON = 1e-4

if TYPE_CHECKING:
    from planetfall.game.config import CameraSettings, GameSettings


def configure_camera() -> None:
    """Set up base camera parent and transform defaults."""
    camera.parent = scene_root
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
        # SLF001: private access; Ursina uses _shader for filters.
        # pylint: disable=protected-access  # W0212: Ursina internal shader.
        camera._shader = None  # noqa: SLF001
        return

    camera.shader = shader


def create_camera_orbit_rig(settings: GameSettings) -> OrbitRig:
    """Create yaw and pitch pivots used for stable orbit controls."""
    yaw_pivot = Entity(name="camera_yaw_pivot", parent=scene_root)
    pitch_pivot = Entity(name="camera_pitch_pivot", parent=yaw_pivot)
    camera.parent = pitch_pivot
    camera.position = Vec3(0.0, 0.0, -settings.camera.distance)
    camera.rotation = Vec3(0.0, 0.0, 0.0)
    return OrbitRig(yaw_pivot=yaw_pivot, pitch_pivot=pitch_pivot)


def configure_mouse_capture() -> None:
    """Capture the mouse cursor for camera look controls."""
    mouse.locked = True
    mouse.visible = False


def sample_path_center(*, band_progress: float) -> Vec3:
    """Return an interpolated path center for fractional band indices."""
    lower = int(band_progress)
    upper = lower + 1
    blend = max(0.0, min(1.0, band_progress - lower))
    lower_anchor = path_center(lower)
    upper_anchor = path_center(upper)
    return Vec3(
        (lower_anchor.x * (1.0 - blend)) + (upper_anchor.x * blend),
        0.0,
        (lower_anchor.z * (1.0 - blend)) + (upper_anchor.z * blend),
    )


def sample_path_direction(*, band_progress: float) -> Vec3:
    """Return an interpolated path direction for fractional band indices."""
    lower = int(band_progress)
    upper = lower + 1
    blend = max(0.0, min(1.0, band_progress - lower))
    lower_dir = path_direction(lower)
    upper_dir = path_direction(upper)
    blended_dir = Vec3(
        (lower_dir.x * (1.0 - blend)) + (upper_dir.x * blend),
        0.0,
        (lower_dir.z * (1.0 - blend)) + (upper_dir.z * blend),
    )
    if blended_dir.length() <= PATH_EPSILON:
        return Vec3(1.0, 0.0, 0.0)
    return blended_dir.normalized()


def resolve_path_yaw_target(
    *,
    band_progress: float,
    lookahead_bands: float,
) -> float | None:
    """Compute a yaw target that follows the path center."""
    lookahead = max(0.0, lookahead_bands)
    base_anchor = sample_path_center(band_progress=band_progress)
    lookahead_anchor = sample_path_center(band_progress=band_progress + lookahead)
    if not isinstance(base_anchor, Vec3) or not isinstance(lookahead_anchor, Vec3):
        return None
    direction = Vec3(
        lookahead_anchor.x - base_anchor.x,
        0.0,
        lookahead_anchor.z - base_anchor.z,
    )
    if direction.length() <= PATH_EPSILON:
        return None
    return degrees(atan2(direction.x, direction.z))


# PLR0913: explicit inputs for camera tuning and follow behavior.
def update_camera_tracking(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    # R0913: explicit camera follow inputs.
    *,
    player: Entity,
    orbit_rig: OrbitRig,
    camera_state: CameraState,
    camera_settings: CameraSettings,
    look_velocity: Vec3,
    band_progress: float,
    yaw_follow_strength: float,
    yaw_input_active: bool,
    dt: float,
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

    if yaw_input_active:
        camera_state.yaw_follow_angle = camera_state.yaw_angle
    if dt > 0.0 and not yaw_input_active and yaw_follow_strength > 0.0:
        target_yaw = resolve_path_yaw_target(
            band_progress=band_progress,
            lookahead_bands=camera_settings.yaw_lookahead_bands,
        )
        if target_yaw is not None:
            current_yaw = camera_state.yaw_angle
            yaw_delta = (target_yaw - current_yaw + 180.0) % 360.0 - 180.0
            target_angle = current_yaw + yaw_delta
            camera_state.yaw_follow_angle = lerp_exponential_decay(
                camera_state.yaw_follow_angle,
                target_angle,
                dt * yaw_follow_strength,
            )
            camera_state.yaw_angle = camera_state.yaw_follow_angle

    orbit_rig.yaw_pivot.world_position = player.world_position + Vec3(
        0.0,
        camera_settings.height,
        0.0,
    )
    orbit_rig.yaw_pivot.rotation = Vec3(0.0, camera_state.yaw_angle, 0.0)
    orbit_rig.pitch_pivot.rotation = Vec3(camera_state.pitch_angle, 0.0, 0.0)
    camera.position = Vec3(0.0, 0.0, -camera_state.distance)
    camera.rotation_z = 0.0
