"""Command-line entrypoint for barproj."""

import argparse

from barproj.game import run_game
from barproj.game.config import GameSettings


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for runtime launch options."""
    parser = argparse.ArgumentParser(description="Run the barproj endless falling game")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Launch the game in fullscreen mode",
    )
    return parser.parse_args()


def main() -> None:
    """Run the CLI entrypoint."""
    args = parse_args()
    run_game(settings=GameSettings(fullscreen=args.fullscreen))


if __name__ == "__main__":
    main()
