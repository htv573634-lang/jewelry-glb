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
TARGET_HEIGHT = 1.7  # Normalize all characters to 1.7m

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
# 1. IMPORT, JOIN, NORMALIZE
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
    
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()
    combined_mesh = bpy.context.active_object
    combined_mesh.name = "Character"
    
    existing_armature = armature_objects[0] if armature_objects else None
    
    # Apply all transforms first
    bpy.ops.object.select_all(action='DESELECT')
    combined_mesh.select_set(True)
    bpy.context.view_layer.objects.active = combined_mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    
    # --- NORMALIZE SCALE ---
    current_height = combined_mesh.dimensions.z
    print(f"    Original height: {current_height:.4f} m")
    
    if current_height < 0.5 or current_height > 3.0:
        scale_factor = TARGET_HEIGHT / current_height
        print(f"    Scaling by {scale_factor:.4f}x to reach {TARGET_HEIGHT}m...")
        
        # Scale mesh
        combined_mesh.scale = (scale_factor, scale_factor, scale_factor)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Scale armature too
        if existing_armature:
            bpy.ops.object.select_all(action='DESELECT')
            existing_armature.select_set(True)
            bpy.context.view_layer.objects.active = existing_armature
            existing_armature.scale = (scale_factor, scale_factor, scale_factor)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # --- DROP FEET TO Z=0 ---
    bpy.ops.object.select_all(action='DESELECT')
    combined_mesh.select_set(True)
    bpy.context.view_layer.objects.active = combined_mesh
    world_corners = [combined_mesh.matrix_world @ Vector(c) for c in combined_mesh.bound_box]
    min_z = min(v.z for v in world_corners)
    combined_mesh.location.z -= min_z
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    
    final_height = combined_mesh.dimensions.z
    final_width = combined_mesh.dimensions.x
    final_depth = combined_mesh.dimensions.y
    print(f"    Final dimensions: X={final_width:.3f}m, Y={final_depth:.3f}m, Z={final_height:.3f}m")
    
    if existing_armature:
        print(f"    [OK] Armature: '{existing_armature.name}' ({len(existing_armature.data.bones)} bones)")
    
    return combined_mesh, existing_armature

# ============================================================
# 2. COMPUTE BODY RADIUS (real, not arm span)
# ============================================================
def estimate_body_radius(mesh_obj):
    """
    Estimates the torso radius by sampling vertices near the character's
    center-of-mass height. This avoids using the arm span.
    """
    height = mesh_obj.dimensions.z
    waist_z_min = height * 0.55
    waist_z_max = height * 0.75
    
    # Gather vertices in the waist band
    world_matrix = mesh_obj.matrix_world
    waist_radii = []
    for v in mesh_obj.data.vertices:
        world_v = world_matrix @ v.co
        if waist_z_min < world_v.z < waist_z_max:
            r = math.sqrt(world_v.x ** 2 + world_v.y ** 2)
            if r > 0.01:  # Skip any vertices at origin
                waist_radii.append(r)
    
    if not waist_radii:
        return 0.20  # fallback
    
    # Use the 25th percentile (closer to body core, ignores clothing edges)
    waist_radii.sort()
    idx = int(len(waist_radii) * 0.25)
    body_radius = waist_radii[idx]
    print(f"    Sampled {len(waist_radii)} waist vertices -> body radius ≈ {body_radius:.3f}m")
    return body_radius

