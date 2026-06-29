"""NinjaAssets Configuration Management."""

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .constants import CATEGORIES, STATUSES


def _default_gdrive_root():
    """Best-guess GDrive root per platform."""
    system = platform.system()
    if system == "Windows":
        return Path("G:/")
    elif system == "Darwin":
        # Google Drive Desktop on macOS
        gdrive = Path.home() / "Google Drive"
        if gdrive.exists():
            return gdrive
        # Newer "My Drive" mount point
        gdrive2 = Path("/Volumes/GoogleDrive/My Drive")
        if gdrive2.exists():
            return gdrive2
        return Path.home() / "Google Drive"
    else:
        return Path.home() / "Google Drive"


def _default_local_data_dir():
    """Local data dir per platform."""
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "NinjaAssets"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "NinjaAssets"
    else:
        return Path.home() / ".ninja_assets"


def _norm_path(path) -> str:
    """Normalize a path for duplicate comparison (case-insensitive on Windows)."""
    return os.path.normcase(os.path.normpath(str(path)))


def find_remote_by_path(remotes: "List[Repo]", path) -> "Optional[Repo]":
    """Return the remote whose path matches ``path`` (normalized), or None."""
    target = _norm_path(path)
    for repo in remotes:
        if _norm_path(repo.path) == target:
            return repo
    return None


def find_remote_by_name(remotes: "List[Repo]", name: str) -> "Optional[Repo]":
    """Return the remote whose name matches ``name`` (case-insensitive), or None."""
    target = name.strip().lower()
    for repo in remotes:
        if repo.name.strip().lower() == target:
            return repo
    return None


@dataclass
class Repo:
    """A remote (cloud/synced) asset repository the tool scans and pulls from."""

    name: str
    path: Path
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

    def to_dict(self) -> dict:
        return {"name": self.name, "path": str(self.path), "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict) -> "Repo":
        return cls(
            name=data["name"],
            path=Path(data["path"]),
            enabled=data.get("enabled", True),
        )


@dataclass
class NinjaConfig:
    """Main configuration container."""

    # Google Drive paths
    gdrive_root: Path = field(default_factory=_default_gdrive_root)

    # Local paths
    local_data_dir: Path = field(default_factory=_default_local_data_dir)

    # Remote repos to scan (cloud/synced folders). When empty, gdrive_root is
    # used as the single default remote (see remote_repos()).
    remotes: List[Repo] = field(default_factory=list)

    # Destination root for "pull to local" copies. None until set in the Setup tab.
    local_repo: Optional[Path] = None

    # Sync settings
    sync_interval_seconds: int = 60
    changelog_poll_interval: int = 30
    spot_check_count: int = 20

    # Thumbnail settings
    thumbnail_size: tuple = (512, 512)
    thumbnail_format: str = "jpg"
    thumbnail_quality: int = 85

    # UI settings
    grid_thumbnail_size: int = 128
    preview_thumbnail_size: int = 400

    # Fixed categories
    categories: List[str] = field(default_factory=lambda: list(CATEGORIES))

    # Valid statuses
    statuses: List[str] = field(default_factory=lambda: list(STATUSES))

    # User identity (set on first launch)
    username: Optional[str] = None

    # Internal flag: when False, skip directory creation in __post_init__
    _ensure_dirs: bool = True

    @property
    def assets_root(self) -> Path:
        return self.gdrive_root / "assets"

    def remote_repos(self) -> List[Repo]:
        """Return enabled remote repos.

        Back-compat: if no remotes are configured, treat gdrive_root as the
        single default remote so existing setups keep working.
        """
        configured = [r for r in self.remotes if r.enabled]
        if configured:
            return configured
        return [Repo("GDrive", self.gdrive_root)]

    def assets_root_for(self, repo: Repo) -> Path:
        """The assets folder inside a given remote repo."""
        return repo.path / "assets"

    @property
    def scenes_root(self) -> Path:
        return self.gdrive_root / "scenes"

    @property
    def pipeline_dir(self) -> Path:
        return self.gdrive_root / ".ninjaassets"

    @property
    def changelog_path(self) -> Path:
        return self.pipeline_dir / "changelog.jsonl"

    @property
    def cache_db_path(self) -> Path:
        return self.local_data_dir / "cache.sqlite"

    @property
    def local_thumbnails_dir(self) -> Path:
        return self.local_data_dir / "thumbnails"

    @property
    def logs_dir(self) -> Path:
        return self.local_data_dir / "logs"

    def __post_init__(self) -> None:
        # Coerce to Path if strings were passed
        if not isinstance(self.gdrive_root, Path):
            self.gdrive_root = Path(self.gdrive_root)
        if not isinstance(self.local_data_dir, Path):
            self.local_data_dir = Path(self.local_data_dir)
        if self.local_repo is not None and not isinstance(self.local_repo, Path):
            self.local_repo = Path(self.local_repo)
        # Coerce any remote paths (e.g. when constructed from dicts/strings)
        self.remotes = [
            r if isinstance(r, Repo) else Repo.from_dict(r) for r in self.remotes
        ]

        if self._ensure_dirs:
            self.local_data_dir.mkdir(parents=True, exist_ok=True)
            self.local_thumbnails_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)
            if self.local_repo is not None:
                self.local_repo.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Save config to local JSON file."""
        config_path = self.local_data_dir / "config.json"
        data = {
            "gdrive_root": str(self.gdrive_root),
            "remotes": [r.to_dict() for r in self.remotes],
            "local_repo": str(self.local_repo) if self.local_repo else None,
            "username": self.username,
            "sync_interval_seconds": self.sync_interval_seconds,
            "changelog_poll_interval": self.changelog_poll_interval,
            "spot_check_count": self.spot_check_count,
            "thumbnail_size": list(self.thumbnail_size),
            "thumbnail_format": self.thumbnail_format,
            "thumbnail_quality": self.thumbnail_quality,
            "grid_thumbnail_size": self.grid_thumbnail_size,
            "preview_thumbnail_size": self.preview_thumbnail_size,
        }
        config_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, local_data_dir: Optional[Path] = None, _ensure_dirs: bool = True) -> "NinjaConfig":
        """Load config from local JSON or return defaults."""
        config = cls(_ensure_dirs=_ensure_dirs)
        if local_data_dir is not None:
            config.local_data_dir = local_data_dir
        config_path = config.local_data_dir / "config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                if "gdrive_root" in data:
                    config.gdrive_root = Path(data["gdrive_root"])
                if "remotes" in data:
                    config.remotes = [
                        Repo.from_dict(r) for r in data["remotes"]
                    ]
                if data.get("local_repo"):
                    config.local_repo = Path(data["local_repo"])
                    if _ensure_dirs:
                        config.local_repo.mkdir(parents=True, exist_ok=True)
                config.username = data.get("username")
                config.sync_interval_seconds = data.get(
                    "sync_interval_seconds", 60
                )
                config.changelog_poll_interval = data.get(
                    "changelog_poll_interval", 30
                )
                config.spot_check_count = data.get("spot_check_count", 20)
                if "thumbnail_size" in data:
                    config.thumbnail_size = tuple(data["thumbnail_size"])
                config.thumbnail_format = data.get("thumbnail_format", "jpg")
                config.thumbnail_quality = data.get("thumbnail_quality", 85)
                config.grid_thumbnail_size = data.get(
                    "grid_thumbnail_size", 100
                )
                config.preview_thumbnail_size = data.get(
                    "preview_thumbnail_size", 250
                )
            except (json.JSONDecodeError, KeyError):
                pass  # Use defaults
        return config
