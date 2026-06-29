"""Maya commands for asset import, reference, and scene versioning"""
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

from ninja_assets.core.models import Asset, Version
from ninja_assets.core.scene_meta import SceneMetaManager
from ninja_assets.core.sidecar import SidecarManager

logger = logging.getLogger(__name__)


def pull_asset(
    asset: Asset, version: Optional[int], local_root: Union[str, Path]
) -> Path:
    """Copy an asset version from its remote folder into the local repo.

    Copies the version file plus its .meta.json sidecar and thumbnail (when
    present) into ``local_root/<category>/<name>/``. Idempotent: a file is only
    copied when missing or older than the source. Returns the local file path.
    """
    local_root = Path(local_root)
    remote_file = _get_asset_file_path(asset, version)
    if not remote_file.exists():
        raise FileNotFoundError(f"Asset file not found: {remote_file}")

    dest_dir = local_root / asset.category / asset.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    remote_folder = Path(asset.path)
    extras = []
    sidecar = SidecarManager.get_sidecar_path(remote_folder, asset.name)
    if sidecar.exists():
        extras.append(sidecar)
    if asset.thumbnail:
        thumb = remote_folder / asset.thumbnail
        if thumb.exists():
            extras.append(thumb)

    for src in [remote_file, *extras]:
        dest = dest_dir / src.name
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dest)

    return dest_dir / remote_file.name


def import_asset(
    asset: Asset,
    version: Optional[int] = None,
    local_root: Optional[Union[str, Path]] = None,
) -> list:
    """Import asset into current scene. Returns list of imported nodes.

    When ``local_root`` is given, the asset is first pulled to the local repo
    and imported from that local copy; otherwise it is imported from its
    remote path.
    """
    import maya.cmds as cmds

    if local_root is not None:
        file_path = pull_asset(asset, version, local_root)
    else:
        file_path = _get_asset_file_path(asset, version)
    if not file_path.exists():
        raise FileNotFoundError(f"Asset file not found: {file_path}")

    ext = file_path.suffix.lower()
    file_type = {'.obj': 'OBJ', '.ma': 'mayaAscii', '.mb': 'mayaBinary', '.fbx': 'FBX'}.get(ext)
    if not file_type:
        raise ValueError(f"Unsupported file type: {ext}")

    before = set(cmds.ls(assemblies=True))
    cmds.file(str(file_path), i=True, type=file_type, ignoreVersion=True,
              mergeNamespacesOnClash=False, namespace=asset.name, preserveReferences=True)
    after = set(cmds.ls(assemblies=True))
    imported = list(after - before)

    v = version or asset.current_version
    cmds.inViewMessage(amg=f"<hl>Imported:</hl> {asset.name} v{v}", pos='topCenter', fade=True)
    return imported


def reference_asset(
    asset: Asset,
    version: Optional[int] = None,
    local_root: Optional[Union[str, Path]] = None,
) -> str:
    """Create a reference to an asset. Returns reference node name.

    When ``local_root`` is given, the asset is pulled to the local repo first
    and referenced from that local copy.
    """
    import maya.cmds as cmds

    if local_root is not None:
        file_path = pull_asset(asset, version, local_root)
    else:
        file_path = _get_asset_file_path(asset, version)
    if not file_path.exists():
        raise FileNotFoundError(f"Asset file not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in ('.ma', '.mb'):
        raise ValueError(f"Cannot reference {ext} files. Use Import instead.")

    file_type = 'mayaAscii' if ext == '.ma' else 'mayaBinary'
    v = version or asset.current_version
    namespace = f"{asset.name}_v{v}"

    ref_node = cmds.file(str(file_path), reference=True, type=file_type,
                          namespace=namespace, mergeNamespacesOnClash=False)
    cmds.inViewMessage(amg=f"<hl>Referenced:</hl> {asset.name} v{v}", pos='topCenter', fade=True)
    return ref_node


def save_scene_version(config, comment="", version_override=None):
    """
    Save current scene as a new version.
    - Reads or creates .scene_meta.json
    - Determines next version (or uses version_override)
    - Saves scene as <base_name>_v<NNN>.ma
    - Updates .scene_meta.json
    """
    import maya.cmds as cmds
    from ninja_assets.maya_integration.utils.maya_utils import get_current_scene_path, get_scene_folder_and_name

    scene_path = get_current_scene_path()
    if not scene_path:
        cmds.warning("NinjaAssets: No scene is currently open. Save your scene first.")
        return None

    folder, base_name = get_scene_folder_and_name(scene_path)

    # Read or create scene meta
    scene_meta = SceneMetaManager.ensure(folder, base_name)

    # Determine version number
    if version_override is not None:
        next_ver = version_override
    else:
        next_ver = scene_meta.get_next_version()

    # Build versioned filename
    ver_str = f"v{next_ver:03d}"
    new_filename = f"{base_name}_{ver_str}.ma"
    new_path = folder / new_filename

    # Save scene
    cmds.file(rename=str(new_path))
    cmds.file(save=True, type="mayaAscii")

    # Update scene meta
    version_entry = Version(
        version=next_ver,
        file=new_filename,
        created_by=config.username or "unknown",
        created_at=datetime.utcnow(),
        comment=comment
    )
    scene_meta.versions.append(version_entry)
    scene_meta.current_version = next_ver
    SceneMetaManager.write(SceneMetaManager.get_meta_path(folder), scene_meta)

    cmds.inViewMessage(amg=f"<hl>Saved:</hl> {new_filename}", pos='topCenter', fade=True)
    return new_path


def _get_asset_file_path(asset: Asset, version: Optional[int] = None) -> Path:
    if version is None:
        return Path(asset.path) / asset.current_file
    v = asset.get_version(version)
    if v is None:
        raise ValueError(f"Version {version} not found for asset {asset.name}")
    return Path(asset.path) / v.file
