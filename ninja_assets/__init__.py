"""NinjaAssets - GDrive-based asset management for Maya."""
import os as _os

__version__ = "0.1.0"


def _load_build():
    """Read the per-install build stamp written by the installer.

    The stamp changes every time the package is (re)installed, so the running
    code can tell when a newer copy has landed on disk and hot-reload itself
    instead of forcing a Maya restart. Falls back to __version__ when no stamp
    is present (e.g. running straight from a checkout), which keeps the value
    stable so no spurious reloads are triggered.
    """
    stamp = _os.path.join(_os.path.dirname(__file__), "_build_stamp.txt")
    try:
        with open(stamp, "r", encoding="utf-8") as f:
            value = f.read().strip()
        return value or __version__
    except OSError:
        return __version__


__build__ = _load_build()


def resource_path(name):
    """Absolute path to a bundled resource under ninja_assets/resources/."""
    return _os.path.join(_os.path.dirname(__file__), "resources", name)

