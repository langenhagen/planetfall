"""HUD and on-screen text helpers for runtime systems."""

from typing import Protocol

from ursina import Text

SPACE_ZONE_DEPTH_LIMIT = 420.0
ATMOSPHERE_ZONE_DEPTH_LIMIT = 980.0


class RunStateLike(Protocol):  # pylint: disable=too-few-public-methods
    # R0903: protocol defines shape only.
    """Minimal run-state shape required by HUD rendering."""

    score: int
    collected_orbs: int
    deepest_y: float
    reset_count: int


def create_controls_hint() -> Text:
    """Render controls help text and return its entity."""
    return Text(
        name="controls_hint_text",
        text=(
            "Steer: arrows or WASD\n"
            "Dive faster: space / R2\n"
            "Air brake: shift / L2\n"
            "Rotate body: q/e or PgUp/PgDn\n"
            "Pad rotate: L1/R1\n"
            "Pad steer: left stick\n"
            "Look: mouse / right stick\n"
            "Zoom: mouse wheel / dpad up-down\n"
            "Pause: p / start\n"
            "Recenter: c / dpad left\n"
            "Auto yaw: v / dpad right\n"
            "Post FX: t\n"
            "Render mode: y\n"
            "Restart: r\n"
            "UI: u"
        ),
        x=-0.86,
        y=0.47,
        scale=0.9,
        background=True,
    )


def create_status_text() -> Text:
    """Create top-right run status text entity."""
    return Text(
        name="run_status_text",
        text="",
        x=0.56,
        y=0.45,
        scale=1.05,
    )


def create_pause_text() -> Text:
    """Create pause overlay text shown when gameplay is paused."""
    return Text(
        name="pause_text",
        text="Paused\nPress P or Start",
        origin=(0.0, 0.0),
        scale=2.1,
        background=True,
        enabled=False,
    )


def depth_zone_label(depth: float) -> str:
    """Return a readable biome label for the current descent depth."""
    if depth < SPACE_ZONE_DEPTH_LIMIT:
        return "Deep Space"
    if depth < ATMOSPHERE_ZONE_DEPTH_LIMIT:
        return "Upper Atmosphere"
    return "Planetfall"


def update_status_text(run_state: RunStateLike, status_text: Text) -> None:
    """Render current score, depth, reset, and debug display status."""
    depth = max(0.0, -run_state.deepest_y)
    status_text.text = (
        f"Score: {run_state.score}\n"
        f"Orbs: {run_state.collected_orbs}\n"
        f"Depth: {depth:.0f} m\n"
        f"Zone: {depth_zone_label(depth)}\n"
        f"Resets: {run_state.reset_count}"
    )
