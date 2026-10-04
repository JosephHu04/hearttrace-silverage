"""Render and audit a third-party rigged glTF before it enters the project.

Usage:
  blender --background --python inspect_rigged_base.py -- input.gltf output.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            collection.remove(item)


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def mesh_bounds() -> tuple[Vector, Vector]:
    corners = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.visible_get():
            continue
        corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise RuntimeError("The imported file contains no visible mesh")
    minimum = Vector(tuple(min(point[index] for point in corners) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in corners) for index in range(3)))
    return minimum, maximum


def add_light(name: str, location, energy: float, size: float, color) -> None:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    light.location = location
    bpy.context.collection.objects.link(light)
    look_at(light, Vector((0, 0, 1.1)))


def render_preview(sources: list[Path], output: Path) -> None:
    reset_scene()
    for source in sources:
        bpy.ops.import_scene.gltf(filepath=str(source))

    minimum, maximum = mesh_bounds()
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    width = maximum.x - minimum.x

    world = bpy.data.worlds.new("AuditWorld")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs[0].default_value = (0.035, 0.045, 0.04, 1)
    background.inputs[1].default_value = 0.42
    bpy.context.scene.world = world

    camera_data = bpy.data.cameras.new("AuditCamera")
    camera = bpy.data.objects.new("AuditCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(height * 1.15, width * 1.4)
    camera.location = (center.x, minimum.y - max(height * 2.5, 5.0), center.z)
    look_at(camera, center)
    bpy.context.scene.camera = camera

    add_light("Key", (-3.5, -4.5, maximum.z + 2), 1100, 4.0, (1.0, .78, .62))
    add_light("Fill", (4.0, -1.5, center.z + 1), 700, 3.0, (.64, .84, .74))
    add_light("Rim", (0, 3.0, maximum.z + 1), 1000, 3.0, (.68, .72, 1.0))

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str(output)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.camera.data.lens = 55
    bpy.ops.render.render(write_still=True)

    armatures = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    bones = sorted({bone.name for armature in armatures for bone in armature.data.bones})
    meshes = [obj.name for obj in scene.objects if obj.type == "MESH"]
    print(f"AUDIT sources={','.join(source.name for source in sources)} meshes={len(meshes)} armatures={len(armatures)} bones={len(bones)}")
    print("AUDIT mesh_names=" + ",".join(meshes))
    print("AUDIT bone_names=" + ",".join(bones))
    print(f"AUDIT dimensions=({width:.3f},{maximum.y - minimum.y:.3f},{height:.3f})")


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) < 2:
        raise SystemExit("Expected one or more input glTF/GLB files followed by output PNG")
    sources = [Path(arg).expanduser().resolve() for arg in args[:-1]]
    output = Path(args[-1]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    render_preview(sources, output)


if __name__ == "__main__":
    main()
