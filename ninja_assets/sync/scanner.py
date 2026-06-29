"""Asset scanner for discovering and syncing sidecar files on disk."""

import logging
import os
import random
import shutil
from pathlib import Path
from typing import List

from ninja_assets.config import NinjaConfig, Repo
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
        """Scan every configured remote repo and sync metadata into the cache.

        For each remote (config.remote_repos()), recursively walk its assets
        tree, read .meta.json sidecars found at any depth, and upsert into the
        cache tagged with the remote's name (source_repo). Found UUIDs are
        accumulated across all remotes; afterwards any cached UUID not found in
        any remote is evicted. Returns list of changed UUIDs.

        Assets are identified by the UUID in their sidecar, not by path, so a
        moved or renamed folder is absorbed cheaply: the asset is rediscovered
        by the tree walk and only its cached path is refreshed (no re-upsert,
        no thumbnail re-copy). This is also the authoritative deletion pass.
        """
        changed: List[str] = []
        found_uuids: set = set()

        for repo in self.config.remote_repos():
            self._scan_repo(repo, changed, found_uuids)

        # Remove stale entries from cache (absent from every remote)
        cached_uuids = set(self.cache.get_all_uuids())
        stale_uuids = cached_uuids - found_uuids
        for uuid in stale_uuids:
            logger.info("Removing stale asset from cache: %s", uuid)
            self.cache.delete_asset(uuid)
            changed.append(uuid)

        return changed

    def _scan_repo(
        self, repo: Repo, changed: List[str], found_uuids: set
    ) -> None:
        """Recursively scan the assets tree of a single remote repo."""
        assets_root = self.config.assets_root_for(repo)
        if not assets_root.exists():
            logger.warning(
                "Assets root for repo %r does not exist: %s", repo.name, assets_root
            )
            return

        self._scan_tree(assets_root, changed, found_uuids, repo.name)

    def _scan_tree(
        self,
        path: Path,
        changed: List[str],
        found_uuids: set,
        source_repo: str,
    ) -> None:
        """Recursively walk a folder, processing every sidecar at any depth.

        Asset folders may be nested arbitrarily deep within a category (e.g.
        assets/Props/Weapons/Swords/excalibur/). Symlinked directories are not
        followed, to avoid cycles during recursion.
        """
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        self._scan_tree(
                            Path(entry.path), changed, found_uuids, source_repo
                        )
                    elif entry.is_file() and entry.name.endswith(SIDECAR_SUFFIX):
                        self._process_sidecar(
                            Path(entry.path), changed, found_uuids, source_repo
                        )
        except OSError as exc:
            logger.warning("Error scanning folder %s: %s", path, exc)

    def _process_sidecar(
        self,
        sidecar_path: Path,
        changed: List[str],
        found_uuids: set,
        source_repo: str,
    ) -> None:
        """Read a sidecar and sync it into the cache.

        The folder we found the sidecar in is the source of truth for the
        asset's location. Moving or renaming a folder leaves the sidecar's
        mtime untouched and may leave the path recorded inside the JSON stale,
        so we trust the discovery location. When *only* the location changed
        (same mtime, different path), we refresh the cached path cheaply
        instead of re-upserting and re-copying the thumbnail.
        """
        try:
            asset, mtime = SidecarManager.read(sidecar_path)
        except SidecarError as exc:
            logger.warning("Skipping corrupted sidecar %s: %s", sidecar_path, exc)
            return

        found_uuids.add(asset.uuid)
        asset.path = str(sidecar_path.parent)

        state = self.cache.get_meta_state(asset.uuid)
        if state is not None and state[0] == mtime:
            # Content unchanged. Absorb a move by refreshing only the path.
            if state[1] != asset.path:
                logger.info(
                    "Asset %s moved, updating path: %s -> %s",
                    asset.uuid,
                    state[1],
                    asset.path,
                )
                self.cache.set_path(asset.uuid, asset.path)
                changed.append(asset.uuid)
            return

        self.cache.upsert_asset(asset, mtime, source_repo=source_repo)
        self._cache_thumbnail(asset)
        changed.append(asset.uuid)

    def _cache_thumbnail(self, asset) -> None:
        """Copy a remote asset thumbnail into the local thumbnail cache.

        Cheap (file copy only) so a scan can build an offline screenshot
        library. Rendering thumbnails for assets that lack one stays in the
        ninja-migrate path. Failures are non-fatal.
        """
        if not asset.thumbnail:
            return
        src = Path(asset.path) / asset.thumbnail
        if not src.exists():
            return
        dest_dir = self.config.local_thumbnails_dir
        dest = dest_dir / f"{asset.uuid}{src.suffix}"
        try:
            if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            self.cache.set_thumbnail_local(asset.uuid, str(dest))
        except OSError as exc:
            logger.warning("Could not cache thumbnail for %s: %s", asset.uuid, exc)

    def spot_check(self, count: int = 20) -> List[str]:
        """Randomly sample `count` UUIDs from cache.

        For each, compare cache mtime with actual sidecar mtime on disk.
        If mtime differs, re-read sidecar and upsert.
        Returns list of changed UUIDs.

        This is a cheap drift detector, not the deletion authority. A sidecar
        that's missing at the cached path usually means the folder was moved
        (a move leaves mtime untouched), not deleted, so we do not evict here —
        a stale-path guess isn't trustworthy. ``full_scan`` walks the whole
        tree and is the only place that relocates moved assets or evicts ones
        that are truly gone.
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
                # Not where the cache thinks it is — most likely moved, not
                # deleted. Defer to full_scan, which has whole-tree ground
                # truth; evicting here would churn a live asset out and back.
                logger.debug(
                    "Sidecar not at cached path during spot check: %s", sidecar_path
                )
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
