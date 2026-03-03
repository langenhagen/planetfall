#!/usr/bin/env bash
#
# Convert runtime assets (SFX, music, skyboxes) into preferred formats.
#
# Requires: ffmpeg in PATH
# Calls the individual conversion scripts so each task stays focused.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/convert-audio-sfx-to-wav.sh"
"$script_dir/convert-audio-background-music-to-ogg.sh"
uv run python "$script_dir/convert-models-to-bam.py"
"$script_dir/convert-skyboxes-to-txo.py"
