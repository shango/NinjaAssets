"""Headless mesh thumbnail renderer using trimesh + pyrender.

Generates asset preview images without Maya. Requires the [thumbnail]
optional dependency group: pip install ninja-assets[thumbnail]

Rendering backends (tried in order):
  1. pyrender + OSMesa (software, headless — best quality)
  2. pyrender + EGL (GPU, headless — needs NVIDIA)
  3. trimesh scene export to PNG (basic fallback — no OpenGL needed)

For OSMesa, install the system library:
  - Linux (Ubuntu/Debian): apt install libosmesa6-dev
  - Linux (Fedora/RHEL): dnf install mesa-libOSMesa-devel
  - macOS: brew install mesa
"""

import logging
import math
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# Mesh formats that trimesh can load and we can render thumbnails for
RENDERABLE_EXTENSIONS = {'.obj', '.glb', '.gltf', '.stl', '.ply', '.off'}


def render_mesh_thumbnail(
    mesh_path,
    output_path=None,
    width=512,
    height=512,
    image_format="jpg",
    quality=85,
):
    """Render a 3D mesh file to a thumbnail image.

    Supports OBJ, GLB, glTF, STL, PLY, and other formats trimesh can load.

    Args:
        mesh_path: Path to the mesh file (.obj, .glb, .gltf, etc.).
        output_path: Where to write the image. If None, writes next to the mesh.
        width: Image width in pixels.
        height: Image height in pixels.
        image_format: "jpg" or "png".
        quality: JPEG quality (1-100), ignored for PNG.

    Returns:
        Path to the written image file.
    """

    mesh_path = Path(mesh_path)
    if output_path is None:
        output_path = mesh_path.with_name(f"{mesh_path.stem}_thumb.{image_format}")
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    mesh = _load_mesh(mesh_path)
    color = _render_mesh(mesh, width, height)

    from PIL import Image
    img = Image.fromarray(color)
    if image_format.lower() == "jpg":
        img.save(str(output_path), "JPEG", quality=quality)
    else:
        img.save(str(output_path), "PNG")

    logger.info("Thumbnail saved: %s (%dx%d)", output_path, width, height)
    return output_path


# Backwards-compatible alias
render_obj_thumbnail = render_mesh_thumbnail


def _load_mesh(mesh_path):
    """Load a mesh file and return a single trimesh.Trimesh."""
    import trimesh

    result = trimesh.load(str(mesh_path), force=None)

    if isinstance(result, trimesh.Trimesh):
        return result

    # Scene with multiple geometries — concatenate
    if isinstance(result, trimesh.Scene) and result.geometry:
        meshes = [g for g in result.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)

    raise ValueError(f"Could not load mesh from {mesh_path}")


def _try_pyrender_backend(platform_name):
    """Try to initialize pyrender with the given platform. Returns True on success."""
    os.environ["PYOPENGL_PLATFORM"] = platform_name
    try:
        import pyrender
        # Test that the renderer actually works
        r = pyrender.OffscreenRenderer(32, 32)
        r.delete()
        logger.info("Using pyrender backend: %s", platform_name)
        return True
    except Exception as exc:
        logger.debug("pyrender backend %s failed: %s", platform_name, exc)
        return False


def _get_pyrender_renderer(width, height):
    """Get a working pyrender OffscreenRenderer, or None if no backend works."""
    # Try backends in preference order
    for backend in ("osmesa", "egl"):
        if _try_pyrender_backend(backend):
            import pyrender
            return pyrender.OffscreenRenderer(width, height)

    logger.warning("No pyrender backend available, falling back to trimesh rendering")
    return None


def _render_mesh(mesh, width, height):
    """Render a trimesh mesh and return an RGB numpy array."""
    renderer = _get_pyrender_renderer(width, height)
    if renderer is not None:
        return _render_pyrender(mesh, width, height, renderer)
    return _render_trimesh_fallback(mesh, width, height)


