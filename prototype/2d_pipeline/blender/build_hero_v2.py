"""Build and render the revised hero as a layered 2.5D cutout character.

Run from any directory:
    blender --background --python build_hero_v2.py

Each pose is assembled from reusable named parts and rendered at a fixed 128x170
native pixel-art resolution. The pose table is data, separate from appearance/material data.
"""
import bpy
import math
import os
import shutil
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "v2")
FRAMES = os.path.join(OUT, "frames")
GODOT_FRAMES = os.path.join(OUT, "godot", "frames")
BLEND_DIR = os.path.join(OUT, "blender")
os.makedirs(FRAMES, exist_ok=True)
os.makedirs(GODOT_FRAMES, exist_ok=True)
os.makedirs(BLEND_DIR, exist_ok=True)

W, H = 128, 170
PX = H / 5.12  # Native pixel-art resolution at the fixed orthographic framing.
FLOOR_Z = 0.0
CAMERA_Z = 2.32
DEPTH_FRONT = -0.32

def linear_channel(value):
    value = value / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

def material(name, hex_color, alpha=1.0):
    rgb = tuple(linear_channel(int(hex_color[i:i+2], 16)) for i in (1, 3, 5))
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*rgb, alpha)
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    return m

PAL = {
    "outline": material("Ink_outline_#171B24", "#171B24"),
    "coat": material("Coat_ink_blue_#27303D", "#27303D"),
    "coat_shadow": material("Coat_shadow_#1D2530", "#1D2530"),
    "coat_light": material("Coat_light_#3A4657", "#3A4657"),
    "ivory": material("Tunic_bone_#E4DED1", "#E4DED1"),
    "ivory_shadow": material("Tunic_shadow_#C6BFAF", "#C6BFAF"),
    "red": material("Scarf_vermilion_#A9473F", "#A9473F"),
    "red_shadow": material("Scarf_shadow_#743530", "#743530"),
    "red_light": material("Scarf_light_#C66355", "#C66355"),
    "brass": material("Brass_#A98245", "#A98245"),
    "brass_light": material("Brass_light_#D1AE69", "#D1AE69"),
    "leather": material("Leather_#49382F", "#49382F"),
    "leather_shadow": material("Leather_shadow_#302722", "#302722"),
    "pants": material("Trousers_#302F32", "#302F32"),
    "pants_light": material("Trousers_light_#454348", "#454348"),
    "skin": material("Skin_#D9A783", "#D9A783"),
    "skin_shadow": material("Skin_shadow_#B98167", "#B98167"),
    "hair": material("Hair_#202127", "#202127"),
    "hair_light": material("Hair_light_#383943", "#383943"),
    "silver": material("Silver_lock_#D4D0C7", "#D4D0C7"),
    "steel": material("Blade_steel_#BBC4C8", "#BBC4C8"),
    "steel_light": material("Blade_edge_#E9ECEA", "#E9ECEA"),
    "glass_amber": material("Memory_core_amber_#D7A84C", "#D7A84C"),
    "glass_green": material("Memory_core_green_#63A58E", "#63A58E"),
    "glass_bone": material("Memory_core_bone_#E8E0C8", "#E8E0C8"),
    "glass_red": material("Memory_core_red_#B95048", "#B95048"),
    "trail_a": material("Slash_trail_a", "#F3DDAA", 0.20),
    "trail_b": material("Slash_trail_b", "#C66355", 0.26),
    "shadow": material("Contact_shadow", "#10141C", 0.26),
}

