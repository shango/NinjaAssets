"""Shared test fixtures for NinjaAssets."""

import pytest
from pathlib import Path

from ninja_assets.config import NinjaConfig
from ninja_assets.constants import CATEGORIES


@pytest.fixture
def fake_gdrive(tmp_path):
    """Create a canonical GDrive folder structure and return a NinjaConfig pointing at it."""
    gdrive = tmp_path / "gdrive"
    assets = gdrive / "assets"
    for cat in CATEGORIES:
        (assets / cat.lower()).mkdir(parents=True)
    (gdrive / "scenes").mkdir()
    pipeline = gdrive / ".ninjaassets"
    pipeline.mkdir()
    (pipeline / "changelog.jsonl").touch()
    (pipeline / "schema_version.txt").write_text("1")

    config = NinjaConfig(
        gdrive_root=gdrive,
        local_data_dir=tmp_path / "local",
        _ensure_dirs=False,
    )
    return config


@pytest.fixture
def tmp_local_dir(tmp_path):
    """Return a temporary local data directory."""
    local = tmp_path / "ninja_local"
    local.mkdir()
    return local
