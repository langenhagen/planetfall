"""Shared runtime state containers for gameplay systems."""

from dataclasses import dataclass, field

from ursina import AmbientLight, DirectionalLight, Entity, Vec3


@dataclass(slots=True)
class OrbitRig:
    """Camera yaw/pitch pivot entities for third-person orbit motion."""

    yaw_pivot: Entity
    pitch_pivot: Entity


@dataclass(slots=True)
class CameraState:
    """Mutable camera state for orbit look and zoom behavior."""

    yaw_angle: float
    pitch_angle: float
    distance: float


@dataclass(slots=True)
class MotionState:
    """Mutable player movement speeds for gentle acceleration/deceleration."""

    horizontal_speed: float = 0.0
    depth_speed: float = 0.0
    yaw_turn_speed: float = 0.0


@dataclass(slots=True)
class SpawnedObject:
    """Runtime state for one spawned world object."""

    entity: Entity
    entity_kind: str
    model_name: str
    collision_radius: float
    score_value: int
    spin_speed_x: float = 0.0
    spin_speed_y: float = 0.0
    spin_speed_z: float = 0.0
    bob_amplitude: float = 0.0
    bob_frequency: float = 0.0
    pulse_amplitude: float = 0.0
    pulse_frequency: float = 0.0
    base_x: float = 0.0
    base_y: float = 0.0
    base_z: float = 0.0
    drift_speed_x: float = 0.0
    drift_speed_z: float = 0.0
    drift_progress: float = 0.0
    drift_blend: float = 0.0
    base_scale: Vec3 = field(default_factory=lambda: Vec3(1.0, 1.0, 1.0))
    spawn_time: float = 0.0
    fade_duration: float = 0.0
    target_rgba: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)


@dataclass(slots=True)
class FallingRunState:
    """Mutable run-state values tracked across gameplay frames."""

    score: int = 0
    collected_orbs: int = 0
    reset_count: int = 0
    deepest_y: float = 0.0
    is_paused: bool = False
    next_band_index: int = 0
    next_band_y: float = 0.0
    last_hit_time: float = 0.0
    spawned_objects: list[SpawnedObject] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LightingRig:
    """Runtime references for lighting entities that change with depth."""

    key_light: DirectionalLight
    ambient_light: AmbientLight


@dataclass(frozen=True, slots=True)
class BackdropState:
    """Runtime references for sky, stars, and atmosphere ambience entities."""

    sky: Entity
    stars: tuple[Entity, ...]
    nebulae: tuple[Entity, ...]
    motion_motes: tuple[Entity, ...]
    depth_overlay: Entity


@dataclass(frozen=True, slots=True)
class PlayerVisualState:
    """Runtime references for player contrails and glow visuals."""

    contrails: tuple[Entity, ...]
    aura: Entity
