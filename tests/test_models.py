"""Tests for core data models round-trip serialization."""

import json
import uuid
from datetime import datetime

from ninja_assets.core.models import (
    Asset,
    AssetStatus,
    Bounds,
    ChangelogEvent,
    EventType,
    SceneMeta,
    Version,
)


class TestVersion:
    def test_round_trip(self):
        v = Version(
            version=1,
            file="hero_v001.obj",
            created_by="alice",
            created_at=datetime(2025, 1, 15, 9, 30, 0),
            comment="Initial blockout",
            poly_count=12000,
        )
        d = v.to_dict()
        v2 = Version.from_dict(d)
        assert v2.version == v.version
        assert v2.file == v.file
        assert v2.created_by == v.created_by
        assert v2.created_at == v.created_at
        assert v2.comment == v.comment
        assert v2.poly_count == v.poly_count

    def test_round_trip_no_poly_count(self):
        v = Version(
            version=2,
            file="scene_v002.ma",
            created_by="bob",
            created_at=datetime(2025, 3, 1, 12, 0, 0),
            comment="Rigging pass",
        )
        d = v.to_dict()
        assert "poly_count" not in d
        v2 = Version.from_dict(d)
        assert v2.poly_count is None

    def test_iso_timestamp_has_z_suffix(self):
        v = Version(
            version=1,
            file="f.obj",
            created_by="x",
            created_at=datetime(2025, 6, 1, 0, 0, 0),
        )
        d = v.to_dict()
        assert d["created_at"].endswith("Z")


class TestAsset:
    def _make_asset(self, with_bounds=True, with_thumbnail=True):
        versions = [
            Version(
                version=1,
                file="hero_v001.obj",
                created_by="alice",
                created_at=datetime(2025, 1, 15, 9, 30, 0),
                comment="Initial",
                poly_count=12000,
            ),
            Version(
                version=2,
                file="hero_v002.obj",
                created_by="bob",
                created_at=datetime(2025, 1, 16, 14, 0, 0),
                comment="Detail pass",
                poly_count=35000,
            ),
        ]
        return Asset(
            uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            name="hero_robot",
            path="/assets/characters/hero_robot",
            current_version=2,
            current_file="hero_v002.obj",
            category="Characters",
            status=AssetStatus.REVIEW,
            modified_at=datetime(2025, 1, 16, 14, 0, 0),
            versions=versions,
            tags=["robot", "hero"],
            thumbnail="hero_robot.thumb.jpg" if with_thumbnail else None,
            bounds=Bounds(x=2.5, y=4.0, z=1.5) if with_bounds else None,
        )

    def test_round_trip_with_bounds_and_thumbnail(self):
        asset = self._make_asset(with_bounds=True, with_thumbnail=True)
        d = asset.to_dict()
        a2 = Asset.from_dict(d, asset.path)
        assert a2.uuid == asset.uuid
        assert a2.name == asset.name
        assert a2.current_version == asset.current_version
        assert a2.current_file == asset.current_file
        assert a2.category == asset.category
        assert a2.status == asset.status
        assert a2.modified_at == asset.modified_at
        assert len(a2.versions) == 2
        assert a2.tags == ["robot", "hero"]
        assert a2.thumbnail == "hero_robot.thumb.jpg"
        assert a2.bounds is not None
        assert a2.bounds.x == 2.5
        assert a2.bounds.y == 4.0
        assert a2.bounds.z == 1.5

    def test_round_trip_without_bounds_and_thumbnail(self):
        asset = self._make_asset(with_bounds=False, with_thumbnail=False)
        d = asset.to_dict()
        assert "bounds" not in d
        a2 = Asset.from_dict(d, asset.path)
        assert a2.bounds is None
        assert a2.thumbnail is None

    def test_new_creates_valid_uuid(self):
        asset = Asset.new(name="test_asset", category="Props", path="/assets/props/test_asset")
        # Should not raise
        parsed = uuid.UUID(asset.uuid)
        assert parsed.version == 4
        assert asset.current_version == 0
        assert asset.current_file == ""
        assert asset.status == AssetStatus.WIP
        assert asset.category == "Props"

    def test_get_version(self):
        asset = self._make_asset()
        v1 = asset.get_version(1)
        assert v1 is not None
        assert v1.file == "hero_v001.obj"
        assert asset.get_version(999) is None

    def test_get_latest_version(self):
        asset = self._make_asset()
        latest = asset.get_latest_version()
        assert latest is not None
        assert latest.version == 2

    def test_get_latest_version_empty(self):
        asset = Asset.new(name="empty", category="Other", path="/x")
        assert asset.get_latest_version() is None

    def test_modified_at_has_z_suffix(self):
        asset = self._make_asset()
        d = asset.to_dict()
        assert d["modified_at"].endswith("Z")


