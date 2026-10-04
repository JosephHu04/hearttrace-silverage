"""Assemble the licensed Xiaohe engineering base and selected ambient actions.

The output is an internal modeling candidate, not a user-facing character.

Usage:
  blender --background --python prepare_xiaohe_rig_base.py -- \
    Teen_Female_FullBody.gltf Hair_Buns_Teen.gltf UAL1_Standard.glb output_dir
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


ACTION_MAP = {
    "Idle_Loop": "Idle_Base",
    "Idle_Talking_Loop": "Talk",
    "Interact": "Idle_Wave",
    "Sitting_Idle_Loop": "Sitting_Idle",
    "Sitting_Talking_Loop": "Sitting_Talk",
}


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def imported_objects(before: set[str]) -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.name not in before]


def import_asset(path: Path) -> list[bpy.types.Object]:
    before = {obj.name for obj in bpy.data.objects}
    bpy.ops.import_scene.gltf(filepath=str(path))
    return imported_objects(before)


def find_armature(objects: list[bpy.types.Object]) -> bpy.types.Object:
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"Expected exactly one armature, found {len(armatures)}")
    return armatures[0]


def bind_to_shared_armature(objects: list[bpy.types.Object], source, target) -> list[bpy.types.Object]:
    meshes = [obj for obj in objects if obj.type == "MESH"]
    for mesh in meshes:
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == source:
                modifier.object = target
        if mesh.parent == source:
            matrix_world = mesh.matrix_world.copy()
            mesh.parent = target
            mesh.matrix_world = matrix_world
    bpy.data.objects.remove(source, do_unlink=True)
    return meshes


def make_hair_brown(hair_meshes: list[bpy.types.Object]) -> None:
    material = bpy.data.materials.new("Xiaohe_Hair_Brown")
    material.diffuse_color = (0.16, 0.065, 0.035, 1)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (0.15, 0.052, 0.025, 1)
    principled.inputs["Roughness"].default_value = 0.48
    for mesh in hair_meshes:
        mesh.data.materials.clear()
        mesh.data.materials.append(material)


def copy_actions(animation_armature, body_armature) -> dict[str, bpy.types.Action]:
    copied = {}
    source_actions = {action.name: action for action in bpy.data.actions}
    for source_name, target_name in ACTION_MAP.items():
        source = source_actions.get(source_name)
        if source is None:
            raise RuntimeError(f"Missing animation action: {source_name}")
        target = source.copy()
        target.name = target_name
        target.use_fake_user = True
        copied[target_name] = target
    bpy.data.objects.remove(animation_armature, do_unlink=True)
    for action in list(bpy.data.actions):
        if action not in copied.values():
            bpy.data.actions.remove(action)
    body_armature.animation_data_create()
    body_armature.animation_data.action = copied["Idle_Base"]
    return copied


def look_at(obj: bpy.types.Object, target) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview(output: Path, armature, action) -> None:
    minimum = Vector((10_000, 10_000, 10_000))
    maximum = Vector((-10_000, -10_000, -10_000))
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            for index in range(3):
                minimum[index] = min(minimum[index], point[index])
                maximum[index] = max(maximum[index], point[index])
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z

    world = bpy.data.worlds.new("XiaoheAuditWorld")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs[0].default_value = (0.035, 0.046, 0.04, 1)
    background.inputs[1].default_value = 0.45
    bpy.context.scene.world = world

    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height * 1.16
    camera.location = (center.x, minimum.y - max(5.0, height * 2.6), center.z)
    look_at(camera, center)
    bpy.context.scene.camera = camera

    for name, location, energy, size, color in (
        ("Key", (-3.2, -4.2, maximum.z + 2), 1150, 4.0, (1.0, .78, .62)),
        ("Fill", (3.8, -1.5, center.z + 1), 650, 3.0, (.62, .84, .72)),
        ("Rim", (0, 3.2, maximum.z + 1), 900, 3.0, (.65, .72, 1.0)),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        light = bpy.data.objects.new(name, data)
        light.location = location
        look_at(light, center)
        bpy.context.collection.objects.link(light)

    armature.animation_data.action = action
    scene = bpy.context.scene
    scene.frame_set(35)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.ops.render.render(write_still=True)


def prepare_nla_tracks(armature, actions: dict[str, bpy.types.Action]) -> None:
    armature.animation_data_create()
    armature.animation_data.action = None
    while armature.animation_data.nla_tracks:
        armature.animation_data.nla_tracks.remove(armature.animation_data.nla_tracks[0])
    for name, action in actions.items():
        track = armature.animation_data.nla_tracks.new()
        track.name = name
        start = int(action.frame_range[0])
        strip = track.strips.new(name, start, action)
        strip.name = name


def export_candidate(output: Path, armature, meshes: list[bpy.types.Object], actions: dict[str, bpy.types.Action]) -> None:
    prepare_nla_tracks(armature, actions)
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_optimize_animation_size=True,
        export_yup=True,
    )


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 4:
        raise SystemExit("Expected body glTF, hair glTF, animation GLB, and output directory")
    body_path, hair_path, animation_path, output_dir = [Path(arg).expanduser().resolve() for arg in args]
    output_dir.mkdir(parents=True, exist_ok=True)

    reset_scene()
    body_objects = import_asset(body_path)
    body_armature = find_armature(body_objects)
    body_meshes = [obj for obj in body_objects if obj.type == "MESH"]

    hair_objects = import_asset(hair_path)
    hair_armature = find_armature(hair_objects)
    hair_meshes = bind_to_shared_armature(hair_objects, hair_armature, body_armature)
    make_hair_brown(hair_meshes)

    animation_objects = import_asset(animation_path)
    animation_armature = find_armature(animation_objects)
    for obj in animation_objects:
        if obj.type == "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    actions = copy_actions(animation_armature, body_armature)

    all_meshes = body_meshes + hair_meshes
    export_candidate(output_dir / "xiaohe-rig-base-v1.glb", body_armature, all_meshes, actions)
    render_preview(output_dir / "xiaohe-rig-base-preview-v1.png", body_armature, actions["Idle_Base"])
    body_armature.animation_data.action = actions["Idle_Base"]
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "xiaohe-rig-base-v1.blend"))
    print(f"XIAOHE_BASE actions={','.join(sorted(actions))} bones={len(body_armature.data.bones)} meshes={len(all_meshes)}")


if __name__ == "__main__":
    main()
