# NinjaAssets

GDrive-based asset management for Maya. Browse, import, publish, and version 3D assets across a studio — no servers, no daemons, just Google Drive.

## Quick Start

1. **Unzip** `NinjaAssets.zip` anywhere
2. **Open Maya**, then drag **`drag_into_maya.py`** from the unzipped folder into the Maya viewport
3. Click **OK** on the install confirmation dialog
4. **Restart Maya** — when prompted that `userSetup.py` was modified, click **Yes** / **Allow**
5. On first launch, a setup dialog asks for your **asset drive location** (the shared Google Drive folder — typically inside `Shared drives`, not `My Drive`) and your **username**
6. Click **Get Started** — you're done

The NinjaAssets folder can be deleted after installing.

## Alternate Install Methods

### Double-click installer

- **Windows** — Double-click `install.bat` in the NinjaAssets folder
- **Mac** — Double-click `install.command` (right-click > Open if macOS blocks it)

Restart Maya when it's done.

### Command line (TDs / developers)

```bash
python -m ninja_assets.cli.install              # auto-detect Maya, symlink
python -m ninja_assets.cli.install --maya 2024  # target a specific version
python -m ninja_assets.cli.install --copy       # copy instead of symlink
python -m ninja_assets.cli.install --uninstall  # remove NinjaAssets
```

> **Note:** The command-line installer uses symlinks by default, so the NinjaAssets folder must stay in place. Use `--copy` to remove it afterward.

### Platform notes

| Platform | GDrive Default | Local Data |
|----------|---------------|------------|
| Windows | `G:\` | `%APPDATA%\NinjaAssets\` |
| macOS | `~/Google Drive` | `~/Library/Application Support/NinjaAssets/` |
| Linux | `~/Google Drive` | `~/.ninja_assets/` |

Change the GDrive root in **NinjaAssets > Settings** if your Google Drive mounts somewhere different.

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
