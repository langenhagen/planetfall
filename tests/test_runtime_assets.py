"""Tests for runtime asset path helpers."""

from unittest import TestCase

from planetfall.game.runtime_assets import ASSETS_DIR, REPO_ROOT

CHECKER = TestCase()


def test_assets_dir_is_under_repo_root() -> None:
    """Ensure assets directory is rooted under the repo."""
    CHECKER.assertEqual(ASSETS_DIR, REPO_ROOT / "assets")
