"""Create the first rigged Yaoyao 3D blockout and export it as GLB.

This is deliberately a pipeline prototype, not the final art model.  It proves
that independently animated limbs, named actions and the web export all work
before time is spent on sculpting and hand-painted textures.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.actions, bpy.data.armatures, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            datablocks.remove(datablock)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.72) -> bpy.types.Material:
    item = bpy.data.materials.new(name)
    item.diffuse_color = color
    item.use_nodes = True
    shader = item.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    return item


def finish_mesh(obj: bpy.types.Object, mat: bpy.types.Material, name: str) -> bpy.types.Object:
    obj.name = name
    obj.data.name = f"{name}_Mesh"
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def uv_sphere(name: str, location, scale, mat, segments: int = 32, rings: int = 20) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=location)
    obj = finish_mesh(bpy.context.object, mat, name)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def rounded_cube(name: str, location, scale, mat, bevel: float = 0.12) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = finish_mesh(bpy.context.object, mat, name)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("SoftEdges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def cylinder_between(name: str, start, end, radius: float, mat, vertices: int = 24) -> bpy.types.Object:
    start_v, end_v = Vector(start), Vector(end)
    direction = end_v - start_v
    midpoint = (start_v + end_v) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=midpoint)
    obj = finish_mesh(bpy.context.object, mat, name)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    obj.rotation_mode = "XYZ"
    return obj


def add_bone(armature: bpy.types.Armature, name: str, head, tail, parent: str | None = None) -> None:
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    if parent:
        bone.parent = armature.edit_bones[parent]


def parent_to_bone(obj: bpy.types.Object, rig: bpy.types.Object, bone_name: str) -> None:
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world


def create_rig() -> bpy.types.Object:
    data = bpy.data.armatures.new("YaoyaoRig")
    rig = bpy.data.objects.new("YaoyaoRig", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    add_bone(data, "root", (0, 0, 0), (0, 0, 0.35))
    add_bone(data, "hips", (0, 0, 1.58), (0, 0, 1.88), "root")
    add_bone(data, "spine", (0, 0, 1.88), (0, 0, 2.35), "hips")
    add_bone(data, "chest", (0, 0, 2.35), (0, 0, 2.83), "spine")
    add_bone(data, "neck", (0, 0, 2.83), (0, 0, 3.08), "chest")
    add_bone(data, "head", (0, 0, 3.08), (0, 0, 3.7), "neck")
    for side, sign in (("L", 1), ("R", -1)):
        add_bone(data, f"upper_arm.{side}", (0.42 * sign, 0, 2.72), (0.98 * sign, 0, 2.36), "chest")
        add_bone(data, f"forearm.{side}", (0.98 * sign, 0, 2.36), (1.43 * sign, 0, 2.08), f"upper_arm.{side}")
        add_bone(data, f"hand.{side}", (1.43 * sign, 0, 2.08), (1.67 * sign, -0.02, 1.94), f"forearm.{side}")
        add_bone(data, f"thigh.{side}", (0.27 * sign, 0, 1.68), (0.29 * sign, 0, 1.0), "hips")
        add_bone(data, f"shin.{side}", (0.29 * sign, 0, 1.0), (0.3 * sign, 0, 0.3), f"thigh.{side}")
        add_bone(data, f"foot.{side}", (0.3 * sign, 0, 0.3), (0.3 * sign, -0.34, 0.13), f"shin.{side}")
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    return rig


def create_character(rig: bpy.types.Object) -> list[bpy.types.Object]:
    skin = material("Skin", (0.96, 0.67, 0.53, 1))
    sage = material("SageJacket", (0.46, 0.67, 0.55, 1))
    lavender = material("LavenderTrim", (0.67, 0.58, 0.79, 1))
    ivory = material("IvoryCloth", (0.91, 0.89, 0.82, 1))
    hair = material("WarmBrownHair", (0.18, 0.08, 0.045, 1), 0.55)
    eye = material("WarmBrownEyes", (0.12, 0.045, 0.025, 1), 0.35)
    white = material("EyeWhite", (0.98, 0.98, 0.96, 1))
    mouth = material("Mouth", (0.55, 0.12, 0.12, 1), 0.5)
    shoe = material("Shoe", (0.88, 0.87, 0.79, 1))

    pieces: list[tuple[bpy.types.Object, str]] = []
    pieces.append((uv_sphere("Head", (0, -0.01, 3.42), (0.46, 0.39, 0.56), skin), "head"))
    pieces.append((uv_sphere("HairCap", (0, 0.05, 3.72), (0.51, 0.43, 0.36), hair), "head"))
    for index, (x, y, z, sx, sy, sz) in enumerate((
        (-0.31, -0.18, 3.78, .23, .18, .2), (-0.08, -0.3, 3.88, .25, .16, .2),
        (0.18, -0.27, 3.86, .25, .16, .2), (0.34, -0.1, 3.7, .2, .18, .24),
        (-0.36, 0.02, 3.62, .2, .2, .27), (0.3, 0.08, 3.58, .22, .21, .27),
    )):
        pieces.append((uv_sphere(f"HairLock{index + 1:02d}", (x, y, z), (sx, sy, sz), hair, 20, 12), "head"))
    for side, sign in (("L", 1), ("R", -1)):
        pieces.append((uv_sphere(f"EyeWhite.{side}", (0.17 * sign, -0.365, 3.5), (.13, .045, .09), white, 20, 12), "head"))
        pieces.append((uv_sphere(f"Eye.{side}", (0.17 * sign, -0.405, 3.5), (.065, .025, .065), eye, 20, 12), "head"))
    pieces.append((rounded_cube("Mouth", (0, -0.405, 3.27), (.12, .018, .025), mouth, .02), "head"))

    pieces.append((rounded_cube("JacketTorso", (0, 0, 2.25), (.52, .3, .68), sage, .16), "chest"))
    pieces.append((rounded_cube("InnerShirt", (0, -0.31, 2.35), (.24, .035, .57), ivory, .05), "chest"))
    lapel_l = rounded_cube("Lapel.L", (.2, -.35, 2.47), (.115, .035, .52), lavender, .04)
    lapel_l.rotation_euler[1] = math.radians(-9)
    pieces.append((lapel_l, "chest"))
    lapel_r = rounded_cube("Lapel.R", (-.2, -.35, 2.47), (.115, .035, .52), lavender, .04)
    lapel_r.rotation_euler[1] = math.radians(9)
    pieces.append((lapel_r, "chest"))
    for z in (2.32, 2.05):
        pieces.append((rounded_cube(f"Closure{z}", (0, -.38, z), (.13, .025, .045), sage, .025), "chest"))

    for side, sign in (("L", 1), ("R", -1)):
        upper_start, upper_end = (.42 * sign, 0, 2.7), (.98 * sign, 0, 2.36)
        fore_start, fore_end = (.98 * sign, 0, 2.36), (1.43 * sign, 0, 2.08)
        pieces.append((cylinder_between(f"UpperArm.{side}", upper_start, upper_end, .19, sage), f"upper_arm.{side}"))
        pieces.append((cylinder_between(f"Forearm.{side}", fore_start, fore_end, .17, sage), f"forearm.{side}"))
        pieces.append((cylinder_between(f"Cuff.{side}", (1.3 * sign, 0, 2.16), (1.47 * sign, 0, 2.05), .195, lavender), f"forearm.{side}"))
        pieces.append((uv_sphere(f"Hand.{side}", (1.6 * sign, -.01, 1.99), (.18, .11, .13), skin, 24, 14), f"hand.{side}"))
        pieces.append((cylinder_between(f"Thigh.{side}", (.27 * sign, 0, 1.69), (.29 * sign, 0, 1.0), .255, ivory), f"thigh.{side}"))
        pieces.append((cylinder_between(f"Shin.{side}", (.29 * sign, 0, 1.01), (.3 * sign, 0, .32), .235, ivory), f"shin.{side}"))
        pieces.append((rounded_cube(f"Shoe.{side}", (.3 * sign, -.17, .17), (.26, .36, .14), shoe, .1), f"foot.{side}"))

    objects = []
    for obj, bone_name in pieces:
        parent_to_bone(obj, rig, bone_name)
        objects.append(obj)
    return objects


def key_rotation(rig: bpy.types.Object, action: bpy.types.Action, bone: str, frame: int, rotation) -> None:
    rig.animation_data.action = action
    pose = rig.pose.bones[bone]
    pose.rotation_mode = "XYZ"
    pose.rotation_euler = rotation
    pose.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone)


def key_location(rig: bpy.types.Object, action: bpy.types.Action, bone: str, frame: int, location) -> None:
    rig.animation_data.action = action
    pose = rig.pose.bones[bone]
    pose.location = location
    pose.keyframe_insert(data_path="location", frame=frame, group=bone)


def action(rig: bpy.types.Object, name: str, frames: int, curves: dict[str, list[tuple[int, tuple[float, float, float]]]], root_motion=None) -> bpy.types.Action:
    item = bpy.data.actions.new(name)
    item.use_fake_user = True
    for bone, keys in curves.items():
        for frame, rotation in keys:
            key_rotation(rig, item, bone, frame, rotation)
    if root_motion:
        for frame, location in root_motion:
            key_location(rig, item, "root", frame, location)
    rig.animation_data.action = item
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frames
    return item


def create_actions(rig: bpy.types.Object) -> dict[str, bpy.types.Action]:
    if not rig.animation_data:
        rig.animation_data_create()
    zero = (0.0, 0.0, 0.0)
    actions = {
        "Idle_Base": action(rig, "Idle_Base", 120, {
            "chest": [(1, zero), (60, (0.015, 0, 0.01)), (120, zero)],
            "head": [(1, zero), (40, (0, 0.02, -0.025)), (80, (0, -0.015, 0.02)), (120, zero)],
        }, [(1, (0, 0, 0)), (60, (0, 0, .025)), (120, (0, 0, 0))]),
        "Idle_Wave": action(rig, "Idle_Wave", 60, {
            "upper_arm.R": [(1, zero), (12, (-0.15, -0.2, -0.8)), (52, (-0.15, -0.2, -0.8)), (60, zero)],
            "forearm.R": [(1, zero), (12, (0.1, 0.05, -1.0)), (22, (0.1, 0.05, -.72)), (32, (0.1, 0.05, -1.0)), (42, (0.1, 0.05, -.72)), (52, (0.1, 0.05, -1.0)), (60, zero)],
            "hand.R": [(1, zero), (18, (0, .18, -.2)), (28, (0, -.18, .2)), (38, (0, .18, -.2)), (48, (0, -.18, .2)), (60, zero)],
        }),
        "Listen": action(rig, "Listen", 72, {
            "spine": [(1, zero), (24, (.06, 0, 0)), (48, (.06, 0, 0)), (72, zero)],
            "head": [(1, zero), (24, (.04, -.03, -.09)), (48, (.04, -.03, -.09)), (72, zero)],
        }),
        "Think": action(rig, "Think", 84, {
            "head": [(1, zero), (28, (-.04, .02, .13)), (56, (-.02, -.02, .08)), (84, zero)],
            "forearm.L": [(1, zero), (28, (0, .18, .42)), (56, (0, .18, .42)), (84, zero)],
        }),
        "Talk": action(rig, "Talk", 48, {
            "head": [(1, zero), (12, (.025, 0, -.02)), (24, (-.018, 0, .02)), (36, (.02, 0, -.015)), (48, zero)],
            "hand.L": [(1, zero), (16, (0, .08, .05)), (32, (0, -.08, -.05)), (48, zero)],
        }),
        "Nod": action(rig, "Nod", 44, {
            "head": [(1, zero), (12, (.16, 0, 0)), (22, (-.04, 0, 0)), (32, (.12, 0, 0)), (44, zero)],
        }),
        "Cheer": action(rig, "Cheer", 56, {
            "upper_arm.L": [(1, zero), (18, (-.1, .1, .35)), (40, (-.1, .1, .35)), (56, zero)],
            "upper_arm.R": [(1, zero), (18, (-.1, -.1, -.35)), (40, (-.1, -.1, -.35)), (56, zero)],
            "head": [(1, zero), (18, (-.06, 0, 0)), (40, (-.06, 0, 0)), (56, zero)],
        }, [(1, (0, 0, 0)), (18, (0, 0, .06)), (40, (0, 0, .06)), (56, (0, 0, 0))]),
        "Concern": action(rig, "Concern", 72, {
            "head": [(1, zero), (24, (.03, 0, -.12)), (48, (.03, 0, -.12)), (72, zero)],
            "chest": [(1, zero), (24, (.035, 0, 0)), (48, (.035, 0, 0)), (72, zero)],
        }),
        "Alert": action(rig, "Alert", 40, {
            "spine": [(1, zero), (8, (-.055, 0, 0)), (32, (-.055, 0, 0)), (40, zero)],
            "head": [(1, zero), (8, (-.04, 0, 0)), (32, (-.04, 0, 0)), (40, zero)],
        }),
    }
    return actions


def look_at(obj: bpy.types.Object, target) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_preview(rig: bpy.types.Object, action_item: bpy.types.Action) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.055, 0.055, 0.055)
    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0, -9.8, 3.1)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 4.8
    look_at(camera, (0, 0, 2.0))
    bpy.context.scene.camera = camera
    for name, location, energy, size in (
        ("Key", (-4, -5, 7), 900, 4.0),
        ("Fill", (4, -2, 5), 600, 3.0),
        ("Rim", (0, 4, 6), 800, 3.0),
    ):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        light.location = location
        look_at(light, (0, 0, 2.1))
        bpy.context.collection.objects.link(light)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    rig.animation_data.action = action_item
    scene.frame_set(30)
    scene.render.filepath = str(EXPORT_DIR / "yaoyao-blockout-preview-v1.png")
    bpy.ops.render.render(write_still=True)


def export_glb(rig: bpy.types.Object, character_objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for obj in character_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(EXPORT_DIR / "yaoyao-blockout-v1.glb"),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_optimize_animation_size=True,
        export_yup=True,
    )


def main() -> None:
    reset_scene()
    rig = create_rig()
    character = create_character(rig)
    actions = create_actions(rig)
    export_glb(rig, character)
    setup_preview(rig, actions["Idle_Wave"])
    rig.animation_data.action = actions["Idle_Base"]
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "yaoyao-blockout-v1.blend"))
    print(f"Created {ROOT / 'yaoyao-blockout-v1.blend'}")
    print(f"Created {EXPORT_DIR / 'yaoyao-blockout-v1.glb'}")


if __name__ == "__main__":
    main()
