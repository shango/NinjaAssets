"""Tests for hot-reload staleness detection (no Maya required)."""
from ninja_assets.maya_integration.reload import (
    _read_stamp, _is_stale, STAMP_FILENAME,
)


class TestReadStamp:
    def test_missing_returns_none(self, tmp_path):
        assert _read_stamp(str(tmp_path)) is None

    def test_reads_value(self, tmp_path):
        (tmp_path / STAMP_FILENAME).write_text("123-abc\n")
        assert _read_stamp(str(tmp_path)) == "123-abc"

    def test_empty_file_returns_none(self, tmp_path):
        (tmp_path / STAMP_FILENAME).write_text("   \n")
        assert _read_stamp(str(tmp_path)) is None


class TestIsStale:
    def test_unknown_on_disk_is_not_stale(self):
        # Can't tell what's on disk -> never force a reload.
        assert _is_stale(None, "running") is False

    def test_same_build_is_not_stale(self):
        assert _is_stale("build-1", "build-1") is False

    def test_different_build_is_stale(self):
        assert _is_stale("build-2", "build-1") is True

    def test_stale_when_nothing_running(self):
        assert _is_stale("build-2", None) is True