def mesh_poly(name, points, y, mat, stroke=True, z_offset=0.0):
    """Create a flat filled x/z polygon; optional backplate gives a clean ink edge."""
    if len(points) < 3:
        return None
    center_x = sum(p[0] for p in points) / len(points)
    center_z = sum(p[1] for p in points) / len(points)
    if stroke:
        expanded = []
        for x, z in points:
            dx, dz = x - center_x, z - center_z
            length = max(math.hypot(dx, dz), 1e-5)
            expanded.append((x + dx / length * 0.018, z + dz / length * 0.018))
        mesh_poly(name + "__ink", expanded, y + 0.012, PAL["outline"], False)
    verts = [(x, y, z + z_offset) for x, z in points]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], [list(range(len(verts)))])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def capsule(name, a, b, width, y, mat, stroke=True):
    """Stylized tapered limb segment with pointed polygon ends and broad planes."""
    ax, az = a; bx, bz = b
    dx, dz = bx-ax, bz-az
    length = max(math.hypot(dx, dz), 0.001)
    nx, nz = -dz / length, dx / length
    wa, wb = width * 0.56, width * 0.44
    pts = [
        (ax + nx*wa, az + nz*wa), (ax + dx*.24 + nx*width*.52, az + dz*.24 + nz*width*.52),
        (ax + dx*.72 + nx*width*.43, az + dz*.72 + nz*width*.43), (bx + nx*wb, bz + nz*wb),
        (bx - nx*wb, bz - nz*wb), (ax + dx*.70 - nx*width*.42, az + dz*.70 - nz*width*.42),
        (ax + dx*.24 - nx*width*.48, az + dz*.24 - nz*width*.48), (ax - nx*wa, az - nz*wa),
    ]
    obj = mesh_poly(name, pts, y, mat, stroke)
    # One broad angular highlight face, kept inside the silhouette.
    facet = [
        (ax + nx*wa*.60 + dx*.12, az + nz*wa*.60 + dz*.12),
        (ax + dx*.29 + nx*width*.24, az + dz*.29 + nz*width*.24),
        (ax + dx*.76 + nx*width*.20, az + dz*.76 + nz*width*.20),
        (bx + nx*wb*.35, bz + nz*wb*.35),
    ]
    mesh_poly(name + "__facet", facet, y-0.008, mat, False)
    return obj

def line_poly(name, a, b, width, y, mat):
    ax, az = a; bx, bz = b
    dx, dz = bx-ax, bz-az
    length = max(math.hypot(dx, dz), 1e-5)
    nx, nz = -dz/length*width/2, dx/length*width/2
    return mesh_poly(name, [(ax+nx,az+nz),(bx+nx,bz+nz),(bx-nx,bz-nz),(ax-nx,az-nz)], y, mat, False)

def bezier_sample(points, count=14):
    p0,p1,p2,p3 = [Vector((x,z)) for x,z in points]
    result=[]
    for i in range(count+1):
        t=i/count; u=1-t
        p=p0*u**3 + p1*3*u*u*t + p2*3*u*t*t + p3*t**3
        result.append((p.x,p.y))
    return result

def add_sword(hand, angle_deg, frame_index):
    angle = math.radians(angle_deg)
    d = Vector((math.cos(angle), math.sin(angle)))
    n = Vector((-d.y, d.x))
    h = Vector(hand)
    guard_at = h + d*0.23
    blade_start = guard_at + d*0.12
    blade_end = h + d*1.18
    pts = [
        (blade_start.x+n.x*.055,blade_start.y+n.y*.055),
        (blade_end.x+n.x*.012,blade_end.y+n.y*.012),
        (blade_end.x,blade_end.y),
        (blade_start.x-n.x*.055,blade_start.y-n.y*.055),
    ]
    mesh_poly("Gear_Sword_Blade", pts, -.82, PAL["steel"], True)
    line_poly("Gear_Sword_Edge", (blade_start.x+n.x*.04,blade_start.y+n.y*.04), (blade_end.x-n.x*.015,blade_end.y-n.y*.015), .018, -.85, PAL["steel_light"])
    guard_a, guard_b = guard_at+n*.17, guard_at-n*.17
    line_poly("Gear_Sword_Guard", tuple(guard_a), tuple(guard_b), .085, -.88, PAL["brass"])
    grip_end = h - d*.27
    line_poly("Gear_Sword_Grip", tuple(grip_end), tuple(guard_at), .09, -.89, PAL["leather"])
    pom = h-d*.30
    mesh_poly("Gear_Sword_Pommel", [(pom.x-.07,pom.y),(pom.x,pom.y+.055),(pom.x+.07,pom.y),(pom.x,pom.y-.055)], -.90, PAL["brass_light"], False)

