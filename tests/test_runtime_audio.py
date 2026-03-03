"""Tests for runtime audio helpers."""

from unittest import TestCase

from planetfall.game.runtime_audio import (
    build_music_playlist,
    resolve_boost_loop_clip,
    resolve_sfx_path,
)

CHECKER = TestCase()


def test_resolve_sfx_path_returns_none_for_missing_assets() -> None:
    """Missing assets should return None instead of raising."""
    resolved = resolve_sfx_path(
        preferred_names=("definitely_missing.wav",),
        fallback_pattern="does_not_exist_*.wav",
    )
    CHECKER.assertIsNone(resolved)


def test_resolve_boost_loop_clip_returns_clip_name_when_available() -> None:
    """Boost loop lookup returns a clip name when assets are present."""
    clip_name = resolve_boost_loop_clip()
    if clip_name is None:
        return
    CHECKER.assertTrue(clip_name.endswith(".wav"))


def test_build_music_playlist_returns_list() -> None:
    """Playlist build should return a list (possibly empty)."""
    playlist = build_music_playlist()
    CHECKER.assertIsInstance(playlist, list)
