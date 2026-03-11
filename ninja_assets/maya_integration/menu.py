"""NinjaAssets Maya Menu"""

MENU_NAME = "NinjaAssetsMenu"


def create_menu():
    """Create the NinjaAssets menu in Maya menu bar"""
    import maya.cmds as cmds

    # Remove existing menu if present
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)

    # Create menu
    cmds.menu(
        MENU_NAME,
        label="NinjaAssets",
        parent="MayaWindow",
        tearOff=True
    )

    # Asset Browser
    cmds.menuItem(
        label="Asset Browser...",
        command=lambda _: _show_browser(),
        annotation="Open the NinjaAssets browser",
        image="fileOpen.png"
    )

    cmds.menuItem(divider=True)

    # Save Version
    cmds.menuItem(
        label="Save Version",
        command=lambda _: _save_version_quick(),
        annotation="Save scene as new version (auto-increment)",
    )

    # Save Version + Comment
    cmds.menuItem(
        label="Save Version + Comment...",
        command=lambda _: _save_version_dialog(),
        annotation="Save scene as new version with comment and optional version edit",
    )

    cmds.menuItem(divider=True)

    # Publish Selection
    cmds.menuItem(
        label="Publish Selection...",
        command=lambda _: _publish_selection(),
        annotation="Publish selected objects as a new asset",
    )

    # Import Asset
    cmds.menuItem(
        label="Import Asset...",
        command=lambda _: _show_browser(),
        annotation="Open browser to import an asset",
    )

    cmds.menuItem(divider=True)

    # Capture Thumbnail
    cmds.menuItem(
        label="Capture Thumbnail",
        command=lambda _: _capture_thumbnail(),
        annotation="Capture viewport as thumbnail for current asset",
    )

    cmds.menuItem(divider=True)

    # Force Sync
    cmds.menuItem(
        label="Force Sync",
        command=lambda _: _force_sync(),
        annotation="Force a full resync of the asset database",
    )

    # Settings
    cmds.menuItem(
        label="Settings...",
        command=lambda _: _show_settings(),
        annotation="Open NinjaAssets settings",
    )


def _show_browser():
    from ninja_assets.maya_integration import plugin
    plugin.show_browser()



def _save_version_quick():
    from ninja_assets.maya_integration.commands import save_scene_version
    from ninja_assets.maya_integration import plugin
    config = plugin.get_config()
    save_scene_version(config)


def _save_version_dialog():
    from ninja_assets.maya_integration.ui.save_version_dialog import SaveVersionDialog
    dialog = SaveVersionDialog()
    dialog.exec_()


def _publish_selection():
    from ninja_assets.maya_integration.ui.publish_dialog import PublishDialog
    dialog = PublishDialog()
    dialog.exec_()


def _capture_thumbnail():
    from ninja_assets.maya_integration.utils.thumbnail import capture_viewport
    capture_viewport()


def _force_sync():
    import maya.cmds as cmds
    from ninja_assets.maya_integration import plugin
    engine = plugin.get_sync_engine()
    if engine:
        engine.force_full_scan()
    cmds.inViewMessage(amg="<hl>NinjaAssets:</hl> Sync started", pos="topCenter", fade=True)


def _show_settings():
    from ninja_assets.maya_integration.ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog()
    dialog.exec_()
