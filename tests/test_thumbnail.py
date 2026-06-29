"""Tests for headless OBJ thumbnail rendering."""

import pytest

# Skip entire module if trimesh/PIL are not installed
trimesh = pytest.importorskip("trimesh")
PIL = pytest.importorskip("PIL")

import numpy as np
from ninja_assets.core.thumbnail import (
    render_mesh_thumbnail, render_obj_thumbnail, _look_at, _load_mesh,
    RENDERABLE_EXTENSIONS,
)

# Minimal OBJ cube for testing
CUBE_OBJ = """\
# Simple cube
v  0.0  0.0  0.0
v  1.0  0.0  0.0
v  1.0  1.0  0.0
v  0.0  1.0  0.0
v  0.0  0.0  1.0
v  1.0  0.0  1.0
v  1.0  1.0  1.0
v  0.0  1.0  1.0
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


@pytest.fixture
def cube_obj(tmp_path):
    """Write a minimal cube OBJ to a temp file."""
    obj_path = tmp_path / "cube.obj"
    obj_path.write_text(CUBE_OBJ)
    return obj_path


class TestLoadMesh:
    def test_load_cube(self, cube_obj):
        mesh = _load_mesh(cube_obj)
        assert mesh is not None
        assert len(mesh.vertices) == 8

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(Exception):
            _load_mesh(tmp_path / "nope.obj")


class TestLookAt:
    def test_produces_4x4_matrix(self):
        eye = np.array([2.0, 1.0, 2.0])
        target = np.array([0.0, 0.0, 0.0])
        up = np.array([0.0, 1.0, 0.0])
        mat = _look_at(eye, target, up)
        assert mat.shape == (4, 4)

    def test_rotation_is_orthonormal(self):
        eye = np.array([3.0, 2.0, 3.0])
        target = np.array([0.0, 0.0, 0.0])
        up = np.array([0.0, 1.0, 0.0])
        mat = _look_at(eye, target, up)
        rot = mat[:3, :3]
        # R^T * R should be identity
        product = rot.T @ rot
        np.testing.assert_allclose(product, np.eye(3), atol=1e-10)

    def test_translation_equals_eye(self):
        eye = np.array([5.0, 3.0, 4.0])
        target = np.array([0.0, 0.0, 0.0])
        up = np.array([0.0, 1.0, 0.0])
        mat = _look_at(eye, target, up)
        np.testing.assert_allclose(mat[:3, 3], eye, atol=1e-10)


class TestRenderableExtensions:
    def test_includes_obj(self):
        assert '.obj' in RENDERABLE_EXTENSIONS

    def test_includes_glb(self):
        assert '.glb' in RENDERABLE_EXTENSIONS

    def test_includes_gltf(self):
        assert '.gltf' in RENDERABLE_EXTENSIONS


class TestRenderMeshThumbnail:
    def test_produces_jpg(self, cube_obj, tmp_path):
        output = tmp_path / "thumb.jpg"
        result = render_mesh_thumbnail(cube_obj, output, width=128, height=128)
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

        from PIL import Image
        img = Image.open(output)
        assert img.size == (128, 128)

    def test_produces_png(self, cube_obj, tmp_path):
        output = tmp_path / "thumb.png"
        render_obj_thumbnail(
            cube_obj, output, width=64, height=64, image_format="png"
        )
        assert output.exists()
        from PIL import Image
        img = Image.open(output)
        assert img.size == (64, 64)
        assert img.mode == "RGB"

    def test_default_output_path(self, cube_obj):
        result = render_obj_thumbnail(cube_obj, width=64, height=64)
        expected = cube_obj.with_name("cube_thumb.jpg")
        assert result == expected
        assert expected.exists()

    def test_custom_size(self, cube_obj, tmp_path):
        output = tmp_path / "big.jpg"
        render_obj_thumbnail(cube_obj, output, width=512, height=512)
        from PIL import Image
        img = Image.open(output)
        assert img.size == (512, 512)

    def test_image_not_blank(self, cube_obj, tmp_path):
        """Verify the rendered image contains actual geometry, not just background."""
        output = tmp_path / "thumb.png"
        render_obj_thumbnail(cube_obj, output, width=128, height=128, image_format="png")
        from PIL import Image
        img = Image.open(output)
        arr = np.array(img)
        # Should have variance (not a solid color)
        assert arr.std() > 5, "Rendered image appears to be a solid color"

    def test_renders_glb(self, tmp_path):
        """Verify GLB files can be rendered to thumbnails."""
        # Create a GLB from a trimesh box
        mesh = trimesh.creation.box()
        glb_path = tmp_path / "box.glb"
        mesh.export(str(glb_path))

        output = tmp_path / "glb_thumb.jpg"
        render_mesh_thumbnail(glb_path, output, width=128, height=128)
        assert output.exists()
        assert output.stat().st_size > 0

        from PIL import Image
        img = Image.open(output)
        assert img.size == (128, 128)

    def test_backwards_compat_alias(self, cube_obj, tmp_path):
        """render_obj_thumbnail still works as an alias."""
        output = tmp_path / "alias.jpg"
        render_obj_thumbnail(cube_obj, output, width=64, height=64)
        assert output.exists()
