"""Background sync engine coordinating scanner, resolver, and changelog."""

import logging
import threading
import time
from typing import Callable, List, Optional

from ninja_assets.config import NinjaConfig
from ninja_assets.core.cache import CacheDB
from ninja_assets.core.changelog import ChangelogManager
from ninja_assets.sync.resolver import SyncResolver
from ninja_assets.sync.scanner import AssetScanner

logger = logging.getLogger(__name__)


class SyncEngine:
    """Background sync engine that keeps the cache in sync with disk."""

    def __init__(
        self,
        config: NinjaConfig,
        cache: CacheDB,
        on_assets_changed: Optional[Callable[[List[str]], None]] = None,
    ):
        self.config = config
        self.cache = cache
        self.on_assets_changed = on_assets_changed
        self._scanner = AssetScanner(config, cache)
        self._resolver = SyncResolver(config, cache)
        self._changelog = ChangelogManager(config.changelog_path)
        self._stop_event = threading.Event()
        self._force_scan_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._changelog_offset: int = 0

    def start(self):
        """Start background sync thread. Thread is daemon=True."""
        saved = self.cache.get_sync_state("changelog_offset")
        if saved is not None:
            self._changelog_offset = int(saved)
        self._stop_event.clear()
        self._force_scan_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal stop and wait for thread to finish (timeout 5s)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def force_full_scan(self):
        """Trigger a full scan (can be called from UI thread)."""
        self._force_scan_event.set()

    def quick_sync(self) -> List[str]:
        """Changelog catchup - read new events since last offset.

        Process via resolver. Save new offset.
        Returns changed UUIDs.
        Can be called directly (not just from background thread).
        """
        events, new_offset = self._changelog.read_from(self._changelog_offset)
        changed: List[str] = []

        if events:
            changed = self._resolver.process_changelog_events(events)

        if new_offset != self._changelog_offset:
            self._changelog_offset = new_offset
            self.cache.set_sync_state("changelog_offset", str(new_offset))

        return changed

    def _run(self):
        """Background loop:
        1. Initial full scan
        2. Loop every changelog_poll_interval seconds:
           a. Quick sync (changelog catchup)
           b. Every sync_interval_seconds: spot check
           c. If force_full_scan requested: full scan
           d. Check stop event
        """
        # Initial full scan
        try:
            changed = self._scanner.full_scan()
            self._notify_changes(changed)
        except Exception:
            logger.exception("Error during initial full scan")

        last_spot_check = time.monotonic()

        while not self._stop_event.is_set():
            # Wait for poll interval or stop signal
            stopped = self._stop_event.wait(
                timeout=self.config.changelog_poll_interval
            )
            if stopped:
                break

            # Quick sync (changelog catchup)
            try:
                changed = self.quick_sync()
                self._notify_changes(changed)
            except Exception:
                logger.exception("Error during quick sync")

            # Periodic spot check
            now = time.monotonic()
            if now - last_spot_check >= self.config.sync_interval_seconds:
                try:
                    changed = self._scanner.spot_check(
                        self.config.spot_check_count
                    )
                    self._notify_changes(changed)
                except Exception:
                    logger.exception("Error during spot check")
                last_spot_check = now

            # Force full scan if requested
            if self._force_scan_event.is_set():
                self._force_scan_event.clear()
                try:
                    changed = self._scanner.full_scan()
                    self._notify_changes(changed)
                except Exception:
                    logger.exception("Error during forced full scan")

    def _notify_changes(self, changed_uuids: List[str]):
        """Call on_assets_changed callback if set and uuids not empty."""
        if changed_uuids and self.on_assets_changed is not None:
            try:
                self.on_assets_changed(changed_uuids)
            except Exception:
                logger.exception("Error in on_assets_changed callback")
