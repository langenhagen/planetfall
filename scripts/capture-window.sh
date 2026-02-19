#!/usr/bin/env bash

# Capture periodic screenshots from an X11 window.
#
# This script is intentionally generic so it can be reused across projects.
# It supports window discovery by title regex (--name) or explicit window id
# (--id), and writes sequential frame files to an output directory.
#
# Typical flow:
#   1) Start the target app/game.
#   2) Run this script with --name or --id.
#   3) Collect frames from the output directory for review or analysis.

set -euo pipefail

WINDOW_NAME=""
WINDOW_ID=""
OUT_DIR="__debug/screens"
INTERVAL="0.5"
FRAMES="120"
STARTUP_WAIT="20"
STOP_WHEN_MISSING="0"
MAX_MISSES="4"

usage() {
    cat <<'EOF'
Capture periodic screenshots from a window.

Usage:
  scripts/capture-window.sh [options]

Options:
  --name <window name regex>   Match window via xdotool search --name
  --id <window id>             Capture a specific X11 window id directly
  --out <directory>            Output directory (default: __debug/screens)
  --interval <seconds>         Delay between frames (default: 0.5)
  --frames <count>             Number of frames to capture (default: 120)
  --startup-wait <seconds>     Max seconds to wait for window (default: 20)
  --stop-when-missing          Stop capture if window is missing repeatedly
  --max-misses <count>         Consecutive misses before stopping (default: 4)
  -h, --help                   Show this help

Examples:
  scripts/capture-window.sh --name "ursina" --out __debug/screens
  scripts/capture-window.sh --id 12345678 --interval 0.25 --frames 240
  scripts/capture-window.sh --name "ursina" --stop-when-missing
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
    --name)
        WINDOW_NAME="$2"
        shift 2
        ;;
    --id)
        WINDOW_ID="$2"
        shift 2
        ;;
    --out)
        OUT_DIR="$2"
        shift 2
        ;;
    --interval)
        INTERVAL="$2"
        shift 2
        ;;
    --frames)
        FRAMES="$2"
        shift 2
        ;;
    --startup-wait)
        STARTUP_WAIT="$2"
        shift 2
        ;;
    --stop-when-missing)
        STOP_WHEN_MISSING="1"
        shift
        ;;
    --max-misses)
        MAX_MISSES="$2"
        shift 2
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    *)
        printf 'Unknown option: %s\n\n' "$1" >&2
        usage >&2
        exit 2
        ;;
    esac
done

if [[ -z "$WINDOW_NAME" && -z "$WINDOW_ID" ]]; then
    printf 'Provide either --name or --id.\n\n' >&2
    usage >&2
    exit 2
fi

if ! command -v xdotool >/dev/null 2>&1; then
    printf 'xdotool is required but not installed.\n' >&2
    exit 1
fi

if ! command -v import >/dev/null 2>&1; then
    printf 'ImageMagick import is required but not installed.\n' >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

resolve_window_id() {
    if [[ -n "$WINDOW_ID" ]]; then
        printf '%s\n' "$WINDOW_ID"
        return
    fi

    xdotool search --name "$WINDOW_NAME" 2>/dev/null | tail -n 1 || true
}

TARGET_WINDOW_ID=""
START_TIME="$(date +%s)"

while [[ -z "$TARGET_WINDOW_ID" ]]; do
    TARGET_WINDOW_ID="$(resolve_window_id)"
    if [[ -n "$TARGET_WINDOW_ID" ]]; then
        break
    fi

    NOW="$(date +%s)"
    if ((NOW - START_TIME >= STARTUP_WAIT)); then
        printf 'Timed out waiting for window (%ss).\n' "$STARTUP_WAIT" >&2
        exit 1
    fi
    sleep 0.25
done

printf 'Capturing window id %s -> %s\n' "$TARGET_WINDOW_ID" "$OUT_DIR"

MISSES="0"

for ((i = 1; i <= FRAMES; i++)); do
    if [[ -z "$WINDOW_ID" ]]; then
        RESOLVED_ID="$(resolve_window_id)"
        if [[ -n "$RESOLVED_ID" ]]; then
            TARGET_WINDOW_ID="$RESOLVED_ID"
            MISSES="0"
        else
            MISSES="$((MISSES + 1))"
            if [[ "$STOP_WHEN_MISSING" == "1" && "$MISSES" -ge "$MAX_MISSES" ]]; then
                printf 'Stopping after %s consecutive missing-window checks.\n' "$MISSES"
                break
            fi
            sleep "$INTERVAL"
            continue
        fi
    fi

    FRAME_STAMP="$(date +%Y-%m-%d-%H-%M-%S-%3N)"
    FRAME_PATH="${OUT_DIR}/frame_$(printf '%04d' "$i")_${FRAME_STAMP}.png"
    if ! import -window "$TARGET_WINDOW_ID" "$FRAME_PATH"; then
        printf 'Frame %s failed for window %s\n' "$i" "$TARGET_WINDOW_ID" >&2
        MISSES="$((MISSES + 1))"
        if [[ "$STOP_WHEN_MISSING" == "1" && "$MISSES" -ge "$MAX_MISSES" ]]; then
            printf 'Stopping after %s consecutive failed captures.\n' "$MISSES"
            break
        fi
    else
        MISSES="0"
    fi
    sleep "$INTERVAL"
done

printf 'Captured %s frames in %s\n' "$FRAMES" "$OUT_DIR"
