"""Hot-reload support so upgrades apply without restarting Maya.

The installer (drag-and-drop or CLI) overwrites the installed package on disk
and writes a fresh value into ``ninja_assets/_build_stamp.txt``. Python, however,
keeps the *old* modules cached in ``sys.modules`` — which is why a Maya restart is
normally required to pick up new code.

This module bridges that gap. ``launch()`` (wired to the shelf button) compares the
build stamp on disk against the one currently loaded in memory; when they differ it
purges every ``ninja_assets`` module from ``sys.modules`` and re-initializes the
plugin, so re-dragging the installer and then clicking the shelf icon applies the
update with no restart.
"""
import logging
import os
import sys

logger = logging.getLogger("ninja_assets")

STAMP_FILENAME = "_build_stamp.txt"


def _read_stamp(pkg_dir):
    """Return the build stamp written next to the package, or None if absent."""
    path = os.path.join(pkg_dir, STAMP_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _is_stale(on_disk, running):
    """Pure comparison: True when the on-disk build differs from the running one.

    Unknown on-disk stamp (None) means we can't tell, so we never force a reload.
    """
    if not on_disk:
        return False
    return on_disk != running


def is_stale():
    """True when a newer build of the package is sitting on disk, unloaded."""
    import ninja_assets
    pkg_dir = os.path.dirname(ninja_assets.__file__)
    return _is_stale(_read_stamp(pkg_dir), getattr(ninja_assets, "__build__", None))


def hot_reload():
    """Tear down the running plugin, purge cached modules, and re-initialize.

    Returns whatever the freshly imported ``plugin.initialize()`` returns
    (True on success), or False if re-initialization could not be attempted.
    """
    # 1. Cleanly shut down the currently running instance (sync thread, window,
    #    hotkeys). Tolerate any error — we're about to throw the modules away.
    try:
        from ninja_assets.maya_integration import plugin
        plugin.shutdown()
    except Exception:
        logger.exception("NinjaAssets: error during shutdown before reload")

    # 2. Drop every cached ninja_assets module so the next import reads new files.
    #    The currently executing frame keeps its own references alive, so this is
    #    safe even though this module is among those being purged.
    purged = 0
    for name in list(sys.modules):
        if name == "ninja_assets" or name.startswith("ninja_assets."):
            del sys.modules[name]
            purged += 1
    logger.info("NinjaAssets: purged %d cached modules for reload", purged)

    # 3. Re-import from disk and initialize the new code.
    try:
        import ninja_assets  # noqa: F401  (re-runs __init__, refreshes __build__)
        from ninja_assets.maya_integration import plugin as new_plugin
    except Exception:
        logger.exception("NinjaAssets: failed to re-import after reload")
        return False

    # Skip the initial remote scan: the SQLite cache is already warm, so an
    # upgrade shouldn't re-walk every remote. Changelog catch-up / spot-checks
    # (and menu -> Force Sync) still reconcile any changes.
    return new_plugin.initialize(initial_scan=False)


def launch():
    """Shelf entry point: apply any pending update, then open the browser.

    If the on-disk build is newer than the running one, hot-reload first so the
    click that opens the browser also "clears the cache" — no Maya restart needed.
    """
    try:
        if is_stale():
            logger.info("NinjaAssets: newer build detected, reloading")
            hot_reload()
    except Exception:
        logger.exception("NinjaAssets: reload check failed; opening as-is")

    # Re-import in case the modules above were purged and replaced.
    from ninja_assets.maya_integration import plugin
    if not plugin.is_initialized():
        plugin.initialize()
    plugin.show_browser()
