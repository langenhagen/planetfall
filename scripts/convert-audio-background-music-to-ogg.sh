#!/usr/bin/env bash
#
# Convert background music files to OGG for smaller runtime footprint.
#
# Requires: ffmpeg in PATH.
# Scans common input formats and writes .ogg files alongside originals.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

music_dir="${script_dir}/../assets/audio/music"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is required but was not found in PATH" >&2
    exit 1
fi

if [[ ! -d "$music_dir" ]]; then
    echo "Music directory not found: $music_dir" >&2
    exit 2
fi

find "$music_dir" -type f \( \
    -iname '*.wav' -o \
    -iname '*.flac' -o \
    -iname '*.mp3' -o \
    -iname '*.m4a' -o \
    -iname '*.aac' -o \
    -iname '*.opus' \
    \) -print0 | while IFS= read -r -d '' inpath; do
    dir="$(dirname -- "$inpath")"
    name="$(basename -- "${inpath%.*}")"
    outpath="$dir/$name.ogg"

    echo "$inpath -> $outpath"

    ffmpeg -nostdin -y -i "$inpath" \
        -vn \
        -c:a libvorbis \
        -q:a 6 \
        "$outpath"
done
