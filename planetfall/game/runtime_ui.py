"""HUD and on-screen text helpers for runtime systems."""

from time import monotonic
from typing import Protocol

from ursina import Text


class RunStateLike(Protocol):  # pylint: disable=too-few-public-methods
    # R0903: protocol defines shape only.
    """Minimal run-state shape required by HUD rendering."""

    score: int
    collected_coins: int
    deepest_y: float
    reset_count: int
    magnet_expires_at: float


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


def update_status_text(run_state: RunStateLike, status_text: Text) -> None:
    """Render current score, depth, reset, and debug display status."""
    depth = max(0.0, -run_state.deepest_y)
    magnet_remaining = max(0.0, run_state.magnet_expires_at - monotonic())
    magnet_line = (
        f"Magnet: {magnet_remaining:.1f}s" if magnet_remaining > 0.0 else "Magnet: --"
    )
    status_text.text = (
        f"Score: {run_state.score}\n"
        f"Coins: {run_state.collected_coins}\n"
        f"Depth: {depth:.0f} m\n"
        f"Resets: {run_state.reset_count}\n"
        f"{magnet_line}"
    )
