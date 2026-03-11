"""Changelog (append-only JSONL) I/O."""

import json
import logging
import os
from pathlib import Path
from typing import List, Tuple

from .models import ChangelogEvent

logger = logging.getLogger(__name__)


class ChangelogManager:
    """Append-only changelog backed by a .jsonl file."""

    def __init__(self, changelog_path: Path) -> None:
        self.path = changelog_path

    def append(self, event: ChangelogEvent) -> None:
        """Append a single event as one JSON line.

        Uses low-level os.open with O_APPEND for NTFS atomicity.
        """
        line = event.to_json_line() + "\n"
        encoded = line.encode("utf-8")
        fd = os.open(
            str(self.path),
            os.O_APPEND | os.O_WRONLY | os.O_CREAT,
            0o666,
        )
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)

    def read_from(self, byte_offset: int = 0) -> Tuple[List[ChangelogEvent], int]:
        """Read events starting from byte_offset.

        Corrupted lines are skipped with a warning.
        Returns (events, new_byte_offset).
        """
        events: List[ChangelogEvent] = []
        try:
            with open(self.path, "rb") as f:
                f.seek(byte_offset)
                raw = f.read()
        except FileNotFoundError:
            return [], byte_offset

        new_offset = byte_offset + len(raw)
        for line in raw.decode("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(ChangelogEvent.from_json_line(stripped))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Skipping corrupted changelog line: %s (%s)", stripped, exc)

        return events, new_offset

    def read_all(self) -> List[ChangelogEvent]:
        """Read all events from the beginning."""
        events, _ = self.read_from(0)
        return events
