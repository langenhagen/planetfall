"""Shared asset path helpers for runtime modules."""

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
ASSETS_DIR: Path = REPO_ROOT / "assets"
