# Assets

This directory contains all runtime assets.

## Audio

Audio files live under these subdirectories:

- [assets/audio/music/](audio/music/): background music.
- [assets/audio/sfx/](audio/sfx/): sound effects.

The game only consumes these formats:

- SFX: `.wav`
- Music: `.ogg`

Other formats (for example `.mp3` or `.flac`) may be kept for reference or
development and are ignored by the runtime.

Conversion scripts:

- [scripts/convert-audio-sfx-to-wav.sh](../scripts/convert-audio-sfx-to-wav.sh)
- [scripts/convert-audio-background-music-to-ogg.sh](../scripts/convert-audio-background-music-to-ogg.sh)

## Models

Models live under [assets/models/](models/) and are authored as `.obj` with
textures. Some models do not include `.mtl` files, so materials are applied
programmatically. The game uses pre-converted `.bam` files next to each `.obj`.

Conversion script:

- [scripts/convert-models-to-bam.py](../scripts/convert-models-to-bam.py)

## Skyboxes

Skybox textures live under [assets/sky/](sky/) and are authored as common image
formats (for example `.png`). The game uses `.txo` files produced next to the
source textures.

Conversion script:

- [scripts/convert-skyboxes-to-txo.py](../scripts/convert-skyboxes-to-txo.py)

## Batch Conversion

Run all asset converters in one pass:

- [scripts/convert-assets.sh](../scripts/convert-assets.sh)
