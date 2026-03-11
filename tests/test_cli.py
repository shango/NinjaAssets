"""Tests for CLI utilities."""

import json
from pathlib import Path

from ninja_assets.cli.init_gdrive import init_gdrive
from ninja_assets.cli.migrate import find_orphaned_assets, migrate
from ninja_assets.constants import CATEGORIES, SCHEMA_VERSION, SIDECAR_SUFFIX
from ninja_assets.core.sidecar import SidecarManager


def test_init_gdrive_creates_structure(tmp_path):
    """Run init_gdrive on tmp_path, verify all folders, changelog, and schema version."""
    gdrive = tmp_path / "gdrive"
    gdrive.mkdir()
    init_gdrive(gdrive)

    # Verify category folders
    for cat in CATEGORIES:
        assert (gdrive / "assets" / cat.lower()).is_dir()

    # Verify scenes
    assert (gdrive / "scenes").is_dir()

    # Verify pipeline dir
    assert (gdrive / ".ninjaassets").is_dir()

    # Verify changelog exists and is empty
    changelog = gdrive / ".ninjaassets" / "changelog.jsonl"
    assert changelog.exists()
    assert changelog.read_text() == ""

    # Verify schema version
    schema = gdrive / ".ninjaassets" / "schema_version.txt"
    assert schema.read_text() == str(SCHEMA_VERSION)


def test_init_gdrive_idempotent(tmp_path):
    """Run init_gdrive twice, verify no errors and structure is correct."""
    gdrive = tmp_path / "gdrive"
    gdrive.mkdir()

    init_gdrive(gdrive)
    # Write something to changelog to verify it's preserved
    changelog = gdrive / ".ninjaassets" / "changelog.jsonl"
    changelog.write_text("test line\n")

    # Run again - should not error or overwrite changelog
    init_gdrive(gdrive)

    for cat in CATEGORIES:
        assert (gdrive / "assets" / cat.lower()).is_dir()
    assert (gdrive / "scenes").is_dir()
    assert changelog.read_text() == "test line\n"
    assert (gdrive / ".ninjaassets" / "schema_version.txt").read_text() == str(SCHEMA_VERSION)


def test_find_orphaned_assets(tmp_path):
    """Create asset folders with/without sidecars and verify detection."""
    assets_root = tmp_path / "assets"

    # Create orphaned asset (no sidecar)
    orphan_dir = assets_root / "props" / "barrel"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "barrel.obj").touch()

    # Create another orphaned asset
    orphan2_dir = assets_root / "characters" / "hero"
    orphan2_dir.mkdir(parents=True)
    (orphan2_dir / "hero_v2.fbx").touch()
    (orphan2_dir / "hero_v1.fbx").touch()

    # Create asset WITH sidecar (should NOT be found)
    managed_dir = assets_root / "props" / "crate"
    managed_dir.mkdir(parents=True)
    (managed_dir / "crate.obj").touch()
    (managed_dir / "crate.meta.json").write_text("{}")

    orphans = find_orphaned_assets(assets_root)
    orphan_names = [name for _, name, _ in orphans]

    assert "barrel" in orphan_names
    assert "hero" in orphan_names
    assert "crate" not in orphan_names

    # Verify hero picks the highest version file
    hero_entry = [(f, n, fn) for f, n, fn in orphans if n == "hero"][0]
    assert hero_entry[2] == "hero_v2.fbx"


def test_migrate_creates_sidecars(tmp_path):
    """Create orphaned assets, run migrate, verify sidecars created."""
    assets_root = tmp_path / "assets"

    # Create orphaned asset in props
    barrel_dir = assets_root / "props" / "barrel"
    barrel_dir.mkdir(parents=True)
    (barrel_dir / "barrel.obj").touch()

    # Create orphaned asset in characters
    hero_dir = assets_root / "characters" / "hero"
    hero_dir.mkdir(parents=True)
    (hero_dir / "hero.fbx").touch()

    migrated = migrate(assets_root, user="testuser", dry_run=False)

    assert len(migrated) == 2
    assert "barrel" in migrated
    assert "hero" in migrated

    # Verify sidecar files exist and have correct content
    barrel_sidecar = barrel_dir / f"barrel{SIDECAR_SUFFIX}"
    assert barrel_sidecar.exists()
    barrel_data = json.loads(barrel_sidecar.read_text())
    assert barrel_data["category"] == "Props"
    assert barrel_data["current_file"] == "barrel.obj"

    hero_sidecar = hero_dir / f"hero{SIDECAR_SUFFIX}"
    assert hero_sidecar.exists()
    hero_data = json.loads(hero_sidecar.read_text())
    assert hero_data["category"] == "Characters"
    assert hero_data["current_file"] == "hero.fbx"


def test_migrate_dry_run(tmp_path):
    """Run with dry_run=True, verify NO sidecar files created but assets are reported."""
    assets_root = tmp_path / "assets"

    barrel_dir = assets_root / "props" / "barrel"
    barrel_dir.mkdir(parents=True)
    (barrel_dir / "barrel.obj").touch()

    migrated = migrate(assets_root, user="testuser", dry_run=True)

    assert len(migrated) == 1
    assert "barrel" in migrated

    # Verify NO sidecar was created
    barrel_sidecar = barrel_dir / f"barrel{SIDECAR_SUFFIX}"
    assert not barrel_sidecar.exists()


def test_migrate_skips_existing(tmp_path):
    """Create an asset with existing sidecar, verify migrate doesn't touch it."""
    assets_root = tmp_path / "assets"

    # Create asset with existing sidecar
    crate_dir = assets_root / "props" / "crate"
    crate_dir.mkdir(parents=True)
    (crate_dir / "crate.obj").touch()
    sidecar = crate_dir / f"crate{SIDECAR_SUFFIX}"
    original_content = '{"existing": true}'
    sidecar.write_text(original_content)

    migrated = migrate(assets_root, user="testuser", dry_run=False)

    assert len(migrated) == 0
    # Verify sidecar was not modified
    assert sidecar.read_text() == original_content
