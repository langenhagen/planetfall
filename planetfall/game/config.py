"""Runtime configuration for the endless falling game."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MovementSettings:
    """Horizontal steering and player tilt settings."""

    horizontal_speed: float = 18.0
    depth_speed: float = 14.0
    horizontal_accel_rate: float = 4.96
    horizontal_decel_rate: float = 0.5
    depth_accel_rate: float = 4.96
    depth_decel_rate: float = 0.5
    yaw_turn_speed: float = 130.0
    yaw_turn_accel_rate: float = 3.2
    yaw_turn_decel_rate: float = 1.2
    play_area_radius: float = 75.0
    tilt_degrees: float = 64.0


@dataclass(frozen=True, slots=True)
class FallSettings:
    """Vertical speed and endless spawning window settings."""

    base_speed: float = 40.3
    boost_multiplier: float = 1.15
    brake_multiplier: float = 0.55
    recovery_height: float = 12.0
    recovery_score_penalty: int = 35
    spawn_ahead_distance: float = 600.0
    cleanup_above_distance: float = 52.0
    initial_spawn_y: float = -36.0


@dataclass(frozen=True, slots=True)
class GameplayTuningSettings:
    """Tunable gameplay constants used across spawn and collision systems."""

    obstacle_hit_cooldown_seconds: float = 0.45
    spawn_fade_duration_seconds: float = 0.16
    high_value_coin_halo_chance: float = 1.0
    obstacle_halo_chance: float = 1.0 / 3.0
    obstacle_spin_speed_min: float = 16.0
    obstacle_spin_speed_max: float = 52.0
    obstacle_rock_speed_min: float = -12.0
    obstacle_rock_speed_max: float = 12.0
    obstacle_spin_variants: int = 7
    obstacle_rock_variants: int = 9


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

    window_title: str = "Planetfall"
    borderless: bool = False
    fullscreen: bool = False
    development_mode: bool = True
    movement: MovementSettings = field(default_factory=MovementSettings)
    fall: FallSettings = field(default_factory=FallSettings)
    gameplay: GameplayTuningSettings = field(default_factory=GameplayTuningSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
