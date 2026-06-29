"""Migrate existing assets that lack sidecar metadata files.

Supports thumbnail generation via trimesh + pyrender (optional).
Install with: pip install ninja-assets[thumbnail]
"""
import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ninja_assets.constants import CATEGORIES
from ninja_assets.core.changelog import ChangelogManager
from ninja_assets.core.models import ChangelogEvent, EventType
from ninja_assets.core.sidecar import SidecarManager

logger = logging.getLogger(__name__)

ASSET_EXTENSIONS = {'.obj', '.ma', '.mb', '.fbx', '.glb', '.gltf'}
THUMBNAIL_FILENAME = "thumbnail.jpg"


def _try_render_thumbnail(mesh_path, output_path, width=512, height=512):
    """Attempt to render a thumbnail. Returns True on success, False if deps missing."""
    try:
        from ninja_assets.core.thumbnail import render_mesh_thumbnail, RENDERABLE_EXTENSIONS
        if mesh_path.suffix.lower() not in RENDERABLE_EXTENSIONS:
            return False
        render_mesh_thumbnail(mesh_path, output_path, width=width, height=height)
        return True
    except ImportError:
        return False
    except Exception as exc:
        logger.warning("Thumbnail render failed for %s: %s", mesh_path, exc)
        return False


def find_orphaned_assets(assets_root: Path) -> List[Tuple[Path, str, str]]:
    """
    Find asset files (.obj, .ma, .mb, .fbx) in category folders
    that don't have a corresponding .meta.json sidecar.

    Returns list of (asset_folder, asset_name, asset_filename) tuples.

    Walk structure: assets_root/<category>/<asset_name>/<files>
    For each asset folder, check if any .meta.json exists.
    If not, find the "best" asset file (prefer highest version number,
    or first file found).
    """
    orphans: List[Tuple[Path, str, str]] = []
    category_lower = [c.lower() for c in CATEGORIES]

    for cat in category_lower:
        cat_dir = assets_root / cat
        if not cat_dir.is_dir():
            continue
        for asset_dir in sorted(cat_dir.iterdir()):
            if not asset_dir.is_dir():
                continue
            # Check if any .meta.json already exists
            has_sidecar = any(
                f.name.endswith(".meta.json") for f in asset_dir.iterdir() if f.is_file()
            )
            if has_sidecar:
                continue
            # Find asset files
            asset_files = [
                f for f in asset_dir.iterdir()
                if f.is_file() and f.suffix.lower() in ASSET_EXTENSIONS
            ]
            if not asset_files:
                continue
            # Prefer highest version number (try to extract digits from stem),
            # fall back to first sorted file
            def _version_key(p: Path) -> int:
                nums = re.findall(r'\d+', p.stem)
                return int(nums[-1]) if nums else 0

            best = max(asset_files, key=_version_key)
            orphans.append((asset_dir, asset_dir.name, best.name))

    return orphans


def migrate(
    assets_root: Path,
    user: str,
    dry_run: bool = False,
    changelog_path: Optional[Path] = None,
    thumbnail_size: int = 512,
) -> List[str]:
    """
    Create .meta.json sidecars for orphaned assets, optionally generate
    thumbnails and append changelog entries for sync.

    Args:
        assets_root: Path to assets root folder.
        user: Username for the created_by field.
        dry_run: If True, only report what would be done.
        changelog_path: If provided, append ASSET_CREATED events.
        thumbnail_size: Width/height for generated thumbnails.

    Returns:
        List of asset names that were migrated.
    """
    orphans = find_orphaned_assets(assets_root)
    migrated: List[str] = []
    category_map = {c.lower(): c for c in CATEGORIES}

    changelog = ChangelogManager(changelog_path) if changelog_path else None

    for asset_folder, asset_name, asset_filename in orphans:
        # Determine category from parent folder name
        cat_folder = asset_folder.parent.name.lower()
        category = category_map.get(cat_folder, cat_folder)

        if dry_run:
            print(f"[DRY RUN] Would create sidecar for: {asset_name} ({category})")
            migrated.append(asset_name)
            continue

        asset = SidecarManager.create_minimal(
            asset_folder=asset_folder,
            asset_name=asset_name,
            asset_file=asset_filename,
            category=category,
            user=user,
        )

        # Generate thumbnail for renderable mesh formats (OBJ, GLB, glTF, STL, etc.)
        thumb_generated = False
        asset_file_path = asset_folder / asset_filename
        thumb_path = asset_folder / THUMBNAIL_FILENAME
        thumb_generated = _try_render_thumbnail(
            asset_file_path, thumb_path,
            width=thumbnail_size, height=thumbnail_size,
        )

        if thumb_generated:
            asset.thumbnail = THUMBNAIL_FILENAME
            # Re-write sidecar with thumbnail field
            sidecar_path = SidecarManager.get_sidecar_path(asset_folder, asset_name)
            SidecarManager.write(sidecar_path, asset)
            print(f"Created sidecar + thumbnail for: {asset_name} ({category})")
        else:
            print(f"Created sidecar for: {asset_name} ({category})")

        # Append changelog entry so other workstations pick it up via quick-sync
        if changelog:
            event = ChangelogEvent(
                timestamp=datetime.utcnow(),
                event_type=EventType.ASSET_CREATED,
                uuid=asset.uuid,
                path=str(asset_folder),
                user=user,
                version=1,
            )
            changelog.append(event)

        migrated.append(asset_name)

    return migrated


def main():
    parser = argparse.ArgumentParser(description="Migrate existing assets to NinjaAssets")
    parser.add_argument("assets_root", type=Path, help="Path to assets root (e.g., G:/assets)")
    parser.add_argument("--user", required=True, help="Username for metadata")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument(
        "--changelog", type=Path, default=None,
        help="Path to changelog.jsonl for sync (e.g., G:/.ninjaassets/changelog.jsonl)",
    )
    parser.add_argument(
        "--thumbnail-size", type=int, default=512,
        help="Thumbnail width/height in pixels (default: 512)",
    )
    args = parser.parse_args()

    if not args.assets_root.exists():
        print(f"Error: {args.assets_root} does not exist", file=sys.stderr)
        sys.exit(1)

    migrated = migrate(
        args.assets_root,
        args.user,
        args.dry_run,
        changelog_path=args.changelog,
        thumbnail_size=args.thumbnail_size,
    )
    print(f"\n{'Would migrate' if args.dry_run else 'Migrated'} {len(migrated)} assets")


if __name__ == "__main__":
    main()
