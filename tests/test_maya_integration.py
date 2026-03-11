"""Tests for Maya integration (Phase 6) using mocked maya.cmds."""
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ninja_assets.config import NinjaConfig
from ninja_assets.core.models import Asset, Version, AssetStatus


# ---------------------------------------------------------------------------
# Mock maya modules so imports don't fail outside Maya
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_maya_modules():
    """Inject fake maya.cmds and maya.mel into sys.modules."""
    maya_mod = types.ModuleType("maya")
    cmds_mod = types.ModuleType("maya.cmds")
    mel_mod = types.ModuleType("maya.mel")
    omui_mod = types.ModuleType("maya.OpenMayaUI")

    # Give cmds some default return values
    cmds_mod.file = MagicMock(return_value=None)
    cmds_mod.ls = MagicMock(return_value=[])
    cmds_mod.menu = MagicMock(return_value="NinjaAssetsMenu")
    cmds_mod.menuItem = MagicMock()
    cmds_mod.deleteUI = MagicMock()
    cmds_mod.inViewMessage = MagicMock()
    cmds_mod.warning = MagicMock()
    cmds_mod.confirmDialog = MagicMock(return_value="Cancel")
    cmds_mod.currentTime = MagicMock(return_value=1.0)
    cmds_mod.playblast = MagicMock(return_value="/tmp/thumb.jpg")
    cmds_mod.getPanel = MagicMock(return_value="modelPanel4")
    cmds_mod.getAttr = MagicMock(return_value=8)
    cmds_mod.setAttr = MagicMock()
    cmds_mod.shelfButton = MagicMock()
    cmds_mod.shelfLayout = MagicMock(return_value=[])
    cmds_mod.tabLayout = MagicMock(return_value="currentShelf")
    cmds_mod.polyEvaluate = MagicMock(return_value=100)
    cmds_mod.exactWorldBoundingBox = MagicMock(return_value=[0, 0, 0, 1, 2, 3])
    cmds_mod.evalDeferred = MagicMock()

    mel_mod.eval = MagicMock(return_value="ShelfLayout")

    maya_mod.cmds = cmds_mod
    maya_mod.mel = mel_mod
    maya_mod.OpenMayaUI = omui_mod

    originals = {}
    for name in ("maya", "maya.cmds", "maya.mel", "maya.OpenMayaUI"):
        originals[name] = sys.modules.get(name)
        sys.modules[name] = {"maya": maya_mod, "maya.cmds": cmds_mod,
                             "maya.mel": mel_mod, "maya.OpenMayaUI": omui_mod}[name]

    yield cmds_mod

    # Restore
    for name, orig in originals.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


def _make_asset(tmp_path, name="test_robot", category="Characters", version=1):
    """Create a test asset with a file on disk."""
    folder = tmp_path / "assets" / category.lower() / name
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{name}_v{version:03d}.obj"
    (folder / filename).write_text("# OBJ file")

    return Asset(
        uuid="test-uuid-1234",
        name=name,
        path=str(folder),
        current_version=version,
        current_file=filename,
        category=category,
        status=AssetStatus.WIP,
        modified_at=datetime(2025, 1, 15, 9, 30),
        versions=[
            Version(
                version=version,
                file=filename,
                created_by="tester",
                created_at=datetime(2025, 1, 15, 9, 30),
                comment="Test version",
                poly_count=1000,
            )
        ],
        tags=["robot", "test"],
    )


# ---------------------------------------------------------------------------
# commands.py tests
# ---------------------------------------------------------------------------
class TestImportAsset:
    def test_import_calls_cmds_file(self, mock_maya_modules, tmp_path):
        cmds = mock_maya_modules
        asset = _make_asset(tmp_path)

        # Simulate new nodes appearing after import
        cmds.ls.side_effect = [["existing_node"], ["existing_node", "test_robot:mesh1"]]

        from ninja_assets.maya_integration.commands import import_asset
        result = import_asset(asset)

        cmds.file.assert_called_once()
        call_args = cmds.file.call_args
        assert call_args[0][0].endswith("test_robot_v001.obj")
        assert "test_robot:mesh1" in result

    def test_import_raises_for_missing_file(self, mock_maya_modules, tmp_path):
        asset = _make_asset(tmp_path)
        asset.current_file = "nonexistent.obj"

        from ninja_assets.maya_integration.commands import import_asset
        with pytest.raises(FileNotFoundError):
            import_asset(asset)

    def test_import_unsupported_type(self, mock_maya_modules, tmp_path):
        asset = _make_asset(tmp_path)
        asset.current_file = "model.abc"
        (Path(asset.path) / "model.abc").write_text("data")

        from ninja_assets.maya_integration.commands import import_asset
        with pytest.raises(ValueError, match="Unsupported"):
            import_asset(asset)


class TestReferenceAsset:
    def test_reference_raises_for_obj(self, mock_maya_modules, tmp_path):
        asset = _make_asset(tmp_path)

        from ninja_assets.maya_integration.commands import reference_asset
        with pytest.raises(ValueError, match="Cannot reference"):
            reference_asset(asset)

    def test_reference_works_for_ma(self, mock_maya_modules, tmp_path):
        cmds = mock_maya_modules
        asset = _make_asset(tmp_path)
        asset.current_file = "test_robot_v001.ma"
        asset.versions[0].file = "test_robot_v001.ma"
        (Path(asset.path) / "test_robot_v001.ma").write_text("// Maya ASCII")

        cmds.file.return_value = "test_robot_v1RN"

        from ninja_assets.maya_integration.commands import reference_asset
        result = reference_asset(asset)

        assert result == "test_robot_v1RN"
        cmds.file.assert_called_once()


