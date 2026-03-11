"""Maya-specific utility helpers"""
import os
from pathlib import Path


def get_maya_main_window():
    """Get Maya's main window as a QWidget for parenting dialogs."""
    try:
        from ninja_assets.maya_integration.ui import qt_compat
        import maya.OpenMayaUI as omui
        main_win_ptr = omui.MQtUtil.mainWindow()
        if main_win_ptr:
            return qt_compat.wrapInstance(int(main_win_ptr), qt_compat.QWidget)
    except Exception:
        pass
    return None


def get_current_scene_path():
    """Get the current Maya scene file path, or None if untitled."""
    import maya.cmds as cmds
    scene = cmds.file(query=True, sceneName=True)
    return scene if scene else None


def get_scene_folder_and_name(scene_path):
    """Extract folder and base name from a scene path.
    e.g. '/scenes/rigging/hero/hero_rigging_v003.ma' -> (Path('/scenes/rigging/hero'), 'hero_rigging')
    Strips version suffix like _v001, _v002, etc.
    """
    from pathlib import Path
    import re
    p = Path(scene_path)
    folder = p.parent
    stem = p.stem
    # Strip version suffix
    base = re.sub(r'_v\d+$', '', stem)
    return folder, base


def open_folder(folder_path):
    """Open a folder in the OS file browser."""
    from ninja_assets.maya_integration.ui.qt_compat import QDesktopServices, QUrl
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))


def copy_to_clipboard(text):
    """Copy text to system clipboard."""
    from ninja_assets.maya_integration.ui.qt_compat import QApplication
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.setText(str(text))


def load_scene_info():
    """Load current scene info. Returns (scene_path, folder, base_name, scene_meta) or None if no scene open."""
    scene_path = get_current_scene_path()
    if not scene_path:
        return None
    folder, base_name = get_scene_folder_and_name(scene_path)
    from ninja_assets.core.scene_meta import SceneMetaManager
    meta_path = SceneMetaManager.get_meta_path(folder)
    try:
        scene_meta = SceneMetaManager.read(meta_path)
    except Exception:
        from ninja_assets.core.models import SceneMeta
        scene_meta = SceneMeta(scene_name=base_name, current_version=0, versions=[])
    return scene_path, folder, base_name, scene_meta