def build_hero(frame_index, pose):
    """Assemble distinct named art parts in a consistent side-view depth stack."""
    angle, hand_x, hand_z, lean, stride, scarf_lag = pose
    # Ground contact and rear silhouette first.
    shadow_pts = [(-.56,.02),(-.42,.075),(.33,.075),(.56,.025),(.36,0.0),(-.38,0.0)]
    mesh_poly("Ground_Contact_Shadow", shadow_pts, .20, PAL["shadow"], False)

    # Rear leg, trouser and boot; one leg holds the planted root, one advances slightly.
    rear_hip=(-.19,2.06); rear_knee=(-.26-stride*.12,1.18); rear_ankle=(-.24-stride*.12,.22)
    front_hip=(.18,2.08); front_knee=(.26+stride*.12,1.15); front_ankle=(.36+stride*.18,.22)
    capsule("Hero_Leg_Back", rear_hip, rear_knee, .38, .08, PAL["pants"])
    capsule("Hero_Leg_Back_Shin", rear_knee, rear_ankle, .27, .065, PAL["pants"])
    capsule("Hero_Leg_Front", front_hip, front_knee, .40, .00, PAL["pants"])
    capsule("Hero_Leg_Front_Shin", front_knee, front_ankle, .28, -.015, PAL["pants_light"])
    # boots, toe points toward the attack direction; sole remains on fixed baseline.
    mesh_poly("Hero_Boot_Back", [(-.50,.04),(-.46,.28),(-.29,.34),(-.12,.25),(-.09,.10),(-.15,0.0),(-.49,0.0)], -.055, PAL["leather"], True)
    mesh_poly("Hero_Boot_Front", [(front_ankle[0]-.12,.04),(front_ankle[0]-.10,.28),(front_ankle[0]+.06,.34),(front_ankle[0]+.30,.22),(front_ankle[0]+.47,.15),(front_ankle[0]+.44,.035),(front_ankle[0]-.12,0.0)], -.075, PAL["leather"], True)
    line_poly("Boot_Sole_Front", (front_ankle[0]-.10,.025),(front_ankle[0]+.43,.025),.025,-.09,PAL["ivory_shadow"])
    line_poly("Boot_Sole_Back", (-.48,.025),(-.13,.025),.025,-.08,PAL["ivory_shadow"])
    for x in (-.37, front_ankle[0]+.02):
        line_poly("Boot_Straps", (x,.19),(x+.10,.19),.032,-.10,PAL["brass"])

    # Scarf tail sits behind the jacket and swings independently through the pose table.
    tail_end_x=-.60-scarf_lag*.30
    tail_end_z=1.00+abs(scarf_lag)*.10
    scarf_pts=bezier_sample([(-.20,3.40),(-.46,3.12),(-.36+scarf_lag*.4,2.1),(tail_end_x,tail_end_z)],12)
    scarf_w=.19
    ribbon=[]
    for i,(x,z) in enumerate(scarf_pts):
        taper=.98-.34*i/(len(scarf_pts)-1)
        ribbon.append((x-scarf_w*taper/2,z))
    for i in reversed(range(len(scarf_pts))):
        x,z=scarf_pts[i]; taper=.98-.34*i/(len(scarf_pts)-1)
        ribbon.append((x+scarf_w*taper/2,z))
    # torn two-point hem
    ribbon[-2]=(ribbon[-2][0]+.055,ribbon[-2][1]-.10)
    mesh_poly("Hero_Scarf_Tail", ribbon, .045, PAL["red"], True)
    line_poly("Scarf_Fold_Shadow",(-.28,3.10),(-.46,1.65),.035,.028,PAL["red_shadow"])
    line_poly("Scarf_Fold_Light",(-.19,3.15),(-.33,2.15),.025,.020,PAL["red_light"])

    # Pelvis, trousers details, and rear short-coat tails.
    mesh_poly("Hero_Pelvis", [(-.36,2.30),(-.34,2.58),(.31,2.58),(.37,2.30),(.25,1.98),(.02,1.88),(-.23,2.0)], -.04, PAL["pants"], True)
    mesh_poly("Hero_Coat_Tail_Back", [(-.39,3.18),(-.59,2.78),(-.66,2.21),(-.40,2.30),(-.20,2.68),(-.14,3.12)], -.13, PAL["coat_shadow"], True)
    mesh_poly("Hero_Coat_Tail_Front", [(.25,3.12),(.53,2.82),(.64,2.22),(.40,2.31),(.15,2.57),(.08,3.08)], -.20, PAL["coat"], True)
    line_poly("Trousers_Seam",(-.19,1.94),(-.22,1.46),.018,-.10,PAL["pants_light"])
    mesh_poly("Trousers_Pocket", [(-.28,2.32),(-.05,2.31),(-.07,2.16),(-.27,2.17)], -.13, PAL["pants_light"], False)
    mesh_poly("Trousers_Pocket_Front", [(.08,2.31),(.30,2.32),(.29,2.17),(.10,2.16)], -.15, PAL["pants_light"], False)

    # Far arm behind torso, then torso and inner wrap tunic.
    far_shoulder=(-.37,3.25); far_elbow=(-.52,2.82); far_wrist=(-.48,2.45)
    capsule("Hero_Arm_Far_Upper", far_shoulder, far_elbow, .28, -.02, PAL["coat_shadow"])
    capsule("Hero_Arm_Far_Forearm", far_elbow, far_wrist, .22, -.04, PAL["coat_light"])
    mesh_poly("Hero_Torso_Outline", [(-.50,3.34),(-.37,3.52),(.34,3.51),(.53,3.31),(.42,2.54),(.30,2.38),(-.36,2.42),(-.47,2.61)], -.16, PAL["outline"], False)
    mesh_poly("Hero_Tunic", [(-.36,3.37),(-.27,3.44),(.28,3.42),(.36,3.28),(.26,2.47),(-.25,2.48)], -.19, PAL["ivory"], True)
    mesh_poly("Tunic_Shadow_Panel", [(-.31,3.30),(-.12,3.35),(-.02,2.50),(-.24,2.50)], -.21, PAL["ivory_shadow"], False)
    mesh_poly("Tunic_Cross_Fold", [(-.25,2.94),(-.12,2.84),(.13,2.56),(.04,2.52),(-.16,2.70)], -.225, PAL["ivory"], False)
    mesh_poly("Tunic_Warm_Shade", [(.17,3.08),(.24,2.92),(.19,2.72),(.10,2.80)], -.23, PAL["ivory_shadow"], False)
    # Chest ring is the forbidden ritual scar; keep it small and under the lapel edge.
    scar_center=(.04,2.98)
    for i in range(12):
        if i in (0, 1, 8, 9):  # Deliberate open breaks; this reads as a healed scar, not jewelry.
            continue
        a0=2*math.pi*i/12
        a1=2*math.pi*(i+.68)/12
        p0=(scar_center[0]+math.cos(a0)*.085,scar_center[1]+math.sin(a0)*.105)
        p1=(scar_center[0]+math.cos(a1)*.085,scar_center[1]+math.sin(a1)*.105)
        line_poly("Hero_Ritual_Scar_Stitch_%02d"%i,p0,p1,.018,-.275,PAL["red_shadow"])

    # Jacket shell with clean split fronts, lapels and controlled angular folds.
    mesh_poly("Hero_Coat_Back", [(-.49,3.32),(-.40,3.49),(-.28,3.42),(-.27,2.52),(-.42,2.40),(-.53,2.66)], -.27, PAL["coat_shadow"], True)
    mesh_poly("Hero_Coat_Front", [( .20,3.46),(.43,3.39),(.54,3.22),(.44,2.47),(.31,2.34),(.13,2.50),(.20,3.00),(.07,3.29)], -.31, PAL["coat"], True)
    mesh_poly("Coat_Lapel", [(-.30,3.46),(-.05,3.42),(.11,3.22),(.01,3.08),(-.16,3.24),(-.26,3.13)], -.34, PAL["coat_light"], False)
    mesh_poly("Coat_Lapel_Front", [(.12,3.44),(.31,3.40),(.41,3.24),(.27,3.10),(.13,3.21),(.02,3.32)], -.35, PAL["coat_light"], False)
    mesh_poly("Coat_Shoulder_Facet", [(-.43,3.31),(-.32,3.42),(-.23,3.29),(-.28,3.05),(-.38,3.13)], -.37, PAL["coat_light"], False)
    mesh_poly("Coat_Front_Fold_Shadow", [(.29,2.98),(.43,2.78),(.39,2.52),(.31,2.44),(.24,2.66)], -.38, PAL["coat_shadow"], False)
    mesh_poly("Coat_Front_Fold_Light", [(.21,2.89),(.27,2.78),(.24,2.58),(.19,2.55)], -.385, PAL["coat_light"], False)
    line_poly("Coat_Stitch_Back",(-.41,3.17),(-.39,2.60),.018,-.36,PAL["coat_light"])
    line_poly("Coat_Stitch_Front",(.38,3.18),(.31,2.55),.018,-.37,PAL["coat_light"])

    # Collar, scarf knot, brass shoulder fastener, and four-core capsule.
    mesh_poly("Hero_Neck", [(-.12,3.48),(-.08,3.75),(.25,3.74),(.28,3.45),(.14,3.36)], -.39, PAL["skin"], True)
    mesh_poly("Scarf_Collar", [(-.32,3.51),(-.20,3.66),(.14,3.66),(.34,3.51),(.25,3.35),(-.23,3.34)], -.43, PAL["red"], True)
    mesh_poly("Scarf_Collar_Shadow", [(-.20,3.48),(-.08,3.58),(.20,3.55),(.14,3.42),(-.13,3.40)], -.45, PAL["red_shadow"], False)
    mesh_poly("Scarf_Clasp", [(-.27,3.53),(-.21,3.60),(-.13,3.53),(-.21,3.46)], -.49, PAL["brass_light"], False)
    # Belt wraps body; an intentional little hanging strap stays outside the hit area.
    mesh_poly("Hero_Belt", [(-.36,2.45),(.35,2.45),(.39,2.31),(-.36,2.31)], -.48, PAL["leather"], True)
    mesh_poly("Hero_Belt_Buckle", [(-.04,2.47),(.17,2.47),(.17,2.29),(-.04,2.29)], -.52, PAL["brass"], True)
    mesh_poly("Hero_Memory_Capsule", [(.18,2.47),(.42,2.47),(.42,2.28),(.18,2.28)], -.54, PAL["brass"], True)
    cores=[PAL["glass_amber"],PAL["glass_green"],PAL["glass_bone"],PAL["glass_red"]]
    for i,core in enumerate(cores):
        x=.205+i*.052
        mesh_poly("Hero_Memory_Core_%d"%(i+1), [(x,2.43),(x+.038,2.43),(x+.038,2.32),(x,2.32)], -.57, core, False)
    line_poly("Belt_Hanging_Tab",(-.30,2.32),(-.27,2.12),.060,-.50,PAL["leather_shadow"])

    # Head: angular jaw, ear, low-key adult face, layered hair and the silver right-temple lock.
    mesh_poly("Hero_Head", [(-.20,3.75),(-.12,4.23),(.13,4.37),(.40,4.27),(.48,4.01),(.40,3.81),(.25,3.69),(.02,3.70)], -.50, PAL["skin"], True)
    mesh_poly("Face_Shadow", [(.29,4.17),(.46,4.10),(.43,3.92),(.28,3.80),(.22,3.98)], -.52, PAL["skin_shadow"], False)
    mesh_poly("Hero_Ear", [(-.19,4.05),(-.30,4.12),(-.35,4.04),(-.31,3.91),(-.20,3.92)], -.52, PAL["skin"], True)
    # Nose and profile contour face right; eye size deliberately stays small at target scale.
    mesh_poly("Hero_Nose", [(.40,4.02),(.55,3.98),(.43,3.92)], -.57, PAL["skin"], False)
    mesh_poly("Hero_Eye", [(.32,4.09),(.40,4.10),(.40,4.06),(.33,4.055)], -.59, PAL["outline"], False)
    line_poly("Hero_Brow",(.29,4.15),(.41,4.16),.025,-.60,PAL["hair"])
    line_poly("Hero_Mouth",(.38,3.87),(.45,3.86),.016,-.60,PAL["leather_shadow"])
    mesh_poly("Hero_Hair_Silhouette", [(-.32,4.05),(-.37,4.24),(-.18,4.35),(-.21,4.45),(.00,4.40),(.09,4.46),(.20,4.41),(.39,4.43),(.33,4.31),(.50,4.28),(.39,4.14),(.32,4.25),(.20,4.16),(.10,4.22),(-.05,4.12),(-.17,4.18),(-.24,3.95)], -.62, PAL["hair"], True)
    mesh_poly("Hero_Hair_Facet", [(-.22,4.28),(-.10,4.39),(.03,4.35),(.13,4.39),(.23,4.32),(.13,4.25),(-.02,4.27)], -.64, PAL["hair_light"], False)
    mesh_poly("Hair_Edge_Glint", [(-.30,4.22),(-.25,4.30),(-.20,4.25),(-.22,4.14)], -.645, PAL["hair_light"], False)
    mesh_poly("Hero_Silver_Lock", [(-.28,4.27),(-.20,4.34),(-.11,4.24),(-.17,4.09),(-.25,4.03),(-.23,4.18)], -.67, PAL["silver"], True)

    # Right arm has the cream wrap; left arm carries the leather bracer.
    shoulder=(.34,3.25)
    elbow=(.45 + .10*math.sin(math.radians(angle)), 2.96 + .10*math.cos(math.radians(angle)))
    hand=(hand_x,hand_z)
    capsule("Hero_Arm_Right_Upper", shoulder, elbow, .29, -.56, PAL["coat"])
    capsule("Hero_Arm_Right_Forearm", elbow, hand, .22, -.62, PAL["skin"])
    # Wrap occupies the last 0.24 units of forearm; drawn as separate visible bands.
    for i in range(4):
        t=.52+i*.085
        x=elbow[0]+(hand[0]-elbow[0])*t
        z=elbow[1]+(hand[1]-elbow[1])*t
        line_poly("Hero_Right_Bandage_%02d"%i,(x-.055,z-.027),(x+.055,z+.027),.035,-.67,PAL["ivory"])
    capsule("Hero_Hand", hand, (hand[0]+.07,hand[1]-.015), .15, -.69, PAL["skin"])
    # Left arm stays visible behind/along the body with a dark bracer patch.
    left_shoulder=(-.37,3.23); left_elbow=(-.52,2.82); left_hand=(-.50,2.43)
    capsule("Hero_Arm_Left_Upper", left_shoulder, left_elbow, .27, -.30, PAL["coat"])
    capsule("Hero_Arm_Left_Forearm", left_elbow, left_hand, .20, -.42, PAL["skin"])
    capsule("Hero_Arm_Left_Bracer", (-.50,2.75), left_hand, .22, -.47, PAL["leather"])
    line_poly("Bracer_Rivet",(-.51,2.60),(-.45,2.60),.028,-.49,PAL["brass_light"])

    add_sword(hand, angle, frame_index)
    # Short, restrained slash cue only around the contact/follow-through frames.
    if frame_index in (5,6,7,8):
        alpha_mat = PAL["trail_a"] if frame_index in (5,6) else PAL["trail_b"]
        curve=bezier_sample([(hand[0]+.26,hand[1]+.38),(hand[0]+.88,hand[1]+.72),(hand[0]+1.20,hand[1]+.16),(hand[0]+1.07,hand[1]-.28)],18)
        pts=[]
        for i,(x,z) in enumerate(curve):
            width=.11*(1-i/(len(curve)-1))
            pts.append((x,z+width))
        for i in reversed(range(len(curve))):
            x,z=curve[i]; width=.11*(1-i/(len(curve)-1))
            pts.append((x,z-width))
        mesh_poly("Slash_Trail", pts, DEPTH_FRONT-.10, alpha_mat, False)

    # Shared upper-body lean: rotate assembled parts around the hip pivot. The feet
    # remain planted; the same lean value moves coat, head, arms, hand and weapon.
    lean_angle = lean * 0.75
    pivot_x, pivot_z = 0.0, 2.38
    follows_lean = (
        "Hero_Pelvis", "Hero_Torso", "Hero_Tunic", "Tunic_", "Hero_Coat", "Coat_",
        "Hero_Neck", "Scarf_Collar", "Scarf_Clasp", "Hero_Belt", "Belt_",
        "Hero_Memory", "Hero_Ritual", "Ritual_", "Hero_Head", "Face_", "Hero_Ear",
        "Hero_Nose", "Hero_Eye", "Hero_Brow", "Hero_Mouth", "Hero_Hair", "Hero_Silver",
        "Hero_Arm", "Hero_Right", "Hero_Hand", "Bracer_", "Gear_Sword_", "Slash_Trail",
    )
    c, s = math.cos(lean_angle), math.sin(lean_angle)
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.name.startswith(follows_lean):
            continue
        for vertex in obj.data.vertices:
            dx, dz = vertex.co.x - pivot_x, vertex.co.z - pivot_z
            vertex.co.x = pivot_x + c*dx + s*dz
            vertex.co.z = pivot_z - s*dx + c*dz

