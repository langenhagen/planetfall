# Fooproj

Third-person 3D Ursina driving sandbox in Python.

This project is nearly entirely vibe coded.

## Requirements

- `pyenv`
- `uv`

## Quick Start

```bash
pyenv install -s 3.14.3
pyenv local 3.14.3
uv sync
uv run fooproj
```

## Controls

- Arrow keys: move (forward/back + strafe left/right)
- Page Up / Page Down: rotate car left/right
- Mouse move: orbit camera (captured cursor)
- Mouse wheel: zoom in/out (zoom-in is clamped, zoom-out unbounded)
- `c`: toggle orbit/chase camera

### Optional PS5 Controller Support

If you have a PS5 controller connected, try these mappings:

- R2 / L2: gas and brake/reverse (analog pressure supported)
- L1 / R1: strafe left/right
- Left stick X: steering
- Right stick: camera look
- D-pad left: toggle orbit/chase camera
- D-pad up/down: zoom in/out
- Impact rumble on collisions (silently disabled when no controller is available)

## Full Setup and Checks

```bash
# install and activate the pinned Python version
pyenv install -s 3.14.3
pyenv local 3.14.3

# create/update virtual environment and dependencies
uv sync

# launch the Ursina sandbox
uv run fooproj

# run quality checks
uv run ruff check .
uv run ruff format .
uv run mypy fooproj
uv run pytest

# install git hooks
uv run pre-commit install

# run all hooks once manually
uv run pre-commit run --all-files

# optional: install and run extended lint stack
uv sync --group lint
uv run --group lint pylint fooproj tests
uv run --group lint vulture fooproj tests
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
drive scenarios and visual debugging.

## Project Layout

- `fooproj/`: application package and CLI entrypoint
- `fooproj/game/`: runtime, input/camera controls, scene setup, lighting
- `tests/`: test suite
- `pyproject.toml`: project metadata and tool/lint configuration

## Notes

- Project defaults use reproducible `uv run ...` commands.
