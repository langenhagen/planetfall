"""Tests for CLI helpers."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING
from unittest import TestCase

from planetfall import cli

if TYPE_CHECKING:
    import pytest

    from planetfall.game.config import GameSettings


CHECKER = TestCase()


def test_main_calls_run_game(monkeypatch: pytest.MonkeyPatch) -> None:
    """Launch the game runtime from the CLI entrypoint."""
    calls: list[object] = []

    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(fullscreen=False, resolution=None)

    def fake_run_game(*, settings: GameSettings) -> None:
        calls.append(settings)

    monkeypatch.setattr("planetfall.cli.parse_args", fake_parse_args)
    monkeypatch.setattr("planetfall.cli.run_game", fake_run_game)
    cli.main()

    CHECKER.assertEqual(len(calls), 1)


def test_main_passes_fullscreen_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forward --fullscreen mode into runtime settings."""
    captured_fullscreen_values: list[bool] = []

    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(fullscreen=True, resolution=None)

    def fake_run_game(*, settings: GameSettings) -> None:
        captured_fullscreen_values.append(settings.fullscreen)

    monkeypatch.setattr("planetfall.cli.parse_args", fake_parse_args)
    monkeypatch.setattr("planetfall.cli.run_game", fake_run_game)
    cli.main()

    CHECKER.assertEqual(captured_fullscreen_values, [True])


def test_main_passes_resolution_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forward --resolution into runtime settings."""
    captured_sizes: list[tuple[int, int] | None] = []

    def fake_parse_args() -> argparse.Namespace:
        return argparse.Namespace(fullscreen=False, resolution="2560x1440")

    def fake_run_game(*, settings: GameSettings) -> None:
        captured_sizes.append(settings.window_size)

    monkeypatch.setattr("planetfall.cli.parse_args", fake_parse_args)
    monkeypatch.setattr("planetfall.cli.run_game", fake_run_game)
    cli.main()

    CHECKER.assertEqual(captured_sizes, [(2560, 1440)])
