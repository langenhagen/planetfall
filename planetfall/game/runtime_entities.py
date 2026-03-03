"""Entity creation helpers for the runtime."""

from typing import cast

import ursina.color as color_module
import ursina.shaders as ursina_shaders
from ursina import AmbientLight, DirectionalLight, Entity, Vec3

from planetfall.game.runtime_colors import resolve_color, rgba_color
from planetfall.game.runtime_state import LightingRig, PlayerVisualState

DEFAULT_LIT_SHADER = cast("object", ursina_shaders.basic_lighting_shader)


def mark_lit_shadowed(entity: Entity) -> Entity:
    """Apply the project-default lit shader."""
    entity.shader = DEFAULT_LIT_SHADER
    return entity


def add_avatar_part(  # noqa: PLR0913
    # pylint: disable=too-many-arguments
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


def configure_lighting(focus_entity: Entity) -> LightingRig:
    """Create one sun light and ambient fill."""
    sun_direction = Vec3(0.75, -1.2, -0.45).normalized()
    key_light = DirectionalLight(shadows=False)
    key_light.color = color_module.white
    key_light.look_at(sun_direction)

    ambient_light = AmbientLight()
    ambient_light.color = color_module.rgba(0.24, 0.26, 0.31, 1.0)

    _ = focus_entity

    return LightingRig(key_light=key_light, ambient_light=ambient_light)
