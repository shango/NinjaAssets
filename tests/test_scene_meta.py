"""Tests for SceneMetaManager."""

import pytest

from ninja_assets.core.scene_meta import SceneMetaManager


class TestSceneMetaRoundTrip:
    def test_write_and_read(self, fake_gdrive):
        scene_folder = fake_gdrive.scenes_root / "level01"
        scene_folder.mkdir(parents=True, exist_ok=True)

        from ninja_assets.core.models import SceneMeta

        meta = SceneMeta(scene_name="level01", current_version=0, versions=[])
        meta_path = SceneMetaManager.get_meta_path(scene_folder)

        SceneMetaManager.write(meta_path, meta)
        loaded = SceneMetaManager.read(meta_path)

        assert loaded.scene_name == "level01"
        assert loaded.current_version == 0
        assert loaded.versions == []


class TestEnsure:
    def test_ensure_creates_new_when_missing(self, fake_gdrive):
        scene_folder = fake_gdrive.scenes_root / "level02"
        scene_folder.mkdir(parents=True, exist_ok=True)

        meta = SceneMetaManager.ensure(scene_folder, "level02")

        assert meta.scene_name == "level02"
        assert meta.current_version == 0
        # File should now exist
        assert SceneMetaManager.get_meta_path(scene_folder).exists()

    def test_ensure_reads_existing(self, fake_gdrive):
        scene_folder = fake_gdrive.scenes_root / "level03"
        scene_folder.mkdir(parents=True, exist_ok=True)

        from ninja_assets.core.models import SceneMeta, Version
        from datetime import datetime

        existing = SceneMeta(
            scene_name="level03",
            current_version=2,
            versions=[
                Version(
                    version=1,
                    file="level03_v1.blend",
                    created_by="dan",
                    created_at=datetime(2025, 1, 1),
                ),
                Version(
                    version=2,
                    file="level03_v2.blend",
                    created_by="dan",
                    created_at=datetime(2025, 2, 1),
                ),
            ],
        )
        meta_path = SceneMetaManager.get_meta_path(scene_folder)
        SceneMetaManager.write(meta_path, existing)

        loaded = SceneMetaManager.ensure(scene_folder, "level03")

        assert loaded.scene_name == "level03"
        assert loaded.current_version == 2
        assert len(loaded.versions) == 2
