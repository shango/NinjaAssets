"""Initialize GDrive folder structure for NinjaAssets"""
import argparse
import sys
from pathlib import Path

from ninja_assets.constants import CATEGORIES, SCHEMA_VERSION


def init_gdrive(gdrive_root: Path, quiet: bool = False) -> None:
    """
    Create the canonical GDrive folder structure:

    gdrive_root/
      assets/
        characters/
        props/
        environments/
        vehicles/
        weapons/
        fx/
        other/
      scenes/
      .ninjaassets/
        changelog.jsonl  (empty file, created if not exists)
        schema_version.txt  (contains SCHEMA_VERSION)
    """
    assets_root = gdrive_root / "assets"
    scenes_root = gdrive_root / "scenes"
    pipeline_dir = gdrive_root / ".ninjaassets"

    # Create dirs
    for category in CATEGORIES:
        (assets_root / category.lower()).mkdir(parents=True, exist_ok=True)
    scenes_root.mkdir(parents=True, exist_ok=True)
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # Create changelog if not exists (open in append mode to avoid updating mtime)
    changelog = pipeline_dir / "changelog.jsonl"
    open(changelog, 'a').close()

    # Write schema version
    schema_file = pipeline_dir / "schema_version.txt"
    schema_file.write_text(str(SCHEMA_VERSION))

    if not quiet:
        print(f"NinjaAssets GDrive structure initialized at: {gdrive_root}")


def main():
    parser = argparse.ArgumentParser(description="Initialize GDrive for NinjaAssets")
    parser.add_argument("gdrive_root", type=Path, help="Path to GDrive root (e.g., G:/)")
    args = parser.parse_args()

    if not args.gdrive_root.exists():
        print(f"Error: {args.gdrive_root} does not exist", file=sys.stderr)
        sys.exit(1)

    init_gdrive(args.gdrive_root)


if __name__ == "__main__":
    main()
