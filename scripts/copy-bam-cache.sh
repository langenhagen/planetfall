#!/usr/bin/env bash
#
# Copy Panda-generated BAM cache files from .venv into repo asset folders.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/.venv/bin/models_compressed"

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Missing BAM source directory: $SOURCE_DIR" >&2
    echo "Run: uv run planetfall" >&2
    exit 1
fi

declare -A DESTINATION_BY_BAM=(
    ["coin.bam"]="assets/models/coins/"
    ["Asteroid_1.bam"]="assets/models/asteroids/"
    ["Rocky_Asteroid_2.bam"]="assets/models/asteroids/"
    ["Rocky_Asteroid_3.bam"]="assets/models/asteroids/"
    ["Rocky_Asteroid_4.bam"]="assets/models/asteroids/"
    ["Rocky_Asteroid_5.bam"]="assets/models/asteroids/"
    ["Rocky_Asteroid_6.bam"]="assets/models/asteroids/"
)

copied_count=0
for bam_name in "${!DESTINATION_BY_BAM[@]}"; do
    source_path="$SOURCE_DIR/$bam_name"
    if [[ ! -f "$source_path" ]]; then
        echo "Skipping missing cache file: $source_path"
        continue
    fi

    destination_dir="$REPO_ROOT/${DESTINATION_BY_BAM[$bam_name]}"
    mkdir -p "$destination_dir"
    cp "$source_path" "$destination_dir"
    echo "Copied $bam_name -> ${DESTINATION_BY_BAM[$bam_name]}"
    copied_count=$((copied_count + 1))
done

echo "Copied $copied_count BAM files."
