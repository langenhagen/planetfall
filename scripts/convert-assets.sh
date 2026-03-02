#!/usr/bin/env bash
#
# Convert runtime assets (SFX, music, skyboxes) into preferred formats.
#
# Requires: ffmpeg in PATH, panda3d importable for the skybox step.
# Calls the individual conversion scripts so each task stays focused.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/convert-audio-sfx-to-wav.sh"
"$script_dir/convert-audio-background-music-to-ogg.sh"
"$script_dir/convert-skyboxes-to-txo.py"
