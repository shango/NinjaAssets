"""Keyboard shortcut registration for Maya."""

HOTKEYS = {
    'ninja_browser': {
        'name': 'NinjaAssets_Browser',
        'key': 'A',
        'alt': True,
        'shift': True,
        'ctrl': False,
        'command': 'from ninja_assets.maya_integration import plugin; plugin.show_browser()',
        'annotation': 'Open NinjaAssets Browser',
    },
    'ninja_save_version': {
        'name': 'NinjaAssets_SaveVersion',
        'key': 'S',
        'alt': True,
        'shift': False,
        'ctrl': True,
        'command': 'from ninja_assets.maya_integration.menu import _save_version_quick; _save_version_quick()',
        'annotation': 'Save Version (quick)',
    },
    'ninja_save_comment': {
        'name': 'NinjaAssets_SaveComment',
        'key': 'S',
        'alt': True,
        'shift': True,
        'ctrl': True,
        'command': 'from ninja_assets.maya_integration.menu import _save_version_dialog; _save_version_dialog()',
        'annotation': 'Save Version + Comment',
    },
    'ninja_publish': {
        'name': 'NinjaAssets_Publish',
        'key': 'P',
        'alt': True,
        'shift': False,
        'ctrl': True,
        'command': 'from ninja_assets.maya_integration.menu import _publish_selection; _publish_selection()',
        'annotation': 'Publish Selection',
    },
    'ninja_thumbnail': {
        'name': 'NinjaAssets_Thumbnail',
        'key': 'T',
        'alt': True,
        'shift': False,
        'ctrl': True,
        'command': 'from ninja_assets.maya_integration.menu import _capture_thumbnail; _capture_thumbnail()',
        'annotation': 'Capture Thumbnail',
    },
}


def register_hotkeys():
    """Register all NinjaAssets keyboard shortcuts in Maya."""
    import maya.cmds as cmds

    for key, info in HOTKEYS.items():
        cmd_name = info['name']

        # Create named command
        if cmds.runTimeCommand(cmd_name, exists=True):
            cmds.runTimeCommand(cmd_name, edit=True, delete=True)

        cmds.runTimeCommand(
            cmd_name,
            annotation=info['annotation'],
            command=info['command'],
            commandLanguage='python',
        )

        # Create name command for hotkey binding
        name_cmd = cmd_name + 'NameCommand'
        cmds.nameCommand(
            name_cmd,
            annotation=info['annotation'],
            command=cmd_name,
            sourceType='mel',
        )

        # Set hotkey
        cmds.hotkey(
            keyShortcut=info['key'],
            altModifier=info['alt'],
            shiftModifier=info.get('shift', False),
            ctrlModifier=info.get('ctrl', False),
            name=name_cmd,
        )


def unregister_hotkeys():
    """Remove NinjaAssets hotkeys."""
    import maya.cmds as cmds

    for key, info in HOTKEYS.items():
        cmd_name = info['name']
        try:
            cmds.hotkey(
                keyShortcut=info['key'],
                altModifier=info['alt'],
                shiftModifier=info.get('shift', False),
                ctrlModifier=info.get('ctrl', False),
                name='',
            )
            if cmds.runTimeCommand(cmd_name, exists=True):
                cmds.runTimeCommand(cmd_name, edit=True, delete=True)
        except Exception:
            pass
