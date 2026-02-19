"""Command-line entrypoint for fooproj."""

import argparse

from fooproj.game import run_game
from fooproj.game.config import GameSettings


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for runtime launch options."""
    parser = argparse.ArgumentParser(description="Run the fooproj driving sandbox")
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
