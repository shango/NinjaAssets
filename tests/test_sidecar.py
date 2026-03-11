"""Tests for SidecarManager."""

import json
import time

import pytest

from ninja_assets.core.exceptions import ConflictError, SidecarError
from ninja_assets.core.sidecar import SidecarManager


class TestSidecarWriteReadRoundTrip:
    def test_round_trip(self, fake_gdrive):
        folder = fake_gdrive.assets_root / "props"
        asset = SidecarManager.create_minimal(
            folder, "barrel", "barrel_v1.fbx", "Props", "alice"
        )
        sidecar_path = SidecarManager.get_sidecar_path(folder, "barrel")

        loaded, mtime = SidecarManager.read(sidecar_path)

        assert loaded.name == "barrel"
        assert loaded.current_file == "barrel_v1.fbx"
        assert loaded.category == "Props"
        assert loaded.current_version == 1
        assert loaded.uuid == asset.uuid
        assert mtime > 0


class TestConflictDetection:
    def test_write_with_wrong_mtime_raises_conflict(self, fake_gdrive):
        folder = fake_gdrive.assets_root / "props"
        asset = SidecarManager.create_minimal(
            folder, "crate", "crate_v1.fbx", "Props", "bob"
        )
        sidecar_path = SidecarManager.get_sidecar_path(folder, "crate")

        _, mtime = SidecarManager.read(sidecar_path)
        # Perform a second write so mtime changes
        time.sleep(0.05)
        SidecarManager.write(sidecar_path, asset)

        with pytest.raises(ConflictError):
            SidecarManager.write(sidecar_path, asset, expected_mtime=mtime)


class TestCreateMinimal:
    def test_creates_valid_sidecar(self, fake_gdrive):
        folder = fake_gdrive.assets_root / "characters"
        asset = SidecarManager.create_minimal(
            folder, "hero", "hero_v1.fbx", "Characters", "carol"
        )
        assert asset.name == "hero"
        assert asset.current_file == "hero_v1.fbx"
        assert asset.category == "Characters"
        assert asset.uuid  # non-empty

        # File should exist on disk
        assert SidecarManager.exists(folder, "hero")


class TestReadErrors:
    def test_read_nonexistent_raises_sidecar_error(self, fake_gdrive):
        folder = fake_gdrive.assets_root / "props"
        sidecar_path = SidecarManager.get_sidecar_path(folder, "nope")
        with pytest.raises(SidecarError):
            SidecarManager.read(sidecar_path)

    def test_read_corrupted_json_raises_sidecar_error(self, fake_gdrive):
        folder = fake_gdrive.assets_root / "props"
        sidecar_path = SidecarManager.get_sidecar_path(folder, "broken")
        sidecar_path.write_text("{not valid json!!")
        with pytest.raises(SidecarError):
            SidecarManager.read(sidecar_path)
