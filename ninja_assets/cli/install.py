"""
Install NinjaAssets into a Maya version's scripts directory.

Creates a symlink (or copies) the ninja_assets package and injects
the initialization hook into userSetup.py without clobbering existing content.

Usage:
    python -m ninja_assets.cli.install              # auto-detects latest Maya version
    python -m ninja_assets.cli.install --maya 2024
    python -m ninja_assets.cli.install --maya 2024 --copy   # copy instead of symlink
    python -m ninja_assets.cli.install --uninstall --maya 2024
"""
import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # ninja_assets/
REPO_ROOT = PACKAGE_ROOT.parent

# Ensure the repo root is on sys.path so `python -m ninja_assets.cli.install`
# works even when invoked via mayapy from a double-click script.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SETUP_HOOK = '''
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

HOOK_START = "# --- NinjaAssets ---"
HOOK_END = "# --- /NinjaAssets ---"


def _get_maya_scripts_dirs():
    """Return dict of {version: scripts_path} for installed Maya versions."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("USERPROFILE", "~")) / "Documents" / "maya"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Preferences" / "Autodesk" / "maya"
    else:
        base = Path.home() / "maya"

    base = base.expanduser()
    if not base.exists():
        return {}

    versions = {}
    for entry in sorted(base.iterdir(), reverse=True):
        if entry.is_dir() and entry.name.replace(".", "").isdigit():
            scripts_dir = entry / "scripts"
            versions[entry.name] = scripts_dir
    return versions


def _detect_maya_version():
    """Find the latest installed Maya version."""
    versions = _get_maya_scripts_dirs()
    if not versions:
        return None, None
    version = next(iter(versions))
    return version, versions[version]


def install(scripts_dir, use_symlink=True):
    """Install ninja_assets into a Maya scripts directory."""
    scripts_dir = Path(scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    target = scripts_dir / "ninja_assets"

    # Remove existing installation
    if target.is_symlink():
        target.unlink()
        print(f"  Removed existing symlink: {target}")
    elif target.is_dir():
        shutil.rmtree(target)
        print(f"  Removed existing copy: {target}")

    # Install package
    if use_symlink:
        # Symlink to the repo so edits are reflected immediately
        if platform.system() == "Windows":
            # Windows needs special handling for directory symlinks
            os.symlink(str(PACKAGE_ROOT), str(target), target_is_directory=True)
        else:
            target.symlink_to(PACKAGE_ROOT)
        print(f"  Symlinked: {target} -> {PACKAGE_ROOT}")
    else:
        shutil.copytree(str(PACKAGE_ROOT), str(target))
        print(f"  Copied to: {target}")

    # Inject userSetup.py hook
    setup_file = scripts_dir / "userSetup.py"
    _inject_hook(setup_file)

    print(f"\n  Installation complete.")
    print(f"  Restart Maya to load NinjaAssets.")


def uninstall(scripts_dir):
    """Remove NinjaAssets from a Maya scripts directory."""
    scripts_dir = Path(scripts_dir)
    target = scripts_dir / "ninja_assets"

    if target.is_symlink():
        target.unlink()
        print(f"  Removed symlink: {target}")
    elif target.is_dir():
        shutil.rmtree(target)
        print(f"  Removed directory: {target}")
    else:
        print(f"  No installation found at: {target}")

    setup_file = scripts_dir / "userSetup.py"
    _remove_hook(setup_file)
    print("  Uninstall complete.")


def _inject_hook(setup_file):
    """Add NinjaAssets init hook to userSetup.py, preserving existing content."""
    existing = ""
    if setup_file.exists():
        existing = setup_file.read_text(encoding="utf-8")

    # Already installed?
    if HOOK_START in existing:
        print(f"  userSetup.py already has NinjaAssets hook (skipped)")
        return

    # Append hook
    with open(setup_file, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(SETUP_HOOK)

    print(f"  Added init hook to: {setup_file}")


def _remove_hook(setup_file):
    """Remove NinjaAssets hook from userSetup.py."""
    if not setup_file.exists():
        return

    content = setup_file.read_text(encoding="utf-8")
    if HOOK_START not in content:
        return

    lines = content.split("\n")
    new_lines = []
    skipping = False
    for line in lines:
        if HOOK_START in line:
            skipping = True
            continue
        if HOOK_END in line:
            skipping = False
            continue
        if not skipping:
            new_lines.append(line)

    # Remove trailing blank lines left behind
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()

    setup_file.write_text("\n".join(new_lines) + "\n" if new_lines else "",
                          encoding="utf-8")
    print(f"  Removed init hook from: {setup_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Install/uninstall NinjaAssets for Maya"
    )
    parser.add_argument(
        "--maya", type=str, default=None,
        help="Maya version (e.g., 2024). Auto-detects if omitted."
    )
    parser.add_argument(
        "--copy", action="store_true",
        help="Copy files instead of symlinking (symlink is default)"
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove NinjaAssets from Maya"
    )
    parser.add_argument(
        "--scripts-dir", type=str, default=None,
        help="Override Maya scripts directory path"
    )
    args = parser.parse_args()

    # Resolve scripts directory
    if args.scripts_dir:
        scripts_dir = Path(args.scripts_dir)
        version = "custom"
    elif args.maya:
        versions = _get_maya_scripts_dirs()
        if args.maya not in versions:
            print(f"Error: Maya {args.maya} not found. Available: {list(versions.keys())}")
            sys.exit(1)
        scripts_dir = versions[args.maya]
        version = args.maya
    else:
        version, scripts_dir = _detect_maya_version()
        if not version:
            print("Error: No Maya installation detected.")
            print("Use --maya VERSION or --scripts-dir PATH")
            sys.exit(1)

    if args.uninstall:
        print(f"  Removing NinjaAssets from Maya {version}...")
        print(f"  Location: {scripts_dir}")
        print()
        uninstall(scripts_dir)
    else:
        print(f"  Installing NinjaAssets for Maya {version}...")
        print(f"  Location: {scripts_dir}")
        print()
        install(scripts_dir, use_symlink=not args.copy)


if __name__ == "__main__":
    main()