class TestSaveSceneVersion:
    def test_save_creates_scene_meta(self, mock_maya_modules, tmp_path):
        cmds = mock_maya_modules
        scene_folder = tmp_path / "scenes" / "rigging" / "hero"
        scene_folder.mkdir(parents=True)
        scene_file = scene_folder / "hero_rigging_v001.ma"
        scene_file.write_text("// Maya")

        cmds.file.side_effect = lambda *a, **kw: (
            str(scene_file) if kw.get("query") and kw.get("sceneName") else None
        )

        config = NinjaConfig(
            gdrive_root=tmp_path,
            local_data_dir=tmp_path / "local",
            username="tester",
            _ensure_dirs=False,
        )

        from ninja_assets.maya_integration.commands import save_scene_version
        result = save_scene_version(config, comment="Test save")

        assert result is not None
        # No prior versions exist, so next version = 1
        assert "v001" in str(result)

        # Check .scene_meta.json was created
        from ninja_assets.core.scene_meta import SceneMetaManager
        meta_path = scene_folder / ".scene_meta.json"
        assert meta_path.exists()
        meta = SceneMetaManager.read(meta_path)
        assert meta.current_version == 1
        assert len(meta.versions) == 1
        assert meta.versions[0].comment == "Test save"


# ---------------------------------------------------------------------------
# export.py tests
# ---------------------------------------------------------------------------
class TestExport:
    def test_export_obj_raises_no_selection(self, mock_maya_modules, tmp_path):
        cmds = mock_maya_modules
        cmds.ls.return_value = []

        from ninja_assets.maya_integration.utils.export import export_obj
        from ninja_assets.core.exceptions import ExportError
        with pytest.raises(ExportError, match="Nothing selected"):
            export_obj(tmp_path / "out.obj")

    def test_get_selection_poly_count(self, mock_maya_modules):
        cmds = mock_maya_modules
        cmds.ls.return_value = ["mesh1", "mesh2"]
        cmds.polyEvaluate.return_value = 500

        from ninja_assets.maya_integration.utils.export import get_selection_poly_count
        count = get_selection_poly_count()
        assert count == 1000  # 500 * 2 meshes

    def test_get_selection_bounds(self, mock_maya_modules):
        cmds = mock_maya_modules
        cmds.ls.return_value = ["obj1"]
        cmds.exactWorldBoundingBox.return_value = [0, 0, 0, 2.5, 4.0, 1.5]

        from ninja_assets.maya_integration.utils.export import get_selection_bounds
        bounds = get_selection_bounds()
        assert bounds.x == 2.5
        assert bounds.y == 4.0
        assert bounds.z == 1.5


# ---------------------------------------------------------------------------
# maya_utils.py tests
# ---------------------------------------------------------------------------
class TestMayaUtils:
    def test_get_current_scene_path(self, mock_maya_modules):
        cmds = mock_maya_modules
        cmds.file.return_value = "/scenes/test_v001.ma"
        # Need to re-mock since file was used as both function and query
        cmds.file.side_effect = lambda *a, **kw: (
            "/scenes/test_v001.ma" if kw.get("query") else None
        )

        from ninja_assets.maya_integration.utils.maya_utils import get_current_scene_path
        assert get_current_scene_path() == "/scenes/test_v001.ma"

    def test_get_current_scene_path_untitled(self, mock_maya_modules):
        cmds = mock_maya_modules
        cmds.file.side_effect = lambda *a, **kw: (
            "" if kw.get("query") else None
        )

        from ninja_assets.maya_integration.utils.maya_utils import get_current_scene_path
        assert get_current_scene_path() is None

    def test_get_scene_folder_and_name(self, mock_maya_modules):
        from ninja_assets.maya_integration.utils.maya_utils import get_scene_folder_and_name
        folder, name = get_scene_folder_and_name("/scenes/rigging/hero/hero_rig_v003.ma")
        assert str(folder).replace("\\", "/") == "/scenes/rigging/hero"
        assert name == "hero_rig"

    def test_get_scene_folder_and_name_no_version(self, mock_maya_modules):
        from ninja_assets.maya_integration.utils.maya_utils import get_scene_folder_and_name
        folder, name = get_scene_folder_and_name("/scenes/test.ma")
        assert name == "test"


# ---------------------------------------------------------------------------
# menu.py tests
# ---------------------------------------------------------------------------
class TestMenu:
    def test_create_menu(self, mock_maya_modules):
        cmds = mock_maya_modules
        cmds.menu.return_value = "NinjaAssetsMenu"
        cmds.menu.side_effect = None

        from ninja_assets.maya_integration.menu import create_menu
        create_menu()

        # Should have created menu items
        assert cmds.menuItem.call_count >= 8  # 8 items + dividers


# ---------------------------------------------------------------------------
# shelf.py tests
# ---------------------------------------------------------------------------
class TestShelf:
    def test_add_shelf_buttons(self, mock_maya_modules):
        cmds = mock_maya_modules
        import maya.mel as mel

        mel.eval.return_value = "ShelfLayout"
        cmds.tabLayout.return_value = "currentShelf"
        cmds.shelfLayout.return_value = []

        from ninja_assets.maya_integration.shelf import add_shelf_buttons
        add_shelf_buttons()

        cmds.shelfButton.assert_called_once()
        call_kwargs = cmds.shelfButton.call_args
        assert "NinjaAssets" in str(call_kwargs)


# ---------------------------------------------------------------------------
# thumbnail.py tests
# ---------------------------------------------------------------------------
class TestThumbnail:
    def test_capture_viewport(self, mock_maya_modules, tmp_path):
        cmds = mock_maya_modules
        output = tmp_path / "thumb.jpg"

        from ninja_assets.maya_integration.utils.thumbnail import capture_viewport
        result = capture_viewport(output_path=output)

        cmds.playblast.assert_called_once()
        assert result == output
