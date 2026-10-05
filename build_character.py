# build_character.py
import bpy
import bmesh
import math
import os
import glob
from mathutils import Vector

# ============================================================
# CONFIGURATION
# ============================================================
INPUT_DIR = "inputs/"
OUTPUT_GLB = "out_character/rigged_saree_character.glb"
SIMULATION_FRAMES = 120
SAREE_COLOR = (0.72, 0.03, 0.08, 1)

def find_input_model():
    patterns = ["*.glb", "*.gltf", "*.obj", "*.GLB", "*.GLTF", "*.OBJ"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(INPUT_DIR, p)))
    if not files:
        raise FileNotFoundError(f"No 3D model found in '{INPUT_DIR}'.")
    files.sort()
    return files[0]

def list_input_dir():
    print(f"--- Contents of '{INPUT_DIR}' ---")
    if not os.path.exists(INPUT_DIR):
        print(f"    Directory '{INPUT_DIR}' does NOT exist.")
        return
    for root, dirs, files in os.walk(INPUT_DIR):
        for name in files:
            path = os.path.join(root, name)
            print(f"    {path} ({os.path.getsize(path)} bytes)")
    print("---------------------------------")

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# ============================================================
# 1. IMPORT
# ============================================================
def import_model(filepath):
    print(f"[1/5] Importing '{filepath}'...")
    ext = filepath.lower().rsplit(".", 1)[-1]
    
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == "obj":
        bpy.ops.import_scene.obj(filepath=filepath)
    
    all_objects = list(bpy.context.selected_objects)
    mesh_objects = [o for o in all_objects if o.type == 'MESH']
    armature_objects = [o for o in all_objects if o.type == 'ARMATURE']
    
    print(f"    Found {len(mesh_objects)} meshes and {len(armature_objects)} armatures.")
    
    if not mesh_objects:
        raise ValueError("No mesh found in the file.")
    
    # Join all meshes into one (preserves vertex weights)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()
    combined_mesh = bpy.context.active_object
    combined_mesh.name = "Character"
    print(f"    Combined mesh: {len(combined_mesh.data.vertices)} vertices")
    
    existing_armature = armature_objects[0] if armature_objects else None
    if existing_armature:
        print(f"    [OK] Existing armature found: '{existing_armature.name}'")
        print(f"         Bone count: {len(existing_armature.data.bones)}")
    else:
        print(f"    [!] No armature in the file. Will generate one with Rigify.")
    
    return combined_mesh, existing_armature

