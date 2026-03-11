"""NinjaAssets Maya Shelf Integration"""

SHELF_BUTTON_NAME = "NinjaAssetsShelfBtn"


def add_shelf_buttons():
    """Add NinjaAssets button to the current shelf."""
    import maya.cmds as cmds
    import maya.mel as mel

    # Get the currently active shelf
    top_shelf = mel.eval("$tmpVar=$gShelfTopLevel")
    if not top_shelf:
        return

    current_shelf = cmds.tabLayout(top_shelf, query=True, selectTab=True)
    if not current_shelf:
        return

    # Remove existing button if present
    existing = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
    for child in existing:
        if cmds.shelfButton(child, query=True, exists=True):
            try:
                label = cmds.shelfButton(child, query=True, label=True)
                if label == "NinjaAssets":
                    cmds.deleteUI(child)
            except Exception:
                pass

    # Add shelf button
    cmds.shelfButton(
        SHELF_BUTTON_NAME,
        parent=current_shelf,
        label="NinjaAssets",
        annotation="Open NinjaAssets Browser (Alt+Shift+A)",
        image1="fileOpen.png",
        command=(
            "from ninja_assets.maya_integration import plugin; "
            "plugin.show_browser()"
        ),
        sourceType="python"
    )