# ============================================================
# 3. SAREE (proper spiral wrap with constant radius)
# ============================================================
def create_saree(mesh_obj):
    print("[2/5] Creating draped saree...")
    height = mesh_obj.dimensions.z
    body_radius = estimate_body_radius(mesh_obj)
    
    waist_z = height * 0.65
    shoulder_z = height * 0.85
    
    # Realistic saree dimensions relative to the character
    saree_length = height * 2.5   # ~4.25m for a 1.7m person
    saree_width  = height * 0.65  # ~1.10m wide fabric
    
    print(f"    Saree size: {saree_length:.2f}m x {saree_width:.2f}m")
    print(f"    Body radius: {body_radius:.3f}m, Waist Z: {waist_z:.2f}m, Shoulder Z: {shoulder_z:.2f}m")
    
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    bm = bmesh.new()
    res_x, res_y = 120, 40
    
    verts = []
    for xi in range(res_x + 1):
        row = []
        for yi in range(res_y + 1):
            px = (xi / res_x) * saree_length
            py = (yi / res_y) * saree_width
            row.append(bm.verts.new((px, py, 0)))
        verts.append(row)
    
    for xi in range(res_x):
        for yi in range(res_y):
            bm.faces.new((verts[xi][yi], verts[xi+1][yi], verts[xi+1][yi+1], verts[xi][yi+1]))
    
    bm.to_mesh(mesh)
    bm.free()
    
    # --- SPIRAL WRAP ---
    # Skirt portion: first 70% of the saree wraps around the hips
    # Pallu portion: last 30% goes over the left shoulder
    skirt_end = saree_length * 0.70
    
    for v in mesh.vertices:
        px = v.co.x
        py = v.co.y
        
        if px < skirt_end:
            # SKIRT: tight spiral around the body, descending
            t = px / skirt_end
            angle = t * 2 * math.pi * 3.0   # 3 wraps around the body
            
            # Slight taper: wider at the bottom hem
            r = body_radius * 1.05 + (py / saree_width) * 0.04
            
            # Height drops from waist to near feet as py increases
            z = waist_z - (py / saree_width) * (waist_z * 0.90)
            
            v.co.x = r * math.cos(angle)
            v.co.y = r * math.sin(angle)
            v.co.z = z
        else:
            # PALLU: over the left shoulder and down the back
            pallu_t = (px - skirt_end) / (saree_length - skirt_end)
            shoulder_x = -body_radius * 0.9  # Left side
            
            if pallu_t < 0.5:
                # Rise from waist, across the chest, up to shoulder
                t = pallu_t / 0.5
                v.co.x = shoulder_x * t + (py / saree_width - 0.5) * (body_radius * 0.8)
                v.co.y = body_radius * (1 - t) * 0.5
                v.co.z = waist_z + (shoulder_z - waist_z) * t
            else:
                # Drape down the back
                t = (pallu_t - 0.5) / 0.5
                v.co.x = shoulder_x + (py / saree_width - 0.5) * (body_radius * 0.8)
                v.co.y = -body_radius * 0.5
                v.co.z = shoulder_z - (shoulder_z * 0.85) * t
    
    # --- MATERIAL ---
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Sheen" in bsdf.inputs: bsdf.inputs["Sheen"].default_value = 0.6
    saree.data.materials.append(mat)
    
    # --- CLOTH PHYSICS ---
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 10
    cs.mass = 0.2
    cs.bending_stiffness = 0.4
    cs.air_damping = 1.5
    
    # --- PIN THE WAIST AND SHOULDER ---
    vgroup = saree.vertex_groups.new(name="PinGroup")
    for v in mesh.vertices:
        # Pin the top edge of the skirt (near the waist)
        if waist_z - 0.05 < v.co.z < waist_z + 0.15 and (v.co.x**2 + v.co.y**2) < (body_radius * 1.5)**2:
            vgroup.add([v.index], 1.0, 'REPLACE')
        # Pin the shoulder area
        elif v.co.z > shoulder_z - 0.15 and v.co.x < -body_radius * 0.5:
            vgroup.add([v.index], 1.0, 'REPLACE')
    cs.vertex_group_mass = "PinGroup"
    
    return saree

# ============================================================
# 4. SIMULATE & EXPORT
# ============================================================
def simulate_and_export(saree, mesh_obj):
    print(f"[3/5] Simulating cloth for {SIMULATION_FRAMES} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    mesh_obj.modifiers.new(name="Collision", type='COLLISION')
    
    bpy.ops.ptcache.bake_all(bake=True)
    
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
    print(" STATIC SAREE DRAPING PIPELINE v2 ")
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
