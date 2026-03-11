# NinjaAssets

GDrive-based asset management for Maya. Browse, import, publish, and version 3D assets across a studio — no servers, no daemons, just Google Drive.

## Install

You'll receive NinjaAssets as a `.zip` file. Here's how to get it running.

### Step 1: Unzip

Download `NinjaAssets.zip` and unzip it somewhere permanent — your Desktop, Documents, or a tools folder. Avoid leaving it in Downloads (it may get cleaned up).

You should end up with a folder called `NinjaAssets` containing files like `install.bat`, `install.command`, `drag_into_maya.py`, and a `ninja_assets/` subfolder.

### Step 2: Install (pick one method)

#### Option A: Drag into Maya (easiest)

1. Open Maya
2. Find the file `drag_into_maya.py` inside your NinjaAssets folder
3. Drag it from your file browser into the Maya viewport
4. A dialog confirms the install — click OK
5. Restart Maya

#### Option B: Double-click the installer

- **Windows** — Double-click `install.bat`
- **Mac** — Double-click `install.command` (if macOS asks about an unidentified developer, right-click the file and choose Open instead)

The installer finds your Maya version automatically, copies the files, and tells you when it's done. Restart Maya.

#### Option C: Command line (for TDs / developers)

```bash
# Auto-detect Maya, symlink for development
python -m ninja_assets.cli.install

# Target a specific Maya version
python -m ninja_assets.cli.install --maya 2024

# Copy instead of symlink (what the double-click installers do)
python -m ninja_assets.cli.install --maya 2024 --copy

# Custom scripts directory
python -m ninja_assets.cli.install --scripts-dir "/path/to/maya/scripts"

# Uninstall
python -m ninja_assets.cli.install --uninstall
```

### Step 3: First Launch

Restart Maya after installing. A setup dialog appears asking for:

1. **Asset drive location** — Browse to the shared folder on Google Drive where your studio keeps assets. This is typically inside `Shared drives` (not `My Drive`). Everyone in the studio should point to the same folder.
2. **Username** — The name other artists will see when you publish or save (e.g. `sarah.jones`)

Click **Get Started**. NinjaAssets creates the folder structure, starts syncing, and adds its menu and shelf button. Both settings can be changed later in **NinjaAssets > Settings**.

### What the installer does

The installer copies the `ninja_assets` Python package into your Maya scripts folder and adds a small startup hook to `userSetup.py` so NinjaAssets loads every time Maya starts. It doesn't modify Maya itself or install anything system-wide.

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
