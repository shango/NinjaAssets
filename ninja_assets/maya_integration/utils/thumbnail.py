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
        # Generate temp path
        fd, tmp = tempfile.mkstemp(suffix=f'.{image_format}')
        os.close(fd)
        output_path = Path(tmp)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # playblast single frame
    result = cmds.playblast(
        frame=cmds.currentTime(query=True),
        format="image",
        compression=image_format,
        quality=quality,
        width=width,
        height=height,
        showOrnaments=False,
        viewer=False,
        filename=str(output_path.with_suffix('')),  # playblast adds extension
        completeFilename=str(output_path)
    )

    return output_path
