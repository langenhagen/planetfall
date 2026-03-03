"""Command-line entrypoint for planetfall."""

import argparse

from planetfall.game import run_game
from planetfall.game.config import GameSettings


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for runtime launch options."""
    parser = argparse.ArgumentParser(
        description="Run the planetfall endless falling game",
    )
    parser.add_argument(
        "--fullscreen",
        "-F",
        action="store_true",
        help="Launch the game in fullscreen mode",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        help="Window resolution as WIDTHxHEIGHT (example: 1920x1080)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed for deterministic run generation",
    )
    return parser.parse_args()


def parse_resolution(value: str | None) -> tuple[int, int] | None:
    """Parse resolution text into a (width, height) tuple."""
    if value is None:
        return None
    raw = value.lower().strip()
    if "x" not in raw:
        msg = "Resolution must be formatted like WIDTHxHEIGHT."
        raise ValueError(msg)
    width_text, height_text = raw.split("x", maxsplit=1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError as exc:
        msg = "Resolution must use integer width and height values."
        raise ValueError(msg) from exc
    if width <= 0 or height <= 0:
        msg = "Resolution width and height must be positive."
        raise ValueError(msg)
    return width, height


def main() -> None:
    """Run the CLI entrypoint."""
    args = parse_args()
    try:
        window_size = parse_resolution(args.resolution)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    run_game(
        settings=GameSettings(
            run_seed=args.seed,
            fullscreen=args.fullscreen,
            window_size=window_size,
        ),
    )


if __name__ == "__main__":
    main()
