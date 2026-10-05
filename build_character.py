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

def import_model(filepath):
    """Imports a file and JOINS all meshes so clothes stay on the body."""
    print(f"[1/5] Importing '{filepath}'...")
    ext = filepath.lower().rsplit(".", 1)[-1]
    
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == "obj":
        bpy.ops.import_scene.obj(filepath=filepath)
    
    # Find ALL imported meshes
    mesh_objects = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not mesh_objects:
        raise ValueError("No mesh found.")
    
    print(f"    Found {len(mesh_objects)} mesh parts. Joining them...")
    
    # Deselect all, then select all mesh parts
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    
    # Set active and join
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()
    
    combined_mesh = bpy.context.active_object
    combined_mesh.name = "Character"
    print(f"    Combined mesh: {len(combined_mesh.data.vertices)} vertices")
    return combined_mesh

def rig_character(mesh_obj):
    print("[2/5] Generating Rigify armature...")
    bpy.ops.preferences.addon_enable(module="rigify")
    
    bpy.ops.object.armature_human_metarig_add()
    armature = bpy.context.active_object
    armature.name = "CharacterRig"
    
    # Scale rig to match character height
    mesh_height = mesh_obj.dimensions.z
    if mesh_height < 0.1: mesh_height = 1.7
    scale_factor = mesh_height / 1.7
    armature.scale = (scale_factor, scale_factor, scale_factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Generate the rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Bind the combined mesh
    print("[3/5] Binding mesh with Automatic Weights...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    return armature

def animate_character(armature):
    print("[4/5] Animating...")
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    bones = {}
    for name in ["thigh.L", "thigh.R", "upper_arm.L", "upper_arm.R"]:
        if name in armature.pose.bones:
            bones[name] = armature.pose.bones[name]
    
    if len(bones) < 4:
        print("    [!] Warning: Missing Rigify bones. Skipping walk cycle.")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear()
    
    for frame in range(1, SIMULATION_FRAMES + 1, 8):
        scene.frame_set(frame)
        t = frame / SIMULATION_FRAMES * 2 * math.pi
        bones["thigh.L"].rotation_euler[0] = math.sin(t) * 0.5
        bones["thigh.R"].rotation_euler[0] = math.sin(t + math.pi) * 0.5
        bones["upper_arm.L"].rotation_euler[0] = math.sin(t + math.pi) * 0.3
        bones["upper_arm.R"].rotation_euler[0] = math.sin(t) * 0.3
        for b in bones.values():
            b.keyframe_insert(data_path="rotation_euler", frame=frame)
    
    bpy.ops.object.mode_set(mode='OBJECT')

def create_saree(mesh_obj):
    """Creates a saree mesh WRAPPED around the character's body."""
    print("[5/5] Creating draped saree...")
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    # Get character dimensions to scale the saree
    height = mesh_obj.dimensions.z
    waist_z = height * 0.65  # Approx waist height
    shoulder_z = height * 0.85
    
    bm = bmesh.new()
    res_x, res_y = 100, 40
    
    # Build a flat grid first
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
    
    # Scale to real saree size
    saree.scale = (5.5, 1.15, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # --- SPIRAL WRAP LOGIC ---
    # Wrap the first 4m around the body, last 1.5m goes over the shoulder
    for v in mesh.vertices:
        x = v.co.x
        y = v.co.y
        
        if x < 4.0:
            # Skirt: wrap around the hips in a spiral
            angle = (x / 4.0) * (2 * math.pi * 2.5) # 2.5 wraps
            radius = (mesh_obj.dimensions.x * 0.25) + (y / 1.15) * 0.05
            z = waist_z - (y / 1.15) * (waist_z * 0.7) # Drop to hem
            v.co.x = radius * math.cos(angle)
            v.co.y = radius * math.sin(angle)
            v.co.z = z
        else:
            # Pallu: over the shoulder
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
    cs.quality = 8
    cs.mass = 0.2
    cs.bending_stiffness = 0.35
    cs.air_damping = 1.5
    
    # Pin the waist and shoulder
    vgroup = saree.vertex_groups.new(name="PinGroup")
    for v in mesh.vertices:
        if v.co.z > waist_z - 0.1 and abs(v.co.x) < 0.3 and abs(v.co.y) < 0.3:
            vgroup.add([v.index], 1.0, 'REPLACE')
        elif v.co.z > shoulder_z - 0.1 and v.co.x < -0.2:
            vgroup.add([v.index], 1.0, 'REPLACE')
    cs.vertex_group_mass = "PinGroup"
    
    return saree

def simulate_and_export(saree, mesh_obj):
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
    saree = create_saree(mesh_obj)
    simulate_and_export(saree, mesh_obj)

if __name__ == "__main__":
    main()
