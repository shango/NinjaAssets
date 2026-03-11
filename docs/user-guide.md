# NinjaAssets User Guide

Welcome to NinjaAssets — a simple way to browse, share, and version your 3D assets and Maya scenes across the studio, all through Google Drive.

This guide walks you through getting set up, finding assets, importing them into your scenes, publishing your own work, and managing scene versions.

---

## Table of Contents

1. [Installation](#installation)
2. [First Launch](#first-launch)
3. [The NinjaAssets Window](#the-ninjaassets-window)
4. [Finding and Importing Assets](#finding-and-importing-assets)
5. [Publishing an Asset](#publishing-an-asset)
6. [Scene Versioning](#scene-versioning)
7. [Capturing Thumbnails](#capturing-thumbnails)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Settings](#settings)
10. [How It Works Behind the Scenes](#how-it-works-behind-the-scenes)
11. [Troubleshooting](#troubleshooting)

---

## Installation

You'll get NinjaAssets as a `.zip` file. Here's how to set it up, step by step.

### Step 1: Unzip the folder

1. Download `NinjaAssets.zip`
2. Unzip it somewhere you'll keep it — your **Desktop**, **Documents**, or a **tools** folder all work fine
3. **Don't leave it in Downloads** — it may get cleaned up later, which would break the install

After unzipping, you should have a folder called `NinjaAssets`. Inside you'll see files like `install.bat`, `install.command`, `drag_into_maya.py`, and a `ninja_assets/` subfolder. You don't need to open or edit any of these — the installer handles everything.

### Step 2: Install (pick whichever method is easiest for you)

#### Drag and Drop (easiest)

This is the simplest way — no terminal, no double-clicking batch files.

1. Open Maya
2. Open your file browser (Explorer on Windows, Finder on Mac) and navigate to the NinjaAssets folder you unzipped
3. Find the file called **`drag_into_maya.py`**
4. Drag that file from your file browser and drop it into the **Maya viewport** (the 3D view where you see your models)
5. A dialog pops up saying "NinjaAssets installed successfully" — click **OK**
6. **Close Maya and reopen it**

That's it. When Maya restarts, NinjaAssets will be loaded and ready.

#### Double-Click Installer

If you'd rather install before opening Maya:

**On Windows:**
1. Open the NinjaAssets folder
2. Double-click **`install.bat`**
3. A black command window appears and shows progress
4. When it says "Done!", press any key to close the window
5. Open (or restart) Maya

**On Mac:**
1. Open the NinjaAssets folder
2. Double-click **`install.command`**
3. If macOS says the file is from an unidentified developer, right-click (or Control-click) the file and choose **Open** instead
4. A Terminal window appears and shows progress
5. When it says "Done!", press Enter to close the window
6. Open (or restart) Maya

#### Manual Install (advanced)

If the above methods don't work, or you prefer to do it by hand:

1. Find your Maya scripts folder:
   - **Windows:** `Documents\maya\2024\scripts\`
   - **Mac:** `~/Library/Preferences/Autodesk/maya/2024/scripts/`
   - Replace `2024` with your Maya version number

2. Copy the entire `ninja_assets` subfolder (from inside the NinjaAssets folder you unzipped) into that scripts folder

3. In that same scripts folder, find or create a file called `userSetup.py` and add these lines at the end:

```python
import maya.cmds as cmds

def init_ninja_assets():
    from ninja_assets.maya_integration import plugin
    plugin.initialize()

cmds.evalDeferred(init_ninja_assets)
```

4. Restart Maya

### Step 3: Verify it worked

After restarting Maya, look for two things:

1. A **NinjaAssets** menu in Maya's menu bar (at the top, next to Help)
2. A **NinjaAssets** button on your shelf

If you see both, you're all set. If not, see the [Troubleshooting](#troubleshooting) section below.

---

## First Launch

The first time NinjaAssets loads, you'll see a small dialog asking for your **studio username**. Type the name you want other artists to see when you publish assets or save scenes (for example, `sarah.jones` or `mike`).

After that, NinjaAssets will:

- Create the shared folder structure on Google Drive (if it doesn't exist yet)
- Start syncing asset data in the background
- Add a **NinjaAssets** menu to Maya's menu bar
- Add a shelf button for quick access

You're ready to go.

---

## The NinjaAssets Window

Open the browser from the menu (**NinjaAssets > Asset Browser**) or press **Alt+Shift+A**.

The window has two tabs along the top:

- **Products** — Browse and import assets from the studio library
- **Scenefiles** — Manage versions of your current Maya scene

The status bar at the bottom shows the last sync time, so you know how current your view is.

---

## Finding and Importing Assets

### Browsing the Library

Switch to the **Products** tab. You'll see:

- **Categories** on the left — Click a category to filter (Characters, Props, Environments, Vehicles, Weapons, FX, Other), or click "All" to see everything
- **Status filters** below the categories — Filter by work status:
  - **WIP** (orange dot) — Work in progress
  - **Review** (yellow dot) — Ready for feedback
  - **Approved** (green checkmark) — Good to use in production
- **Search bar** at the top of the grid — Type any part of an asset name to find it quickly
- **Thumbnail grid** — Visual cards for each asset showing a preview image, name, version, and status

### Previewing an Asset

**Click once** on any thumbnail to select it. The **Preview Panel** at the bottom shows:

- A larger thumbnail
- Asset details: category, status, author, polygon count, dimensions, and tags
- A **Version** dropdown to pick a specific version
- The comment left by whoever published that version

### Importing an Asset

There are several ways to bring an asset into your scene:

- **Double-click** a thumbnail to import the latest version immediately
- Click a thumbnail, then click the **Import** button in the preview panel
- **Right-click** a thumbnail and choose **Import** from the menu

To import a specific older version, select the version from the dropdown in the preview panel first, then click **Import**.

### Referencing an Asset

If you want to reference an asset (so it stays linked to the original file and updates when the asset is republished), use the **Reference** button in the preview panel, or right-click and choose **Reference**.

Note: Referencing only works with Maya files (.ma/.mb). OBJ files can only be imported.

### Other Quick Actions

Right-click any thumbnail (or use the preview panel buttons) to:

- **Open Folder** — Opens the asset's folder in your file browser
- **Copy Path** — Copies the file path to your clipboard

---

## Publishing an Asset

When you've finished modeling something and want to share it with the studio:

1. **Select the objects** you want to publish in your Maya viewport
2. Go to **NinjaAssets > Publish Selection** (or press **Ctrl+Alt+P**)

The Publish dialog opens. Fill in:

- **Name** — A short, descriptive name (e.g., `hero_sword`, `wooden_chair`). Use underscores, no spaces.
- **Category** — Pick from the dropdown (Characters, Props, Environments, etc.)
- **Version** — Defaults to 1 for new assets. If you're updating an existing asset, it will suggest the next version number. You can change it.
- **Tags** — Comma-separated keywords to help others find your asset (e.g., `weapon, scifi, rifle`)
- **Format** — Choose OBJ, Maya ASCII, or Both
- **Comment** — A short note about this version (e.g., "Initial blockout" or "Fixed topology issues")

### Adding a Thumbnail

A good thumbnail helps everyone find your asset quickly.

- Click **Capture from Viewport** to grab what's currently shown in your viewport
- Or click **Load from File** to pick an image from disk

Frame your model nicely before capturing — the viewport snapshot is what everyone will see in the browser.

### Destination Preview

At the bottom of the dialog, you'll see where the files will be saved (for example, `G:\assets\weapons\hero_sword\hero_sword_v001.obj`). This is automatic — you don't need to pick a location.

Click **Publish** when you're happy with everything.

### Updating an Existing Asset

To publish a new version of an asset that already exists:

1. Select your updated objects
2. Open **Publish Selection**
3. Type the **same name** as the existing asset
4. The version number will auto-increment
5. Add a comment describing what changed
6. Click **Publish**

If someone else published a version while you were working, NinjaAssets will warn you about the conflict and let you choose what to do.

---

## Scene Versioning

The **Scenefiles** tab helps you save clean versions of your Maya scenes with comments, so you can always go back to an earlier state.

### Saving a New Version

The quickest way:

- Press **Ctrl+Alt+S** to save a new version with auto-incremented version number
- Press **Ctrl+Alt+Shift+S** to open a dialog where you can edit the version number and add a comment

Or from the Scenefiles tab:

1. Type a comment in the **Comment** field at the bottom
2. Adjust the **Version** number if needed (it suggests the next one)
3. Click **Save Version**

Your scene is saved as a new file (e.g., `hero_rig_v006.ma`) — the original version is untouched.

### From the Menu

- **NinjaAssets > Save Version** — Quick save, auto-increment, no dialog
- **NinjaAssets > Save Version + Comment** — Opens a dialog where you can set the version number and write a comment. There's also a checkbox to automatically open the new version after saving.

### Viewing Version History

The Scenefiles tab shows a table of all saved versions with:

- The filename
- Who saved it
- When it was saved
- The comment they left

The current version is marked with a **>** arrow.

### Opening an Older Version

**Double-click** any row in the version history to open that version. You can also right-click for options:

- **Open** — Open the scene
- **Open in Explorer** — Show the file in your file browser
- **Copy Path** — Copy the file path to clipboard

### Editing Version Numbers

Version numbers are editable — you're not locked into sequential numbering. If you want to skip from v003 to v010, go for it. The system handles gaps just fine.

---

## Capturing Thumbnails

Thumbnails are captured from your Maya viewport — they're not generated automatically.

To capture a thumbnail for the current asset:

1. Frame your model in the viewport the way you want it to look
2. Go to **NinjaAssets > Capture Thumbnail** (or press **Ctrl+Alt+T**)

You can also capture a thumbnail during publishing using the **Capture from Viewport** button in the Publish dialog.

Tips for good thumbnails:

- Use a clean background
- Frame the object to fill the viewport
- Turn off grid and HUD elements (the capture does this automatically)

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Open Asset Browser | **Alt + Shift + A** |
| Save Version (quick) | **Ctrl + Alt + S** |
| Save Version + Comment | **Ctrl + Alt + Shift + S** |
| Publish Selection | **Ctrl + Alt + P** |
| Capture Thumbnail | **Ctrl + Alt + T** |

---

## Settings

Open **NinjaAssets > Settings** to customize:

| Setting | What it does | Default |
|---------|-------------|---------|
| GDrive Root | Where your studio's shared Google Drive is mounted | `G:\` (Windows) or `~/Google Drive` (Mac) |
| Username | Your studio name shown on published assets | Set on first launch |
| Sync Interval | How often NinjaAssets checks for changes (seconds) | 60 |
| Changelog Poll | How often the changelog is checked (seconds) | 30 |
| Thumbnail Grid Size | Size of thumbnails in the browser (pixels) | 100 |
| Preview Thumbnail Size | Size of the preview thumbnail (pixels) | 250 |

Click **Apply** to save without closing, or **OK** to save and close.

---

## How It Works Behind the Scenes

You don't need to know any of this to use NinjaAssets, but it might help if you're curious or troubleshooting.

### Where Are My Files?

Everything lives on Google Drive in a simple folder structure:

```
Google Drive
  assets/
    characters/
      hero_robot/
        hero_robot_v001.obj        <-- The actual model file
        hero_robot_v002.obj        <-- A newer version
        hero_robot.meta.json       <-- Metadata (see below)
        hero_robot.thumb.jpg       <-- Thumbnail image
    props/
    environments/
    vehicles/
    weapons/
    fx/
    other/
  scenes/
    (your scene folders)
      .scene_meta.json             <-- Scene version history
  .ninjaassets/
    changelog.jsonl                <-- Activity log for syncing
    schema_version.txt
```

### What Are .meta.json Files?

Each asset has a small `.meta.json` file next to it. This is a plain text file that stores:

- The asset's unique ID
- Its name, category, and status
- Version history (who published each version and when)
- Tags and polygon count
- Which file is the current version

These files are the "source of truth" for the asset library. NinjaAssets reads them to know what assets exist and what state they're in. You generally don't need to touch these files — NinjaAssets manages them for you.

### What About .scene_meta.json?

Each scene folder can have a `.scene_meta.json` file that tracks version history for that scene. It records every version you save along with the comment and timestamp. Again, NinjaAssets manages this automatically.

### Local Cache

NinjaAssets keeps a local copy of the asset database on your machine so browsing is fast (you're not waiting for Google Drive every time you search). This cache lives at:

- **Windows:** `%APPDATA%\NinjaAssets\cache.sqlite`
- **Mac:** `~/Library/Application Support/NinjaAssets/cache.sqlite`

The sync engine keeps this cache updated in the background. If things ever get out of sync, use **NinjaAssets > Force Sync** to rebuild it.

### How Syncing Works

When you publish an asset, NinjaAssets writes to a shared log file (`changelog.jsonl`). Other artists' Maya sessions pick up these changes within about 30-60 seconds. The system also does random spot-checks to catch anything the log might have missed.

---

## Troubleshooting

### The drag-and-drop install didn't work

- Make sure you're dragging `drag_into_maya.py` — not the whole folder, and not a different file
- You need to drop it into the **3D viewport** (the area where your models appear), not the Script Editor or outliner
- If Maya says it can't find the ninja_assets folder, make sure you unzipped the entire NinjaAssets folder and that `drag_into_maya.py` is still inside it (next to the `ninja_assets/` subfolder)
- After the install dialog says "OK", you **must restart Maya** for NinjaAssets to load

### The double-click installer says "Could not find Maya or Python"

- Make sure Maya is installed in the default location (`C:\Program Files\Autodesk\Maya2024` on Windows or `/Applications/Autodesk/maya2024` on Mac)
- If Maya is installed somewhere unusual, use the drag-and-drop method instead — it always works because it runs inside Maya

### NinjaAssets menu doesn't appear in Maya

- Make sure you restarted Maya after installing
- Make sure the `ninja_assets` folder is in your Maya scripts directory
- Check that `userSetup.py` exists and contains the init code (see [Installation](#installation))
- Open Maya's Script Editor and look for error messages mentioning "NinjaAssets"
- Try running this in Maya's Python console:
  ```python
  from ninja_assets.maya_integration import plugin
  plugin.initialize()
  ```

### "GDrive not accessible" warning at startup

- Make sure Google Drive Desktop is running and synced
- Check that the drive letter or mount point is correct in **Settings > GDrive Root**
- On Mac, the default path is `~/Google Drive` — if your Google Drive mounts somewhere else, update it in Settings

### Assets aren't showing up in the browser

- Click **NinjaAssets > Force Sync** to trigger a full rescan
- Check that asset folders have `.meta.json` files (assets without metadata won't appear)
- If you've added files manually (without using Publish), you can generate metadata with:
  ```
  python -m ninja_assets.cli.migrate "G:/assets" --user yourname
  ```

### Thumbnails aren't loading

- Thumbnails load in the background — give it a moment
- If a thumbnail is missing, the asset will show a gray placeholder. You can capture one with **Ctrl+Alt+T** or during publishing.

### "Conflict detected" when publishing

This means someone else updated the same asset while you were working on it. You'll see a dialog with options:

- **Save as next version** — Your changes become the next version (safest choice)
- **Overwrite** — Replace their version with yours (use with caution)
- **Cancel** — Back out and review what changed

### Scene versioning isn't working

- Make sure a scene is open (File > Open or File > Save As first)
- The scene needs to be saved to disk at least once before versioning starts
- Check Maya's Script Editor for any error messages

### Everything seems slow

- Try **Force Sync** to rebuild the cache from scratch
- In **Settings**, increase the Sync Interval if the background sync is causing lag
- If the thumbnail grid is sluggish, try reducing the **Thumbnail Grid Size** in Settings

### Logs

If something's going wrong and you need to dig deeper, check the log files:

- **Windows:** `%APPDATA%\NinjaAssets\logs\ninja_assets.log`
- **Mac:** `~/Library/Application Support/NinjaAssets/logs/ninja_assets.log`

These logs rotate automatically and won't fill up your disk.

### Resetting Everything

If you need a fresh start on your local machine (this won't affect the shared assets on Google Drive):

1. Close Maya
2. Delete the local data folder:
   - **Windows:** `%APPDATA%\NinjaAssets\`
   - **Mac:** `~/Library/Application Support/NinjaAssets/`
3. Reopen Maya — NinjaAssets will rebuild the cache and prompt for your username again
