"""Tests for pull-to-local (maya-free; pull_asset imports no maya modules)."""

from datetime import datetime

import pytest

from ninja_assets.core.models import Asset, AssetStatus, Version
from ninja_assets.core.sidecar import SidecarManager
from ninja_assets.maya_integration.commands import pull_asset


def _make_remote_asset(remote_root, name="sword", category="Props"):
    """Create a remote asset folder with file + sidecar + thumbnail."""
    folder = remote_root / "assets" / category.lower() / name
    folder.mkdir(parents=True, exist_ok=True)

    asset_file = f"{name}_v001.obj"
    (folder / asset_file).write_text("# OBJ data")
    thumb = f"{name}.thumb.jpg"
    (folder / thumb).write_bytes(b"\xff\xd8\xff")  # tiny fake jpeg

    asset = Asset(
        uuid="uuid-pull-1",
        name=name,
        path=str(folder),
        current_version=1,
        current_file=asset_file,
        category=category,
        status=AssetStatus.WIP,
        modified_at=datetime(2025, 1, 15, 9, 30),
        versions=[
            Version(1, asset_file, "tester", datetime(2025, 1, 15, 9, 30)),
        ],
        thumbnail=thumb,
    )
    sidecar = SidecarManager.get_sidecar_path(folder, name)
    SidecarManager.write(sidecar, asset)
    return asset


class TestPullAsset:
    def test_copies_file_sidecar_and_thumbnail(self, tmp_path):
        asset = _make_remote_asset(tmp_path / "remote")
        local_root = tmp_path / "local"

        result = pull_asset(asset, None, local_root)

        dest_dir = local_root / asset.category / asset.name
        assert result == dest_dir / "sword_v001.obj"
        assert (dest_dir / "sword_v001.obj").exists()
        assert (dest_dir / "sword.meta.json").exists()
        assert (dest_dir / "sword.thumb.jpg").exists()

    def test_returns_path_and_creates_category_tree(self, tmp_path):
        asset = _make_remote_asset(tmp_path / "remote", category="Characters")
        result = pull_asset(asset, None, tmp_path / "local")
        assert result.parent == tmp_path / "local" / "Characters" / "sword"

    def test_idempotent_second_pull(self, tmp_path):
        asset = _make_remote_asset(tmp_path / "remote")
        local_root = tmp_path / "local"

        first = pull_asset(asset, None, local_root)
        # Mark the local copy so we can detect an unwanted overwrite.
        first.write_text("# locally edited")
        second = pull_asset(asset, None, local_root)

        assert second == first
        # Source mtime <= dest mtime, so no re-copy happened.
        assert first.read_text() == "# locally edited"

    def test_missing_remote_file_raises(self, tmp_path):
        asset = _make_remote_asset(tmp_path / "remote")
        asset.current_file = "gone.obj"
        asset.versions = []
        with pytest.raises(FileNotFoundError):
            pull_asset(asset, None, tmp_path / "local")
