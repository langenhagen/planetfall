#!/usr/bin/env bash

# Capture Ursina game window screenshots into a timestamped run folder.
#
# This is a project-specific wrapper around scripts/capture-window.sh.
# It always targets windows matching "ursina" and writes screenshots to:
#   __debug/drive_run_YYYY-MM-DD-HH-MM-SS/screens
#
# By default this captures screenshots from an already-running game window.
# Optionally pass --run-game to launch the game from this script and write
# game stdout/stderr to a log file in the same run directory.

set -euo pipefail

usage() {
    cat <<'EOF'
Capture screenshots from the game window into a timestamped run folder.

Usage:
  scripts/capture-game.sh [options] [capture-window options]

Options:
  --run-game                  Launch game and capture its stdout/stderr log
  --game-cmd <command>        Command used with --run-game
                              (default: .venv/bin/python -u barproj/cli.py)
  -h, --help                  Show this help

Examples:
  scripts/capture-game.sh
  scripts/capture-game.sh --interval 0.5 --frames 120
  scripts/capture-game.sh --run-game --frames 60
  scripts/capture-game.sh --run-game --game-cmd "uv run barproj --fullscreen"
  scripts/capture-game.sh --startup-wait 30 --frames 240

Notes:
  - Output path format:
      __debug/drive_run_YYYY-MM-DD-HH-MM-SS/
  - Capture log file:
      <run>/capture.log
  - Game log file (with --run-game):
      <run>/game.log
  - Unknown options are forwarded to scripts/capture-window.sh.
EOF
}

RUN_GAME="0"
GAME_CMD=".venv/bin/python -u barproj/cli.py"
CAPTURE_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
    --run-game)
        RUN_GAME="1"
        shift
        ;;
    --game-cmd)
        GAME_CMD="$2"
        shift 2
        ;;
    -h | --help)
        usage
        echo
        scripts/capture-window.sh --help
        exit 0
        ;;
    *)
        CAPTURE_ARGS+=("$1")
        shift
        ;;
    esac
done

STAMP="$(date +%Y-%m-%d-%H-%M-%S)"
RUN_DIR="__debug/drive_run_${STAMP}"
OUT_DIR="${RUN_DIR}/screens"
CAPTURE_LOG="${RUN_DIR}/capture.log"
GAME_LOG="${RUN_DIR}/game.log"

mkdir -p "$RUN_DIR"

GAME_PID=""
CAPTURE_PID=""

cleanup() {
    if [[ -n "$CAPTURE_PID" ]] && kill -0 "$CAPTURE_PID" 2>/dev/null; then
        kill "$CAPTURE_PID" 2>/dev/null || true
    fi
    if [[ -n "$GAME_PID" ]] && kill -0 "$GAME_PID" 2>/dev/null; then
        kill "$GAME_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT

if [[ "$RUN_GAME" == "1" ]]; then
    bash -lc "$GAME_CMD" >"$GAME_LOG" 2>&1 &
    GAME_PID="$!"
else
    printf 'Game log capture disabled (use --run-game to enable).\n' >"$GAME_LOG"
fi

if [[ "$RUN_GAME" == "1" ]]; then
    scripts/capture-window.sh --name "ursina" --out "$OUT_DIR" --stop-when-missing \
        "${CAPTURE_ARGS[@]}" > >(tee "$CAPTURE_LOG") 2>&1 &
    CAPTURE_PID="$!"

    while kill -0 "$GAME_PID" 2>/dev/null && kill -0 "$CAPTURE_PID" 2>/dev/null; do
        sleep 0.25
    done

    if ! kill -0 "$GAME_PID" 2>/dev/null && kill -0 "$CAPTURE_PID" 2>/dev/null; then
        kill "$CAPTURE_PID" 2>/dev/null || true
    fi

    wait "$CAPTURE_PID" 2>/dev/null || true
    wait "$GAME_PID" 2>/dev/null || true
else
    scripts/capture-window.sh --name "ursina" --out "$OUT_DIR" "${CAPTURE_ARGS[@]}" \
        2>&1 | tee "$CAPTURE_LOG"
fi

printf 'Game screenshots saved to %s\n' "$OUT_DIR"
printf 'Capture log saved to %s\n' "$CAPTURE_LOG"
printf 'Game log saved to %s\n' "$GAME_LOG"
