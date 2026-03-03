#!/usr/bin/env python3
"""Convert OBJ models to Panda3D .bam via Ursina's OBJ parser."""

import logging
from pathlib import Path

from ursina.mesh_importer import obj_to_ursinamesh
from ursina.sequence import Func


def convert_obj(obj_path: Path) -> None:
    """Convert one OBJ path to a BAM alongside it."""
    bam_path = obj_path.with_suffix(".bam")
    mesh = obj_to_ursinamesh(
        folder=Func(lambda: obj_path.parent),
        name=obj_path.stem,
        return_mesh=True,
    )
    if mesh is None:
        message = f"Failed to convert {obj_path}"
        raise SystemExit(message)
    mesh.save(name=bam_path.name, folder=bam_path.parent)


def main() -> None:
    """Convert all OBJ models under assets/models."""
    logger = logging.getLogger(__name__)
    script_dir = Path(__file__).resolve().parent
    models_dir = script_dir.parent / "assets" / "models"
    if not models_dir.is_dir():
        message = f"Models directory not found: {models_dir}"
        raise SystemExit(message)

    for obj_path in models_dir.rglob("*.obj"):
        logger.info("%s -> %s", obj_path, obj_path.with_suffix(".bam"))
        convert_obj(obj_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