POSES = [
    # sword angle, hand x/z, torso lean, lead-foot stride, scarf lag; feet stay grounded.
    (-32, .44, 2.78, .00, .00, -.10), (-2, .43, 3.02, .00, .00, -.24),
    ( 30, .38, 3.20, .00, .00, -.34), ( 70, .35, 3.24, .00, .00, -.38),
    (108, .40, 3.18, .00, .00, -.45), ( 62, .51, 3.05, .02, .02, -.20),
    ( 20, .60, 2.88, .06, .08,  .32), (-18, .70, 2.56, .10, .14,  .48),
    (-42, .66, 2.38, .08, .12,  .32), (-52, .56, 2.43, .03, .07,  .12),
    (-30, .48, 2.65, .01, .02, -.08), (-32, .44, 2.78, .00, .00, -.10),
]

def clear_art():
    for obj in list(bpy.data.objects):
        if obj.type not in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

def build_camera():
    scene=bpy.context.scene
    cam_data=bpy.data.cameras.new("Camera_Hero_Side_Ortho")
    cam=bpy.data.objects.new("Camera_Hero_Side_Ortho",cam_data)
    scene.collection.objects.link(cam)
    cam.location=(0,-12,CAMERA_Z)
    cam.rotation_euler=(math.radians(90),0,0)
    cam.data.type="ORTHO"
    cam.data.ortho_scale=5.12
    scene.camera=cam

