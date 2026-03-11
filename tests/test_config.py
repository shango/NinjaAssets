"""Tests for NinjaConfig."""

import platform
from pathlib import Path

from ninja_assets.config import NinjaConfig, _default_gdrive_root
from ninja_assets.constants import CATEGORIES, STATUSES


class TestNinjaConfigNoEnsureDirs:
    def test_no_dirs_created(self, tmp_path):
        local = tmp_path / "nonexistent_local"
        config = NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=local,
            _ensure_dirs=False,
        )
        assert not local.exists()
        assert config.gdrive_root == tmp_path / "gdrive"

    def test_ensure_dirs_creates_dirs(self, tmp_path):
        local = tmp_path / "local_dir"
        config = NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=local,
            _ensure_dirs=True,
        )
        assert local.exists()
        assert (local / "thumbnails").exists()
        assert (local / "logs").exists()


class TestNinjaConfigDefaults:
    def test_default_values(self):
        config = NinjaConfig(_ensure_dirs=False)
        assert config.gdrive_root == _default_gdrive_root()
        assert config.sync_interval_seconds == 60
        assert config.changelog_poll_interval == 30
        assert config.spot_check_count == 20
        assert config.thumbnail_size == (256, 256)
        assert config.thumbnail_format == "jpg"
        assert config.thumbnail_quality == 85
        assert config.grid_thumbnail_size == 100
        assert config.preview_thumbnail_size == 250
        assert config.categories == list(CATEGORIES)
        assert config.statuses == list(STATUSES)
        assert config.username is None


class TestNinjaConfigProperties:
    def test_properties_return_correct_paths(self, tmp_path):
        gdrive = tmp_path / "gdrive"
        local = tmp_path / "local"
        config = NinjaConfig(
            gdrive_root=gdrive,
            local_data_dir=local,
            _ensure_dirs=False,
        )
        assert config.assets_root == gdrive / "assets"
        assert config.scenes_root == gdrive / "scenes"
        assert config.pipeline_dir == gdrive / ".ninjaassets"
        assert config.changelog_path == gdrive / ".ninjaassets" / "changelog.jsonl"
        assert config.cache_db_path == local / "cache.sqlite"
        assert config.local_thumbnails_dir == local / "thumbnails"
        assert config.logs_dir == local / "logs"


class TestNinjaConfigSaveLoad:
    def test_save_load_round_trip(self, tmp_path):
        local = tmp_path / "local"
        local.mkdir()
        gdrive = tmp_path / "gdrive"

        config = NinjaConfig(
            gdrive_root=gdrive,
            local_data_dir=local,
            username="alice",
            sync_interval_seconds=120,
            changelog_poll_interval=45,
            spot_check_count=10,
            thumbnail_size=(512, 512),
            thumbnail_format="png",
            thumbnail_quality=90,
            grid_thumbnail_size=150,
            preview_thumbnail_size=300,
            _ensure_dirs=False,
        )
        config.save()

        config2 = NinjaConfig.load(local_data_dir=local, _ensure_dirs=False)
        assert config2.gdrive_root == gdrive
        assert config2.username == "alice"
        assert config2.sync_interval_seconds == 120
        assert config2.changelog_poll_interval == 45
        assert config2.spot_check_count == 10
        assert config2.thumbnail_size == (512, 512)
        assert config2.thumbnail_format == "png"
        assert config2.thumbnail_quality == 90
        assert config2.grid_thumbnail_size == 150
        assert config2.preview_thumbnail_size == 300

    def test_load_missing_config_returns_defaults(self, tmp_path):
        local = tmp_path / "empty_local"
        local.mkdir()
        config = NinjaConfig.load(local_data_dir=local, _ensure_dirs=False)
        assert config.sync_interval_seconds == 60
        assert config.username is None


class TestFakeGDriveFixture:
    def test_fixture_structure(self, fake_gdrive):
        """Verify the fake_gdrive fixture creates the expected structure."""
        config = fake_gdrive
        assert (config.gdrive_root / "assets" / "characters").is_dir()
        assert (config.gdrive_root / "assets" / "props").is_dir()
        assert (config.gdrive_root / "assets" / "environments").is_dir()
        assert (config.gdrive_root / "assets" / "vehicles").is_dir()
        assert (config.gdrive_root / "assets" / "weapons").is_dir()
        assert (config.gdrive_root / "assets" / "fx").is_dir()
        assert (config.gdrive_root / "assets" / "other").is_dir()
        assert (config.gdrive_root / "scenes").is_dir()
        assert (config.pipeline_dir / "changelog.jsonl").exists()
        assert (config.pipeline_dir / "schema_version.txt").read_text() == "1"
