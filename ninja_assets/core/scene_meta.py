"""Scene metadata file I/O."""

import json
from pathlib import Path

from ..constants import SCENE_META_FILE
from .exceptions import SidecarError
from .models import SceneMeta


class SceneMetaManager:
    """Static methods for reading/writing .scene_meta.json files."""

    @staticmethod
    def get_meta_path(scene_folder: Path) -> Path:
        """Return the scene meta path for a scene folder."""
        return scene_folder / SCENE_META_FILE

    @staticmethod
    def read(meta_path: Path) -> SceneMeta:
        """Read and return a SceneMeta.

        Raises SidecarError if file not found or JSON is invalid.
        """
        try:
            text = meta_path.read_text(encoding="utf-8")
            data = json.loads(text)
            return SceneMeta.from_dict(data)
        except FileNotFoundError:
            raise SidecarError(f"Scene meta not found: {meta_path}")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise SidecarError(f"Invalid scene meta {meta_path}: {exc}")

    @staticmethod
    def write(meta_path: Path, scene_meta: SceneMeta) -> None:
        """Write SceneMeta to disk as JSON."""
        text = json.dumps(scene_meta.to_dict(), indent=2, ensure_ascii=False)
        meta_path.write_text(text, encoding="utf-8")

    @staticmethod
    def ensure(scene_folder: Path, scene_name: str) -> SceneMeta:
        """Read existing SceneMeta or create a new empty one."""
        meta_path = SceneMetaManager.get_meta_path(scene_folder)
        try:
            return SceneMetaManager.read(meta_path)
        except SidecarError:
            scene_meta = SceneMeta(
                scene_name=scene_name,
                current_version=0,
                versions=[],
            )
            SceneMetaManager.write(meta_path, scene_meta)
            return scene_meta
