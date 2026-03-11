"""Tests for SQLite cache layer."""

from datetime import datetime

from ninja_assets.core.cache import CacheDB
from ninja_assets.core.models import Asset, AssetStatus, Bounds, Version


def make_asset(
    uuid="test-uuid-001",
    name="HeroSword",
    path="/assets/props/hero_sword",
    category="props",
    status=AssetStatus.WIP,
    tags=None,
    current_version=1,
    current_file="hero_sword_v001.obj",
    thumbnail=None,
    bounds=None,
    versions=None,
    modified_at=None,
):
    """Helper to build test Asset objects."""
    if tags is None:
        tags = ["weapon", "metal"]
    if modified_at is None:
        modified_at = datetime(2025, 6, 15, 10, 30, 0)
    if versions is None:
        versions = [
            Version(
                version=1,
                file="hero_sword_v001.obj",
                created_by="alice",
                created_at=datetime(2025, 6, 15, 10, 30, 0),
                comment="Initial",
                poly_count=5000,
            )
        ]
    return Asset(
        uuid=uuid,
        name=name,
        path=path,
        current_version=current_version,
        current_file=current_file,
        category=category,
        status=status,
        modified_at=modified_at,
        versions=versions,
        tags=tags,
        thumbnail=thumbnail,
        bounds=bounds,
    )


class TestCacheDB:
    def _make_db(self):
        return CacheDB()

    def test_upsert_and_get_asset_round_trip(self):
        db = self._make_db()
        asset = make_asset(
            bounds=Bounds(x=1.0, y=2.0, z=3.0),
            thumbnail="thumbs/hero.jpg",
        )
        db.upsert_asset(asset, mtime=1234567890.0)

        result = db.get_asset("test-uuid-001")
        assert result is not None
        assert result.uuid == asset.uuid
        assert result.name == asset.name
        assert result.path == asset.path
        assert result.current_version == asset.current_version
        assert result.current_file == asset.current_file
        assert result.category == asset.category
        assert result.status == asset.status
        assert result.tags == asset.tags
        assert result.modified_at == asset.modified_at
        assert result.thumbnail == asset.thumbnail
        assert result.bounds is not None
        assert result.bounds.x == 1.0
        assert result.bounds.y == 2.0
        assert result.bounds.z == 3.0

    def test_get_asset_not_found(self):
        db = self._make_db()
        assert db.get_asset("nonexistent") is None

    def test_search_with_text_query(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1", name="HeroSword"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a2", name="VillainShield"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a3", name="HeroHelmet"), mtime=1.0)

        results = db.search_assets(query="Hero")
        assert len(results) == 2
        names = {a.name for a in results}
        assert names == {"HeroSword", "HeroHelmet"}

    def test_search_with_category_filter(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1", category="props"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a2", category="characters"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a3", category="props"), mtime=1.0)

        results = db.search_assets(category="props")
        assert len(results) == 2
        assert all(a.category == "props" for a in results)

    def test_search_with_status_filter(self):
        db = self._make_db()
        db.upsert_asset(
            make_asset(uuid="a1", status=AssetStatus.WIP), mtime=1.0
        )
        db.upsert_asset(
            make_asset(uuid="a2", status=AssetStatus.APPROVED), mtime=1.0
        )
        db.upsert_asset(
            make_asset(uuid="a3", status=AssetStatus.APPROVED), mtime=1.0
        )

        results = db.search_assets(status="approved")
        assert len(results) == 2
        assert all(a.status == AssetStatus.APPROVED for a in results)

    def test_search_with_tags_filter(self):
        db = self._make_db()
        db.upsert_asset(
            make_asset(uuid="a1", tags=["weapon", "metal"]), mtime=1.0
        )
        db.upsert_asset(
            make_asset(uuid="a2", tags=["armor", "metal"]), mtime=1.0
        )
        db.upsert_asset(
            make_asset(uuid="a3", tags=["weapon", "wood"]), mtime=1.0
        )

        results = db.search_assets(tags=["weapon"])
        assert len(results) == 2
        uuids = {a.uuid for a in results}
        assert uuids == {"a1", "a3"}

        results = db.search_assets(tags=["weapon", "metal"])
        assert len(results) == 1
        assert results[0].uuid == "a1"

    def test_get_categories_with_counts(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1", category="props"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a2", category="props"), mtime=1.0)
        db.upsert_asset(
            make_asset(uuid="a3", category="characters"), mtime=1.0
        )

        counts = db.get_categories_with_counts()
        assert counts == {"props": 2, "characters": 1}

    def test_get_all_uuids(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a2"), mtime=1.0)
        db.upsert_asset(make_asset(uuid="a3"), mtime=1.0)

        uuids = db.get_all_uuids()
        assert set(uuids) == {"a1", "a2", "a3"}

    def test_get_asset_mtime(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1"), mtime=1234567890.5)

        assert db.get_asset_mtime("a1") == 1234567890.5
        assert db.get_asset_mtime("nonexistent") is None

    def test_delete_asset(self):
        db = self._make_db()
        db.upsert_asset(make_asset(uuid="a1"), mtime=1.0)
        assert db.get_asset("a1") is not None

        db.delete_asset("a1")
        assert db.get_asset("a1") is None

    def test_get_set_sync_state(self):
        db = self._make_db()
        assert db.get_sync_state("last_scan") is None

        db.set_sync_state("last_scan", "2025-06-15T10:30:00Z")
        assert db.get_sync_state("last_scan") == "2025-06-15T10:30:00Z"

        # Update existing key
        db.set_sync_state("last_scan", "2025-06-16T12:00:00Z")
        assert db.get_sync_state("last_scan") == "2025-06-16T12:00:00Z"

    def test_upsert_updates_existing_asset(self):
        db = self._make_db()
        asset = make_asset(uuid="a1", name="OldName", status=AssetStatus.WIP)
        db.upsert_asset(asset, mtime=1.0)

        updated = make_asset(
            uuid="a1", name="NewName", status=AssetStatus.APPROVED
        )
        db.upsert_asset(updated, mtime=2.0)

        result = db.get_asset("a1")
        assert result is not None
        assert result.name == "NewName"
        assert result.status == AssetStatus.APPROVED
        assert db.get_asset_mtime("a1") == 2.0

        # Should still be only one asset
        assert len(db.get_all_uuids()) == 1
