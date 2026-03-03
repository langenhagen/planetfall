"""Tests for runtime feedback helpers."""

from unittest import TestCase
from unittest.mock import patch

from planetfall.game.runtime_fx import trigger_impact_rumble

CHECKER = TestCase()


def test_trigger_impact_rumble_noop_without_gamepad() -> None:
    """Silently ignore missing gamepad modules."""
    with patch(
        "planetfall.game.runtime_fx.resolve_gamepad_vibrate_callable",
        return_value=None,
    ):
        trigger_impact_rumble(intensity=0.6)


def test_trigger_impact_rumble_clamps_intensity() -> None:
    """Clamp rumble inputs before calling vibrate."""
    calls: list[dict[str, float]] = []

    def fake_vibrate(**kwargs: float) -> None:
        calls.append(kwargs)

    with patch(
        "planetfall.game.runtime_fx.resolve_gamepad_vibrate_callable",
        return_value=fake_vibrate,
    ):
        trigger_impact_rumble(intensity=2.5)

    CHECKER.assertEqual(len(calls), 1)
    CHECKER.assertEqual(calls[0]["low_freq_motor"], 1.0)
    CHECKER.assertEqual(calls[0]["high_freq_motor"], 1.0)
    CHECKER.assertEqual(calls[0]["duration"], 0.09)


def test_trigger_impact_rumble_ignores_vibrate_failures() -> None:
    """Swallow exceptions from optional gamepad hooks."""

    def broken_vibrate(**_kwargs: float) -> None:
        raise RuntimeError("boom")

    with patch(
        "planetfall.game.runtime_fx.resolve_gamepad_vibrate_callable",
        return_value=broken_vibrate,
    ):
        trigger_impact_rumble(intensity=0.3)
