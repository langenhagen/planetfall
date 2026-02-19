"""Tests for CLI helpers."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING
from unittest import TestCase

from fooproj import cli

if TYPE_CHECKING:
    import pytest

    from fooproj.game.config import GameSettings


CHECKER = TestCase()


def test_main_calls_run_game(monkeypatch: pytest.MonkeyPatch) -> None:
    """Launch the game runtime from the CLI entrypoint."""
    calls: list[object] = []

    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(fullscreen=False)

    def fake_run_game(*, settings: GameSettings) -> None:
        calls.append(settings)

    monkeypatch.setattr("fooproj.cli.parse_args", fake_parse_args)
    monkeypatch.setattr("fooproj.cli.run_game", fake_run_game)
    cli.main()

    CHECKER.assertEqual(len(calls), 1)


def test_main_passes_fullscreen_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forward --fullscreen mode into runtime settings."""
    captured_fullscreen_values: list[bool] = []

    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(fullscreen=True)

    def fake_run_game(*, settings: GameSettings) -> None:
        captured_fullscreen_values.append(settings.fullscreen)

    monkeypatch.setattr("fooproj.cli.parse_args", fake_parse_args)
    monkeypatch.setattr("fooproj.cli.run_game", fake_run_game)
    cli.main()

    CHECKER.assertEqual(captured_fullscreen_values, [True])
