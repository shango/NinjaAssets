"""Sidecar file I/O for asset metadata."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..constants import SIDECAR_SUFFIX
from .exceptions import ConflictError, SidecarError
from .models import Asset, AssetStatus


class SidecarManager:
    """Static methods for reading/writing .meta.json sidecar files."""

    @staticmethod
    def get_sidecar_path(asset_folder: Path, asset_name: str) -> Path:
        """Return the sidecar path for an asset."""
        return asset_folder / f"{asset_name}{SIDECAR_SUFFIX}"

    @staticmethod
    def read(sidecar_path: Path) -> Tuple[Asset, float]:
        """Read a sidecar JSON file and return (Asset, file_mtime).

        Raises SidecarError if file not found or JSON is invalid.
        """
        try:
            mtime = os.path.getmtime(sidecar_path)
            text = sidecar_path.read_text(encoding="utf-8")
            data = json.loads(text)
            asset = Asset.from_dict(data, path=str(sidecar_path.parent))
            return asset, mtime
        except FileNotFoundError:
            raise SidecarError(f"Sidecar not found: {sidecar_path}")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise SidecarError(f"Invalid sidecar {sidecar_path}: {exc}")

    @staticmethod
    def write(
        sidecar_path: Path,
        asset: Asset,
        expected_mtime: Optional[float] = None,
    ) -> float:
        """Atomic write via temp file + os.replace().

        If expected_mtime is provided, check current mtime first and raise
        ConflictError if it differs. Returns the new file mtime.
        """
        if expected_mtime is not None:
            try:
                current_mtime = os.path.getmtime(sidecar_path)
            except FileNotFoundError:
                raise ConflictError(
                    f"Sidecar disappeared: {sidecar_path}"
                )
            if current_mtime != expected_mtime:
                raise ConflictError(
                    f"Sidecar modified by another process: {sidecar_path} "
                    f"(expected mtime {expected_mtime}, got {current_mtime})"
                )

        temp_path = sidecar_path.with_suffix(".tmp")
        data = asset.to_dict()
        text = json.dumps(data, indent=2, ensure_ascii=False)
        temp_path.write_text(text, encoding="utf-8")
        os.replace(str(temp_path), str(sidecar_path))
        return os.path.getmtime(sidecar_path)

    @staticmethod
    def exists(asset_folder: Path, asset_name: str) -> bool:
        """Check whether a sidecar file exists."""
        path = SidecarManager.get_sidecar_path(asset_folder, asset_name)
        return path.exists()

    @staticmethod
    def create_minimal(
        asset_folder: Path,
        asset_name: str,
        asset_file: str,
        category: str,
        user: str,
    ) -> Asset:
        """Create a minimal sidecar for an unmanaged asset (migration helper).

        Writes the sidecar to disk and returns the Asset.
        """
        asset = Asset.new(name=asset_name, category=category, path=str(asset_folder))
        asset.current_file = asset_file
        asset.current_version = 1
        asset.modified_at = datetime.utcnow()

        sidecar_path = SidecarManager.get_sidecar_path(asset_folder, asset_name)
        SidecarManager.write(sidecar_path, asset)
        return asset