class TestBounds:
    def test_round_trip(self):
        b = Bounds(x=1.0, y=2.0, z=3.0)
        d = b.to_dict()
        b2 = Bounds.from_dict(d)
        assert b2.x == b.x
        assert b2.y == b.y
        assert b2.z == b.z


class TestSceneMeta:
    def test_round_trip(self):
        versions = [
            Version(
                version=1,
                file="scene_v001.ma",
                created_by="alice",
                created_at=datetime(2025, 1, 14, 9, 0, 0),
                comment="Initial setup",
            ),
            Version(
                version=3,
                file="scene_v003.ma",
                created_by="bob",
                created_at=datetime(2025, 1, 15, 16, 0, 0),
                comment="Added skeleton",
            ),
        ]
        sm = SceneMeta(
            scene_name="hero_rigging",
            current_version=3,
            versions=versions,
        )
        d = sm.to_dict()
        sm2 = SceneMeta.from_dict(d)
        assert sm2.scene_name == sm.scene_name
        assert sm2.current_version == sm.current_version
        assert len(sm2.versions) == 2
        assert sm2.versions[1].file == "scene_v003.ma"

    def test_get_next_version(self):
        versions = [
            Version(
                version=1,
                file="s_v001.ma",
                created_by="x",
                created_at=datetime(2025, 1, 1),
            ),
            Version(
                version=5,
                file="s_v005.ma",
                created_by="x",
                created_at=datetime(2025, 1, 2),
            ),
        ]
        sm = SceneMeta(scene_name="test", current_version=5, versions=versions)
        assert sm.get_next_version() == 6

    def test_get_next_version_empty(self):
        sm = SceneMeta(scene_name="new_scene", current_version=0, versions=[])
        assert sm.get_next_version() == 1


class TestChangelogEvent:
    def test_round_trip(self):
        event = ChangelogEvent(
            timestamp=datetime(2025, 1, 17, 11, 45, 0),
            event_type=EventType.ASSET_CREATED,
            uuid="a1b2c3d4",
            path="/assets/characters/hero_robot",
            user="sarah",
            version=1,
        )
        line = event.to_json_line()
        parsed = json.loads(line)
        assert parsed["ts"] == "2025-01-17T11:45:00Z"
        assert parsed["type"] == "asset_created"
        assert parsed["v"] == 1

        event2 = ChangelogEvent.from_json_line(line)
        assert event2.timestamp == event.timestamp
        assert event2.event_type == event.event_type
        assert event2.uuid == event.uuid
        assert event2.path == event.path
        assert event2.user == event.user
        assert event2.version == event.version

    def test_round_trip_no_version(self):
        event = ChangelogEvent(
            timestamp=datetime(2025, 2, 1, 10, 0, 0),
            event_type=EventType.ASSET_DELETED,
            uuid="xyz789",
            path="/assets/props/old_chair",
            user="admin",
        )
        line = event.to_json_line()
        parsed = json.loads(line)
        assert "v" not in parsed

        event2 = ChangelogEvent.from_json_line(line)
        assert event2.version is None

    def test_extra_fields_preserved(self):
        event = ChangelogEvent(
            timestamp=datetime(2025, 3, 1),
            event_type=EventType.METADATA_CHANGED,
            uuid="abc",
            path="/assets/props/table",
            user="alice",
            extra={"field": "status", "value": "approved"},
        )
        line = event.to_json_line()
        parsed = json.loads(line)
        assert parsed["field"] == "status"
        assert parsed["value"] == "approved"
