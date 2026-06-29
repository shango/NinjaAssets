"""Tests for AssetScanner."""

import time
from pathlib import Path


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

    def test_finds_assets_in_nested_subfolders(self, fake_gdrive):
        """full_scan discovers sidecars nested arbitrarily deep under assets/."""
        config = fake_gdrive
        cache = CacheDB()

        # Asset nested deeper than the flat category/asset layout.
        deep_folder = (
            config.gdrive_root / "assets" / "props" / "weapons" / "swords"
            / "excalibur"
        )
        deep_folder.mkdir(parents=True, exist_ok=True)
        asset = Asset.new(name="excalibur", category="Props", path=str(deep_folder))
        sidecar_path = SidecarManager.get_sidecar_path(deep_folder, "excalibur")
        SidecarManager.write(sidecar_path, asset)

        scanner = AssetScanner(config, cache)
        changed = scanner.full_scan()

        assert asset.uuid in changed
        cached = cache.get_asset(asset.uuid)
        assert cached is not None
        assert cached.name == "excalibur"

    def test_moved_folder_refreshes_path_cheaply(self, fake_gdrive):
        """A relocated asset keeps its UUID and just gets its path refreshed.

        Moving a folder leaves the sidecar's mtime untouched, so the rescan
        must still notice the new location and update the cached path without
        duplicating or evicting the asset.
        """
        import shutil

        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "lantern")
        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        old_folder = config.gdrive_root / "assets" / "props" / "lantern"
        new_folder = config.gdrive_root / "assets" / "props" / "lighting" / "lantern"
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_folder), str(new_folder))

        changed = scanner.full_scan()

        assert asset.uuid in changed
        cached = cache.get_asset(asset.uuid)
        assert cached is not None
        assert cached.path == str(new_folder)
        # Exactly one asset — not duplicated, not evicted.
        assert cache.get_all_uuids() == [asset.uuid]

    def test_moved_folder_is_a_noop_on_steady_state(self, fake_gdrive):
        """Once a move is absorbed, further scans report no changes."""
        import shutil

        config = fake_gdrive
        cache = CacheDB()

        create_test_asset(config.gdrive_root, "Props", "candle")
        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        old_folder = config.gdrive_root / "assets" / "props" / "candle"
        new_folder = config.gdrive_root / "assets" / "props" / "wax" / "candle"
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_folder), str(new_folder))

        assert len(scanner.full_scan()) == 1  # absorbs the move
        assert scanner.full_scan() == []  # steady state, no rescan churn

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


class TestMultiRemoteScan:
    def _make_remote(self, tmp_path, name):
        root = tmp_path / name
        (root / "assets").mkdir(parents=True)
        return root

    def test_scans_all_remotes_and_tags_source_repo(self, tmp_path):
        """One full_scan aggregates assets from every configured remote."""
        from ninja_assets.config import Repo

        studio = self._make_remote(tmp_path, "studio")
        archive = self._make_remote(tmp_path, "archive")

        a1 = create_test_asset(studio, "Props", "sword")
        a2 = create_test_asset(archive, "Characters", "hero")

        config = NinjaConfig(
            gdrive_root=tmp_path / "unused",
            local_data_dir=tmp_path / "local",
            remotes=[Repo("studio", studio), Repo("archive", archive)],
            _ensure_dirs=False,
        )
        cache = CacheDB()
        scanner = AssetScanner(config, cache)
        changed = scanner.full_scan()

        assert set(changed) == {a1.uuid, a2.uuid}
        assert cache.get_asset(a1.uuid).source_repo == "studio"
        assert cache.get_asset(a2.uuid).source_repo == "archive"
        assert cache.get_repos_with_counts() == {"studio": 1, "archive": 1}

    def test_stale_eviction_across_remotes(self, tmp_path):
        """An asset removed from its remote is evicted on the next scan."""
        from ninja_assets.config import Repo

        studio = self._make_remote(tmp_path, "studio")
        archive = self._make_remote(tmp_path, "archive")
        a1 = create_test_asset(studio, "Props", "sword")
        a2 = create_test_asset(archive, "Characters", "hero")

        config = NinjaConfig(
            gdrive_root=tmp_path / "unused",
            local_data_dir=tmp_path / "local",
            remotes=[Repo("studio", studio), Repo("archive", archive)],
            _ensure_dirs=False,
        )
        cache = CacheDB()
        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        # Delete the archive asset's sidecar, rescan.
        sidecar = SidecarManager.get_sidecar_path(
            archive / "assets" / "characters" / "hero", "hero"
        )
        sidecar.unlink()
        changed = scanner.full_scan()

        assert a2.uuid in changed
        assert cache.get_asset(a2.uuid) is None
        assert cache.get_asset(a1.uuid) is not None


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

    def test_spot_check_ignores_moved_folder(self, fake_gdrive):
        """A moved asset is not evicted by spot_check; full_scan relocates it."""
        import shutil

        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "torch")
        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        old_folder = config.gdrive_root / "assets" / "props" / "torch"
        new_folder = config.gdrive_root / "assets" / "props" / "relit" / "torch"
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_folder), str(new_folder))

        # The cheap sampler leaves the live asset alone...
        changed = scanner.spot_check(count=100)
        assert asset.uuid not in changed
        assert cache.get_asset(asset.uuid) is not None

        # ...and the authoritative scan picks up the new location.
        scanner.full_scan()
        assert cache.get_asset(asset.uuid).path == str(new_folder)

    def test_spot_check_defers_deletion_to_full_scan(self, fake_gdrive):
        """spot_check is not the deletion authority; full_scan evicts.

        A sidecar missing at the cached path is ambiguous (moved vs deleted),
        so spot_check leaves the cache alone. The authoritative full_scan,
        which walks the whole tree, performs the eviction.
        """
        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "staff")

        scanner = AssetScanner(config, cache)
        scanner.full_scan()

        # Remove sidecar from disk
        asset_folder = config.gdrive_root / "assets" / "props" / "staff"
        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, "staff")
        sidecar_path.unlink()

        # spot_check must not evict on a missing path...
        changed = scanner.spot_check(count=100)
        assert asset.uuid not in changed
        assert cache.get_asset(asset.uuid) is not None

        # ...full_scan is where the eviction actually happens.
        changed = scanner.full_scan()
        assert asset.uuid in changed
        assert cache.get_asset(asset.uuid) is None
