# Fooproj

Third-person endless falling game built with Ursina and Python.

The player dives from deep space toward a distant planet, steers around
obstacles, and collects chained glowing orbs while descending.

## Requirements

- `pyenv`
- `uv`

## Quick Start

```bash
pyenv install -s 3.14.3
pyenv local 3.14.3
uv sync
uv run barproj
```

## Controls

- Arrow keys or `WASD`: steer while falling
- `Space`: dive faster
- Left Shift / Right Shift: air brake
- Obstacle hit: rumble + reset a bit higher (no death)
- Mouse move: orbit look (captured cursor)
- Mouse wheel: zoom in/out
- `p`: pause/resume
- `c`: recenter camera
- `r`: restart run
- `u`: toggle controls hint

### PS5 Controller (Generic Gamepad Mapping)

Ursina exposes standard gamepad names, so PS5 controls map as:

- Left stick: steer
- R2 / L2: dive faster / air brake
- L1 / R1: digital steer assist left/right
- Right stick: camera look
- D-pad up/down: zoom in/out
- D-pad left: recenter camera
- Start: pause/resume

## Full Setup and Checks

```bash
# install and activate the pinned Python version
pyenv install -s 3.14.3
pyenv local 3.14.3

# create/update virtual environment and dependencies
uv sync

# launch the Ursina game
uv run barproj

# run quality checks
uv run ruff check .
uv run ruff format .
uv run mypy barproj
uv run pytest

# install git hooks
uv run pre-commit install

# run all hooks once manually
uv run pre-commit run --all-files
```

## Debug Capture Scripts

- `scripts/capture-window.sh`: generic X11 window screenshot capture tool.
  - Capture any window by name or id at a fixed interval.
  - Outputs numbered+timestamped frames to a target directory.
- `scripts/capture-game.sh`: game-focused wrapper around `capture-window.sh`.
  - Targets `ursina` window names automatically.
  - Writes to `__debug/drive_run_YYYY-MM-DD-HH-MM-SS/` with:
    - `screens/` (captured frames)
    - `capture.log`
    - `game.log` (when using `--run-game`)

Examples:

```bash
# capture an already-running game window
scripts/capture-game.sh --interval 0.5 --frames 120

# launch game and capture frames + logs in one run folder
scripts/capture-game.sh --run-game --frames 120 --interval 0.5

# generic capture for any X11 window name
scripts/capture-window.sh --name "ursina" --out __debug/screens --frames 60
```

You can combine capture scripts with `xdotool` input automation for repeatable
fall scenarios and visual debugging.

## Project Layout

- `barproj/`: application package and CLI entrypoint
- `barproj/game/`: runtime, control logic, procedural falling-scene generation
- `tests/`: test suite
- `pyproject.toml`: project metadata and tool/lint configuration
