# NinjaAssets

GDrive-based asset management for Maya. Browse, import, publish, and version 3D assets across a studio — no servers, no daemons, just Google Drive.

## Install

### Quick Install (symlink, recommended for dev)

```bash
python -m ninja_assets.cli.install
```

This auto-detects your latest Maya version, symlinks the package into your scripts folder, and adds the startup hook to `userSetup.py`.

### Options

```bash
# Target a specific Maya version
python -m ninja_assets.cli.install --maya 2024

# Copy files instead of symlink (for distribution)
python -m ninja_assets.cli.install --maya 2024 --copy

# Custom scripts directory
python -m ninja_assets.cli.install --scripts-dir "/path/to/maya/scripts"

# Uninstall
python -m ninja_assets.cli.install --uninstall
```

### Manual Install

1. Copy `ninja_assets/` to `Documents/maya/<version>/scripts/`
2. Add to `Documents/maya/<version>/scripts/userSetup.py`:

```python
import maya.cmds as cmds

def init_ninja_assets():
    from ninja_assets.maya_integration import plugin
    plugin.initialize()

cmds.evalDeferred(init_ninja_assets)
```

3. Restart Maya.

### First Launch

On first launch you'll be prompted for your studio username. The GDrive folder structure is created automatically. The **NinjaAssets** menu and shelf button appear once initialization completes.

### Platform Support

| Platform | GDrive Default | Local Data |
|----------|---------------|------------|
| Windows | `G:\` | `%APPDATA%\NinjaAssets\` |
| macOS | `~/Google Drive` | `~/Library/Application Support/NinjaAssets/` |
| Linux | `~/Google Drive` | `~/.ninja_assets/` |

Change the GDrive root in **NinjaAssets > Settings** or during first-run setup.

## Features

### Asset Browser (Products Tab)
- Thumbnail grid with category sidebar and status filters
- Search by name across all assets
- Single-click to preview, double-click to import
- Right-click for Import, Reference, Open Folder, Copy Path
- Version selector to import specific versions
- Async thumbnail loading for smooth scrolling

### Asset Publishing
- Export selected objects as OBJ, Maya ASCII, or both
- Set name, category, tags, version, and comment
- Capture viewport thumbnail or load from file
- Optimistic locking prevents silent overwrites between artists

### Scene Versioning (Scenefiles Tab)
- Version history table for the current scene
- Save new versions with editable version numbers and comments
- Double-click any version to open it
- Works with any scene location — not project-tied

### Sync Engine
- Background thread keeps local SQLite cache in sync with GDrive
- Changelog-based fast sync on startup (~1-5s)
- Periodic spot-checks catch changes the changelog missed
- Force Sync from the menu for a full rescan

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Open Asset Browser | `Alt+Shift+A` |
| Save Version | `Ctrl+Alt+S` |
| Save Version + Comment | `Ctrl+Alt+Shift+S` |
| Publish Selection | `Ctrl+Alt+P` |
| Capture Thumbnail | `Ctrl+Alt+T` |

## CLI Tools

```bash
# Initialize GDrive folder structure
python -m ninja_assets.cli.init_gdrive "G:/"

# Migrate existing assets that lack metadata
python -m ninja_assets.cli.migrate "G:/assets" --user yourname

# Preview migration without making changes
python -m ninja_assets.cli.migrate "G:/assets" --user yourname --dry-run
```

## Architecture

```
Google Drive (shared)          Local (per workstation)
========================       =======================
assets/                        %APPDATA%/NinjaAssets/
  characters/                    cache.sqlite
  props/                         config.json
  environments/                  thumbnails/
  ...                            logs/
scenes/
.ninjaassets/
  changelog.jsonl
  schema_version.txt
```

- **Source of truth**: `.meta.json` sidecar files alongside each asset
- **Fast queries**: Local SQLite cache, refreshed via changelog + spot-checks
- **No servers**: Everything runs through GDrive Desktop file sync
- **Scale**: Designed for ~1,000 assets / ~500 artists

## Requirements

- Maya 2022+ (Python 3.7+)
- Google Drive Desktop
- Windows, macOS, or Linux

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check ninja_assets/
```
