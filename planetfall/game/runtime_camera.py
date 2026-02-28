"""Camera setup and tracking helpers for the runtime."""

from contextlib import suppress
from typing import TYPE_CHECKING

from ursina import Entity, Vec3, camera, mouse
from ursina import scene as scene_root

from planetfall.game.runtime_controls import compute_look_angles
from planetfall.game.runtime_state import CameraState, OrbitRig

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
