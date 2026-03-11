"""Sync resolver for processing changelog events into cache updates."""

import logging
from pathlib import Path
from typing import List

from ninja_assets.config import NinjaConfig
from ninja_assets.constants import SIDECAR_SUFFIX
from ninja_assets.core.cache import CacheDB
from ninja_assets.core.exceptions import SidecarError
from ninja_assets.core.models import ChangelogEvent, EventType
from ninja_assets.core.sidecar import SidecarManager

logger = logging.getLogger(__name__)


class SyncResolver:
    """Processes changelog events and updates the cache accordingly."""

    def __init__(self, config: NinjaConfig, cache: CacheDB):
        self.config = config
        self.cache = cache

    def process_changelog_events(self, events: List[ChangelogEvent]) -> List[str]:
        """Process changelog events and update cache accordingly.

        For asset_created/asset_updated: re-read sidecar from disk, upsert cache.
        For asset_deleted: delete from cache.
        For metadata_changed: re-read sidecar from disk, upsert cache.
        For scene_saved: no cache action needed (scenes aren't cached).
        Returns list of changed UUIDs.
        Skip events where sidecar can't be read (log warning).
        """
        changed: List[str] = []

        for event in events:
            if event.event_type == EventType.SCENE_SAVED:
                continue

            if event.event_type == EventType.ASSET_DELETED:
                self.cache.delete_asset(event.uuid)
                changed.append(event.uuid)
                continue

            # For created, updated, metadata_changed: re-read sidecar
            if event.event_type in (
                EventType.ASSET_CREATED,
                EventType.ASSET_UPDATED,
                EventType.METADATA_CHANGED,
            ):
                asset_folder = Path(event.path)
                # Find the sidecar file in the asset folder
                sidecar_path = self._find_sidecar(asset_folder)
                if sidecar_path is None:
                    logger.warning(
                        "No sidecar found for event %s at %s, skipping",
                        event.event_type.value,
                        event.path,
                    )
                    continue

                try:
                    asset, mtime = SidecarManager.read(sidecar_path)
                except SidecarError as exc:
                    logger.warning(
                        "Cannot read sidecar for event %s at %s: %s",
                        event.event_type.value,
                        sidecar_path,
                        exc,
                    )
                    continue

                self.cache.upsert_asset(asset, mtime)
                changed.append(event.uuid)

        return changed

    def _find_sidecar(self, asset_folder: Path) -> Path | None:
        """Find the .meta.json sidecar file in an asset folder."""
        if not asset_folder.is_dir():
            return None

        for item in asset_folder.iterdir():
            if item.is_file() and item.name.endswith(SIDECAR_SUFFIX):
                return item
        return None
