"""Runtime configuration for the Ursina sandbox."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MovementSettings:
    """Movement and rotation speeds for the player vehicle."""

    move_speed: float = 20.0
    turn_speed: float = 90.0


@dataclass(frozen=True, slots=True)
class CameraSettings:
    """Orbit camera settings for look and zoom behavior."""

    mouse_look_speed: float = 120.0
    distance: float = 10.0
    height: float = 1.1
    min_distance: float = 4.0
    max_distance: float | None = None
    zoom_step: float = 1.0


@dataclass(frozen=True, slots=True)
class GameSettings:
    """Settings used to bootstrap the Ursina app."""

    window_title: str = "fooproj Ursina sandbox"
    borderless: bool = False
    fullscreen: bool = False
    development_mode: bool = True
    movement: MovementSettings = field(default_factory=MovementSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
