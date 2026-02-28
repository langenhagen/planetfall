"""Audio helper utilities for runtime sound and music."""

from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from random import Random
from typing import Any

from ursina import Audio

from .runtime_assets import ASSETS_DIR

COIN_SFX_NAMES = ("audio/sfx/345297_6212127-lq.mp3",)
IMPACT_SFX_NAMES = ("audio/sfx/explosionCrunch_000.ogg",)
BOOST_LOOP_SFX_NAMES = ("audio/sfx/freesound_community-loopingthrust-95548.mp3",)
BOOST_LOOP_VOLUME = 0.7
BOOST_LOOP_FADE_SECONDS = 0.4
MUSIC_VOLUME = 0.6


def play_sfx_clip(*, clip_name: str, volume: float, pitch: float) -> None:
    """Play a one-shot sound effect clip."""
    audio_factory: Any = Audio
    audio_factory(clip_name, volume=volume, pitch=pitch, auto_destroy=True)


def play_coin_pickup_sfx() -> None:
    """Play the configured coin pickup sound effect."""
    with suppress(Exception):
        coin_path = resolve_sfx_path(
            preferred_names=COIN_SFX_NAMES,
            fallback_pattern="coin*.ogg",
        )
        if coin_path is not None:
            play_sfx_clip(clip_name=coin_path.name, volume=0.7, pitch=1.0)
            return
        play_sfx_clip(clip_name="sine", volume=1.0, pitch=2.0)


def play_obstacle_hit_sfx() -> None:
    """Play the configured obstacle impact sound effect."""
    with suppress(Exception):
        impact_path = resolve_sfx_path(
            preferred_names=IMPACT_SFX_NAMES,
            fallback_pattern="*impact*.ogg",
        )
        if impact_path is not None:
            play_sfx_clip(clip_name=impact_path.name, volume=0.75, pitch=1.0)
            return
        play_sfx_clip(clip_name="sine", volume=1.0, pitch=1.0)


def resolve_boost_loop_clip() -> str | None:
    """Resolve the looping boost audio clip name."""
    with suppress(Exception):
        boost_path = resolve_sfx_path(
            preferred_names=BOOST_LOOP_SFX_NAMES,
            fallback_pattern="*thrust*.*",
        )
        if boost_path is not None:
            return boost_path.name
    return None


@lru_cache(maxsize=8)
def resolve_sfx_path(
    *,
    preferred_names: tuple[str, ...],
    fallback_pattern: str,
) -> Path | None:
    """Resolve an audio file path from preferred names or a fallback glob."""
    for file_name in preferred_names:
        candidate_path = Path(ASSETS_DIR / file_name)
        if candidate_path.exists():
            return candidate_path

    fallback_matches = sorted(Path(ASSETS_DIR).glob(fallback_pattern))
    if fallback_matches:
        return Path(fallback_matches[0])

    return None


@lru_cache(maxsize=8)
def resolve_music_paths() -> tuple[Path, ...]:
    """Resolve all available background music tracks."""
    music_dir = Path(ASSETS_DIR / "audio" / "music")
    if not music_dir.exists():
        return ()
    return tuple(
        sorted(Path(path) for path in music_dir.glob("*.mp3") if path.is_file()),
    )


def build_music_playlist() -> list[Path]:
    """Build a shuffled playlist of all available music tracks."""
    playlist = list(resolve_music_paths())
    _shuffle_playlist(playlist)
    return playlist


# S311: non-crypto RNG; gameplay playlist ordering.
def _shuffle_playlist(playlist: list[Path]) -> None:
    # S311: non-crypto RNG; B311: gameplay.
    Random().shuffle(playlist)  # noqa: S311  # nosec B311


def start_music_track(track_path: Path) -> Audio:
    """Start a single background music track (non-looping)."""
    relative_track = track_path.relative_to(Path(ASSETS_DIR).parent).as_posix()
    audio_factory: Any = Audio
    return audio_factory(
        relative_track,
        loop=False,
        autoplay=True,
        auto_destroy=True,
        volume=MUSIC_VOLUME,
    )


def advance_music_playlist(
    *,
    current_track: Audio | None,
    playlist: list[Path],
) -> Audio | None:
    """Advance to the next track when the current one finishes."""
    if current_track is not None and current_track.playing:
        return current_track

    if not playlist:
        playlist.extend(build_music_playlist())
        if not playlist:
            return None

    return start_music_track(playlist.pop(0))
