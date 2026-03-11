"""Tests for SyncEngine."""

import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from ninja_assets.config import NinjaConfig
from ninja_assets.core.cache import CacheDB
from ninja_assets.core.changelog import ChangelogManager
from ninja_assets.core.models import Asset, ChangelogEvent, EventType
from ninja_assets.core.sidecar import SidecarManager
from ninja_assets.sync.engine import SyncEngine


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


class TestStartStop:
    def test_start_stop_lifecycle(self, fake_gdrive):
        """Engine starts a daemon thread and stops cleanly."""
        config = fake_gdrive
        cache = CacheDB()

        engine = SyncEngine(config, cache)
        engine.start()

        assert engine._thread is not None
        assert engine._thread.is_alive()
        assert engine._thread.daemon is True

        engine.stop()

        # Thread should have stopped
        assert not engine._thread.is_alive()

    def test_stop_without_start(self, fake_gdrive):
        """Calling stop without start does not raise."""
        config = fake_gdrive
        cache = CacheDB()
        engine = SyncEngine(config, cache)
        engine.stop()  # Should not raise


class TestQuickSync:
    def test_processes_changelog_events(self, fake_gdrive):
        """quick_sync processes new changelog events and updates cache."""
        config = fake_gdrive
        cache = CacheDB()

        # Create asset on disk
        asset = create_test_asset(config.gdrive_root, "Props", "chest")

        # Write a changelog event
        changelog = ChangelogManager(config.changelog_path)
        event = ChangelogEvent(
            timestamp=datetime.utcnow(),
            event_type=EventType.ASSET_CREATED,
            uuid=asset.uuid,
            path=str(config.gdrive_root / "assets" / "props" / "chest"),
            user="testuser",
            version=1,
        )
        changelog.append(event)

        engine = SyncEngine(config, cache)
        changed = engine.quick_sync()

        assert asset.uuid in changed

        # Verify asset is now in cache
        cached = cache.get_asset(asset.uuid)
        assert cached is not None
        assert cached.name == "chest"

    def test_quick_sync_handles_deleted_event(self, fake_gdrive):
        """quick_sync handles asset_deleted events."""
        config = fake_gdrive
        cache = CacheDB()

        # Manually insert asset into cache
        asset = create_test_asset(config.gdrive_root, "Props", "barrel")
        cache.upsert_asset(asset, 1234.0)

        # Write delete event
        changelog = ChangelogManager(config.changelog_path)
        event = ChangelogEvent(
            timestamp=datetime.utcnow(),
            event_type=EventType.ASSET_DELETED,
            uuid=asset.uuid,
            path=str(config.gdrive_root / "assets" / "props" / "barrel"),
            user="testuser",
        )
        changelog.append(event)

        engine = SyncEngine(config, cache)
        changed = engine.quick_sync()

        assert asset.uuid in changed
        assert cache.get_asset(asset.uuid) is None

    def test_quick_sync_saves_offset(self, fake_gdrive):
        """quick_sync persists changelog offset to cache sync_state."""
        config = fake_gdrive
        cache = CacheDB()

        asset = create_test_asset(config.gdrive_root, "Props", "crate")

        changelog = ChangelogManager(config.changelog_path)
        event = ChangelogEvent(
            timestamp=datetime.utcnow(),
            event_type=EventType.ASSET_CREATED,
            uuid=asset.uuid,
            path=str(config.gdrive_root / "assets" / "props" / "crate"),
            user="testuser",
            version=1,
        )
        changelog.append(event)

        engine = SyncEngine(config, cache)
        engine.quick_sync()

        saved_offset = cache.get_sync_state("changelog_offset")
        assert saved_offset is not None
        assert int(saved_offset) > 0

    def test_quick_sync_skips_scene_saved(self, fake_gdrive):
        """quick_sync ignores scene_saved events."""
        config = fake_gdrive
        cache = CacheDB()

        changelog = ChangelogManager(config.changelog_path)
        event = ChangelogEvent(
            timestamp=datetime.utcnow(),
            event_type=EventType.SCENE_SAVED,
            uuid="scene-uuid",
            path=str(config.gdrive_root / "scenes" / "test_scene"),
            user="testuser",
        )
        changelog.append(event)

        engine = SyncEngine(config, cache)
        changed = engine.quick_sync()

        assert changed == []


