"""Asset export utilities for OBJ and MA formats"""
from pathlib import Path
from typing import Optional

from ninja_assets.core.exceptions import ExportError


def export_obj(output_path: Path, selection_only: bool = True) -> Path:
    """Export selection as OBJ file."""
    import maya.cmds as cmds

    if selection_only and not cmds.ls(selection=True):
        raise ExportError("Nothing selected for export")

    # Ensure parent dir exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmds.file(
        str(output_path),
        force=True,
        options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1",
        type="OBJexport",
        preserveReferences=False,
        exportSelected=selection_only
    )
    return output_path


def export_ma(output_path: Path, selection_only: bool = True) -> Path:
    """Export selection as Maya ASCII file."""
    import maya.cmds as cmds

    if selection_only and not cmds.ls(selection=True):
        raise ExportError("Nothing selected for export")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmds.file(
        str(output_path),
        force=True,
        type="mayaAscii",
        preserveReferences=True,
        exportSelected=selection_only
    )
    return output_path


def get_selection_poly_count() -> Optional[int]:
    """Get total polygon count of selected meshes."""
    import maya.cmds as cmds

    selected = cmds.ls(selection=True, dag=True, type='mesh')
    if not selected:
        return None

    total = 0
    for mesh in selected:
        count = cmds.polyEvaluate(mesh, face=True)
        if isinstance(count, int):
            total += count
    return total


def get_selection_bounds():
    """Get bounding box of selection. Returns Bounds or None."""
    import maya.cmds as cmds
    from ninja_assets.core.models import Bounds

    selected = cmds.ls(selection=True)
    if not selected:
        return None

    bbox = cmds.exactWorldBoundingBox(selected)
    # bbox = [xmin, ymin, zmin, xmax, ymax, zmax]
    return Bounds(
        x=round(bbox[3] - bbox[0], 3),
        y=round(bbox[4] - bbox[1], 3),
        z=round(bbox[5] - bbox[2], 3)
    )
