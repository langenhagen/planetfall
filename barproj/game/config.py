"""Runtime configuration for the endless falling game."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MovementSettings:
    """Horizontal steering and player tilt settings."""

    horizontal_speed: float = 18.0
    depth_speed: float = 14.0
    horizontal_accel_rate: float = 6.2
    horizontal_decel_rate: float = 7.0
    depth_accel_rate: float = 5.4
    depth_decel_rate: float = 6.2
    play_area_radius: float = 12.3
    tilt_degrees: float = 24.0


@dataclass(frozen=True, slots=True)
class FallSettings:
    """Vertical speed and endless spawning window settings."""

    base_speed: float = 26.0
    boost_multiplier: float = 1.15
    brake_multiplier: float = 0.55
    recovery_height: float = 12.0
    recovery_score_penalty: int = 35
    spawn_ahead_distance: float = 220.0
    cleanup_above_distance: float = 52.0
    initial_spawn_y: float = -36.0


@dataclass(frozen=True, slots=True)
class CameraSettings:
    """Third-person orbit camera settings for the falling avatar."""

    mouse_look_speed: float = 120.0
    distance: float = 19.0
    height: float = 3.0
    min_distance: float = 9.0
    max_distance: float = 28.0
    zoom_step: float = 1.0
    min_pitch: float = 22.0
    max_pitch: float = 88.0
    start_pitch: float = 82.0


@dataclass(frozen=True, slots=True)
class GameSettings:
    """Settings used to bootstrap and tune the game runtime."""

    window_title: str = "Abyss Dive"
    borderless: bool = False
    fullscreen: bool = False
    development_mode: bool = True
    movement: MovementSettings = field(default_factory=MovementSettings)
    fall: FallSettings = field(default_factory=FallSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
