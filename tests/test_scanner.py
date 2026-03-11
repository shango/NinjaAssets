"""Tests for AssetScanner."""

import os
import time
from pathlib import Path

import pytest

from ninja_assets.config import NinjaConfig
from ninja_assets.constants import SIDECAR_SUFFIX
from ninja_assets.core.cache import CacheDB
from ninja_assets.core.sidecar import SidecarManager
from ninja_assets.core.models import Asset
from ninja_assets.sync.scanner import AssetScanner


def create_test_asset(
    gdrive_path: Path, category: str, name: str
) -> Asset:
    """Create a folder + sidecar file and return the Asset."""
    asset_folder = gdrive_path / "assets" / category.lower() / name
    asset_folder.mkdir(parents=True, exist_ok=True)

    asset = Asset.new(name=name, category=category, path=str(asset_folder))
    asset.current_file = f"{name}_v001.fbx"
    asset.current_version = 1

    sidecar_path = SidecarManager.get_sidecar_path(asset_folder, name)
    SidecarManager.write(sidecar_path, asset)
    return asset


class TestFullScan:
    def test_finds_assets_in_fake_gdrive(self, fake_gdrive):
        """full_scan discovers sidecar files and populates cache."""
        config = fake_gdrive
        cache = CacheDB()

        # Create test assets
        asset1 = create_test_asset(config.gdrive_root, "Props", "sword")
        asset2 = create_test_asset(config.gdrive_root, "Characters", "hero")

        scanner = AssetScanner(config, cache)
        changed = scanner.full_scan()

        assert len(changed) == 2
        assert asset1.uuid in changed
        assert asset2.uuid in changed

        # Verify assets are in cache
        cached1 = cache.get_asset(asset1.uuid)
        assert cached1 is not None
        assert cached1.name == "sword"
        assert cached1.category == "Props"

        cached2 = cache.get_asset(asset2.uuid)
        assert cached2 is not None
        assert cached2.name == "hero"

    def test_full_scan_no_changes_on_second_run(self, fake_gdrive):
        """Second full_scan with no disk changes returns empty list."""
        config = fake_gdrive
        cache = CacheDB()

        create_test_asset(config.gdrive_root, "Props", "shield")

        scanner = AssetScanner(config, cache)
        changed1 = scanner.full_scan()
        assert len(changed1) == 1

        changed2 = scanner.full_scan()
        assert len(changed2) == 0

    def test_removes_stale_entries_from_cache(self, fake_gdrive):
        """full_scan removes cache entries whose sidecars no longer exist on disk."""
        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "bow")

        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        # Verify asset is in cache
        assert cache.get_asset(asset.uuid) is not None

        # Remove the sidecar file from disk
        asset_folder = config.gdrive_root / "assets" / "props" / "bow"
        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, "bow")
        sidecar_path.unlink()

        # Re-scan
        changed = scanner.full_scan()
        assert asset.uuid in changed

        # Verify it's removed from cache
        assert cache.get_asset(asset.uuid) is None

    def test_handles_missing_assets_root(self, tmp_path):
        """full_scan returns empty list when assets root doesn't exist."""
        config = NinjaConfig(
            gdrive_root=tmp_path / "nonexistent",
            local_data_dir=tmp_path / "local",
            _ensure_dirs=False,
        )
        cache = CacheDB()
        scanner = AssetScanner(config, cache)
        changed = scanner.full_scan()
        assert changed == []

    def test_handles_corrupted_sidecar(self, fake_gdrive):
        """full_scan skips corrupted sidecar files gracefully."""
        config = fake_gdrive
        cache = CacheDB()

        # Create a valid asset
        asset_good = create_test_asset(config.gdrive_root, "Props", "axe")

        # Create a corrupted sidecar
        bad_folder = config.gdrive_root / "assets" / "props" / "broken"
        bad_folder.mkdir(parents=True, exist_ok=True)
        bad_sidecar = bad_folder / f"broken{SIDECAR_SUFFIX}"
        bad_sidecar.write_text("{invalid json", encoding="utf-8")

        scanner = AssetScanner(config, cache)
        changed = scanner.full_scan()

        # Good asset should be found
        assert asset_good.uuid in changed
        # Cache should have only the good asset
        assert len(cache.get_all_uuids()) == 1


class TestSpotCheck:
    def test_detects_mtime_changes(self, fake_gdrive):
        """spot_check detects when a sidecar has been modified."""
        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "dagger")

        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        # Modify the sidecar on disk (change mtime)
        asset_folder = config.gdrive_root / "assets" / "props" / "dagger"
        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, "dagger")

        # Re-read and re-write to change mtime
        asset_obj, _ = SidecarManager.read(sidecar_path)
        asset_obj.tags = ["modified"]
        # Ensure mtime changes by sleeping briefly
        time.sleep(0.05)
        SidecarManager.write(sidecar_path, asset_obj)

        changed = scanner.spot_check(count=100)
        assert asset.uuid in changed

        # Verify cache was updated
        cached = cache.get_asset(asset.uuid)
        assert cached is not None
        assert "modified" in cached.tags

    def test_spot_check_no_changes(self, fake_gdrive):
        """spot_check returns empty list when nothing changed."""
        config = fake_gdrive
        cache = CacheDB()

        create_test_asset(config.gdrive_root, "Props", "helmet")

        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        changed = scanner.spot_check(count=100)
        assert changed == []

    def test_spot_check_handles_empty_cache(self, fake_gdrive):
        """spot_check works with empty cache."""
        config = fake_gdrive
        cache = CacheDB()
        scanner = AssetScanner(config, cache)
        changed = scanner.spot_check(count=20)
        assert changed == []

    def test_spot_check_handles_deleted_sidecar(self, fake_gdrive):
        """spot_check removes cache entry if sidecar was deleted."""
        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "staff")

        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        # Remove sidecar from disk
        asset_folder = config.gdrive_root / "assets" / "props" / "staff"
        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, "staff")
        sidecar_path.unlink()

        changed = scanner.spot_check(count=100)
        assert asset.uuid in changed
        assert cache.get_asset(asset.uuid) is None
