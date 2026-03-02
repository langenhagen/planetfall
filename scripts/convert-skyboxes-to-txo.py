#!/usr/bin/env python3
"""Convert skybox textures to .txo for faster runtime loading.

Scans common image formats under assets/sky and writes .txo alongside them.
Uses clamp wrap modes and linear filtering without mipmaps.
"""

import importlib
import logging
from pathlib import Path

ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".exr"}


def convert_sky_textures() -> None:
    """Convert supported sky textures under assets/sky to .txo."""
    logger = logging.getLogger(__name__)
    script_dir = Path(__file__).resolve().parent
    sky_dir = (script_dir / ".." / "assets" / "sky").resolve()

    if not sky_dir.is_dir():
        message = f"Sky directory not found: {sky_dir}"
        raise SystemExit(message)

    try:
        panda_core = importlib.import_module("panda3d.core")
    except ModuleNotFoundError as exc:
        message = "panda3d is required but could not be imported"
        raise SystemExit(message) from exc

    pnm_image_class = panda_core.PNMImage
    sampler_state_class = panda_core.SamplerState
    texture_class = panda_core.Texture

    for path in sorted(sky_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ASSET_EXTENSIONS:
            continue

        out_path = path.with_suffix(".txo")

        image = pnm_image_class()
        if not image.read(str(path)):
            logger.error("failed: %s", path)
            continue

        texture = texture_class()
        texture.load(image)
        texture.set_wrap_u(sampler_state_class.WM_clamp)
        texture.set_wrap_v(sampler_state_class.WM_clamp)
        texture.set_minfilter(sampler_state_class.FT_linear)
        texture.set_magfilter(sampler_state_class.FT_linear)

        if not texture.write(str(out_path)):
            logger.error("failed to write: %s", out_path)
            continue

        logger.info("%s -> %s", path, out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    convert_sky_textures()