def main():
    # Start with a clean scene and fixed transparent orthographic camera.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=W; scene.render.resolution_y=H; scene.render.resolution_percentage=100
    scene.eevee.taa_render_samples=1  # Hard pixel clusters; no temporal antialias blur.
    scene.render.film_transparent=True
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.render.image_settings.color_depth="8"
    scene.render.image_settings.compression=15
    scene.view_settings.view_transform="Standard"
    scene.view_settings.look="None"
    scene.view_settings.exposure=0; scene.view_settings.gamma=1
    scene.camera=None
    build_camera()
    scene.camera.data.ortho_scale=5.12
    scene.camera.data.lens=50
    scene.world.color=(0,0,0)
    scene.render.resolution_percentage=100
    scene.frame_start=1; scene.frame_end=len(POSES)
    scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=True
    scene.use_nodes=False
    # Native pixel camera: 5.12 units high -> 170px. Godot displays each pixel 3x.
    for i,pose in enumerate(POSES, start=1):
        clear_art()
        build_hero(i, pose)
        scene.frame_set(i)
        scene.camera.location.z=CAMERA_Z
        scene.camera.data.ortho_scale=5.12
        # transparent canvas bottom maps to z=-0.24; feet at z=0 => row ~162/170.
        scene.camera.location.z=2.32
        scene.render.filepath=os.path.join(FRAMES,f"hero_slash_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        shutil.copy2(scene.render.filepath, os.path.join(GODOT_FRAMES,f"hero_slash_{i:02d}.png"))
    # Leave an editable, named final pose in the blend file; pose recipe lives in this script.
    clear_art()
    build_hero(6, POSES[5])
    scene.frame_set(6)
    scene.render.filepath=os.path.join(FRAMES,"hero_slash_")
    scene["asset_version"]="hero_v2"
    scene["canvas_px"]="128x170 RGBA native pixel art; display scale 3x"
    scene["root_anchor_px"]="64,162 native pixels"
    scene["pose_source"]="blender/build_hero_v2.py :: POSES"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND_DIR,"hero_slash_v2.blend"))
    print("Rendered revised hero: %s" % FRAMES)

if __name__ == "__main__":
    main()
