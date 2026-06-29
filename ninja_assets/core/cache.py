"""SQLite cache for fast local asset lookups."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ninja_assets.core.exceptions import CacheError
from ninja_assets.core.models import Asset, AssetStatus, Bounds


class CacheDB:
    SCHEMA_VERSION = 2

    def __init__(self, db_path=None):
        """If db_path is None, use ':memory:' for testing."""
        self.db_path = str(db_path) if db_path else ":memory:"
        self._persistent_conn = None
        # For in-memory databases, keep a single persistent connection
        # since each new connection to ':memory:' creates a separate database.
        if self.db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._persistent_conn.row_factory = sqlite3.Row
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """New connection per operation (thread-safe).

        For in-memory databases, reuses a persistent connection.
        For file-backed databases, creates a new connection each time.
        """
        if self._persistent_conn is not None:
            try:
                yield self._persistent_conn
                self._persistent_conn.commit()
            except sqlite3.Error as e:
                self._persistent_conn.rollback()
                raise CacheError(f"SQLite error: {e}") from e
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise CacheError(f"SQLite error: {e}") from e
        finally:
            conn.close()

    def _init_db(self):
        """Create schema from PRD 3.4."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    uuid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    current_file TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'model',
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'wip',
                    tags TEXT,
                    poly_count INTEGER,
                    bounds_x REAL,
                    bounds_y REAL,
                    bounds_z REAL,
                    thumbnail_path TEXT,
                    thumbnail_local TEXT,
                    created_by TEXT,
                    modified_at TEXT NOT NULL,
                    meta_file_mtime REAL,
                    synced_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
                CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
                CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);
                CREATE INDEX IF NOT EXISTS idx_assets_modified ON assets(modified_at);
                """
            )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn):
        """Idempotently bring the assets table up to the current schema.

        The cache is rebuildable, so additive ALTER TABLE migrations are safe:
        any existing file-backed DB created at schema v1 gets the new columns
        without losing data, and rescanning repopulates them.
        """
        existing = {
            row["name"] for row in conn.execute("PRAGMA table_info(assets)").fetchall()
        }
        if "source_repo" not in existing:
            conn.execute("ALTER TABLE assets ADD COLUMN source_repo TEXT")
        if "local_path" not in existing:
            conn.execute("ALTER TABLE assets ADD COLUMN local_path TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assets_source_repo "
            "ON assets(source_repo)"
        )

    def upsert_asset(
        self, asset: Asset, mtime: float, source_repo: Optional[str] = None
    ) -> None:
        """INSERT OR REPLACE into assets.

        ``source_repo`` records which remote the asset came from. Existing
        ``local_path`` and ``thumbnail_local`` values are preserved across
        rescans (INSERT OR REPLACE deletes the old row, so we carry them over).
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        tags_json = json.dumps(asset.tags) if asset.tags else None

        bounds_x = asset.bounds.x if asset.bounds else None
        bounds_y = asset.bounds.y if asset.bounds else None
        bounds_z = asset.bounds.z if asset.bounds else None

        # Get poly_count from latest version if available
        latest = asset.get_latest_version()
        poly_count = latest.poly_count if latest else None

        with self._get_connection() as conn:
            prev = conn.execute(
                "SELECT local_path, thumbnail_local, source_repo "
                "FROM assets WHERE uuid = ?",
                (asset.uuid,),
            ).fetchone()
            local_path = asset.local_path or (prev["local_path"] if prev else None)
            thumbnail_local = prev["thumbnail_local"] if prev else None
            # Preserve the recorded origin when a caller (spot_check, resolver)
            # re-upserts without specifying it.
            resolved_repo = (
                source_repo
                if source_repo is not None
                else (asset.source_repo or (prev["source_repo"] if prev else None))
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO assets
                    (uuid, name, path, current_version, current_file, type,
                     category, status, tags, poly_count, bounds_x, bounds_y,
                     bounds_z, thumbnail_path, thumbnail_local, created_by,
                     modified_at, meta_file_mtime, synced_at, source_repo,
                     local_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.uuid,
                    asset.name,
                    asset.path,
                    asset.current_version,
                    asset.current_file,
                    "model",
                    asset.category,
                    asset.status.value,
                    tags_json,
                    poly_count,
                    bounds_x,
                    bounds_y,
                    bounds_z,
                    asset.thumbnail,
                    thumbnail_local,
                    latest.created_by if latest else None,
                    asset.modified_at.isoformat() + "Z",
                    mtime,
                    now,
                    resolved_repo,
                    local_path,
                ),
            )

    def get_asset(self, uuid: str) -> Optional[Asset]:
        """Get asset by UUID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM assets WHERE uuid = ?", (uuid,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_asset(row)

    def delete_asset(self, uuid: str) -> None:
        """Delete an asset by UUID."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM assets WHERE uuid = ?", (uuid,))

    def search_assets(
        self,
        query="",
        category=None,
        status=None,
        tags=None,
        source_repo=None,
        limit=100,
        offset=0,
    ) -> List[Asset]:
        """Search assets with filters. Tags filtered in Python (JSON field)."""
        clauses = []
        params: list = []

        if query:
            clauses.append("name LIKE ?")
            params.append(f"%{query}%")
        if category:
            clauses.append("category = ?")
            params.append(category)
        if status:
            clauses.append("status = ?")
            params.append(status if isinstance(status, str) else status.value)
        if source_repo:
            clauses.append("source_repo = ?")
            params.append(source_repo)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = f"SELECT * FROM assets {where} ORDER BY modified_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        assets = [self._row_to_asset(row) for row in rows]

        # Filter by tags in Python since tags are stored as JSON
        if tags:
            tag_set = set(tags)
            assets = [a for a in assets if tag_set.issubset(set(a.tags))]

        return assets

    def get_categories_with_counts(self) -> Dict[str, int]:
        """GROUP BY category and return counts."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM assets GROUP BY category"
            ).fetchall()
            return {row["category"]: row["cnt"] for row in rows}

    def get_repos_with_counts(self) -> Dict[str, int]:
        """GROUP BY source_repo and return counts (skips NULL/unknown)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT source_repo, COUNT(*) as cnt FROM assets "
                "WHERE source_repo IS NOT NULL GROUP BY source_repo"
            ).fetchall()
            return {row["source_repo"]: row["cnt"] for row in rows}

    def set_local_path(self, uuid: str, local_path: Optional[str]) -> None:
        """Record where an asset has been pulled to on the local repo."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE assets SET local_path = ? WHERE uuid = ?",
                (local_path, uuid),
            )

    def set_thumbnail_local(self, uuid: str, thumbnail_local: Optional[str]) -> None:
        """Record the locally cached thumbnail path for an asset."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE assets SET thumbnail_local = ? WHERE uuid = ?",
                (thumbnail_local, uuid),
            )

    def get_all_uuids(self) -> List[str]:
        """Get all asset UUIDs (needed by scanner)."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT uuid FROM assets").fetchall()
            return [row["uuid"] for row in rows]

    def get_asset_mtime(self, uuid: str) -> Optional[float]:
        """Get meta_file_mtime for a uuid (needed by scanner)."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT meta_file_mtime FROM assets WHERE uuid = ?", (uuid,)
            ).fetchone()
            if row is None:
                return None
            return row["meta_file_mtime"]

    def get_meta_state(self, uuid: str) -> Optional[Tuple[float, str]]:
        """Return ``(meta_file_mtime, path)`` for a uuid, or None if absent.

        Lets the scanner check the change signal (mtime) and the recorded
        location in a single query on the hot path, so a moved folder can be
        absorbed with a cheap path update instead of a full re-upsert.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT meta_file_mtime, path FROM assets WHERE uuid = ?", (uuid,)
            ).fetchone()
            if row is None:
                return None
            return (row["meta_file_mtime"], row["path"])

    def set_path(self, uuid: str, path: str) -> None:
        """Update only the on-disk location of an asset (used to absorb moves)."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE assets SET path = ? WHERE uuid = ?", (path, uuid)
            )

    def get_sync_state(self, key: str) -> Optional[str]:
        """Get a sync state value by key."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM sync_state WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            return row["value"]

    def set_sync_state(self, key: str, value: str) -> None:
        """Set a sync state value."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)",
                (key, value),
            )

    def _row_to_asset(self, row) -> Asset:
        """Convert sqlite3.Row to Asset."""
        tags = []
        if row["tags"]:
            tags = json.loads(row["tags"])

        bounds = None
        if row["bounds_x"] is not None:
            bounds = Bounds(
                x=row["bounds_x"], y=row["bounds_y"], z=row["bounds_z"]
            )

        keys = row.keys()
        return Asset(
            uuid=row["uuid"],
            name=row["name"],
            path=row["path"],
            current_version=row["current_version"],
            current_file=row["current_file"],
            category=row["category"],
            status=AssetStatus(row["status"]),
            modified_at=datetime.fromisoformat(row["modified_at"].rstrip("Z")),
            tags=tags,
            thumbnail=row["thumbnail_path"],
            bounds=bounds,
            source_repo=row["source_repo"] if "source_repo" in keys else None,
            local_path=row["local_path"] if "local_path" in keys else None,
        )
