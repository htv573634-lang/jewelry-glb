# build_character.py
import bpy
import bmesh
import math
import os
from mathutils import Vector

# ============================================================
# CONFIGURATION
# ============================================================
INPUT_GLB = "inputs/model.glb"
OUTPUT_GLB = "out_character/rigged_saree_character.glb"
SIMULATION_FRAMES = 120
SAREE_COLOR = (0.72, 0.03, 0.08, 1) # Deep silk red

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# ============================================================
# 1. IMPORT & RIG THE CHARACTER
# ============================================================
def import_and_rig():
    print(f"[1/5] Importing {INPUT_GLB}...")
    bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
    
    mesh_obj = next((o for o in bpy.context.selected_objects if o.type == 'MESH'), None)
    if not mesh_obj:
        raise ValueError("No mesh found in the GLB file.")
    
    print("[2/5] Generating humanoid armature with Rigify...")
    # Add Rigify metarig (a standard human skeleton template)
    bpy.ops.object.armature_human_metarig_add()
    armature = bpy.context.active_object
    armature.name = "CharacterRig"
    
    # Scale the metarig to fit the imported mesh
    mesh_height = mesh_obj.dimensions.z
    armature.scale = (mesh_height / 1.7, mesh_height / 1.7, mesh_height / 1.7)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Generate the rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    print("[3/5] Binding mesh to armature with Automatic Weights...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    
    # This creates the skin deformation "curves"
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    return mesh_obj, armature

# ============================================================
# 2. POSE & ANIMATE
# ============================================================
def animate_character(armature):
    print("[4/5] Posing and animating the character...")
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    # Rigify bone names
    try:
        thigh_l = armature.pose.bones["thigh.L"]
        thigh_r = armature.pose.bones["thigh.R"]
        upperarm_l = armature.pose.bones["upper_arm.L"]
        upperarm_r = armature.pose.bones["upper_arm.R"]
    except KeyError:
        print("    [!] Warning: Rigify bone names not found. Skipping animation.")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    # Clear any existing pose
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear()
    
    # Animate a simple walk cycle
    for frame in range(1, SIMULATION_FRAMES + 1, 8):
        scene.frame_set(frame)
        t = frame / SIMULATION_FRAMES * 2 * math.pi
        
        # Legs swing back and forth
        thigh_l.rotation_euler[0] = math.sin(t) * 0.5
        thigh_r.rotation_euler[0] = math.sin(t + math.pi) * 0.5
        
        # Arms swing opposite to legs
        upperarm_l.rotation_euler[0] = math.sin(t + math.pi) * 0.3
        upperarm_r.rotation_euler[0] = math.sin(t) * 0.3
        
        # Insert keyframes
        thigh_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        thigh_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        upperarm_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        upperarm_r.keyframe_insert(data_path="rotation_euler", frame=frame)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("    Character animation created.")

# ============================================================
# 3. CREATE & SIMULATE SAREE
# ============================================================
def create_saree():
    print("[5/5] Creating and simulating the saree...")
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
    
    # Scale and position the saree roughly around the body
    saree.scale = (5.5, 1.15, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    saree.location = (0, 0, 1.0)
    
    # Add material
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Sheen" in bsdf.inputs: bsdf.inputs["Sheen"].default_value = 0.6
    saree.data.materials.append(mat)
    
    # Add Cloth Physics
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 8
    cs.mass = 0.2
    cs.bending_stiffness = 0.3
    cs.air_damping = 1.5
    
    return saree

def simulate_and_export(saree, armature, mesh_obj):
    print(f"    Running cloth simulation for {SIMULATION_FRAMES} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    # Make the character mesh a collision object
    mesh_obj.modifiers.new(name="Collision", type='COLLISION')
    
    # Bake the physics
    bpy.ops.ptcache.bake_all(bake=True)
    
    # Apply the cloth modifier to bake the animation into the mesh
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    
    # Export
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
    print("    Done!")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print(" CHARACTER RIGGING & SAREE DRAPING PIPELINE ")
    print("=" * 55)
    
    if not os.path.exists(INPUT_GLB):
        print(f"ERROR: {INPUT_GLB} not found. Please upload your GLB file.")
        return
    
    clear_scene()
    mesh_obj, armature = import_and_rig()
    animate_character(armature)
    saree = create_saree()
    simulate_and_export(saree, armature, mesh_obj)

if __name__ == "__main__":
    main()
