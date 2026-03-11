"""Core data models using dataclasses."""

import json
import uuid as uuid_lib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


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
    """A single version of an asset or scene."""

    version: int
    file: str
    created_by: str
    created_at: datetime
    comment: str = ""
    poly_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "version": self.version,
            "file": self.file,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() + "Z",
            "comment": self.comment,
        }
        if self.poly_count is not None:
            result["poly_count"] = self.poly_count
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Version":
        return cls(
            version=data["version"],
            file=data["file"],
            created_by=data["created_by"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip("Z")),
            comment=data.get("comment", ""),
            poly_count=data.get("poly_count"),
        )


@dataclass
class Bounds:
    """Bounding box dimensions."""

    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "Bounds":
        return cls(x=data["x"], y=data["y"], z=data["z"])


@dataclass
class Asset:
    """Complete asset representation."""

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

    @classmethod
    def new(cls, name: str, category: str, path: str) -> "Asset":
        """Create a new asset with generated UUID."""
        return cls(
            uuid=str(uuid_lib.uuid4()),
            name=name,
            path=path,
            current_version=0,
            current_file="",
            category=category,
            status=AssetStatus.WIP,
            modified_at=datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        result = {
            "uuid": self.uuid,
            "name": self.name,
            "version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
            "current_file": self.current_file,
            "type": "model",
            "category": self.category,
            "status": self.status.value,
            "tags": self.tags,
            "thumbnail": self.thumbnail,
            "modified_at": self.modified_at.isoformat() + "Z",
        }
        if self.bounds:
            result["bounds"] = self.bounds.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: str) -> "Asset":
        """Create from sidecar JSON data."""
        bounds = None
        if "bounds" in data and data["bounds"]:
            bounds = Bounds.from_dict(data["bounds"])

        return cls(
            uuid=data["uuid"],
            name=data["name"],
            path=path,
            current_version=data["version"],
            current_file=data["current_file"],
            category=data["category"],
            status=AssetStatus(data.get("status", "wip")),
            modified_at=datetime.fromisoformat(data["modified_at"].rstrip("Z")),
            versions=[Version.from_dict(v) for v in data.get("versions", [])],
            tags=data.get("tags", []),
            thumbnail=data.get("thumbnail"),
            bounds=bounds,
        )

    def get_version(self, version_num: int) -> Optional[Version]:
        """Get a specific version by number."""
        for v in self.versions:
            if v.version == version_num:
                return v
        return None

    def get_latest_version(self) -> Optional[Version]:
        """Get the latest version."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version)


@dataclass
class SceneMeta:
    """Scene file version metadata."""

    scene_name: str
    current_version: int
    versions: List[Version] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_name": self.scene_name,
            "current_version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneMeta":
        return cls(
            scene_name=data["scene_name"],
            current_version=data["current_version"],
            versions=[Version.from_dict(v) for v in data.get("versions", [])],
        )

    def get_next_version(self) -> int:
        """Get the next version number."""
        if not self.versions:
            return 1
        return max(v.version for v in self.versions) + 1


@dataclass
class ChangelogEvent:
    """An event in the changelog."""

    timestamp: datetime
    event_type: EventType
    uuid: str
    path: str
    user: str
    version: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        data = {
            "ts": self.timestamp.isoformat() + "Z",
            "type": self.event_type.value,
            "uuid": self.uuid,
            "path": self.path,
            "user": self.user,
        }
        if self.version is not None:
            data["v"] = self.version
        data.update(self.extra)
        return json.dumps(data, separators=(",", ":"))

    @classmethod
    def from_json_line(cls, line: str) -> "ChangelogEvent":
        data = json.loads(line)
        known_keys = {'ts', 'type', 'uuid', 'path', 'user', 'v'}
        extra = {k: v for k, v in data.items() if k not in known_keys}
        return cls(
            timestamp=datetime.fromisoformat(data["ts"].rstrip("Z")),
            event_type=EventType(data["type"]),
            uuid=data.get("uuid", ""),
            path=data["path"],
            user=data["user"],
            version=data.get("v"),
            extra=extra,
        )
