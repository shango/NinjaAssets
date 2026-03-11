"""
NinjaAssets Installer — Drag-and-Drop for Maya

Drag this file into Maya's viewport to install NinjaAssets.
It will copy the ninja_assets package into your Maya scripts folder
and set it up to load automatically on startup.
"""
import os
import shutil
import sys

# --- Find where this script lives (the NinjaAssets folder) ---
_THIS_FILE = os.path.abspath(__file__ if "__file__" in dir() else
    # Maya's drag-and-drop sometimes uses a different mechanism
    sys.argv[0] if sys.argv else "")

_NINJA_ROOT = os.path.dirname(_THIS_FILE)
_PACKAGE_SRC = os.path.join(_NINJA_ROOT, "ninja_assets")

# --- Startup hook that goes into userSetup.py ---
_HOOK_START = "# --- NinjaAssets ---"
_HOOK_END = "# --- /NinjaAssets ---"
_SETUP_HOOK = '''
# --- NinjaAssets ---
def _init_ninja_assets():
    try:
        from ninja_assets.maya_integration import plugin
        plugin.initialize()
    except Exception as e:
        import maya.cmds as cmds
        cmds.warning("Failed to initialize NinjaAssets: {}".format(e))

import maya.cmds as cmds
cmds.evalDeferred(_init_ninja_assets)
# --- /NinjaAssets ---
'''


def _get_scripts_dir():
    """Find the current Maya version's scripts directory."""
    import maya.cmds as cmds
    version = cmds.about(version=True).split()[0]  # e.g. "2024"
    import platform
    system = platform.system()
    if system == "Windows":
        base = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                            "Documents", "maya")
    elif system == "Darwin":
        base = os.path.join(os.path.expanduser("~"),
                            "Library", "Preferences", "Autodesk", "maya")
    else:
        base = os.path.join(os.path.expanduser("~"), "maya")

    scripts_dir = os.path.join(base, version, "scripts")
    return scripts_dir


def _install():
    """Copy ninja_assets into Maya's scripts folder and add startup hook."""
    import maya.cmds as cmds

    if not os.path.isdir(_PACKAGE_SRC):
        cmds.warning("NinjaAssets: Cannot find ninja_assets folder at: " + _PACKAGE_SRC)
        cmds.warning("Make sure you unzipped the entire NinjaAssets folder first.")
        return

    scripts_dir = _get_scripts_dir()
    os.makedirs(scripts_dir, exist_ok=True)
    target = os.path.join(scripts_dir, "ninja_assets")

    # Remove old installation if present
    if os.path.islink(target):
        os.unlink(target)
    elif os.path.isdir(target):
        shutil.rmtree(target)

    # Copy the package
    shutil.copytree(_PACKAGE_SRC, target)

    # Add startup hook to userSetup.py
    setup_file = os.path.join(scripts_dir, "userSetup.py")
    existing = ""
    if os.path.exists(setup_file):
        with open(setup_file, "r", encoding="utf-8") as f:
            existing = f.read()

    if _HOOK_START not in existing:
        with open(setup_file, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(_SETUP_HOOK)

    # Done — tell the artist
    msg = (
        "NinjaAssets installed successfully!\n\n"
        "Restart Maya to start using NinjaAssets.\n\n"
        "Files installed to:\n" + scripts_dir
    )
    cmds.confirmDialog(
        title="NinjaAssets Installer",
        message=msg,
        button=["OK"],
        defaultButton="OK",
    )
    print("NinjaAssets: Installed to " + scripts_dir)
    print("NinjaAssets: Restart Maya to load.")


# --- Run on drag-and-drop ---
try:
    import maya.cmds
    _install()
except ImportError:
    # Not running inside Maya
    print("This script is meant to be dragged into Maya's viewport.")
    print("For command-line install, use: python -m ninja_assets.cli.install")
