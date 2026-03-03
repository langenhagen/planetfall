"""Tests for runtime UI helpers."""

from unittest import TestCase

from ursina import Text

from planetfall.game.runtime_ui import update_status_text

CHECKER = TestCase()


class _RunStateStub:  # pylint: disable=too-few-public-methods
    """Minimal run state stub for HUD tests."""

    def __init__(self) -> None:
        self.score = 10
        self.collected_coins = 2
        self.deepest_y = -50.0
        self.reset_count = 1
        self.magnet_expires_at = 0.0
        self.shield_expires_at = 0.0
        self.coin_multiplier_expires_at = 0.0


def test_update_status_text_includes_powerups() -> None:
    """Status text should include powerup timers."""
    status_text = Text(text="")
    run_state = _RunStateStub()

    update_status_text(run_state, status_text)

    CHECKER.assertIn("Magnet:", status_text.text)
    CHECKER.assertIn("Shield:", status_text.text)
    CHECKER.assertIn("Multiplier:", status_text.text)
