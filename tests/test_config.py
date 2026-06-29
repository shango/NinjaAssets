"""Tests for NinjaConfig."""

from pathlib import Path

from ninja_assets.config import (
    NinjaConfig, Repo, find_remote_by_path, find_remote_by_name,
    _default_gdrive_root,
)
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
        NinjaConfig(
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
        assert config.thumbnail_size == (512, 512)
        assert config.thumbnail_format == "jpg"
        assert config.thumbnail_quality == 85
        assert config.grid_thumbnail_size == 128
        assert config.preview_thumbnail_size == 400
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


class TestRepos:
    def test_remote_repos_fallback_to_gdrive(self, tmp_path):
        """With no remotes configured, gdrive_root is the single default remote."""
        config = NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=tmp_path / "local",
            _ensure_dirs=False,
        )
        remotes = config.remote_repos()
        assert len(remotes) == 1
        assert remotes[0].name == "GDrive"
        assert remotes[0].path == tmp_path / "gdrive"

    def test_remote_repos_uses_configured_enabled_only(self, tmp_path):
        config = NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=tmp_path / "local",
            remotes=[
                Repo("studio", tmp_path / "studio"),
                Repo("archive", tmp_path / "archive", enabled=False),
            ],
            _ensure_dirs=False,
        )
        remotes = config.remote_repos()
        assert [r.name for r in remotes] == ["studio"]

    def test_assets_root_for(self, tmp_path):
        config = NinjaConfig(_ensure_dirs=False)
        repo = Repo("studio", tmp_path / "studio")
        assert config.assets_root_for(repo) == tmp_path / "studio" / "assets"

    def test_save_load_round_trip_repos(self, tmp_path):
        local = tmp_path / "local"
        local.mkdir()
        config = NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=local,
            remotes=[
                Repo("studio", tmp_path / "studio"),
                Repo("archive", tmp_path / "archive", enabled=False),
            ],
            local_repo=tmp_path / "mylocal",
            _ensure_dirs=False,
        )
        config.save()

        loaded = NinjaConfig.load(local_data_dir=local, _ensure_dirs=False)
        assert loaded.local_repo == tmp_path / "mylocal"
        assert len(loaded.remotes) == 2
        assert loaded.remotes[0].name == "studio"
        assert loaded.remotes[0].path == tmp_path / "studio"
        assert loaded.remotes[1].enabled is False

    def test_local_repo_created_when_ensure_dirs(self, tmp_path):
        local_repo = tmp_path / "pulled"
        NinjaConfig(
            gdrive_root=tmp_path / "gdrive",
            local_data_dir=tmp_path / "local",
            local_repo=local_repo,
            _ensure_dirs=True,
        )
        assert local_repo.exists()


class TestDuplicateRemoteGuards:
    def test_find_remote_by_path_matches_normalized(self, tmp_path):
        remotes = [Repo("studio", tmp_path / "studio")]
        # Trailing slash / redundant separators should still match.
        assert find_remote_by_path(remotes, str(tmp_path / "studio") + "/") is not None
        assert find_remote_by_path(remotes, tmp_path / "studio") is not None

    def test_find_remote_by_path_no_false_positive(self, tmp_path):
        remotes = [Repo("studio", tmp_path / "studio")]
        assert find_remote_by_path(remotes, tmp_path / "archive") is None
        # A parent/sibling path must not be treated as a duplicate.
        assert find_remote_by_path(remotes, tmp_path / "studio" / "..") is None

    def test_find_remote_by_name_case_insensitive(self):
        remotes = [Repo("Studio", "/a"), Repo("Archive", "/b")]
        assert find_remote_by_name(remotes, "studio").path == Path("/a")
        assert find_remote_by_name(remotes, "  ARCHIVE ").path == Path("/b")
        assert find_remote_by_name(remotes, "vault") is None


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
