# NinjaAssets
## Product Requirements Document

**Cloud/Synced-Folder Asset Management for Maya** *(multi-remote + local repo)*

| Document Info | |
|---------------|-------------|
| Version | 1.1 |
| Date | June 2026 |
| Status | Draft |
| Platform | Maya 2022+ / Windows |
| Storage Backend | Cloud/synced folders (one or more remotes; Google Drive Desktop, Dropbox, OneDrive, NAS, etc.) |
| Scale | ~1,000 assets / ~500 artists |

---

## Revision History

| Version | Date | Summary |
|---------|------|---------|
| 1.0 | March 2026 | Initial design: single Google Drive root, local SQLite cache, Products/Scenefiles tabs. |
| 1.1 | June 2026 | **Multi-remote + local repo model.** Adds a **Setup tab** to register a **local repo** and one or more **remote repos** (cloud/synced folders); the scanner builds a searchable metadata + thumbnail library aggregated across all remotes (each asset tagged with its `source_repo`); import gains an optional **"pull to local"** that copies the asset into the local repo first; Products gains a **repo filter**. Cache schema bumped to v2 (`source_repo`, `local_path`). Backward compatible: an existing single `gdrive_root` is treated as the default remote. **UI cleanup:** the workflow STATUS surface (sidebar filter, card badge, preview line) was removed from the browser; the `status` field remains in the model/sidecar/Publish dialog. |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Data Structures & Schemas](#3-data-structures--schemas)
4. [Core Python Package](#4-core-python-package)
5. [Maya Integration](#5-maya-integration)
6. [User Interface Specifications](#6-user-interface-specifications)
7. [Sync Engine](#7-sync-engine)
8. [Deployment & Installation](#8-deployment--installation)
9. [Code Examples](#9-code-examples)
10. [Appendices](#10-appendices)

---

## 1. Executive Summary

### 1.1 Problem Statement

A VFX studio with approximately 500 artists requires a lightweight asset management system that operates entirely through Google Drive Desktop. Artists need to browse, import, reference, and publish 3D model assets (OBJ/MA files) with visual thumbnails, plus manage versions of their Maya scene files. No external database servers or daemons can run on GDrive infrastructure.

### 1.2 Solution: NinjaAssets

NinjaAssets is a distributed, eventually-consistent asset management system featuring:

- Prism-inspired UI integrated natively into Maya
- JSON sidecar metadata files stored alongside assets on cloud/synced storage
- One or more **remote repos** (cloud/synced folders) plus a **local repo** the artist can pull assets into
- A **Setup tab** for pointing at the local repo and registering/scanning remote repos
- A searchable metadata + thumbnail library aggregated across **all** remotes
- Optional **pull-to-local** on import (copy the asset into the local repo, then import from the local copy)
- Local SQLite cache on each workstation for instant queries
- Append-only changelog for near-real-time sync across 500+ workstations
- Maya-only interface (no external applications required)

### 1.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| App Name | NinjaAssets | User preference |
| Maya Menu Name | NinjaAssets | Consistent branding |
| Shelf Integration | Add to existing shelf | Less intrusive |
| Window Type | Floating window | Simpler implementation |
| Double-click Action | Import (Products) / Open (Scenes) | Prism-style UX |
| UI Theme | Maya native | Consistent look |
| Version Editing | User can edit version number | Flexibility for artists |
| Scene Versioning | Freeform (not project-tied) | Minimal structure |
| Categories | Fixed list | Consistency across studio |
| Remote Repos | One or more, configurable | Aggregate multiple shared libraries in one browser |
| Remote Backend | Cloud/synced folders (file copy) | No git/object-store dependency; "pull" is a plain copy |
| Local Repo | Single pull destination | Fast/offline access; Maya can reference local files |
| Pull on Import | Optional (checkbox) | Artist chooses remote-direct vs. local copy per import |
| Repo Identity | Unique name + path | `source_repo` keys the library; duplicates are rejected |

### 1.4 Feature Scope

| In Scope (MVP) | Out of Scope |
|----------------|--------------|
| Asset browser with thumbnail grid | Shot/sequence management |
| Asset import and referencing | Render farm integration |
| Asset publishing with metadata | Review/approval workflows |
| Scene versioning with comments | USD/MaterialX support |
| Editable version numbers | Multi-project support |
| Artist-triggered thumbnail capture | User permissions/roles |
| Local caching and sync | Dependencies tracking |
| Maya-only UI | External dashboard applications |
| Setup tab: local + remote repo config | Per-asset pull/version pinning policies |
| Multiple remote repos, scanned into one library | Two-way sync of the local repo back to remotes |
| Repo filter + search across all remotes | Conflict resolution between remotes |
| Optional pull-to-local on import | Garbage collection of the local repo |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GOOGLE DRIVE (G:\)                              │
│                         "Dumb Storage Layer"                            │
│                                                                         │
│   /assets/                              /.ninjaassets/                  │
│     /characters/                          changelog.jsonl               │
│       /hero_robot/                        schema_version.txt            │
│         hero_robot_v003.obj                                             │
│         hero_robot.meta.json  ◄── Sidecar (source of truth)            │
│         hero_robot.thumb.jpg                                            │
│     /props/                                                             │
│     /environments/                                                      │
│                                                                         │
│   /scenes/                                                              │
│     /rigging/                                                           │
│       /hero_robot/                                                      │
│         hero_robot_rigging_v001.ma                                      │
│         hero_robot_rigging_v002.ma                                      │
│         .scene_meta.json      ◄── Scene version metadata               │
└─────────────────────────────────────────────────────────────────────────┘
                    │                              │                       
     ┌──────────────┼──────────────┬───────────────┼──────────────┐       
     ▼              ▼              ▼               ▼              ▼       
┌─────────┐   ┌─────────┐   ┌─────────┐    ┌─────────┐    ┌─────────┐    
│ Maya    │   │ Maya    │   │ Maya    │    │ Maya    │    │ Maya    │    
│ Artist1 │   │ Artist2 │   │ Artist3 │    │ Artist4 │    │ Artist5 │    
│         │   │         │   │         │    │         │    │         │    
│ SQLite  │   │ SQLite  │   │ SQLite  │    │ SQLite  │    │ SQLite  │    
│ Cache   │   │ Cache   │   │ Cache   │    │ Cache   │    │ Cache   │    
└─────────┘   └─────────┘   └─────────┘    └─────────┘    └─────────┘    
```

> **v1.1 note:** The single Google Drive root above generalizes to **one or more remote repos**.
> Each remote is an independent cloud/synced folder with the same internal layout
> (`/assets/<category>/<name>/`, `/.ninjaassets/`). The diagram's "G:\" becomes any number of
> registered remotes; an existing single `gdrive_root` is treated as the default remote for
> backward compatibility.

#### 2.1.1 Multi-Remote Topology (v1.1)

```
   Remote repo "studio"        Remote repo "archive"        ... (N remotes)
   (cloud/synced folder)       (cloud/synced folder)
   /assets/...  /.ninjaassets  /assets/...  /.ninjaassets
        │                            │
        └──────────────┬─────────────┘
                       ▼   scan (tags each asset with source_repo)
              ┌──────────────────────┐
              │  Local SQLite cache  │  ◄── one library, searchable across all remotes
              │  (source_repo, ...)  │
              └──────────┬───────────┘
                         │  pull-to-local (optional, on import) = file copy
                         ▼
              ┌──────────────────────┐
              │  LOCAL REPO          │  /<category>/<name>/  (Maya imports/refs from here)
              └──────────────────────┘
```

### 2.2 Component Overview

| Component | Location | Purpose |
|-----------|----------|---------|
| Remote Repos | Registered cloud/synced folders | One or more shared asset libraries to scan |
| Sidecar Files (.meta.json) | `<remote>\assets\*\` | Source of truth for each asset |
| Scene Meta (.scene_meta.json) | `<remote>\scenes\*\` | Scene version history |
| Changelog | `<remote>\.ninjaassets\changelog.jsonl` | Append-only sync event log |
| Thumbnails (.thumb.jpg) | `<remote>\assets\*\` | Artist-captured previews |
| Local Repo | User-chosen folder | Pull destination; holds local copies for import/reference |
| Local Cache | `%APPDATA%\NinjaAssets\cache.sqlite` | Fast local queries; tracks `source_repo` + `local_path` |
| Cached Thumbnails | `%APPDATA%\NinjaAssets\thumbnails\` | Local copies of remote thumbnails (offline library) |
| Sync Engine | Maya Python thread | Background sync coordinator (scans every remote) |
| NinjaAssets UI | Maya PySide2/PySide6 window | Artist interface (Products / Scenefiles / **Setup**) |

### 2.3 Data Flow Patterns

#### Read Path (Artist browses assets)
- UI queries local SQLite cache (instant, <50ms)
- Thumbnails loaded from local cache or fetched on-demand from GDrive
- Sync Engine keeps cache updated via changelog polling

#### Write Path (Artist publishes asset)
- Publisher exports file to `G:\assets\<category>\<name>\`
- Publisher creates/updates .meta.json sidecar
- Publisher appends event to changelog.jsonl
- Publisher updates local SQLite cache immediately
- Other Maya instances detect change via Sync Engine within 30-60s

#### Scene Save Path
- User clicks Save Version or Save + Comment
- Scene saved with versioned filename (e.g., scene_v003.ma)
- User can edit version number before saving
- .scene_meta.json updated with version entry

#### Library Scan Path (v1.1 — multi-remote)
- Setup tab "Scan Remotes Now" (or Force Sync / first run) runs a full scan
- Scanner walks `<remote>/assets/<category>/<name>/` for **every** registered remote
- Each discovered asset is upserted into the cache tagged with its `source_repo`
- Remote thumbnails are copied into the local thumbnail cache (offline screenshot library)
- Cache entries absent from **all** remotes are evicted (stale cleanup)

#### Pull-to-Local Path (v1.1)
- Artist selects an asset and enables "Pull to local" (only when a local repo is configured)
- On Import/Reference, the version file + sidecar + thumbnail are copied to
  `<local_repo>/<category>/<name>/` (idempotent: copy only when missing/older)
- Maya imports/references from the **local copy**; the cache records `local_path`
- Without pull, import/reference reads directly from the remote path (unchanged v1.0 behavior)

---

## 3. Data Structures & Schemas

### 3.1 Asset Sidecar Schema (*.meta.json)

Each asset folder contains a `.meta.json` file that serves as the source of truth:

```json
{
  "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "hero_robot",
  "version": 3,
  "versions": [
    {
      "version": 1,
      "file": "hero_robot_v001.obj",
      "created_by": "sarah.jones",
      "created_at": "2025-01-15T09:30:00Z",
      "comment": "Initial blockout",
      "poly_count": 12000
    },
    {
      "version": 2,
      "file": "hero_robot_v002.obj",
      "created_by": "sarah.jones",
      "created_at": "2025-01-16T14:20:00Z",
      "comment": "Added detail pass",
      "poly_count": 35000
    },
    {
      "version": 3,
      "file": "hero_robot_v003.obj",
      "created_by": "mike.chen",
      "created_at": "2025-01-17T11:45:00Z",
      "comment": "Fixed topology issues",
      "poly_count": 45000
    }
  ],
  "current_file": "hero_robot_v003.obj",
  "type": "model",
  "category": "Characters",
  "tags": ["robot", "hero", "mechanical"],
  "status": "review",
  "thumbnail": "hero_robot.thumb.jpg",
  "bounds": { "x": 2.5, "y": 4.0, "z": 1.5 },
  "modified_at": "2025-01-17T11:45:00Z"
}
```

#### 3.1.1 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| uuid | string (UUID v4) | Yes | Globally unique identifier |
| name | string | Yes | Asset display name (folder name) |
| version | integer | Yes | Current/latest version number |
| versions | array\<Version\> | Yes | Complete version history |
| current_file | string | Yes | Filename of current version |
| type | string | Yes | Asset type (always "model") |
| category | string | Yes | One of fixed categories |
| tags | array\<string\> | No | User-defined searchable tags |
| status | string | Yes | wip \| review \| approved |
| thumbnail | string | No | Thumbnail filename |
| bounds | object | No | Bounding box {x, y, z} |
| modified_at | string (ISO 8601) | Yes | Last modification timestamp |

### 3.2 Scene Metadata Schema (.scene_meta.json)

Stored in each scene folder to track version history:

```json
{
  "scene_name": "hero_robot_rigging",
  "current_version": 5,
  "versions": [
    {
      "version": 1,
      "file": "hero_robot_rigging_v001.ma",
      "created_by": "mike.chen",
      "created_at": "2025-01-14T09:00:00Z",
      "comment": "Initial scene setup"
    },
    {
      "version": 2,
      "file": "hero_robot_rigging_v002.ma",
      "created_by": "mike.chen",
      "created_at": "2025-01-15T16:30:00Z",
      "comment": "Basic skeleton"
    },
    {
      "version": 5,
      "file": "hero_robot_rigging_v005.ma",
      "created_by": "sarah.jones",
      "created_at": "2025-01-17T14:30:00Z",
      "comment": "Fixed weight painting on arms"
    }
  ]
}
```

> **Note:** Version numbers can have gaps (v001, v002, v005) when users edit version numbers.

### 3.3 Changelog Schema (changelog.jsonl)

Append-only log for distributed sync. Each line is a JSON event:

```jsonl
{"ts":"2025-01-17T11:45:00Z","type":"asset_created","uuid":"a1b2...","path":"/assets/characters/hero_robot","user":"sarah","v":1}
{"ts":"2025-01-17T12:30:00Z","type":"asset_updated","uuid":"a1b2...","path":"/assets/characters/hero_robot","user":"mike","v":3}
{"ts":"2025-01-17T14:00:00Z","type":"asset_deleted","uuid":"x9y8...","path":"/assets/props/old_chair","user":"admin"}
{"ts":"2025-01-17T14:30:00Z","type":"scene_saved","path":"/scenes/rigging/hero_robot","user":"sarah","v":5}
```

#### 3.3.1 Event Types

| Event Type | Required Fields | Description |
|------------|-----------------|-------------|
| asset_created | uuid, path, user, v | New asset published |
| asset_updated | uuid, path, user, v | New version of existing asset |
| asset_deleted | uuid, path, user | Asset removed from library |
| metadata_changed | uuid, field, value, user | Status or tags modified |
| scene_saved | path, user, v | New scene version saved |

### 3.4 Local Cache Schema (SQLite) — Schema v2

> **v1.1:** `SCHEMA_VERSION` is bumped from 1 to **2**, adding `source_repo` and `local_path`.
> Because the cache is rebuildable, the migration is additive and idempotent: on open, missing
> columns are added via `ALTER TABLE ... ADD COLUMN` and a rescan repopulates them — no data loss
> for existing file-backed caches.

```sql
-- Main assets table
CREATE TABLE assets (
    uuid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    current_version INTEGER NOT NULL,
    current_file TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'model',
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'wip',
    tags TEXT,  -- JSON array as text
    poly_count INTEGER,
    bounds_x REAL,
    bounds_y REAL,
    bounds_z REAL,
    thumbnail_path TEXT,
    thumbnail_local TEXT,  -- Local cached thumbnail path
    created_by TEXT,
    modified_at TEXT NOT NULL,
    meta_file_mtime REAL,  -- For change detection
    synced_at TEXT NOT NULL,
    source_repo TEXT,      -- v2: name of the remote repo this asset came from
    local_path TEXT        -- v2: path to the pulled local copy, if any
);

CREATE INDEX idx_assets_category ON assets(category);
CREATE INDEX idx_assets_status ON assets(status);
CREATE INDEX idx_assets_name ON assets(name);
CREATE INDEX idx_assets_modified ON assets(modified_at);
CREATE INDEX idx_assets_source_repo ON assets(source_repo);  -- v2

-- Sync state tracking
CREATE TABLE sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- User preferences
CREATE TABLE preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

> **Note on identity:** `uuid` remains the primary key. If the *same* asset (same UUID) exists in
> two remotes — e.g. a pulled duplicate that grew its own sidecar — the rows collide on one entry;
> the last scanned wins. This is acceptable for v1.1 and is documented as a known limitation.
> On re-upsert (spot-check/changelog resolver), `source_repo` and `local_path` are **preserved**
> when the caller does not supply them.

---

## 4. Core Python Package

### 4.1 Package Structure

```
ninja_assets/
├── __init__.py
├── config.py                 # Configuration management
├── constants.py              # Categories, statuses, paths
│
├── core/
│   ├── __init__.py
│   ├── models.py             # Asset, Version, Event dataclasses
│   ├── sidecar.py            # Read/write .meta.json files
│   ├── scene_meta.py         # Read/write .scene_meta.json
│   ├── changelog.py          # Append/read changelog.jsonl
│   ├── cache.py              # SQLite operations
│   └── exceptions.py         # Custom exceptions
│
├── sync/
│   ├── __init__.py
│   ├── engine.py             # Background sync coordinator
│   ├── scanner.py            # Filesystem scanning
│   └── resolver.py           # Conflict resolution
│
├── maya_integration/
│   ├── __init__.py
│   ├── plugin.py             # Maya plugin entry point
│   ├── menu.py               # NinjaAssets menu
│   ├── shelf.py              # Shelf button creation
│   ├── commands.py           # Import, reference, export
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py    # Main floating window
│   │   ├── products_tab.py   # Asset browser (Products)
│   │   ├── scenefiles_tab.py # Scene versions
│   │   ├── publish_dialog.py # Publish asset dialog
│   │   ├── save_version_dialog.py # Save scene version
│   │   ├── thumbnail_widget.py # Grid of thumbnails
│   │   ├── preview_panel.py  # Asset detail preview (+ pull-to-local checkbox)
│   │   ├── setup_tab.py      # v1.1: local + remote repo config and scan
│   │   ├── settings_dialog.py # Settings/preferences
│   │   └── username_dialog.py # First-run username prompt
│   │
│   └── utils/
│       ├── __init__.py
│       ├── maya_utils.py     # Maya-specific helpers
│       ├── export.py         # OBJ/MA export logic
│       └── thumbnail.py      # Viewport capture
│
└── cli/
    ├── __init__.py
    ├── migrate.py            # Migration for existing assets
    └── init_gdrive.py        # Initialize GDrive structure
```

### 4.2 Configuration Module (config.py)

```python
"""
NinjaAssets Configuration Management
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NinjaConfig:
    """Main configuration container"""
    
    # Google Drive paths
    gdrive_root: Path = Path("G:/")
    
    @property
    def assets_root(self) -> Path:
        return self.gdrive_root / "assets"
    
    @property
    def scenes_root(self) -> Path:
        return self.gdrive_root / "scenes"
    
    @property
    def pipeline_dir(self) -> Path:
        return self.gdrive_root / ".ninjaassets"
    
    @property
    def changelog_path(self) -> Path:
        return self.pipeline_dir / "changelog.jsonl"
    
    # Local paths
    local_data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get('APPDATA', os.path.expanduser('~'))
        ) / 'NinjaAssets'
    )
    
    @property
    def cache_db_path(self) -> Path:
        return self.local_data_dir / "cache.sqlite"
    
    @property
    def local_thumbnails_dir(self) -> Path:
        return self.local_data_dir / "thumbnails"
    
    # Sync settings
    sync_interval_seconds: int = 60
    changelog_poll_interval: int = 30
    spot_check_count: int = 20
    
    # Thumbnail settings
    thumbnail_size: tuple = (256, 256)
    thumbnail_format: str = "jpg"
    thumbnail_quality: int = 85
    
    # UI settings
    grid_thumbnail_size: int = 100
    preview_thumbnail_size: int = 250
    
    # Fixed categories
    categories: List[str] = field(default_factory=lambda: [
        "Characters",
        "Props",
        "Environments",
        "Vehicles",
        "Weapons",
        "FX",
        "Other"
    ])
    
    # Valid statuses
    statuses: List[str] = field(default_factory=lambda: [
        "wip",
        "review",
        "approved"
    ])
    
    # User identity (set on first launch)
    username: Optional[str] = None
    
    def __post_init__(self):
        # Ensure local directories exist
        self.local_data_dir.mkdir(parents=True, exist_ok=True)
        self.local_thumbnails_dir.mkdir(exist_ok=True)
        (self.local_data_dir / "logs").mkdir(exist_ok=True)
    
    def save(self):
        """Save config to local JSON file"""
        config_path = self.local_data_dir / 'config.json'
        data = {
            'gdrive_root': str(self.gdrive_root),
            'username': self.username,
            'sync_interval_seconds': self.sync_interval_seconds,
            'grid_thumbnail_size': self.grid_thumbnail_size,
        }
        config_path.write_text(json.dumps(data, indent=2))
    
    @classmethod
    def load(cls) -> 'NinjaConfig':
        """Load config from local JSON or return defaults"""
        config = cls()
        config_path = config.local_data_dir / 'config.json'
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                if 'gdrive_root' in data:
                    config.gdrive_root = Path(data['gdrive_root'])
                config.username = data.get('username')
                config.sync_interval_seconds = data.get('sync_interval_seconds', 60)
                config.grid_thumbnail_size = data.get('grid_thumbnail_size', 100)
            except (json.JSONDecodeError, KeyError):
                pass  # Use defaults
        return config


# Global config instance
CONFIG = NinjaConfig.load()
```

#### 4.2.1 v1.1 Additions — Repos (config.py)

A lightweight `Repo` dataclass plus two `NinjaConfig` fields model the multi-remote + local
design. Existing single-`gdrive_root` configs keep working via the `remote_repos()` fallback.

```python
@dataclass
class Repo:
    """A remote (cloud/synced) asset repository the tool scans and pulls from."""
    name: str            # unique, case-insensitive; keys the cache `source_repo`
    path: Path
    enabled: bool = True


@dataclass
class NinjaConfig:
    ...
    remotes: List[Repo] = field(default_factory=list)   # registered remotes
    local_repo: Optional[Path] = None                   # pull-to-local destination

    def remote_repos(self) -> List[Repo]:
        """Enabled remotes; falls back to [Repo('GDrive', gdrive_root)] when none set."""
        configured = [r for r in self.remotes if r.enabled]
        return configured or [Repo("GDrive", self.gdrive_root)]

    def assets_root_for(self, repo: Repo) -> Path:
        return repo.path / "assets"


# Duplicate-registration guards (used by the Setup tab):
def find_remote_by_path(remotes, path) -> Optional[Repo]: ...   # normcase+normpath compare
def find_remote_by_name(remotes, name) -> Optional[Repo]: ...   # case-insensitive compare
```

`save()`/`load()` persist `remotes` (as `{name, path, enabled}`) and `local_repo` in
`config.json`. The Setup tab rejects a remote whose **path** is already registered, and any
**name** that collides (case-insensitively) with an existing remote.

### 4.3 Data Models (models.py)

```python
"""
Core data models using dataclasses
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid as uuid_lib


class AssetStatus(Enum):
    WIP = "wip"
    REVIEW = "review"
    APPROVED = "approved"


class EventType(Enum):
    ASSET_CREATED = "asset_created"
    ASSET_UPDATED = "asset_updated"
    ASSET_DELETED = "asset_deleted"
    METADATA_CHANGED = "metadata_changed"
    SCENE_SAVED = "scene_saved"


@dataclass
class Version:
    """A single version of an asset or scene"""
    version: int
    file: str
    created_by: str
    created_at: datetime
    comment: str = ""
    poly_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'version': self.version,
            'file': self.file,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() + 'Z',
            'comment': self.comment,
        }
        if self.poly_count is not None:
            result['poly_count'] = self.poly_count
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Version':
        return cls(
            version=data['version'],
            file=data['file'],
            created_by=data['created_by'],
            created_at=datetime.fromisoformat(data['created_at'].rstrip('Z')),
            comment=data.get('comment', ''),
            poly_count=data.get('poly_count')
        )


@dataclass
class Bounds:
    """Bounding box dimensions"""
    x: float
    y: float
    z: float


@dataclass
class Asset:
    """Complete asset representation"""
    uuid: str
    name: str
    path: str
    current_version: int
    current_file: str
    category: str
    status: AssetStatus
    modified_at: datetime
    versions: List[Version] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    thumbnail: Optional[str] = None
    bounds: Optional[Bounds] = None
    # v1.1: cache-only fields, populated by the cache/scanner layer.
    # Excluded from to_dict()/from_dict() so .meta.json sidecars stay clean.
    source_repo: Optional[str] = None  # which remote this came from
    local_path: Optional[str] = None   # path to pulled local copy, if any
    
    @classmethod
    def new(cls, name: str, category: str, path: str) -> 'Asset':
        """Create a new asset with generated UUID"""
        return cls(
            uuid=str(uuid_lib.uuid4()),
            name=name,
            path=path,
            current_version=0,
            current_file='',
            category=category,
            status=AssetStatus.WIP,
            modified_at=datetime.utcnow()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        result = {
            'uuid': self.uuid,
            'name': self.name,
            'version': self.current_version,
            'versions': [v.to_dict() for v in self.versions],
            'current_file': self.current_file,
            'type': 'model',
            'category': self.category,
            'status': self.status.value,
            'tags': self.tags,
            'thumbnail': self.thumbnail,
            'modified_at': self.modified_at.isoformat() + 'Z'
        }
        if self.bounds:
            result['bounds'] = {
                'x': self.bounds.x,
                'y': self.bounds.y,
                'z': self.bounds.z
            }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: str) -> 'Asset':
        """Create from sidecar JSON data"""
        bounds = None
        if 'bounds' in data and data['bounds']:
            b = data['bounds']
            bounds = Bounds(x=b['x'], y=b['y'], z=b['z'])
        
        return cls(
            uuid=data['uuid'],
            name=data['name'],
            path=path,
            current_version=data['version'],
            current_file=data['current_file'],
            category=data['category'],
            status=AssetStatus(data.get('status', 'wip')),
            modified_at=datetime.fromisoformat(data['modified_at'].rstrip('Z')),
            versions=[Version.from_dict(v) for v in data.get('versions', [])],
            tags=data.get('tags', []),
            thumbnail=data.get('thumbnail'),
            bounds=bounds
        )
    
    def get_version(self, version_num: int) -> Optional[Version]:
        """Get a specific version by number"""
        for v in self.versions:
            if v.version == version_num:
                return v
        return None
    
    def get_latest_version(self) -> Optional[Version]:
        """Get the latest version"""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version)


@dataclass
class SceneMeta:
    """Scene file version metadata"""
    scene_name: str
    current_version: int
    versions: List[Version] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'scene_name': self.scene_name,
            'current_version': self.current_version,
            'versions': [v.to_dict() for v in self.versions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SceneMeta':
        return cls(
            scene_name=data['scene_name'],
            current_version=data['current_version'],
            versions=[Version.from_dict(v) for v in data.get('versions', [])]
        )
    
    def get_next_version(self) -> int:
        """Get the next version number"""
        if not self.versions:
            return 1
        return max(v.version for v in self.versions) + 1


@dataclass
class ChangelogEvent:
    """An event in the changelog"""
    timestamp: datetime
    event_type: EventType
    uuid: str
    path: str
    user: str
    version: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_json_line(self) -> str:
        import json
        data = {
            'ts': self.timestamp.isoformat() + 'Z',
            'type': self.event_type.value,
            'uuid': self.uuid,
            'path': self.path,
            'user': self.user
        }
        if self.version is not None:
            data['v'] = self.version
        data.update(self.extra)
        return json.dumps(data, separators=(',', ':'))
    
    @classmethod
    def from_json_line(cls, line: str) -> 'ChangelogEvent':
        import json
        data = json.loads(line)
        return cls(
            timestamp=datetime.fromisoformat(data['ts'].rstrip('Z')),
            event_type=EventType(data['type']),
            uuid=data.get('uuid', ''),
            path=data['path'],
            user=data['user'],
            version=data.get('v')
        )
```

### 4.4 Sidecar Operations (sidecar.py)

```python
"""
Read and write asset sidecar (.meta.json) files
"""
import json
import os
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from .models import Asset, Version, AssetStatus
from .exceptions import SidecarError, ConflictError


class SidecarManager:
    """Handles reading/writing sidecar metadata files"""
    
    SIDECAR_SUFFIX = '.meta.json'
    
    @staticmethod
    def get_sidecar_path(asset_folder: Path, asset_name: str) -> Path:
        """Get the sidecar file path for an asset"""
        return asset_folder / f"{asset_name}{SidecarManager.SIDECAR_SUFFIX}"
    
    @staticmethod
    def read(sidecar_path: Path) -> Tuple[Asset, float]:
        """
        Read sidecar file and return Asset + mtime.
        
        Returns:
            Tuple of (Asset, file_mtime)
        Raises:
            SidecarError: If file cannot be read or parsed
        """
        try:
            mtime = os.path.getmtime(sidecar_path)
            data = json.loads(sidecar_path.read_text(encoding='utf-8'))
            asset = Asset.from_dict(data, str(sidecar_path.parent))
            return asset, mtime
        except FileNotFoundError:
            raise SidecarError(f"Sidecar not found: {sidecar_path}")
        except json.JSONDecodeError as e:
            raise SidecarError(f"Invalid JSON in {sidecar_path}: {e}")
        except KeyError as e:
            raise SidecarError(f"Missing required field in {sidecar_path}: {e}")
    
    @staticmethod
    def write(sidecar_path: Path, asset: Asset, expected_mtime: Optional[float] = None) -> float:
        """
        Write asset data to sidecar file with optimistic locking.
        
        Args:
            sidecar_path: Path to write
            asset: Asset data to write
            expected_mtime: If provided, check file hasn't changed since this mtime
        
        Returns:
            New file mtime
        Raises:
            ConflictError: If file was modified since expected_mtime
        """
        # Optimistic concurrency check
        if expected_mtime is not None and sidecar_path.exists():
            current_mtime = os.path.getmtime(sidecar_path)
            if current_mtime != expected_mtime:
                raise ConflictError(
                    f"Sidecar was modified by another process. "
                    f"Expected mtime {expected_mtime}, got {current_mtime}"
                )
        
        # Write atomically via temp file
        temp_path = sidecar_path.with_suffix('.tmp')
        try:
            data = asset.to_dict()
            temp_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            temp_path.replace(sidecar_path)  # Atomic on most filesystems
            return os.path.getmtime(sidecar_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise SidecarError(f"Failed to write sidecar: {e}")
    
    @staticmethod
    def exists(asset_folder: Path, asset_name: str) -> bool:
        """Check if sidecar exists for an asset"""
        path = SidecarManager.get_sidecar_path(asset_folder, asset_name)
        return path.exists()
    
    @staticmethod
    def create_minimal(
        asset_folder: Path,
        asset_name: str,
        asset_file: str,
        category: str,
        user: str
    ) -> Asset:
        """
        Create a minimal sidecar for a discovered (unmanaged) asset.
        Used during migration or when files are dropped manually.
        """
        asset = Asset.new(name=asset_name, category=category, path=str(asset_folder))
        asset.current_version = 1
        asset.current_file = asset_file
        asset.versions = [
            Version(
                version=1,
                file=asset_file,
                created_by=user,
                created_at=datetime.utcnow(),
                comment="Auto-registered asset"
            )
        ]
        asset.status = AssetStatus.WIP
        
        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, asset_name)
        SidecarManager.write(sidecar_path, asset)
        
        return asset
```

### 4.5 Cache Operations (cache.py)

```python
"""
Local SQLite cache for fast asset queries
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from contextlib import contextmanager

from .models import Asset, AssetStatus, Bounds
from ..config import CONFIG


class CacheDB:
    """SQLite cache database operations"""
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or CONFIG.cache_db_path
        self._init_db()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._connection() as conn:
            conn.executescript('''
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
                
                CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
                CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
                CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);
                
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            ''')
    
    def upsert_asset(self, asset: Asset, mtime: float) -> None:
        """Insert or update an asset in the cache"""
        with self._connection() as conn:
            latest = asset.get_latest_version()
            conn.execute('''
                INSERT OR REPLACE INTO assets
                (uuid, name, path, current_version, current_file, type, category,
                 status, tags, poly_count, bounds_x, bounds_y, bounds_z,
                 thumbnail_path, created_by, modified_at, meta_file_mtime, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset.uuid,
                asset.name,
                asset.path,
                asset.current_version,
                asset.current_file,
                'model',
                asset.category,
                asset.status.value,
                json.dumps(asset.tags),
                latest.poly_count if latest else None,
                asset.bounds.x if asset.bounds else None,
                asset.bounds.y if asset.bounds else None,
                asset.bounds.z if asset.bounds else None,
                asset.thumbnail,
                latest.created_by if latest else None,
                asset.modified_at.isoformat(),
                mtime,
                datetime.utcnow().isoformat()
            ))
    
    def get_asset(self, uuid: str) -> Optional[Asset]:
        """Get a single asset by UUID"""
        with self._connection() as conn:
            row = conn.execute(
                'SELECT * FROM assets WHERE uuid = ?', (uuid,)
            ).fetchone()
            return self._row_to_asset(row) if row else None
    
    def search_assets(
        self,
        query: str = '',
        category: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Asset]:
        """Search assets with filters"""
        conditions = []
        params = []
        
        if query:
            conditions.append('name LIKE ?')
            params.append(f'%{query}%')
        
        if category:
            conditions.append('category = ?')
            params.append(category)
        
        if status:
            conditions.append('status = ?')
            params.append(status)
        
        where = ' AND '.join(conditions) if conditions else '1=1'
        
        with self._connection() as conn:
            rows = conn.execute(f'''
                SELECT * FROM assets
                WHERE {where}
                ORDER BY modified_at DESC
                LIMIT ? OFFSET ?
            ''', params + [limit, offset]).fetchall()
            
            assets = [self._row_to_asset(row) for row in rows]
            
            # Filter by tags in Python (JSON field)
            if tags:
                assets = [a for a in assets if any(t in a.tags for t in tags)]
            
            return assets
    
    def get_categories_with_counts(self) -> Dict[str, int]:
        """Get category names with asset counts"""
        with self._connection() as conn:
            rows = conn.execute('''
                SELECT category, COUNT(*) as count
                FROM assets
                GROUP BY category
                ORDER BY category
            ''').fetchall()
            return {row['category']: row['count'] for row in rows}
    
    def delete_asset(self, uuid: str) -> None:
        """Remove an asset from cache"""
        with self._connection() as conn:
            conn.execute('DELETE FROM assets WHERE uuid = ?', (uuid,))
    
    def get_sync_state(self, key: str) -> Optional[str]:
        """Get a sync state value"""
        with self._connection() as conn:
            row = conn.execute(
                'SELECT value FROM sync_state WHERE key = ?', (key,)
            ).fetchone()
            return row['value'] if row else None
    
    def set_sync_state(self, key: str, value: str) -> None:
        """Set a sync state value"""
        with self._connection() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)',
                (key, value)
            )
    
    def _row_to_asset(self, row: sqlite3.Row) -> Asset:
        """Convert a database row to an Asset object"""
        bounds = None
        if row['bounds_x'] is not None:
            bounds = Bounds(
                x=row['bounds_x'],
                y=row['bounds_y'],
                z=row['bounds_z']
            )
        
        return Asset(
            uuid=row['uuid'],
            name=row['name'],
            path=row['path'],
            current_version=row['current_version'],
            current_file=row['current_file'],
            category=row['category'],
            status=AssetStatus(row['status']),
            modified_at=datetime.fromisoformat(row['modified_at']),
            tags=json.loads(row['tags']) if row['tags'] else [],
            thumbnail=row['thumbnail_path'],
            bounds=bounds
        )
```

#### 4.5.1 v1.1 Cache Changes

- `SCHEMA_VERSION = 2`; `_init_db()` runs an idempotent migration (adds `source_repo` /
  `local_path` columns + `idx_assets_source_repo` when missing).
- `upsert_asset(asset, mtime, source_repo=None)` — writes `source_repo`; **preserves** existing
  `source_repo`, `local_path`, and `thumbnail_local` across re-upserts (so spot-check / changelog
  resolver and rescans don't clobber a recorded local pull or origin).
- `search_assets(..., source_repo=None)` — adds an optional equality filter on `source_repo`.
- New: `get_repos_with_counts()` (sidebar repo filter), `set_local_path(uuid, path)`,
  `set_thumbnail_local(uuid, path)`; `_row_to_asset()` populates `source_repo` / `local_path`.

---

## 5. Maya Integration

### 5.1 Plugin Entry Point (plugin.py)

```python
"""
NinjaAssets Maya Plugin Entry Point
Add to userSetup.py or load as plugin
"""
import sys
from pathlib import Path

# Add package to path
PACKAGE_ROOT = Path(__file__).parent.parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import maya.cmds as cmds

from ninja_assets.config import CONFIG
from ninja_assets.sync.engine import SyncEngine
from ninja_assets.maya_integration.ui.main_window import NinjaAssetsWindow
from ninja_assets.maya_integration.menu import create_menu
from ninja_assets.maya_integration.shelf import add_shelf_buttons


# Global references
_sync_engine = None
_main_window = None


def initialize():
    """Initialize NinjaAssets"""
    global _sync_engine
    
    # Check for username - prompt if not set
    if not CONFIG.username:
        from ninja_assets.maya_integration.ui.username_dialog import prompt_username
        username = prompt_username()
        if username:
            CONFIG.username = username
            CONFIG.save()
        else:
            cmds.warning("NinjaAssets: Username required to continue")
            return False
    
    # Ensure GDrive structure exists
    _ensure_gdrive_structure()
    
    # Start sync engine in background
    _sync_engine = SyncEngine()
    _sync_engine.start()
    
    # Create menu and shelf
    create_menu()
    add_shelf_buttons()
    
    print(f"NinjaAssets initialized for user: {CONFIG.username}")
    return True


def _ensure_gdrive_structure():
    """Create required GDrive directories if missing"""
    CONFIG.assets_root.mkdir(parents=True, exist_ok=True)
    CONFIG.scenes_root.mkdir(parents=True, exist_ok=True)
    CONFIG.pipeline_dir.mkdir(parents=True, exist_ok=True)
    
    # Create category folders
    for category in CONFIG.categories:
        (CONFIG.assets_root / category.lower()).mkdir(exist_ok=True)


def show_browser():
    """Show the NinjaAssets browser window"""
    global _main_window
    
    if _main_window is None:
        _main_window = NinjaAssetsWindow()
    
    _main_window.show()
    _main_window.raise_()
    _main_window.activateWindow()


def shutdown():
    """Cleanup on Maya exit"""
    global _sync_engine
    if _sync_engine:
        _sync_engine.stop()


# Auto-initialize when imported via userSetup.py
if __name__ != '__main__':
    cmds.evalDeferred(initialize)
```

### 5.2 Menu Integration (menu.py)

```python
"""
NinjaAssets Maya Menu
"""
import maya.cmds as cmds


MENU_NAME = "NinjaAssetsMenu"


def create_menu():
    """Create the NinjaAssets menu in Maya menu bar"""
    
    # Remove existing menu if present
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    
    # Create menu
    cmds.menu(
        MENU_NAME,
        label="NinjaAssets",
        parent="MayaWindow",
        tearOff=True
    )
    
    # Asset Browser
    cmds.menuItem(
        label="Asset Browser...",
        command=lambda _: _show_browser(),
        annotation="Open the NinjaAssets browser",
        image="fileOpen.png"
    )
    
    cmds.menuItem(divider=True)
    
    # Save Version
    cmds.menuItem(
        label="Save Version",
        command=lambda _: _save_version_quick(),
        annotation="Save scene as new version (auto-increment)",
    )
    
    # Save Version + Comment
    cmds.menuItem(
        label="Save Version + Comment...",
        command=lambda _: _save_version_dialog(),
        annotation="Save scene as new version with comment and optional version edit",
    )
    
    cmds.menuItem(divider=True)
    
    # Publish Selection
    cmds.menuItem(
        label="Publish Selection...",
        command=lambda _: _publish_selection(),
        annotation="Publish selected objects as a new asset",
    )
    
    # Import Asset
    cmds.menuItem(
        label="Import Asset...",
        command=lambda _: _show_browser_import(),
        annotation="Open browser to import an asset",
    )
    
    cmds.menuItem(divider=True)
    
    # Capture Thumbnail
    cmds.menuItem(
        label="Capture Thumbnail",
        command=lambda _: _capture_thumbnail(),
        annotation="Capture viewport as thumbnail for current asset",
    )
    
    cmds.menuItem(divider=True)
    
    # Force Sync
    cmds.menuItem(
        label="Force Sync",
        command=lambda _: _force_sync(),
        annotation="Force a full resync of the asset database",
    )
    
    # Settings
    cmds.menuItem(
        label="Settings...",
        command=lambda _: _show_settings(),
        annotation="Open NinjaAssets settings",
    )


def _show_browser():
    from ninja_assets.maya_integration import plugin
    plugin.show_browser()


def _show_browser_import():
    from ninja_assets.maya_integration import plugin
    plugin.show_browser()


def _save_version_quick():
    from ninja_assets.maya_integration.commands import save_scene_version
    save_scene_version(prompt_comment=False)


def _save_version_dialog():
    from ninja_assets.maya_integration.ui.save_version_dialog import SaveVersionDialog
    dialog = SaveVersionDialog()
    dialog.exec_()


def _publish_selection():
    from ninja_assets.maya_integration.ui.publish_dialog import PublishDialog
    dialog = PublishDialog()
    dialog.exec_()


def _capture_thumbnail():
    from ninja_assets.maya_integration.utils.thumbnail import capture_viewport
    capture_viewport()


def _force_sync():
    from ninja_assets.maya_integration import plugin
    if plugin._sync_engine:
        plugin._sync_engine.force_full_scan()
    cmds.inViewMessage(amg="<hl>NinjaAssets:</hl> Sync started", pos="topCenter", fade=True)


def _show_settings():
    from ninja_assets.maya_integration.ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog()
    dialog.exec_()
```

### 5.3 Maya Commands (commands.py)

```python
"""
Maya commands for importing/referencing assets
"""
import os
from pathlib import Path
from typing import Optional, List

import maya.cmds as cmds

from ninja_assets.core.models import Asset


def import_asset(asset: Asset, version: Optional[int] = None) -> List[str]:
    """
    Import an asset into the current scene.
    
    Args:
        asset: The asset to import
        version: Specific version number, or None for latest
    
    Returns:
        List of imported node names
    """
    file_path = _get_asset_file_path(asset, version)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Asset file not found: {file_path}")
    
    # Determine file type
    ext = file_path.suffix.lower()
    file_type = {
        '.obj': 'OBJ',
        '.ma': 'mayaAscii',
        '.mb': 'mayaBinary',
        '.fbx': 'FBX'
    }.get(ext)
    
    if not file_type:
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Import
    before = set(cmds.ls(assemblies=True))
    
    cmds.file(
        str(file_path),
        i=True,
        type=file_type,
        ignoreVersion=True,
        mergeNamespacesOnClash=False,
        namespace=asset.name,
        preserveReferences=True,
        options="mo=1"  # OBJ options
    )
    
    after = set(cmds.ls(assemblies=True))
    imported = list(after - before)
    
    v = version or asset.current_version
    cmds.inViewMessage(
        amg=f"<hl>Imported:</hl> {asset.name} v{v}",
        pos='topCenter',
        fade=True
    )
    
    return imported


def reference_asset(asset: Asset, version: Optional[int] = None) -> str:
    """
    Create a reference to an asset.
    
    Args:
        asset: The asset to reference
        version: Specific version number, or None for latest
    
    Returns:
        Reference node name
    """
    file_path = _get_asset_file_path(asset, version)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Asset file not found: {file_path}")
    
    # Only MA/MB can be referenced
    ext = file_path.suffix.lower()
    if ext not in ['.ma', '.mb']:
        raise ValueError(f"Cannot reference {ext} files. Use Import instead.")
    
    file_type = 'mayaAscii' if ext == '.ma' else 'mayaBinary'
    v = version or asset.current_version
    namespace = f"{asset.name}_v{v}"
    
    ref_node = cmds.file(
        str(file_path),
        reference=True,
        type=file_type,
        namespace=namespace,
        mergeNamespacesOnClash=False
    )
    
    cmds.inViewMessage(
        amg=f"<hl>Referenced:</hl> {asset.name} v{v}",
        pos='topCenter',
        fade=True
    )
    
    return ref_node


def _get_asset_file_path(asset: Asset, version: Optional[int] = None) -> Path:
    """Get the file path for a specific asset version"""
    if version is None:
        return Path(asset.path) / asset.current_file
    
    # Find specific version
    for v in asset.versions:
        if v.version == version:
            return Path(asset.path) / v.file
    
    raise ValueError(f"Version {version} not found for asset {asset.name}")
```

#### 5.3.1 v1.1 — Pull-to-Local (commands.py)

```python
def pull_asset(asset: Asset, version: Optional[int], local_root: Union[str, Path]) -> Path:
    """Copy a version's file + sidecar + thumbnail from the remote folder into
    local_root/<category>/<name>/. Idempotent (copy only when missing/older).
    Returns the local file path. Imports no maya modules (pure file ops)."""
```

`import_asset` and `reference_asset` gain an optional `local_root=` parameter:

- `local_root` **None** (default) → import/reference directly from the remote path (v1.0 behavior).
- `local_root` set → `pull_asset(...)` first, then import/reference from the **local copy**.

The preview panel passes `config.local_repo` as `local_root` when the "Pull to local" checkbox
is ticked, and records the resulting path via `cache.set_local_path(uuid, path)`.

---

## 6. User Interface Specifications

### 6.1 Maya Menu Structure

```
NinjaAssets (Menu)
├── Asset Browser...              → Opens main window
├── ─────────────────
├── Save Version                  → Quick save, auto-increment
├── Save Version + Comment...     → Dialog with comment & version edit
├── ─────────────────
├── Publish Selection...          → Publish dialog
├── Import Asset...               → Opens browser in Products tab
├── ─────────────────
├── Capture Thumbnail             → Viewport capture
├── ─────────────────
├── Force Sync                    → Trigger full rescan
└── Settings...                   → Preferences dialog
```

### 6.2 Main Window Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  NinjaAssets                                               [_][□][X]   │
├─────────────────────────────────────────────────────────────────────────┤
│  [Products]  [Scenefiles]  [Setup]                🔄 Synced: 12s ago   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   (Tab content changes based on selection - see 6.3, 6.4 and 6.7)      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

> **v1.1:** A third **Setup** tab is added (see 6.7). When repos are reconfigured or a scan
> completes, the Setup tab emits `repos_changed`, which refreshes the Products tab.

### 6.3 Products Tab (Asset Library)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Products]  [Scenefiles]  [Setup]                🔄 Synced: 12s ago   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────┐   │
│  │ [🔍 Search...     ] │  │  ┌────────┐ ┌────────┐ ┌────────┐      │   │
│  │                     │  │  │  IMG   │ │  IMG   │ │  IMG   │      │   │
│  │ CATEGORIES          │  │  │        │ │        │ │        │      │   │
│  │ ▸ All         (847) │  │  │hero_ro │ │laser_r │ │alien_c │      │   │
│  │   Characters  (124) │  │  │  v3    │ │  v1    │ │  v5    │      │   │
│  │   Props       (392) │  │  └────────┘ └────────┘ └────────┘      │   │
│  │   Environments (89) │  │  ┌────────┐ ┌────────┐ ┌────────┐      │   │
│  │   Vehicles     (67) │  │  │  IMG   │ │  IMG   │ │  IMG   │      │   │
│  │   Weapons     (112) │  │  │        │ │        │ │        │      │   │
│  │   FX           (34) │  │  │wood_ch │ │metal_b │ │rock_fo │      │   │
│  │   Other        (29) │  │  │  v2    │ │  v1    │ │  v3    │      │   │
│  │                     │  │  └────────┘ └────────┘ └────────┘      │   │
│  │ REPOS               │  │                                         │   │
│  │ ▸ All         (847) │  │                                         │   │
│  │   studio      (612) │  │                                         │   │
│  │   archive     (235) │  │                                         │   │
│  └─────────────────────┘  └─────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ PREVIEW                                                             ││
│  │ ┌─────────────┐  hero_robot                                         ││
│  │ │             │  ─────────────────────────────────────              ││
│  │ │  THUMBNAIL  │  Category: Characters     Repo: studio  (local)     ││
│  │ │             │  Author: mike.chen        Polys: 45,000             ││
│  │ │             │  Modified: Jan 17, 2025   Size: 2.5 x 4.0 x 1.5     ││
│  │ └─────────────┘  Tags: robot, hero, mechanical                      ││
│  │                                                                     ││
│  │  Version: [v3 ▼]  Comment: "Fixed topology issues"                  ││
│  │                                                                     ││
│  │  [📥 Import]  [🔗 Reference]  [📂 Open Folder]  [📋 Copy Path]      ││
│  │  ☐ Pull to local before import   (enabled when a local repo is set) ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Interactions:
  • Single-click thumbnail → Select asset, show in preview
  • Double-click thumbnail → Import asset (latest version)
  • Right-click thumbnail  → Context menu (Import, Reference, Copy Path...)
  • Click version dropdown → Select specific version to import
  • REPOS filter (v1.1)    → Show assets from one remote, or All; counts per repo
  • Pull-to-local (v1.1)   → When ticked, Import/Reference copy to the local repo first

Note (v1.1): The asset workflow STATUS (wip/review/approved) is no longer surfaced in the
browser — the sidebar status filter, per-card status badge, and preview status line were
removed. The `status` field remains in the data model / sidecar and Publish dialog; the
cache still supports filtering by it programmatically.
```

### 6.4 Scenefiles Tab (Scene Versioning)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Scenefiles]  [Products]                         🔄 Synced: 12s ago   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Current Scene: G:\scenes\rigging\hero_robot\hero_robot_rig_v005.ma    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ VERSION HISTORY                                    [Sort: Recent ▼] ││
│  │                                                                     ││
│  │  ┌───┬─────────────────────────────────┬──────────────────┬────────┐││
│  │  │   │ File                            │ Comment          │ Author │││
│  │  ├───┼─────────────────────────────────┼──────────────────┼────────┤││
│  │  │ ► │ hero_robot_rig_v005.ma          │ Fixed weights    │ sarah  │││
│  │  │   │ hero_robot_rig_v004.ma          │ Facial controls  │ sarah  │││
│  │  │   │ hero_robot_rig_v003.ma          │ IK/FK switch     │ mike   │││
│  │  │   │ hero_robot_rig_v002.ma          │ Basic skeleton   │ mike   │││
│  │  │   │ hero_robot_rig_v001.ma          │ Initial setup    │ mike   │││
│  │  └───┴─────────────────────────────────┴──────────────────┴────────┘││
│  │                                                                     ││
│  │  Right-click: Open | Open in Explorer | Copy Path                   ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ SAVE NEW VERSION                                                    ││
│  │                                                                     ││
│  │  Version: [006    ]  (editable - next suggested: 006)               ││
│  │                                                                     ││
│  │  Comment: [Added arm twist joints                                 ] ││
│  │                                                                     ││
│  │                                              [💾 Save Version]      ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Interactions:
  • Double-click version row → Open that scene version
  • Version field is editable → User can set custom version number
  • Save Version button → Saves current scene as specified version
```

### 6.5 Save Version Dialog

```
┌─────────────────────────────────────────────────────────────┐
│  Save Scene Version                                    [X] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Current Scene: hero_robot_rigging_v005.ma                 │
│  Location: G:\scenes\rigging\hero_robot\                   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Version Number:  [006         ]                            │
│                   (suggested: 006, editable)                │
│                                                             │
│  Comment:         [                                      ]  │
│                   [                                      ]  │
│                                                             │
│  ☐ Open new version after saving                           │
│                                                             │
│                         [Cancel]     [💾 Save Version]      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.6 Publish Dialog

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Publish Asset                                                     [X] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Selection: 3 objects (pCube1, pSphere1, pCylinder1)                   │
│  Poly Count: 2,450                                                      │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  ASSET DETAILS                                                          │
│  ───────────────────────────────────────────────────────────────────   │
│                                                                         │
│  Name:       [laser_rifle                                            ]  │
│                                                                         │
│  Category:   [Weapons                                              ▼ ]  │
│                                                                         │
│  Version:    [001        ]  (editable for republishing)                 │
│                                                                         │
│  Tags:       [weapon, scifi, rifle                                   ]  │
│              (comma separated)                                          │
│                                                                         │
│  Format:     ○ OBJ (.obj)    ○ Maya ASCII (.ma)    ○ Both               │
│                                                                         │
│  Comment:    [Initial model - needs texturing                        ]  │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  THUMBNAIL                                                              │
│  ───────────────────────────────────────────────────────────────────   │
│                                                                         │
│  ┌─────────────────────┐                                                │
│  │                     │    [📷 Capture from Viewport]                  │
│  │    (preview or      │                                                │
│  │     placeholder)    │    [📂 Load from File...]                      │
│  │                     │                                                │
│  └─────────────────────┘    [🔄 Re-capture]                             │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  Destination: G:\assets\weapons\laser_rifle\                           │
│  Filename:    laser_rifle_v001.obj                                      │
│                                                                         │
│                                      [Cancel]   [📤 Publish Asset]      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Notes:
  • Version is editable (defaults to next version, or 1 for new assets)
  • Existing assets: version dropdown shows history, can overwrite or add
  • Thumbnail: captured from viewport by artist (not auto-generated)
```

### 6.7 Setup Tab (v1.1 — Repos & Library)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Products]  [Scenefiles]  [Setup]                🔄 Synced: 12s ago   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Local Repo ────────────────────────────────────────────────────────┐│
│  │  Local repo:  [ D:\NinjaLocal                          ] [ Browse… ] ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─ Remote Repos ──────────────────────────────────────────────────────┐│
│  │  Cloud/synced folders to scan for assets:                           ││
│  │  ┌─────────────────────────────────────────────────────────────────┐││
│  │  │ studio  — G:\Shared drives\Studio\NinjaAssets                    │││
│  │  │ archive — \\nas\library\ninja_archive                           │││
│  │  └─────────────────────────────────────────────────────────────────┘││
│  │  [ Add… ]  [ Rename… ]  [ Remove ]                                   ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─ Library ───────────────────────────────────────────────────────────┐│
│  │  [ Scan Remotes Now ]    [████████████ scanning… ]                   ││
│  │  Scan complete — 847 asset(s) updated.                               ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                [ Save ]   │
└─────────────────────────────────────────────────────────────────────────┘

Behavior:
  • Local repo: directory picker (QFileDialog.getExistingDirectory). Created on Save.
  • Add remote: pick a folder, then name it (default = folder name).
      - Rejects a folder already registered (path compared via normcase+normpath).
      - Rejects a name that collides case-insensitively with an existing remote.
  • Rename: blocks renaming to a name already used by another remote.
  • Scan Remotes Now: runs a full scan off the UI thread (QThreadPool/QRunnable);
      indeterminate progress bar; on finish shows count and emits repos_changed.
  • Save: persists local_repo + remotes to config.json; emits repos_changed.
  • repos_changed → main window refreshes the Products tab.
```

---

## 7. Sync Engine

### 7.1 Sync Strategy Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SYNC ENGINE LIFECYCLE                           │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │   MAYA STARTUP   │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ 1. QUICK SYNC    │  ◄── Read changelog from last known position
    │    (~1-5 sec)    │      Process new events, update local SQLite
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ 2. UI READY      │  ◄── Artist can browse immediately
    │                  │      All queries hit local SQLite (fast!)
    └────────┬─────────┘
             │
             ▼
    ┌────────────────────────────────────────────────────────────────┐
    │ 3. BACKGROUND LOOP (runs every 30-60 seconds)                 │
    │                                                                │
    │   ┌─────────────────┐                                          │
    │   │ Poll changelog  │ ◄── Check for new lines since last read │
    │   │ for new events  │     Update cache with changes            │
    │   └────────┬────────┘                                          │
    │            │                                                   │
    │            ▼                                                   │
    │   ┌─────────────────┐                                          │
    │   │ Spot-check      │ ◄── Pick 10-20 random cached assets      │
    │   │ random assets   │     Compare .meta.json mtime vs cache    │
    │   │                 │     Catches changes changelog missed     │
    │   └────────┬────────┘                                          │
    │            │                                                   │
    │            ▼                                                   │
    │   ┌─────────────────┐                                          │
    │   │ Emit UI signal  │ ◄── "2 assets updated" notification     │
    │   │ if changes      │     UI refreshes affected items          │
    │   └─────────────────┘                                          │
    └────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────┐
    │ 4. FULL RESCAN   │  ◄── Force Sync menu, Setup-tab "Scan Remotes Now",
    │    (~30-60 sec)  │      or first run on fresh workstation
    └──────────────────┘
```

> **v1.1:** A full rescan iterates **every** registered remote
> (`config.remote_repos()`), tagging each upserted asset with its `source_repo` and caching
> remote thumbnails locally. `found_uuids` is accumulated across all remotes, then a single
> stale-cleanup evicts cache entries absent from every remote. `spot_check` is unchanged
> (asset paths are absolute), and re-upserts preserve `source_repo` / `local_path`.

### 7.2 Conflict Resolution

With 500 artists, conflicts are inevitable. NinjaAssets uses optimistic concurrency:

#### Scenario: Two artists publish same asset simultaneously

```
Timeline:
  T1: Artist A reads meta.json (version: 3)
  T2: Artist B reads meta.json (version: 3)
  T3: Artist A writes meta.json (version: 4) ✓ SUCCESS
  T4: Artist B tries to write (version: 4) ✗ CONFLICT DETECTED

Resolution:
  • Artist B's client detects version mismatch (mtime changed)
  • Dialog: "Asset was updated by Artist A. What would you like to do?"
    - [Save as v5] → B's changes become v5
    - [Overwrite v4] → B replaces A's version (needs confirmation)
    - [Cancel] → Discard B's publish attempt
```

#### Scenario: Changelog corruption from concurrent writes

```
Risk: Two processes append to changelog.jsonl simultaneously
Result: Possibly corrupted line like:
  {"ts":"2025-01{"ts":"2025-01-17T11:46:30Z","type":"asset_created"...

Mitigation:
  • Sync engine uses try/except when parsing each line
  • Corrupted lines are logged and skipped
  • Sidecar files (.meta.json) are SOURCE OF TRUTH
  • Changelog is just "hints" for faster sync
  • Periodic spot-checks catch anything changelog missed
```

---

## 8. Deployment & Installation

### 8.1 Prerequisites

- Maya 2022 or later (Python 3.7+)
- Windows 10/11
- Google Drive Desktop installed and syncing to G: drive
- Network access to shared GDrive

### 8.2 Installation Steps

#### Step 1: Copy package to Maya scripts

```
# Copy ninja_assets folder to:
C:\Users\<username>\Documents\maya\<version>\scripts\ninja_assets\
```

#### Step 2: Add to userSetup.py

```python
# In Documents/maya/<version>/scripts/userSetup.py
import maya.cmds as cmds

def init_ninja_assets():
    try:
        from ninja_assets.maya_integration import plugin
        plugin.initialize()
    except Exception as e:
        cmds.warning(f"Failed to initialize NinjaAssets: {e}")

cmds.evalDeferred(init_ninja_assets)
```

#### Step 3: First Launch

- Open Maya
- NinjaAssets will prompt for username on first launch
- GDrive folder structure is created automatically
- Menu and shelf buttons appear

> **v1.1 first launch:** After the username prompt, open the **Setup** tab to register a
> local repo and one or more remote repos, then click **Scan Remotes Now**. The structure
> below is created for the default remote and applies to each registered remote.

### 8.3 Remote Repo Folder Structure (Auto-Created, per remote)

```
G:\
├── .ninjaassets/
│   ├── changelog.jsonl
│   └── schema_version.txt
├── assets/
│   ├── characters/
│   ├── props/
│   ├── environments/
│   ├── vehicles/
│   ├── weapons/
│   ├── fx/
│   └── other/
└── scenes/
    └── (artist-created folders)
```

### 8.4 Local Data Location

```
%APPDATA%\NinjaAssets\
├── config.json              # User prefs + remotes[] + local_repo
├── cache.sqlite             # Local asset cache (schema v2)
├── thumbnails/              # Cached remote thumbnails (offline library)
└── logs/                    # Debug logs

<local_repo>\                # v1.1: user-chosen pull destination (Setup tab)
└── <category>\<name>\       # local copies of pulled assets (file + sidecar + thumb)
```

---

## 9. Code Examples

### 9.1 Publishing an Asset

```python
from pathlib import Path
from datetime import datetime
from ninja_assets.config import CONFIG
from ninja_assets.core.models import Asset, Version, AssetStatus, ChangelogEvent, EventType
from ninja_assets.core.sidecar import SidecarManager
from ninja_assets.core.changelog import ChangelogManager
from ninja_assets.maya_integration.utils.export import export_selection_obj
from ninja_assets.maya_integration.utils.thumbnail import save_thumbnail


def publish_asset(
    name: str,
    category: str,
    version: int,
    comment: str,
    tags: list,
    thumbnail_path: Path = None
):
    """
    Publish selected Maya objects as a new asset version.
    """
    # Determine destination
    asset_folder = CONFIG.assets_root / category.lower() / name
    asset_folder.mkdir(parents=True, exist_ok=True)
    
    # Export file
    filename = f"{name}_v{version:03d}.obj"
    export_path = asset_folder / filename
    export_path, poly_count = export_selection_obj(export_path)
    
    # Check for existing sidecar
    sidecar_path = asset_folder / f"{name}.meta.json"
    if sidecar_path.exists():
        asset, mtime = SidecarManager.read(sidecar_path)
    else:
        asset = Asset.new(name=name, category=category, path=str(asset_folder))
        mtime = None
    
    # Create version entry
    new_version = Version(
        version=version,
        file=filename,
        created_by=CONFIG.username,
        created_at=datetime.utcnow(),
        comment=comment,
        poly_count=poly_count
    )
    
    # Update asset
    asset.versions.append(new_version)
    asset.current_version = version
    asset.current_file = filename
    asset.tags = tags
    asset.modified_at = datetime.utcnow()
    
    # Handle thumbnail
    if thumbnail_path:
        thumb_name = f"{name}.thumb.jpg"
        save_thumbnail(thumbnail_path, asset_folder / thumb_name)
        asset.thumbnail = thumb_name
    
    # Write sidecar (with conflict detection)
    SidecarManager.write(sidecar_path, asset, expected_mtime=mtime)
    
    # Append to changelog
    changelog = ChangelogManager()
    event = ChangelogEvent(
        timestamp=datetime.utcnow(),
        event_type=EventType.ASSET_CREATED if mtime is None else EventType.ASSET_UPDATED,
        uuid=asset.uuid,
        path=str(asset_folder),
        user=CONFIG.username,
        version=version
    )
    changelog.append(event)
    
    return asset
```

### 9.2 Saving a Scene Version

```python
import maya.cmds as cmds
from pathlib import Path
from datetime import datetime
from ninja_assets.config import CONFIG
from ninja_assets.core.models import Version, SceneMeta
from ninja_assets.core.scene_meta import SceneMetaManager


def save_scene_version(version: int = None, comment: str = ''):
    """
    Save current scene as a new version.
    Version is editable by user - if None, auto-increment.
    """
    # Get current scene path
    current_scene = cmds.file(q=True, sceneName=True)
    if not current_scene:
        raise ValueError("No scene is currently open")
    
    current_path = Path(current_scene)
    scene_folder = current_path.parent
    
    # Load or create scene metadata
    meta_path = scene_folder / ".scene_meta.json"
    if meta_path.exists():
        scene_meta = SceneMetaManager.read(meta_path)
    else:
        scene_meta = SceneMeta(
            scene_name=current_path.stem.rsplit('_v', 1)[0],
            current_version=0,
            versions=[]
        )
    
    # Determine version number
    if version is None:
        version = scene_meta.get_next_version()
    
    # Build new filename
    new_filename = f"{scene_meta.scene_name}_v{version:03d}.ma"
    new_path = scene_folder / new_filename
    
    # Check for version conflict
    existing = scene_meta.get_version(version)
    if existing:
        # Version already exists - confirm overwrite
        result = cmds.confirmDialog(
            title="Version Exists",
            message=f"Version {version} already exists. Overwrite?",
            button=["Overwrite", "Cancel"],
            defaultButton="Cancel"
        )
        if result == "Cancel":
            return None
        # Remove old version entry
        scene_meta.versions = [v for v in scene_meta.versions if v.version != version]
    
    # Save scene
    cmds.file(rename=str(new_path))
    cmds.file(save=True, type="mayaAscii")
    
    # Create version entry
    new_version = Version(
        version=version,
        file=new_filename,
        created_by=CONFIG.username,
        created_at=datetime.utcnow(),
        comment=comment
    )
    
    # Update metadata
    scene_meta.versions.append(new_version)
    scene_meta.versions.sort(key=lambda v: v.version)
    scene_meta.current_version = version
    
    # Write metadata
    SceneMetaManager.write(meta_path, scene_meta)
    
    # Notify user
    cmds.inViewMessage(
        amg=f"<hl>Saved:</hl> {new_filename}",
        pos="topCenter",
        fade=True
    )
    
    return new_path
```

### 9.3 Capturing a Thumbnail

```python
import maya.cmds as cmds
from pathlib import Path
from ninja_assets.config import CONFIG


def capture_viewport(output_path: Path = None, width: int = 256, height: int = 256) -> Path:
    """
    Capture the current viewport as a thumbnail image.
    
    Args:
        output_path: Where to save the image. If None, saves to temp location.
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        Path to the saved thumbnail
    """
    if output_path is None:
        output_path = CONFIG.local_thumbnails_dir / "temp_thumbnail.jpg"
    
    # Get the current model panel
    current_panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=current_panel) != "modelPanel":
        # Find a model panel
        model_panels = cmds.getPanel(type="modelPanel")
        if model_panels:
            current_panel = model_panels[0]
        else:
            raise RuntimeError("No model panel found for thumbnail capture")
    
    # Store current settings
    current_width = cmds.getAttr("defaultRenderGlobals.imageFormat")
    
    # Set to JPEG
    cmds.setAttr("defaultRenderGlobals.imageFormat", 8)  # JPEG
    
    # Capture
    cmds.playblast(
        completeFilename=str(output_path),
        format="image",
        width=width,
        height=height,
        percent=100,
        viewer=False,
        frame=cmds.currentTime(query=True),
        framePadding=0,
        showOrnaments=False,
        compression="jpg",
        quality=CONFIG.thumbnail_quality
    )
    
    # Restore settings
    cmds.setAttr("defaultRenderGlobals.imageFormat", current_width)
    
    return output_path
```

---

## 10. Appendices

### A. Fixed Categories

| Category | Description | Typical Contents |
|----------|-------------|------------------|
| Characters | Rigged or organic models | Humans, creatures, robots |
| Props | Handheld and small objects | Tools, furniture, accessories |
| Environments | Large-scale sets | Buildings, landscapes, rooms |
| Vehicles | Transportation | Cars, ships, aircraft |
| Weapons | Combat items | Guns, swords, explosives |
| FX | Effects geometry | Debris, particles, destruction |
| Other | Uncategorized | Miscellaneous assets |

### B. Status Definitions

| Status | Code | Description |
|--------|------|-------------|
| Work In Progress | wip | Asset is being actively developed |
| Ready for Review | review | Artist considers it ready for feedback |
| Approved | approved | Supervisor has approved for use |

### C. Keyboard Shortcuts

| Action | Shortcut | Context |
|--------|----------|---------|
| Open Asset Browser | Alt+Shift+A | Maya |
| Save Version (quick) | Ctrl+Alt+S | Maya |
| Save Version + Comment | Ctrl+Alt+Shift+S | Maya |
| Publish Selection | Ctrl+Alt+P | Maya |
| Capture Thumbnail | Ctrl+Alt+T | Maya |

### D. File Naming Conventions

```
Assets:
  G:\assets\<category>\<asset_name>\
    <asset_name>_v001.obj
    <asset_name>_v002.obj
    <asset_name>.meta.json
    <asset_name>.thumb.jpg

Scenes (freeform structure):
  G:\scenes\<user_folders>\
    <scene_name>_v001.ma
    <scene_name>_v002.ma
    .scene_meta.json

Local repo (v1.1 — pulled copies mirror the remote layout):
  <local_repo>\<category>\<asset_name>\
    <asset_name>_v003.obj      ← the pulled version file
    <asset_name>.meta.json     ← copied sidecar
    <asset_name>.thumb.jpg     ← copied thumbnail
```

### E. Error Codes

| Code | Name | Description |
|------|------|-------------|
| E001 | SidecarNotFound | Asset .meta.json file missing |
| E002 | SidecarCorrupt | Invalid JSON in sidecar file |
| E003 | ConflictDetected | Asset modified by another user |
| E004 | ExportFailed | Maya export operation failed |
| E005 | ChangelogError | Failed to append to changelog |
| E006 | SyncTimeout | Background sync timed out |
| E007 | GDriveOffline | Cannot access GDrive location |

---

*— End of Document —*