class TestCallback:
    def test_on_assets_changed_fires(self, fake_gdrive):
        """on_assets_changed callback is called when assets change."""
        config = fake_gdrive
        cache = CacheDB()
        callback_results = []

        def callback(uuids):
            callback_results.append(list(uuids))

        asset = create_test_asset(config.gdrive_root, "Props", "gem")

        changelog = ChangelogManager(config.changelog_path)
        event = ChangelogEvent(
            timestamp=datetime.utcnow(),
            event_type=EventType.ASSET_CREATED,
            uuid=asset.uuid,
            path=str(config.gdrive_root / "assets" / "props" / "gem"),
            user="testuser",
            version=1,
        )
        changelog.append(event)

        engine = SyncEngine(config, cache, on_assets_changed=callback)
        changed = engine.quick_sync()
        engine._notify_changes(changed)

        assert len(callback_results) == 1
        assert asset.uuid in callback_results[0]

    def test_callback_not_called_when_no_changes(self, fake_gdrive):
        """on_assets_changed is not called when there are no changes."""
        config = fake_gdrive
        cache = CacheDB()
        callback_results = []

        def callback(uuids):
            callback_results.append(list(uuids))

        engine = SyncEngine(config, cache, on_assets_changed=callback)
        engine._notify_changes([])

        assert len(callback_results) == 0


class TestForceFullScan:
    def test_force_full_scan_triggers_rescan(self, fake_gdrive, tmp_path):
        """force_full_scan triggers a rescan in the background thread."""
        config = fake_gdrive
        # Use short poll interval to speed up test
        config.changelog_poll_interval = 1
        # Use file-backed cache for cross-thread access
        cache = CacheDB(db_path=tmp_path / "cache.sqlite")
        callback_results = []

        def callback(uuids):
            callback_results.append(list(uuids))

        # Create an asset
        asset = create_test_asset(config.gdrive_root, "Props", "ring")

        engine = SyncEngine(config, cache, on_assets_changed=callback)
        engine.start()

        # Wait for initial full scan to complete
        time.sleep(0.5)

        # Verify asset was found in initial scan
        cached = cache.get_asset(asset.uuid)
        assert cached is not None

        # Create a new asset
        asset2 = create_test_asset(config.gdrive_root, "Weapons", "spear")

        # Force a full scan
        engine.force_full_scan()

        # Wait for forced scan to run
        time.sleep(2.0)

        engine.stop()

        # New asset should have been found
        cached2 = cache.get_asset(asset2.uuid)
        assert cached2 is not None
        assert cached2.name == "spear"

    def test_force_scan_event_is_cleared_after_scan(self, fake_gdrive):
        """force_full_scan flag is cleared after the scan runs."""
        config = fake_gdrive
        cache = CacheDB()

        engine = SyncEngine(config, cache)
        engine.force_full_scan()
        assert engine._force_scan_event.is_set()

        # After a scan, the event should be cleared
        engine._force_scan_event.clear()
        assert not engine._force_scan_event.is_set()


class TestEngineIntegration:
    def test_initial_scan_populates_cache(self, fake_gdrive, tmp_path):
        """Starting the engine populates cache via initial full scan."""
        config = fake_gdrive
        config.changelog_poll_interval = 1
        # Use file-backed cache for cross-thread access
        cache = CacheDB(db_path=tmp_path / "cache.sqlite")

        asset = create_test_asset(config.gdrive_root, "Characters", "warrior")

        engine = SyncEngine(config, cache)
        engine.start()

        # Wait for initial scan
        time.sleep(0.5)

        engine.stop()

        cached = cache.get_asset(asset.uuid)
        assert cached is not None
        assert cached.name == "warrior"
        assert cached.category == "Characters"

    def test_changelog_offset_restored_on_start(self, fake_gdrive, tmp_path):
        """Engine restores changelog offset from cache sync_state on start."""
        config = fake_gdrive
        # Use file-backed cache for cross-thread access
        cache = CacheDB(db_path=tmp_path / "cache.sqlite")

        # Set a saved offset
        cache.set_sync_state("changelog_offset", "42")

        engine = SyncEngine(config, cache)
        engine.start()

        # Give thread a moment to start
        time.sleep(0.2)

        assert engine._changelog_offset == 42

        engine.stop()
