# build_character.py
import bpy
import bmesh
import math
import os
import glob

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
        return
    for root, dirs, files in os.walk(INPUT_DIR):
        for name in files:
            print(f"    {os.path.join(root, name)}")
    print("---------------------------------")

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# ============================================================
# 1. IMPORT & CENTER
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
    
    # Join meshes
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()
    combined_mesh = bpy.context.active_object
    combined_mesh.name = "Character"
    
    existing_armature = armature_objects[0] if armature_objects else None
    
    # --- CENTER THE CHARACTER AT ORIGIN ---
    bpy.ops.object.select_all(action='DESELECT')
    if existing_armature:
        existing_armature.select_set(True)
    combined_mesh.select_set(True)
    bpy.context.view_layer.objects.active = combined_mesh
    
    # Move to origin (0,0,0) and drop feet to Z=0
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    min_z = combined_mesh.bound_box[0][2]
    combined_mesh.location.z -= min_z
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    
    print(f"    Combined mesh: {len(combined_mesh.data.vertices)} vertices")
    if existing_armature:
        print(f"    [OK] Armature found: '{existing_armature.name}' ({len(existing_armature.data.bones)} bones)")
    
    return combined_mesh, existing_armature

# ============================================================
# 2. SAREE (Scaled to character)
# ============================================================
def create_saree(mesh_obj):
    print("[2/5] Creating draped saree...")
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    # Get character dimensions
    height = mesh_obj.dimensions.z
    width = mesh_obj.dimensions.x
    waist_z = height * 0.65
    shoulder_z = height * 0.85
    
    # Create a flat grid
    bm = bmesh.new()
    res_x, res_y = 80, 40
    verts = []
    for x in range(res_x + 1):
        row = []
        for y in range(res_y + 1):
            # Create a rectangle of size 4.0m x 1.1m (realistic saree)
            px = (x / res_x) * 4.0
            py = (y / res_y) * 1.1
            row.append(bm.verts.new((px, py, 0)))
        verts.append(row)
    
    for x in range(res_x):
        for y in range(res_y):
            bm.faces.new((verts[x][y], verts[x+1][y], verts[x+1][y+1], verts[x][y+1]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    # --- SPIRAL WRAP LOGIC (Scaled properly) ---
    # We wrap the first 3m around the body, last 1m goes over the shoulder
    for v in mesh.vertices:
        x = v.co.x
        y = v.co.y
        
        if x < 3.0:
            # Wrap around hips (approx 2.5 turns)
            angle = (x / 3.0) * (2 * math.pi * 2.5)
            # Radius based on character width
            radius = (width * 0.6) + (y / 1.1) * 0.05
            z = waist_z - (y / 1.1) * (waist_z * 0.8)
            v.co.x = radius * math.cos(angle)
            v.co.y = radius * math.sin(angle)
            v.co.z = z
        else:
            # Pallu (over shoulder)
            pallu_t = (x - 3.0) / 1.0
            if pallu_t < 0.5:
                t = pallu_t / 0.5
                v.co.x = -0.15 * t + (y / 1.1 - 0.5) * 0.2
                v.co.y = 0.10 - 0.05 * t
                v.co.z = waist_z + (shoulder_z - waist_z) * t
            else:
                t = (pallu_t - 0.5) / 0.5
                v.co.x = -0.30 + (y / 1.1 - 0.5) * 0.2
                v.co.y = -0.15 - 0.10 * t
                v.co.z = shoulder_z - (shoulder_z * 0.8) * t
    
    # Material
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Sheen" in bsdf.inputs: bsdf.inputs["Sheen"].default_value = 0.6
    saree.data.materials.append(mat)
    
    # Cloth Physics
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 10
    cs.mass = 0.2
    cs.bending_stiffness = 0.35
    cs.air_damping = 1.5
    
    # Pin waist and shoulder
    vgroup = saree.vertex_groups.new(name="PinGroup")
    for v in mesh.vertices:
        if v.co.z > waist_z - 0.1 and abs(v.co.x) < 0.3 and abs(v.co.y) < 0.3:
            vgroup.add([v.index], 1.0, 'REPLACE')
        elif v.co.z > shoulder_z - 0.1 and v.co.x < -0.2:
            vgroup.add([v.index], 1.0, 'REPLACE')
    cs.vertex_group_mass = "PinGroup"
    
    return saree

# ============================================================
# 3. SIMULATE & EXPORT
# ============================================================
def simulate_and_export(saree, mesh_obj):
    print(f"[3/5] Simulating cloth for {SIMULATION_FRAMES} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    # Add collision to the character mesh
    mesh_obj.modifiers.new(name="Collision", type='COLLISION')
    
    # Bake the cloth
    bpy.ops.ptcache.bake_all(bake=True)
    
    # Apply modifier to bake the drape permanently
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    
    print(f"[4/5] Exporting to {OUTPUT_GLB}...")
    os.makedirs(os.path.dirname(OUTPUT_GLB), exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_GLB,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True
    )
    print(f"[5/5] Saved to {OUTPUT_GLB}")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print(" STATIC SAREE DRAPING PIPELINE ")
    print("=" * 55)
    
    list_input_dir()
    try:
        model_path = find_input_model()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    
    clear_scene()
    mesh_obj, armature = import_model(model_path)
    saree = create_saree(mesh_obj)
    simulate_and_export(saree, mesh_obj)

if __name__ == "__main__":
    main()
