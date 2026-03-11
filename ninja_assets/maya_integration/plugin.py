"""
NinjaAssets Maya Plugin Entry Point.

Add to userSetup.py:
    import maya.cmds as cmds
    def init_ninja_assets():
        from ninja_assets.maya_integration import plugin
        plugin.initialize()
    cmds.evalDeferred(init_ninja_assets)
"""
import sys
import logging
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

logger = logging.getLogger("ninja_assets")

# Global references
_sync_engine = None
_main_window = None
_config = None
_cache = None


def get_config():
    """Get the active NinjaConfig instance."""
    return _config


def get_cache():
    """Get the active CacheDB instance."""
    return _cache


def get_sync_engine():
    """Get the active SyncEngine instance."""
    return _sync_engine


def initialize(config=None):
    """
    Initialize NinjaAssets.

    Args:
        config: Optional NinjaConfig. If None, loads from disk.

    Returns:
        True on success, False on failure.
    """
    import maya.cmds as cmds
    global _sync_engine, _config, _cache

    # Load or use provided config
    if config is not None:
        _config = config
    else:
        from ninja_assets.config import NinjaConfig
        _config = NinjaConfig.load()

    # Setup logging
    _setup_logging(_config.logs_dir)

    # Check for username
    if not _config.username:
        from ninja_assets.maya_integration.ui.username_dialog import prompt_username
        username = prompt_username()
        if username:
            _config.username = username
            _config.save()
        else:
            cmds.warning("NinjaAssets: Username required to continue")
            return False

    # Check GDrive accessibility
    if not _config.gdrive_root.exists():
        from ninja_assets.core.exceptions import GDriveOfflineError
        cmds.warning(
            f"NinjaAssets: GDrive not accessible at {_config.gdrive_root}. "
            "Check Google Drive Desktop is running."
        )
        logger.error("GDrive root not found: %s", _config.gdrive_root)
        return False

    # Ensure GDrive structure exists
    _ensure_gdrive_structure()

    # Initialize cache
    from ninja_assets.core.cache import CacheDB
    _cache = CacheDB(_config.cache_db_path)

    # Start sync engine in background
    from ninja_assets.sync.engine import SyncEngine
    _sync_engine = SyncEngine(
        config=_config,
        cache=_cache,
        on_assets_changed=_on_assets_changed
    )
    _sync_engine.start()

    # Create menu and shelf
    from ninja_assets.maya_integration.menu import create_menu
    from ninja_assets.maya_integration.shelf import add_shelf_buttons
    create_menu()
    add_shelf_buttons()

    # Register keyboard shortcuts
    from ninja_assets.maya_integration.hotkeys import register_hotkeys
    register_hotkeys()

    logger.info("NinjaAssets initialized for user: %s", _config.username)
    print(f"NinjaAssets initialized for user: {_config.username}")
    return True


def _setup_logging(logs_dir):
    """Configure file-based logging with rotation."""
    import logging.handlers

    log_dir = logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ninja_assets.log"

    handler = logging.handlers.RotatingFileHandler(
        str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    root_logger = logging.getLogger("ninja_assets")
    if not root_logger.handlers:
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)


def _ensure_gdrive_structure():
    """Create required GDrive directories if missing."""
    from ninja_assets.cli.init_gdrive import init_gdrive
    init_gdrive(_config.gdrive_root, quiet=True)


def _on_assets_changed(changed_uuids):
    """Callback from sync engine. Marshal to Qt main thread if window is open."""
    if _main_window is not None:
        try:
            _main_window.on_assets_changed(changed_uuids)
        except Exception:
            logger.exception("Error notifying UI of asset changes")


def show_browser():
    """Show the NinjaAssets browser window."""
    global _main_window

    if _main_window is None:
        from ninja_assets.maya_integration.ui.main_window import NinjaAssetsWindow
        _main_window = NinjaAssetsWindow()

    _main_window.show()
    _main_window.raise_()
    _main_window.activateWindow()


def shutdown():
    """Cleanup on Maya exit."""
    global _sync_engine, _main_window

    from ninja_assets.maya_integration.hotkeys import unregister_hotkeys
    unregister_hotkeys()

    if _sync_engine:
        _sync_engine.stop()
        _sync_engine = None
    if _main_window:
        _main_window.close()
        _main_window = None