def _render_pyrender(mesh, width, height, renderer):
    """Render using pyrender (high quality with lighting)."""
    import pyrender

    scene = pyrender.Scene(
        ambient_light=[0.3, 0.3, 0.3],
        bg_color=[0.18, 0.18, 0.18, 1.0],
    )

    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[0.7, 0.7, 0.7, 1.0],
        metallicFactor=0.15,
        roughnessFactor=0.7,
    )
    py_mesh = pyrender.Mesh.from_trimesh(mesh, material=material)
    scene.add(py_mesh)

    # Auto-frame camera
    centroid = mesh.centroid
    scale = max(mesh.extents)
    fov = math.radians(45)
    distance = (scale / (2.0 * math.tan(fov / 2.0))) * 1.8

    # 3/4 hero angle
    direction = np.array([1.0, 0.6, 1.0])
    direction = direction / np.linalg.norm(direction)
    eye = centroid + direction * distance

    camera_pose = _look_at(eye, centroid, up=np.array([0.0, 1.0, 0.0]))
    camera = pyrender.PerspectiveCamera(yfov=fov, aspectRatio=width / height)
    scene.add(camera, pose=camera_pose)

    # Key light
    key_pose = _look_at(eye * 1.2, centroid, up=np.array([0.0, 1.0, 0.0]))
    key_light = pyrender.DirectionalLight(color=[1.0, 0.95, 0.9], intensity=4.0)
    scene.add(key_light, pose=key_pose)

    # Fill light
    fill_dir = np.array([-1.0, 0.3, -0.5])
    fill_dir = fill_dir / np.linalg.norm(fill_dir)
    fill_eye = centroid + fill_dir * distance
    fill_pose = _look_at(fill_eye, centroid, up=np.array([0.0, 1.0, 0.0]))
    fill_light = pyrender.DirectionalLight(color=[0.85, 0.9, 1.0], intensity=1.5)
    scene.add(fill_light, pose=fill_pose)

    try:
        color, _ = renderer.render(scene)
    finally:
        renderer.delete()

    return color


def _render_trimesh_fallback(mesh, width, height):
    """Fallback renderer using trimesh's built-in scene rendering.

    Uses Pillow to rasterize a simple shaded view of the mesh.
    No OpenGL required.
    """
    from PIL import Image, ImageDraw

    # Project vertices to 2D using a simple perspective projection
    centroid = mesh.centroid
    scale = max(mesh.extents) if max(mesh.extents) > 0 else 1.0

    # Camera at 3/4 hero angle
    direction = np.array([1.0, 0.6, 1.0])
    direction = direction / np.linalg.norm(direction)
    fov = math.radians(45)
    distance = (scale / (2.0 * math.tan(fov / 2.0))) * 1.8
    eye = centroid + direction * distance

    # Build view matrix
    forward = centroid - eye
    forward = forward / np.linalg.norm(forward)
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)
    actual_up = np.cross(right, forward)

    # Transform vertices to camera space
    verts = mesh.vertices - eye
    cam_x = verts @ right
    cam_y = verts @ actual_up
    cam_z = verts @ forward

    # Perspective projection
    near = 0.01
    cam_z = np.clip(cam_z, near, None)
    proj_x = cam_x / cam_z
    proj_y = cam_y / cam_z

    # Normalize to image coordinates
    margin = 0.1
    all_proj = np.stack([proj_x, proj_y], axis=1)
    pmin = all_proj.min(axis=0)
    pmax = all_proj.max(axis=0)
    span = pmax - pmin
    span[span == 0] = 1.0

    img_size = min(width, height) * (1 - 2 * margin)
    screen_x = margin * width + (all_proj[:, 0] - pmin[0]) / span[0] * img_size
    screen_y = margin * height + (1 - (all_proj[:, 1] - pmin[1]) / span[1]) * img_size

    # Center in frame
    cx = (screen_x.min() + screen_x.max()) / 2
    cy = (screen_y.min() + screen_y.max()) / 2
    screen_x += width / 2 - cx
    screen_y += height / 2 - cy

    # Draw with basic face shading
    img = Image.new("RGB", (width, height), (46, 46, 46))
    draw = ImageDraw.Draw(img)

    light_dir = direction / np.linalg.norm(direction)

    # Sort faces by average depth (painter's algorithm)
    if hasattr(mesh, 'faces') and len(mesh.faces) > 0:
        face_depths = cam_z[mesh.faces].mean(axis=1)
        sorted_indices = np.argsort(face_depths)

        face_normals = mesh.face_normals if mesh.face_normals is not None else np.zeros((len(mesh.faces), 3))

        for fi in sorted_indices:
            face = mesh.faces[fi]
            poly = [(screen_x[v], screen_y[v]) for v in face]

            # Simple diffuse shading
            if fi < len(face_normals):
                normal = face_normals[fi]
                brightness = max(0.15, float(np.dot(normal, light_dir)))
            else:
                brightness = 0.5

            gray = int(brightness * 200)
            draw.polygon(poly, fill=(gray, gray, gray), outline=(gray + 20, gray + 20, gray + 20))

    return np.array(img)


def _look_at(eye, target, up):
    """Build a 4x4 camera pose matrix (OpenGL: camera looks down -Z)."""
    forward = target - eye
    forward = forward / np.linalg.norm(forward)

    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)

    actual_up = np.cross(right, forward)

    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = actual_up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye
    return pose
