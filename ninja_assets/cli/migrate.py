"""Migrate existing assets that lack sidecar metadata files"""
import argparse
import re
import sys
import os
from pathlib import Path
from typing import List, Tuple

from ninja_assets.constants import CATEGORIES
from ninja_assets.core.sidecar import SidecarManager


ASSET_EXTENSIONS = {'.obj', '.ma', '.mb', '.fbx'}


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


def migrate(assets_root: Path, user: str, dry_run: bool = False) -> List[str]:
    """
    Create minimal .meta.json sidecars for orphaned assets.

    Args:
        assets_root: Path to assets root folder
        user: Username for the created_by field
        dry_run: If True, only report what would be done

    Returns:
        List of asset names that were migrated

    For each orphaned asset:
    - Determine category from parent folder name (match against CATEGORIES, case-insensitive)
    - Use SidecarManager.create_minimal() to create the sidecar
    - Print what was done
    """
    orphans = find_orphaned_assets(assets_root)
    migrated: List[str] = []
    category_map = {c.lower(): c for c in CATEGORIES}

    for asset_folder, asset_name, asset_filename in orphans:
        # Determine category from parent folder name
        cat_folder = asset_folder.parent.name.lower()
        category = category_map.get(cat_folder, cat_folder)

        if dry_run:
            print(f"[DRY RUN] Would create sidecar for: {asset_name} ({category})")
        else:
            SidecarManager.create_minimal(
                asset_folder=asset_folder,
                asset_name=asset_name,
                asset_file=asset_filename,
                category=category,
                user=user,
            )
            print(f"Created sidecar for: {asset_name} ({category})")

        migrated.append(asset_name)

    return migrated


def main():
    parser = argparse.ArgumentParser(description="Migrate existing assets to NinjaAssets")
    parser.add_argument("assets_root", type=Path, help="Path to assets root (e.g., G:/assets)")
    parser.add_argument("--user", required=True, help="Username for metadata")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    if not args.assets_root.exists():
        print(f"Error: {args.assets_root} does not exist", file=sys.stderr)
        sys.exit(1)

    migrated = migrate(args.assets_root, args.user, args.dry_run)
    print(f"\n{'Would migrate' if args.dry_run else 'Migrated'} {len(migrated)} assets")


if __name__ == "__main__":
    main()
