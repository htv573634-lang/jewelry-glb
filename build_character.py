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
    """Finds the first 3D model file in the inputs folder (any name, .glb/.gltf/.obj)."""
    patterns = ["*.glb", "*.gltf", "*.obj", "*.GLB", "*.GLTF", "*.OBJ"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(INPUT_DIR, p)))
    if not files:
        raise FileNotFoundError(
            f"No 3D model file found in '{INPUT_DIR}'. "
            f"Please upload a .glb, .gltf, or .obj file."
        )
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
            size = os.path.getsize(path)
            print(f"    {path} ({size} bytes)")
    print("---------------------------------")

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def import_model(filepath):
    """Imports a GLB, glTF, or OBJ file based on its extension."""
    print(f"[1/5] Importing '{filepath}'...")
    ext = filepath.lower().rsplit(".", 1)[-1]
    
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == "obj":
        bpy.ops.import_scene.obj(filepath=filepath)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
    
    mesh_obj = next((o for o in bpy.context.selected_objects if o.type == 'MESH'), None)
    if not mesh_obj:
        # Fallback: search all objects
        mesh_obj = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    if not mesh_obj:
        raise ValueError("No mesh found in the imported file.")
    
    print(f"    Imported mesh: {mesh_obj.name} ({len(mesh_obj.data.vertices)} vertices)")
    return mesh_obj

# ============================================================
# 2. RIG THE CHARACTER
# ============================================================
def rig_character(mesh_obj):
    print("[2/5] Generating humanoid armature with Rigify...")
    
    # Enable Rigify addon
    bpy.ops.preferences.addon_enable(module="rigify")
    
    # Add Rigify metarig
    bpy.ops.object.armature_human_metarig_add()
    armature = bpy.context.active_object
    armature.name = "CharacterRig"
    
    # Scale the metarig to fit the imported mesh
    mesh_height = mesh_obj.dimensions.z
    if mesh_height < 0.1:
        mesh_height = 1.7
    scale_factor = mesh_height / 1.7
    armature.scale = (scale_factor, scale_factor, scale_factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Generate the actual rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    print("[3/5] Binding mesh to armature with Automatic Weights...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    return armature

# ============================================================
# 3. ANIMATE
# ============================================================
def animate_character(armature):
    print("[4/5] Animating the character...")
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    # Find Rigify bone names
    bone_names = ["thigh.L", "thigh.R", "upper_arm.L", "upper_arm.R"]
    bones = {}
    for name in bone_names:
        if name in armature.pose.bones:
            bones[name] = armature.pose.bones[name]
    
    if len(bones) < 4:
        print(f"    [!] Warning: Only found {len(bones)}/4 Rigify bones.")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    # Clear existing pose
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear()
    
    # Walk cycle
    for frame in range(1, SIMULATION_FRAMES + 1, 8):
        scene.frame_set(frame)
        t = frame / SIMULATION_FRAMES * 2 * math.pi
        
        bones["thigh.L"].rotation_euler[0] = math.sin(t) * 0.5
        bones["thigh.R"].rotation_euler[0] = math.sin(t + math.pi) * 0.5
        bones["upper_arm.L"].rotation_euler[0] = math.sin(t + math.pi) * 0.3
        bones["upper_arm.R"].rotation_euler[0] = math.sin(t) * 0.3
        
        for name, bone in bones.items():
            bone.keyframe_insert(data_path="rotation_euler", frame=frame)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("    Animation complete.")

# ============================================================
# 4. SAREE
# ============================================================
def create_saree():
    print("[5/5] Creating saree fabric...")
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    bm = bmesh.new()
    res_x, res_y = 80, 30
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
    saree.location = (0, 0, 1.0)
    
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Sheen" in bsdf.inputs:
        bsdf.inputs["Sheen"].default_value = 0.6
    saree.data.materials.append(mat)
    
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 8
    cs.mass = 0.2
    cs.bending_stiffness = 0.3
    cs.air_damping = 1.5
    
    return saree

def simulate_and_export(saree, mesh_obj):
    print(f"    Simulating cloth for {SIMULATION_FRAMES} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    mesh_obj.modifiers.new(name="Collision", type='COLLISION')
    
    bpy.ops.ptcache.bake_all(bake=True)
    
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    
    print(f"    Exporting to {OUTPUT_GLB}...")
    os.makedirs(os.path.dirname(OUTPUT_GLB), exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_GLB,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True
    )
    print("    Export complete.")

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
    mesh_obj = import_model(model_path)
    armature = rig_character(mesh_obj)
    animate_character(armature)
    saree = create_saree()
    simulate_and_export(saree, mesh_obj)
    
    print("=" * 55)
    print(" DONE. Download the artifact. ")
    print("=" * 55)

if __name__ == "__main__":
    main()
