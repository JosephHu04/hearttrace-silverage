"""Dress and soften the local Xiaohe motion candidate without replacing its rig.

Usage:
  blender --background assets/blender/candidates/xiaohe-rig-base-v1.blend \
    --python assets/blender/scripts/refine_xiaohe_candidate.py -- \
    assets/blender/candidates

The resulting GLB is for internal motion review only. It is not final character art.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy


def material(name: str, color: tuple[float, float, float], roughness: float = 0.82):
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    return mat


def soften_head(body, facial_meshes):
    """Improve the age impression modestly while keeping every skin weight."""
    for mesh in [body, *facial_meshes]:
        for vertex in mesh.data.vertices:
            point = vertex.co
            influence = min(1.0, max(0.0, (point.z - 1.29) / 0.075))
            if mesh != body:
                influence = 1.0
            point.x *= 1.0 + 0.26 * influence
            point.y *= 1.0 + 0.17 * influence
            point.z = 1.34 + (point.z - 1.34) * (1.0 + 0.12 * influence)
        mesh.data.update()


def weighted_loft(name, armature, rings, shade, weights_for_axis, along="z", segments=32):
    """Make a continuous tailored tube and blend its vertices across adjacent bones."""
    vertices = []
    weights = []
    faces = []
    for axis, center_1, center_2, radius_1, radius_2 in rings:
        for step in range(segments):
            angle = math.tau * step / segments
            if along == "z":
                point = (center_1 + radius_1 * math.sin(angle), center_2 - radius_2 * math.cos(angle), axis)
            else:
                point = (axis, center_1 - radius_1 * math.cos(angle), center_2 + radius_2 * math.sin(angle))
            vertices.append(point)
            weights.append(weights_for_axis(axis))
    for ring in range(len(rings) - 1):
        for step in range(segments):
            first = ring * segments + step
            next_step = ring * segments + (step + 1) % segments
            faces.append((first, next_step, next_step + segments, first + segments))
    data = bpy.data.meshes.new(name + "Mesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(shade)
    for polygon in data.polygons:
        polygon.use_smooth = True
    groups = {}
    for index, weight_map in enumerate(weights):
        for bone_name, amount in weight_map.items():
            group = groups.setdefault(bone_name, obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name))
            group.add([index], amount, "REPLACE")
    modifier = obj.modifiers.new("Shared 65 bone rig", "ARMATURE")
    modifier.object = armature
    obj.parent = armature
    return obj


def blend_weights(value, anchors):
    if value <= anchors[0][0]:
        return {anchors[0][1]: 1.0}
    if value >= anchors[-1][0]:
        return {anchors[-1][1]: 1.0}
    for (low, first), (high, second) in zip(anchors, anchors[1:]):
        if low <= value <= high:
            portion = (value - low) / (high - low)
            return {first: 1.0 - portion, second: portion}
    raise RuntimeError("Unreachable weight interval")


def duplicate_clothes(body, armature):
    apricot = material("Xiaohe_Knit_Apricot", (0.62, 0.27, 0.13))
    peach_light = material("Xiaohe_Knit_Edge", (0.73, 0.41, 0.24))
    cream = material("Xiaohe_Shirt_Cream", (0.82, 0.77, 0.65))
    sage = material("Xiaohe_Trousers_Sage", (0.33, 0.52, 0.40))
    cuff = material("Xiaohe_Sock_Cream", (0.85, 0.81, 0.70))
    shoes = material("Xiaohe_Shoes_Oat", (0.67, 0.61, 0.49))

    # Colour the underlying connected body first. It prevents skin gaps when
    # the loose overlay changes shape at shoulders, crotch and knees.
    base_materials = (sage, cuff, shoes, cream, apricot, peach_light)
    base_indices = {}
    for shade in base_materials:
        body.data.materials.append(shade)
        base_indices[shade.name] = len(body.data.materials) - 1
    for face in body.data.polygons:
        x, y, z = face.center
        if z < .11:
            shade = shoes
        elif z < .20:
            shade = cuff
        elif z < .86 and abs(x) < .32:
            shade = sage
        elif .83 < z < 1.265 and abs(x) < .24:
            shade = cream if y < -.045 and abs(x) < .075 else apricot
        elif 1.105 < z < 1.315 and .20 < abs(x) < .56:
            shade = peach_light if abs(x) > .50 else apricot
        else:
            continue
        face.material_index = base_indices[shade.name]

    jacket_rings = [
        (.825, 0, .023, .159, .120),
        (.86, 0, .020, .161, .122),
        (.96, 0, .014, .139, .119),
        (1.06, 0, .010, .139, .118),
        (1.15, 0, .016, .160, .112),
        (1.22, 0, .022, .170, .108),
        (1.255, 0, .020, .095, .075),
    ]
    clothing = [weighted_loft(
        "Xiaohe_Continuous_Apricot_Cardigan", armature, jacket_rings, apricot,
        lambda z: blend_weights(z, ((.82, "pelvis"), (.92, "spine_01"), (1.04, "spine_02"), (1.18, "spine_03"))),
    )]
    clothing.append(weighted_loft(
        "Xiaohe_Sage_Waistband", armature,
        ((.80, 0, .024, .151, .112), (.84, 0, .024, .156, .118), (.87, 0, .022, .156, .118)),
        sage, lambda _: {"pelvis": 1.0},
    ))
    for side, sign in (("l", 1), ("r", -1)):
        leg_rings = [
            (.16, sign * .096, .071, .091, .085),
            (.18, sign * .096, .069, .094, .089),
            (.32, sign * .096, .055, .083, .079),
            (.48, sign * .096, .038, .079, .085),
            (.64, sign * .096, .025, .085, .098),
            (.78, sign * .096, .025, .092, .109),
            (.86, sign * .096, .028, .091, .108),
        ]
        clothing.append(weighted_loft(
            f"Xiaohe_{side}_Wide_Cropped_Trouser", armature, leg_rings, sage,
            lambda z, side=side: blend_weights(z, ((.16, f"calf_{side}"), (.40, f"calf_{side}"), (.67, f"thigh_{side}"), (.86, f"thigh_{side}"))),
        ))
        sleeve_rings = [
            (sign * .12, .045, 1.226, .068, .069),
            (sign * .19, .046, 1.226, .071, .073),
            (sign * .29, .048, 1.226, .065, .066),
            (sign * .39, .050, 1.226, .056, .058),
            (sign * .48, .050, 1.226, .048, .051),
            (sign * .53, .049, 1.226, .046, .049),
        ]
        if sign < 0:
            sleeve_rings.reverse()
        clothing.append(weighted_loft(
            f"Xiaohe_{side}_Soft_Sleeve", armature, sleeve_rings, apricot,
            lambda x, side=side: blend_weights(abs(x), ((.12, f"upperarm_{side}"), (.33, f"upperarm_{side}"), (.53, f"lowerarm_{side}"))),
            along="x", segments=24,
        ))
        cuff_rings = [(sign * x, .049, 1.226, .047, .050) for x in (.515, .53, .548)]
        if sign < 0:
            cuff_rings.reverse()
        clothing.append(weighted_loft(
            f"Xiaohe_{side}_Cream_Cuff", armature, cuff_rings, cream,
            lambda x, side=side: {f"lowerarm_{side}": 1.0}, along="x", segments=24,
        ))
    # A fitted central shirt opening on top of the jacket cylinder.
    rows = ((.865, .052), (.96, .049), (1.06, .050), (1.15, .056), (1.22, .064), (1.25, .048))
    vertices = []
    faces = []
    weights = []
    for z, width in rows:
        ring = min(jacket_rings, key=lambda row: abs(row[0] - z))
        for step in range(9):
            x = width * (step / 4 - 1)
            y = ring[2] - ring[4] * math.sqrt(max(.1, 1 - (x / ring[3]) ** 2)) - .006
            vertices.append((x, y, z))
            weights.append(blend_weights(z, ((.82, "pelvis"), (.92, "spine_01"), (1.04, "spine_02"), (1.18, "spine_03"))))
    for row in range(len(rows) - 1):
        for step in range(8):
            first = row * 9 + step
            faces.append((first, first + 1, first + 10, first + 9))
    data = bpy.data.meshes.new("Xiaohe_Shirt_PlacketMesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    placket = bpy.data.objects.new("Xiaohe_Shirt_Placket", data)
    bpy.context.collection.objects.link(placket)
    data.materials.append(cream)
    groups = {}
    for index, mapping in enumerate(weights):
        for bone_name, amount in mapping.items():
            group = groups.setdefault(bone_name, placket.vertex_groups.get(bone_name) or placket.vertex_groups.new(name=bone_name))
            group.add([index], amount, "REPLACE")
    placket.modifiers.new("Shared 65 bone rig", "ARMATURE").object = armature
    placket.parent = armature
    clothing.append(placket)
    return clothing


def add_weighted_sphere(name, location, scale, shade, armature, bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(shade)
    group = obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Shared 65 bone rig", "ARMATURE")
    modifier.object = armature
    obj.parent = armature
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_details(armature):
    ivory = material("Xiaohe_Flower_Ivory", (1.0, 0.94, 0.76))
    gold = material("Xiaohe_Flower_Gold", (0.94, 0.69, 0.29))
    details = []
    for side in (-1, 1):
        for index in range(5):
            angle = index * math.tau / 5
            x = side * 0.145 + math.cos(angle) * .018
            z = 1.49 + math.sin(angle) * .018
            details.append(add_weighted_sphere(f"BunFlower_{side}_{index}", (x, -.079, z), (.010, .004, .015), ivory, armature, "Head"))
        details.append(add_weighted_sphere(f"BunFlowerCenter_{side}", (side * .145, -.085, 1.49), (.009, .006, .009), gold, armature, "Head"))
    for index, height in enumerate((.91, 1.015, 1.12)):
        details.append(add_weighted_sphere(f"CardiganFlowerButton_{index}", (.012, -.118, height), (.011, .006, .011), gold, armature, "spine_02"))
    return details


def reduce_textures():
    for image in bpy.data.images:
        if image.type == "IMAGE" and image.size[0] > 1024:
            image.scale(1024, 1024)
            image.pack()


def export(output, armature, meshes):
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


def render(output, armature):
    for track in armature.animation_data.nla_tracks:
        track.mute = True
    armature.animation_data.action = bpy.data.actions["Idle_Base"]
    bpy.context.scene.frame_set(10)
    scene = bpy.context.scene
    scene.render.filepath = str(output)
    scene.render.resolution_x = 720
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    bpy.ops.render.render(write_still=True)
    armature.animation_data.action = None


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise SystemExit("Expected output directory")
    output_dir = Path(args[0]).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    armature = bpy.data.objects["Armature"]
    body = bpy.data.objects["Teen_Female"]
    facial = [bpy.data.objects[name] for name in ("Eyes", "Eyebrows", "Hair_Buns_Teen")]
    soften_head(body, facial)
    clothes = duplicate_clothes(body, armature)
    details = add_details(armature)
    reduce_textures()
    meshes = [body, *facial, *clothes, *details]
    export(output_dir / "xiaohe-dressed-v2.glb", armature, meshes)
    render(output_dir / "xiaohe-dressed-preview-v2.png", armature)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "xiaohe-dressed-v2.blend"))
    print(f"XIAOHE_DRESSED meshes={len(meshes)} bones={len(armature.data.bones)}")


if __name__ == "__main__":
    main()
