"""Viewport thumbnail capture"""
import os
import tempfile
from pathlib import Path
from typing import Optional


def capture_viewport(
    output_path: Optional[Path] = None,
    width: int = 256,
    height: int = 256,
    image_format: str = "jpg",
    quality: int = 85
) -> Path:
    """
    Capture the active viewport as a thumbnail.
    Uses cmds.playblast for a single frame capture.
    """
    import maya.cmds as cmds

    if output_path is None:
        tmp_dir = tempfile.mkdtemp(prefix="ninja_thumb_")
        output_path = Path(tmp_dir) / "thumbnail.{}".format(image_format)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing file so playblast doesn't complain
    if output_path.exists():
        output_path.unlink()

    # playblast single frame
    cmds.playblast(
        frame=cmds.currentTime(query=True),
        format="image",
        compression=image_format,
        quality=quality,
        width=width,
        height=height,
        showOrnaments=False,
        viewer=False,
        completeFilename=str(output_path),
        forceOverwrite=True,
        percent=100,
    )

    return output_path
