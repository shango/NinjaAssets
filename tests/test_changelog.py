"""Tests for ChangelogManager."""

from datetime import datetime

import pytest

from ninja_assets.core.changelog import ChangelogManager
from ninja_assets.core.models import ChangelogEvent, EventType


def _make_event(user="alice", path="assets/props/barrel", version=1):
    return ChangelogEvent(
        timestamp=datetime(2025, 6, 15, 12, 0, 0),
        event_type=EventType.ASSET_CREATED,
        uuid="aaaa-bbbb",
        path=path,
        user=user,
        version=version,
    )


class TestAppendAndReadRoundTrip:
    def test_append_read(self, tmp_path):
        log_path = tmp_path / "changelog.jsonl"
        mgr = ChangelogManager(log_path)

        event = _make_event()
        mgr.append(event)

        events, offset = mgr.read_from(0)
        assert len(events) == 1
        assert events[0].user == "alice"
        assert events[0].event_type == EventType.ASSET_CREATED
        assert offset > 0


class TestReadFromWithOffset:
    def test_resumes_correctly(self, tmp_path):
        log_path = tmp_path / "changelog.jsonl"
        mgr = ChangelogManager(log_path)

        mgr.append(_make_event(user="alice"))
        _, offset1 = mgr.read_from(0)

        mgr.append(_make_event(user="bob"))
        events, offset2 = mgr.read_from(offset1)

        assert len(events) == 1
        assert events[0].user == "bob"
        assert offset2 > offset1


class TestCorruptedLine:
    def test_corrupted_line_skipped(self, tmp_path):
        log_path = tmp_path / "changelog.jsonl"
        mgr = ChangelogManager(log_path)

        mgr.append(_make_event(user="alice"))
        # Write a corrupted line directly
        with open(log_path, "a") as f:
            f.write("THIS IS NOT JSON\n")
        mgr.append(_make_event(user="carol"))

        events = mgr.read_all()
        assert len(events) == 2
        assert events[0].user == "alice"
        assert events[1].user == "carol"


class TestReadAll:
    def test_returns_all_events(self, tmp_path):
        log_path = tmp_path / "changelog.jsonl"
        mgr = ChangelogManager(log_path)

        for name in ["alice", "bob", "carol"]:
            mgr.append(_make_event(user=name))

        events = mgr.read_all()
        assert len(events) == 3
        assert [e.user for e in events] == ["alice", "bob", "carol"]


class TestAppendCreatesFile:
    def test_creates_file_if_missing(self, tmp_path):
        log_path = tmp_path / "new_changelog.jsonl"
        assert not log_path.exists()

        mgr = ChangelogManager(log_path)
        mgr.append(_make_event())

        assert log_path.exists()
        events = mgr.read_all()
        assert len(events) == 1
