"""
NinjaAssets Installer — Drag-and-Drop for Maya

Drag this file into Maya's viewport to install NinjaAssets.
It copies the ninja_assets package into your Maya scripts folder and sets it up
to load automatically on startup.

Upgrading: drag this file in again to copy the new version, then click the
NinjaAssets shelf button. The shelf button detects the newer build and reloads
it in place — no Maya restart required.
"""
import os
import shutil
import sys
import time
import uuid

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


def _write_build_stamp(target_dir):
    """Write a unique per-install stamp so the running plugin can detect upgrades.

    Pure file I/O (no maya import) so it's unit-testable. Returns the value.
    """
    value = "{}-{}".format(int(time.time()), uuid.uuid4().hex[:8])
    with open(os.path.join(target_dir, "_build_stamp.txt"), "w", encoding="utf-8") as f:
        f.write(value)
    return value


def _is_already_running():
    """True when a NinjaAssets plugin is already initialized in this session."""
    mod = sys.modules.get("ninja_assets.maya_integration.plugin")
    if not mod:
        return False
    try:
        return mod.is_initialized()
    except AttributeError:
        # Older installed version without is_initialized(); fall back to cache ref.
        return getattr(mod, "_cache", None) is not None


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

    # An upgrade is when a plugin is already live in this Maya session.
    upgrading = _is_already_running()

    # Remove old installation if present
    if os.path.islink(target):
        os.unlink(target)
    elif os.path.isdir(target):
        shutil.rmtree(target)

    # Copy the package and stamp this build so the running plugin can detect it.
    shutil.copytree(_PACKAGE_SRC, target)
    _write_build_stamp(target)

    # Make sure the installed copy is importable this session.
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

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

    if upgrading:
        # Old modules are still cached in this session. Don't reload mid-drag;
        # the shelf button reconciles the new build on the next click.
        msg = (
            "NinjaAssets updated!\n\n"
            "Click the NinjaAssets shelf button to apply the update.\n"
            "No restart required.\n\n"
            "Updated files in:\n" + scripts_dir
        )
        cmds.confirmDialog(
            title="NinjaAssets Updater",
            message=msg,
            button=["OK"],
            defaultButton="OK",
        )
        print("NinjaAssets: Updated in " + scripts_dir)
        print("NinjaAssets: Click the shelf button to apply (no restart needed).")
        return

    # Fresh install — nothing is loaded yet, so initialize right now. No restart.
    started = _try_initialize()
    if started:
        msg = (
            "NinjaAssets installed and ready!\n\n"
            "Look for the NinjaAssets shelf button and menu.\n"
            "No restart required.\n\n"
            "Files installed to:\n" + scripts_dir
        )
    else:
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


def _try_initialize():
    """Import the freshly installed package and initialize it. Returns success."""
    try:
        from ninja_assets.maya_integration import plugin
        return bool(plugin.initialize())
    except Exception as e:
        import maya.cmds as cmds
        cmds.warning("NinjaAssets: installed, but could not start automatically: {}".format(e))
        return False


# --- Maya drag-and-drop entry point ---
# Maya calls this function when a .py file is dropped into the viewport.
def onMayaDroppedPythonFile(*args, **kwargs):
    _install()


# Also run directly for backwards compat (e.g. execfile or script editor)
if __name__ == "__main__":
    try:
        import maya.cmds
        _install()
    except ImportError:
        print("This script is meant to be dragged into Maya's viewport.")
        print("For command-line install, use: python -m ninja_assets.cli.install")
