#!/usr/bin/env bash
#
# Convert short audio sfx files to WAV for fast runtime playback.
#
# Requires: ffmpeg in PATH.
# Scans common input formats and writes .wav files alongside originals.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sfx_dir="${script_dir}/../assets/audio/sfx"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is required but was not found in PATH" >&2
    exit 1
fi

if [[ ! -d "$sfx_dir" ]]; then
    echo "SFX directory not found: $sfx_dir" >&2
    exit 2
fi

find "$sfx_dir" -type f \( \
    -iname '*.mp3' -o \
    -iname '*.flac' -o \
    -iname '*.m4a' -o \
    -iname '*.aac' -o \
    -iname '*.opus' -o \
    -iname '*.ogg' \
    \) -print0 | while IFS= read -r -d '' inpath; do
    dir="$(dirname -- "$inpath")"
    name="$(basename -- "${inpath%.*}")"
    outpath="$dir/$name.wav"

    echo "$inpath -> $outpath"

    ffmpeg -nostdin -y -i "$inpath" \
        -ac 1 \
        -ar 22050 \
        -c:a pcm_s16le \
        "$outpath"
done