# ============================================================
# 2. RIG
# ============================================================
def rig_character(mesh_obj, existing_armature=None):
    if existing_armature:
        print("[2/5] Using the model's own armature - skipping Rigify.")
        print("[3/5] Mesh is already skinned - no re-weighting needed.")
        return existing_armature
    
    print("[2/5] Generating Rigify armature...")
    bpy.ops.preferences.addon_enable(module="rigify")
    bpy.ops.object.armature_human_metarig_add()
    armature = bpy.context.active_object
    armature.name = "CharacterRig"
    
    mesh_height = mesh_obj.dimensions.z or 1.7
    scale_factor = mesh_height / 1.7
    armature.scale = (scale_factor, scale_factor, scale_factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    print("[3/5] Binding mesh with Automatic Weights...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    return armature

# ============================================================
# 3. ANIMATE (pattern-matched bone finder for any rig)
# ============================================================
def animate_character(armature):
    print("[4/5] Animating the character...")
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    all_bone_names = [b.name for b in armature.pose.bones]
    print(f"    All bones: {all_bone_names}")
    
    # Pattern-based bone finder
    def find_bone(keywords):
        for bone in armature.pose.bones:
            name_lower = bone.name.lower()
            if all(k.lower() in name_lower for k in keywords):
                return bone
        return None
    
    # Try Mixamo first, then Rigify, then generic
    thigh_l = (
        find_bone(["upleg", "left"]) or
        find_bone(["thigh", "left"]) or
        find_bone(["thigh.l"])
    )
    thigh_r = (
        find_bone(["upleg", "right"]) or
        find_bone(["thigh", "right"]) or
        find_bone(["thigh.r"])
    )
    arm_l = (
        find_bone(["leftarm"]) or
        find_bone(["upper_arm", "left"]) or
        find_bone(["upperarm.l"]) or
        find_bone(["upper_arm.l"])
    )
    arm_r = (
        find_bone(["rightarm"]) or
        find_bone(["upper_arm", "right"]) or
        find_bone(["upperarm.r"]) or
        find_bone(["upper_arm.r"])
    )
    
    bones = {"thigh.L": thigh_l, "thigh.R": thigh_r, "arm.L": arm_l, "arm.R": arm_r}
    bones = {k: v for k, v in bones.items() if v is not None}
    
    print(f"    Matched bones:")
    for k, v in bones.items():
        print(f"      {k} -> {v.name}")
    
    if len(bones) < 4:
        print(f"    [!] Only found {len(bones)}/4 bones. Cannot animate.")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    # Clear any existing pose
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear()
    
    # Walk cycle
    for frame in range(1, SIMULATION_FRAMES + 1, 8):
        scene.frame_set(frame)
        t = frame / SIMULATION_FRAMES * 2 * math.pi
        
        bones["thigh.L"].rotation_euler[0] = math.sin(t) * 0.5
        bones["thigh.R"].rotation_euler[0] = math.sin(t + math.pi) * 0.5
        bones["arm.L"].rotation_euler[0] = math.sin(t + math.pi) * 0.3
        bones["arm.R"].rotation_euler[0] = math.sin(t) * 0.3
        
        for b in bones.values():
            b.keyframe_insert(data_path="rotation_euler", frame=frame)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("    Walk cycle applied successfully.")

# ============================================================
# 4. SAREE
# ============================================================
def create_saree(mesh_obj):
    print("[5/5] Creating draped saree...")
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    height = mesh_obj.dimensions.z
    waist_z = height * 0.65
    shoulder_z = height * 0.85
    
    bm = bmesh.new()
    res_x, res_y = 100, 40
    
    verts = []
    for x in range(res_x + 1):
        row = []
        for y in range(res_y + 1):
            row.append(bm.verts.new((x/res_x, y/res_y, 0)))
        verts.append(row)
    
    for x in range(res_x):
        for y in range(res_y):
            bm.faces.new((verts[x][y], verts[x+1][y], verts[x+1][y+1], verts[x][y+1]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    saree.scale = (5.5, 1.15, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Spiral wrap
    for v in mesh.vertices:
        x = v.co.x
        y = v.co.y
        
        if x < 4.0:
            angle = (x / 4.0) * (2 * math.pi * 2.5)
            radius = (mesh_obj.dimensions.x * 0.25) + (y / 1.15) * 0.05
            z = waist_z - (y / 1.15) * (waist_z * 0.7)
            v.co.x = radius * math.cos(angle)
            v.co.y = radius * math.sin(angle)
            v.co.z = z
        else:
            pallu_t = (x - 4.0) / 1.5
            if pallu_t < 0.5:
                t = pallu_t / 0.5
                v.co.x = -0.15 * t + (y / 1.15 - 0.5) * 0.15
                v.co.y = 0.10 - 0.05 * t
                v.co.z = waist_z + (shoulder_z - waist_z) * t
            else:
                t = (pallu_t - 0.5) / 0.5
                v.co.x = -0.30 + (y / 1.15 - 0.5) * 0.15
                v.co.y = -0.15 - 0.10 * t
                v.co.z = shoulder_z - (shoulder_z * 0.7) * t
    
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Sheen" in bsdf.inputs: bsdf.inputs["Sheen"].default_value = 0.6
    saree.data.materials.append(mat)
    
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 8
    cs.mass = 0.2
    cs.bending_stiffness = 0.35
    cs.air_damping = 1.5
    
    vgroup = saree.vertex_groups.new(name="PinGroup")
    for v in mesh.vertices:
        if v.co.z > waist_z - 0.1 and abs(v.co.x) < 0.3 and abs(v.co.y) < 0.3:
            vgroup.add([v.index], 1.0, 'REPLACE')
        elif v.co.z > shoulder_z - 0.1 and v.co.x < -0.2:
            vgroup.add([v.index], 1.0, 'REPLACE')
    cs.vertex_group_mass = "PinGroup"
    
    return saree

# ============================================================
# 5. SIMULATE & EXPORT
# ============================================================
def simulate_and_export(saree, mesh_obj, armature):
    print(f"    Simulating for {SIMULATION_FRAMES} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    mesh_obj.modifiers.new(name="Collision", type='COLLISION')
    
    bpy.ops.ptcache.bake_all(bake=True)
    
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    
    os.makedirs(os.path.dirname(OUTPUT_GLB), exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_GLB,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True
    )
    print(f"    Saved to {OUTPUT_GLB}")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print(" AUTO-DETECT CHARACTER RIGGING PIPELINE ")
    print("=" * 55)
    
    list_input_dir()
    try:
        model_path = find_input_model()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    
    clear_scene()
    mesh_obj, existing_arm = import_model(model_path)
    armature = rig_character(mesh_obj, existing_arm)
    animate_character(armature)
    saree = create_saree(mesh_obj)
    simulate_and_export(saree, mesh_obj, armature)

if __name__ == "__main__":
    main()
