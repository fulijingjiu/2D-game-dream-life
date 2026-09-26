"""Build a modular low-poly hero, rig one reusable slash action, and render PNG frames."""
import bpy
import math
import os
import shutil
from mathutils import Euler, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRAMES = os.path.join(ROOT, "frames")
os.makedirs(FRAMES, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    return m

teal = mat("Cloth_Teal", (0.10, 0.31, 0.33))
gold = mat("Scarf_Ochre", (0.72, 0.43, 0.12))
skin = mat("Skin_Warm", (0.77, 0.52, 0.34))
hair = mat("Hair_Charcoal", (0.09, 0.075, 0.07))
leather = mat("Leather_Dark", (0.19, 0.14, 0.12))
steel = mat("Steel_Muted", (0.52, 0.61, 0.62))
ivory = mat("Eye_Ivory", (0.88, 0.84, 0.72))

def cube(name, loc, scale, material, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new("Soft low-poly edges", "BEVEL")
        mod.width = bevel
        mod.segments = 1
    o.data.materials.append(material)
    return o

def sphere(name, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = False
    return o

def beam(name, a, b, width, material):
    mid = (Vector(a) + Vector(b)) * 0.5
    vec = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cube_add(size=1, location=mid)
    o = bpy.context.object
    o.name = name
    o.dimensions = (width, width, vec.length)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = vec.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = o.modifiers.new("Rounded silhouette", "BEVEL")
    bevel.width = width * 0.28
    bevel.segments = 1
    o.data.materials.append(material)
    return o

# Character axis: X is left/right, Z is up, camera looks along Y.
reference_path = os.path.join(ROOT, "reference", "hero_side_reference.png")
reference_image = bpy.data.images.load(reference_path, check_existing=True)
bpy.ops.object.empty_add(type="IMAGE", location=(-2.1, 0.45, 2.25))
reference = bpy.context.object
reference.name = "Reference_AI_Side_Concept"
reference.data = reference_image
reference.rotation_euler[0] = math.radians(90)
reference.empty_display_size = 4.2
reference.hide_render = True
turnaround_path = os.path.join(ROOT, "reference", "2026-09-25-角色三视图参考.png")
turnaround_image = bpy.data.images.load(turnaround_path, check_existing=True)
bpy.ops.object.empty_add(type="IMAGE", location=(2.7, 0.5, 2.2))
turnaround = bpy.context.object
turnaround.name = "Reference_Three_View"
turnaround.data = turnaround_image
turnaround.rotation_euler[0] = math.radians(90)
turnaround.empty_display_size = 5.0
turnaround.hide_render = True

cube("Torso_Tunic", (0, 0, 2.65), (0.82, 0.48, 1.05), teal, 0.18)
cube("Vest_Front", (0.20, -0.255, 2.72), (0.42, 0.055, 0.70), leather, 0.10)
cube("Chest_Panel", (0.21, -0.292, 2.78), (0.30, 0.025, 0.48), teal, 0.07)
cube("Belt", (0, -0.005, 2.13), (0.9, 0.5, 0.16), leather, 0.05)
cube("Belt_Buckle", (0.18, -0.275, 2.13), (0.16, 0.035, 0.13), gold, 0.025)
cube("Belt_Pouch", (-0.28, -0.29, 2.12), (0.22, 0.12, 0.24), leather, 0.04)
beam("Crossbody_Strap", (-0.34, -0.30, 3.05), (0.30, -0.30, 2.30), 0.10, leather)
sphere("Head", (0.06, 0, 3.55), (0.38, 0.34, 0.43), skin)
sphere("Ear", (-0.18, -0.275, 3.57), (0.105, 0.055, 0.12), skin)
sphere("Hair", (-0.05, 0.015, 3.82), (0.40, 0.36, 0.25), hair)
sphere("Eye_White", (0.285, -0.295, 3.62), (0.07, 0.035, 0.055), ivory)
sphere("Eye_Dark", (0.315, -0.327, 3.62), (0.027, 0.018, 0.035), hair)
beam("Eyebrow", (0.20, -0.32, 3.72), (0.33, -0.32, 3.74), 0.035, hair)
sphere("Nose", (0.405, -0.27, 3.52), (0.075, 0.07, 0.06), skin)
beam("Mouth", (0.29, -0.33, 3.39), (0.37, -0.32, 3.385), 0.018, leather)
for i, (x, z, tilt) in enumerate([(-0.24, 3.98, -0.22), (-0.04, 4.03, 0.04), (0.15, 3.98, 0.24)]):
    bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=0.17, radius2=0.015, depth=0.30, location=(x, -0.01, z))
    lock = bpy.context.object
    lock.name = f"Hair_Lock_{i+1:02d}"
    lock.rotation_euler[1] = tilt
    lock.data.materials.append(hair)
cube("Scarf", (0.02, -0.28, 3.24), (0.55, 0.12, 0.22), gold, 0.08)
tail = cube("Scarf_Tail", (-0.37, -0.25, 2.98), (0.20, 0.10, 0.62), gold, 0.06)
tail.rotation_euler[1] = -0.16
sphere("Shoulder_Pad_Back", (-0.34, -0.02, 3.02), (0.27, 0.29, 0.24), leather)
sphere("Shoulder_Pad_Sword", (0.34, -0.06, 3.02), (0.27, 0.29, 0.23), teal)

# Separate limbs are deliberately independent, so appearance and motion can be swapped.
beam("Leg_Back", (-0.14, 0, 2.12), (-0.20, 0, 0.62), 0.30, leather)
beam("Leg_Front", (0.15, -0.03, 2.12), (0.22, -0.03, 0.62), 0.30, leather)
cube("Boot_Back", (-0.26, -0.10, 0.43), (0.57, 0.38, 0.25), leather, 0.08)
cube("Boot_Front", (0.30, -0.12, 0.43), (0.57, 0.38, 0.25), leather, 0.08)
beam("Arm_Back", (-0.35, 0, 3.02), (-0.54, -0.03, 2.40), 0.22, teal)
arm = beam("Arm_Sword", (0.34, -0.12, 3.02), (0.58, -0.14, 2.54), 0.22, teal)
sphere("Hand_Sword", (0.58, -0.14, 2.53), (0.13, 0.13, 0.13), skin)
beam("Bracer_Sword", (0.48, -0.17, 2.77), (0.56, -0.17, 2.60), 0.25, leather)

# A tiny geometric sword, kept as its own prop object for modular gear swapping.
sword = beam("Gear_Sword_Blade", (0.60, -0.18, 2.56), (0.76, -0.18, 1.95), 0.09, steel)
cube("Gear_Sword_Grip", (0.58, -0.18, 2.62), (0.28, 0.11, 0.09), leather, 0.025)
beam("Gear_Sword_Guard", (0.49, -0.19, 2.55), (0.69, -0.19, 2.60), 0.055, gold)
sphere("Gear_Sword_Pommel", (0.48, -0.19, 2.69), (0.07, 0.06, 0.07), gold)

# Rig bones are a reusable motion skeleton. Rigid bone parenting keeps outfits and gear swappable.
armature_data = bpy.data.armatures.new("Rig_Hero_Data")
rig = bpy.data.objects.new("Rig_Hero", armature_data)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
edit_bones = armature_data.edit_bones
bone_specs = {
    "Root": ((0, 0, 0), (0, 0, 2.1), None),
    "Pelvis": ((0, 0, 2.1), (0, 0, 2.4), "Root"),
    "Spine": ((0, 0, 2.25), (0, 0, 3.2), "Pelvis"),
    "Head": ((0.06, 0, 3.22), (0.06, 0, 3.88), "Spine"),
    "Arm_Back": ((-0.35, 0, 3.02), (-0.54, -0.03, 2.40), "Spine"),
    "Arm_Sword": ((0.34, -0.12, 3.02), (0.58, -0.14, 2.54), "Spine"),
    "Hand_Sword": ((0.58, -0.14, 2.54), (0.62, -0.18, 2.28), "Arm_Sword"),
    "Leg_Back": ((-0.14, 0, 2.12), (-0.20, 0, 0.62), "Pelvis"),
    "Leg_Front": ((0.15, -0.03, 2.12), (0.22, -0.03, 0.62), "Pelvis"),
    "Scarf_Tail": ((-0.12, -0.25, 3.2), (-0.37, -0.25, 2.68), "Spine"),
}
for name, (head, tail_point, parent_name) in bone_specs.items():
    b = edit_bones.new(name)
    b.head = head
    b.tail = tail_point
    b.align_roll(Vector((0, 1, 0)))
    if parent_name:
        b.parent = edit_bones[parent_name]
        b.use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")
rig.show_in_front = True
armature_data.display_type = "OCTAHEDRAL"

def parent_to_bone(obj, bone_name):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    armature_data.bones.active = armature_data.bones[bone_name]
    bpy.ops.object.parent_set(type="BONE", keep_transform=True)
    bpy.ops.object.mode_set(mode="OBJECT")

bone_assignments = {
    "Torso_Tunic": "Spine", "Vest_Front": "Spine", "Chest_Panel": "Spine",
    "Belt": "Pelvis", "Belt_Buckle": "Pelvis", "Belt_Pouch": "Pelvis",
    "Crossbody_Strap": "Spine", "Head": "Head", "Ear": "Head", "Hair": "Head",
    "Eye_White": "Head", "Eye_Dark": "Head", "Eyebrow": "Head", "Nose": "Head", "Mouth": "Head",
    "Hair_Lock_01": "Head", "Hair_Lock_02": "Head", "Hair_Lock_03": "Head",
    "Scarf": "Spine", "Scarf_Tail": "Scarf_Tail", "Shoulder_Pad_Back": "Spine",
    "Shoulder_Pad_Sword": "Spine", "Leg_Back": "Leg_Back", "Boot_Back": "Leg_Back",
    "Leg_Front": "Leg_Front", "Boot_Front": "Leg_Front", "Arm_Back": "Arm_Back",
    "Arm_Sword": "Arm_Sword", "Hand_Sword": "Hand_Sword", "Bracer_Sword": "Arm_Sword",
}
for object_name, bone_name in bone_assignments.items():
    parent_to_bone(bpy.data.objects[object_name], bone_name)

# A compact anticipation → strike → follow-through → recovery clip.
scene = bpy.context.scene
action = bpy.data.actions.new("Action_Slash")
rig.animation_data_create()
rig.animation_data.action = action
pose_angles = {
    1: {}, 2: {"Pelvis": 0.02, "Spine": -0.02, "Arm_Sword": 0.08},
    3: {"Pelvis": 0.04, "Spine": -0.05, "Arm_Sword": 0.18, "Hand_Sword": 0.10},
    4: {"Spine": -0.02, "Arm_Sword": 0.04, "Hand_Sword": 0.02},
    5: {"Spine": 0.02, "Arm_Sword": -0.42, "Hand_Sword": -0.48},
    6: {"Spine": 0.03, "Arm_Sword": -0.82, "Hand_Sword": -1.15},
    7: {"Spine": 0.02, "Arm_Sword": -0.58, "Hand_Sword": -0.78},
    8: {"Arm_Sword": -0.30, "Hand_Sword": -0.38, "Scarf_Tail": 0.14},
    9: {"Arm_Sword": -0.12, "Hand_Sword": -0.16, "Scarf_Tail": 0.10},
    10: {"Spine": 0.01, "Scarf_Tail": 0.04},
    11: {"Scarf_Tail": 0.01}, 12: {},
}
for frame in range(1, 13):
    for bone_name in bone_specs:
        pb = rig.pose.bones[bone_name]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler[2] = pose_angles.get(frame, {}).get(bone_name, 0.0)
        pb.keyframe_insert(data_path="rotation_euler", index=2, frame=frame, group=bone_name)
    scene.frame_set(frame)
scene.frame_start = 1
scene.frame_end = 12

# Keep weapon rotation independent of bone roll while its grip point follows the animated hand.
scene.frame_set(1)
hand_bone = rig.pose.bones["Hand_Sword"]
hand_world = rig.matrix_world @ hand_bone.matrix.translation
bpy.ops.object.empty_add(type="ARROWS", location=hand_world)
weapon_pivot = bpy.context.object
weapon_pivot.name = "EquipmentPivot_Sword"
weapon_pivot.rotation_mode = "XYZ"
weapon_parts = [bpy.data.objects[name] for name in (
    "Gear_Sword_Blade", "Gear_Sword_Grip", "Gear_Sword_Guard", "Gear_Sword_Pommel"
)]
for part in weapon_parts:
    world = part.matrix_world.copy()
    part.parent = weapon_pivot
    part.matrix_parent_inverse = weapon_pivot.matrix_world.inverted()
    part.matrix_world = world
weapon_action = bpy.data.actions.new("Action_Slash_Equipment")
weapon_pivot.animation_data_create()
weapon_pivot.animation_data.action = weapon_action
weapon_angles = {
    1: 0.0, 2: 0.08, 3: 0.16, 4: 0.02,
    5: -0.78, 6: -1.30, 7: -1.00, 8: -0.58,
    9: -0.22, 10: -0.06, 11: 0.0, 12: 0.0,
}
for frame in range(1, 13):
    scene.frame_set(frame)
    hand_world = rig.matrix_world @ hand_bone.matrix.translation
    weapon_pivot.location = hand_world
    weapon_pivot.rotation_euler[1] = weapon_angles[frame]
    weapon_pivot.keyframe_insert(data_path="location", frame=frame)
    weapon_pivot.keyframe_insert(data_path="rotation_euler", index=1, frame=frame)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 12
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 384
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1

# Camera and simple studio light.
bpy.ops.object.camera_add(location=(0, -12, 2.12))
camera = bpy.context.object
camera.name = "Camera_Side_Ortho"
camera.rotation_euler = (math.radians(90), 0, 0)
camera.data.type = "ORTHO"
camera.data.ortho_scale = 5.2
scene.camera = camera

bpy.ops.object.light_add(type="AREA", location=(-3, -5, 7))
light = bpy.context.object
light.name = "Key_Light"
light.data.energy = 1100
light.data.shape = "DISK"
light.data.size = 5
light.rotation_euler = (math.radians(25), 0, math.radians(-25))

# Keep a Z/depth pass available in the saved Blender project for later 2.5D use.
scene.view_layers[0].use_pass_z = True
scene.render.filepath = os.path.join(FRAMES, "frame_")
for frame in range(1, 13):
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(FRAMES, f"frame_{frame:02d}.png")
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "hero_slash_prototype.blend"))
godot_frames = os.path.join(ROOT, "godot", "frames")
os.makedirs(godot_frames, exist_ok=True)
for frame in range(1, 13):
    filename = f"frame_{frame:02d}.png"
    shutil.copy2(os.path.join(FRAMES, filename), os.path.join(godot_frames, filename))
print(f"Rendered 12 PNG frames to {FRAMES}")
