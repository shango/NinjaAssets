"""Asset scanner for discovering and syncing sidecar files on disk."""

import logging
import os
import random
from pathlib import Path
from typing import List

from ninja_assets.config import NinjaConfig
from ninja_assets.constants import SIDECAR_SUFFIX
from ninja_assets.core.cache import CacheDB
from ninja_assets.core.exceptions import SidecarError
from ninja_assets.core.sidecar import SidecarManager

logger = logging.getLogger(__name__)


class AssetScanner:
    """Scans asset folders on disk and syncs metadata into the cache."""

    def __init__(self, config: NinjaConfig, cache: CacheDB):
        self.config = config
        self.cache = cache

    def full_scan(self) -> List[str]:
        """Walk all category folders under config.assets_root using os.scandir().

        For each subfolder, look for .meta.json sidecar files.
        Read each sidecar via SidecarManager.read().
        Upsert into cache via cache.upsert_asset().
        Remove any UUIDs from cache that no longer exist on disk.
        Returns list of changed UUIDs.
        """
        changed: List[str] = []
        found_uuids: set = set()
        assets_root = self.config.assets_root

        if not assets_root.exists():
            logger.warning("Assets root does not exist: %s", assets_root)
            return changed

        # Walk category folders
        try:
            with os.scandir(assets_root) as cat_entries:
                for cat_entry in cat_entries:
                    if not cat_entry.is_dir():
                        continue
                    self._scan_category(
                        Path(cat_entry.path), changed, found_uuids
                    )
        except OSError as exc:
            logger.warning("Error scanning assets root %s: %s", assets_root, exc)
            return changed

        # Remove stale entries from cache
        cached_uuids = set(self.cache.get_all_uuids())
        stale_uuids = cached_uuids - found_uuids
        for uuid in stale_uuids:
            logger.info("Removing stale asset from cache: %s", uuid)
            self.cache.delete_asset(uuid)
            changed.append(uuid)

        return changed

    def _scan_category(
        self, category_path: Path, changed: List[str], found_uuids: set
    ) -> None:
        """Scan a single category folder for asset subfolders with sidecars."""
        try:
            with os.scandir(category_path) as entries:
                for entry in entries:
                    if not entry.is_dir():
                        continue
                    self._scan_asset_folder(
                        Path(entry.path), changed, found_uuids
                    )
        except OSError as exc:
            logger.warning(
                "Error scanning category folder %s: %s", category_path, exc
            )

    def _scan_asset_folder(
        self, folder_path: Path, changed: List[str], found_uuids: set
    ) -> None:
        """Scan an asset folder for sidecar files."""
        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    if not entry.name.endswith(SIDECAR_SUFFIX):
                        continue
                    self._process_sidecar(
                        Path(entry.path), changed, found_uuids
                    )
        except OSError as exc:
            logger.warning(
                "Error scanning asset folder %s: %s", folder_path, exc
            )

    def _process_sidecar(
        self, sidecar_path: Path, changed: List[str], found_uuids: set
    ) -> None:
        """Read a sidecar and upsert into cache if changed."""
        try:
            asset, mtime = SidecarManager.read(sidecar_path)
        except SidecarError as exc:
            logger.warning("Skipping corrupted sidecar %s: %s", sidecar_path, exc)
            return

        found_uuids.add(asset.uuid)

        # Check if cache already has this asset with the same mtime
        cached_mtime = self.cache.get_asset_mtime(asset.uuid)
        if cached_mtime is not None and cached_mtime == mtime:
            return  # No change

        self.cache.upsert_asset(asset, mtime)
        changed.append(asset.uuid)

    def spot_check(self, count: int = 20) -> List[str]:
        """Randomly sample `count` UUIDs from cache.

        For each, compare cache mtime with actual sidecar mtime on disk.
        If mtime differs, re-read sidecar and upsert.
        Returns list of changed UUIDs.
        """
        changed: List[str] = []
        all_uuids = self.cache.get_all_uuids()

        if not all_uuids:
            return changed

        sample_count = min(count, len(all_uuids))
        sampled = random.sample(all_uuids, sample_count)

        for uuid in sampled:
            asset_obj = self.cache.get_asset(uuid)
            if asset_obj is None:
                continue

            # Reconstruct sidecar path from cached asset
            asset_folder = Path(asset_obj.path)
            sidecar_path = SidecarManager.get_sidecar_path(
                asset_folder, asset_obj.name
            )

            try:
                disk_mtime = os.path.getmtime(sidecar_path)
            except OSError:
                # Sidecar no longer exists on disk
                logger.warning(
                    "Sidecar missing during spot check, removing: %s", sidecar_path
                )
                self.cache.delete_asset(uuid)
                changed.append(uuid)
                continue

            cached_mtime = self.cache.get_asset_mtime(uuid)
            if cached_mtime is not None and cached_mtime == disk_mtime:
                continue

            # Mtime differs, re-read
            try:
                asset, mtime = SidecarManager.read(sidecar_path)
            except SidecarError as exc:
                logger.warning(
                    "Error re-reading sidecar during spot check %s: %s",
                    sidecar_path,
                    exc,
                )
                continue

            self.cache.upsert_asset(asset, mtime)
            changed.append(uuid)

        return changed
