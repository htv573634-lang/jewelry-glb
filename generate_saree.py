# generate_saree.py
import bpy
import bmesh
import math
import os
from mathutils import Vector

# --- CONFIGURATION (CUSTOMIZE HERE) ---
CONFIG = {
    "output_path": "output/standalone_saree.glb",
    "saree_color": (0.7, 0.02, 0.05, 1), # Rich Red
    "fabric_mass": 0.3,
    "stiffness": 15.0,
    "air_damping": 1.0,
    "simulation_frames": 120
}

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_mannequin():
    """Creates a smooth, human-like mannequin and animates it."""
    # Head
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0, 0, 1.85))
    head = bpy.context.active_object
    head.name = "Mannequin_Head"
    
    # Torso (use a scaled sphere for smoother curves)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(0, 0, 1.4))
    torso = bpy.context.active_object
    torso.name = "Mannequin_Torso"
    torso.scale = (1.0, 0.8, 1.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Hips
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(0, 0, 1.0))
    hips = bpy.context.active_object
    hips.name = "Mannequin_Hips"
    hips.scale = (1.0, 0.9, 0.8)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Legs
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=1.0, location=(0, 0, 0.4))
    legs = bpy.context.active_object
    legs.name = "Mannequin_Legs"
    
    # Left Arm (for pallu)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.7, location=(-0.3, 0, 1.4), rotation=(0, math.radians(90), 0))
    arm = bpy.context.active_object
    arm.name = "Mannequin_Arm"
    
    # Add collision physics
    for obj in [head, torso, hips, legs, arm]:
        obj.modifiers.new(name="Collision", type='COLLISION')
        obj.collision.thickness_outer = 0.02
        obj.collision.thickness_inner = 0.02

    # --- ANIMATE THE MANNEQUIN (To create swaying) ---
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = CONFIG["simulation_frames"]
    
    for frame in range(1, CONFIG["simulation_frames"] + 1, 10):
        bpy.context.scene.frame_set(frame)
        # Dramatic sine wave motion for hips and torso
        angle = math.sin(frame * 0.15) * 0.4 
        hips.rotation_euler[1] = angle 
        torso.rotation_euler[1] = angle * 0.5
        arm.rotation_euler[1] = angle * 0.2
        
        hips.keyframe_insert(data_path="rotation_euler", frame=frame)
        torso.keyframe_insert(data_path="rotation_euler", frame=frame)
        arm.keyframe_insert(data_path="rotation_euler", frame=frame)

def create_parametric_saree():
    """Generates a structured saree mesh using bmesh."""
    print("Generating Parametric Saree Mesh...")
    
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    bm = bmesh.new()
    
    # --- 1. Create the Pleated Skirt (Wrap around hips) ---
    waist_z = 1.3
    hem_z = 0.2
    num_segments = 64
    pleats = 16
    
    verts_bottom = []
    verts_top = []
    
    for i in range(num_segments):
        angle = (2 * math.pi * i) / num_segments
        # Pleat effect using sine wave
        pleat_offset = math.sin(angle * pleats) * 0.03
        
        radius = 0.28 + pleat_offset
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        # Bottom hem (flared out slightly)
        hem_radius = 0.35 + pleat_offset
        hem_x = hem_radius * math.cos(angle)
        hem_y = hem_radius * math.sin(angle)
        
        verts_bottom.append(bm.verts.new((hem_x, hem_y, hem_z)))
        verts_top.append(bm.verts.new((x, y, waist_z)))
    
    # Create faces for the skirt
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        bm.faces.new((verts_bottom[i], verts_bottom[next_i], verts_top[next_i], verts_top[i]))
        
    # --- 2. Create the Pallu (Draped over left shoulder) ---
    # We will create a flat panel that starts at the waist, goes up to the shoulder, and hangs down
    pallu_width = 0.4
    pallu_length = 1.2
    
    # Create a grid for the pallu
    pallu_res_x = 20
    pallu_res_y = 30
    pallu_verts = []
    
    start_z = waist_z - 0.1
    shoulder_z = 1.7
    
    for y in range(pallu_res_y + 1):
        row = []
        for x in range(pallu_res_x + 1):
            u = x / pallu_res_x
            v = y / pallu_res_y
            
            # Map u to width, v to height
            px = (u - 0.5) * pallu_width
            pz = start_z + v * pallu_length
            
            # Curve the pallu over the shoulder
            if pz > shoulder_z:
                py = (pz - shoulder_z) * 0.5
                pz = shoulder_z
            else:
                py = 0.05
                
            row.append(bm.verts.new((px - 0.1, py, pz)))
        pallu_verts.append(row)
        
    for y in range(pallu_res_y):
        for x in range(pallu_res_x):
            v1 = pallu_verts[y][x]
            v2 = pallu_verts[y][x+1]
            v3 = pallu_verts[y+1][x+1]
            v4 = pallu_verts[y+1][x]
            bm.faces.new((v1, v2, v3, v4))
            
    bm.to_mesh(mesh)
    bm.free()
    
    # --- ADD COLOR MATERIAL (Silk) ---
    mat = bpy.data.materials.new(name="Saree_Red")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = CONFIG["saree_color"]
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Sheen"].default_value = 0.8 # Silk
    saree.data.materials.append(mat)
    
    # --- ADD CLOTH PHYSICS ---
    cloth_mod = saree.modifiers.new(name="Cloth", type='CLOTH')
    cloth_mod.settings.quality = 10
    cloth_mod.settings.mass = CONFIG["fabric_mass"]
    cloth_mod.settings.tension_stiffness = CONFIG["stiffness"]
    cloth_mod.settings.air_damping = CONFIG["air_damping"]
    
    # --- PIN THE WAIST AND SHOULDER ---
    vgroup = saree.vertex_groups.new(name="PinGroup")
    
    for vert in mesh.vertices:
        # Pin the waist area
        if 1.2 < vert.co.z < 1.4:
            vgroup.add([vert.index], 1.0, 'REPLACE')
        # Pin the shoulder area
        elif vert.co.z > 1.6 and vert.co.x < 0:
            vgroup.add([vert.index], 1.0, 'REPLACE')
            
    cloth_mod.settings.vertex_group_mass = "PinGroup"
    return saree

def simulate_and_bake(saree):
    """Runs the cloth simulation and bakes it."""
    print(f"Running Cloth Simulation for {CONFIG['simulation_frames']} frames...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = CONFIG["simulation_frames"]
    
    bpy.ops.ptcache.bake_all(bake=True)
    
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    print("Simulation baked and applied successfully.")

def export_glb():
    """Exports the final animated GLB."""
    print(f"Exporting GLB to {CONFIG['output_path']}...")
    os.makedirs(os.path.dirname(CONFIG["output_path"]), exist_ok=True)
    
    for obj in bpy.data.objects:
        if "Mannequin" in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
            
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=CONFIG["output_path"],
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True
    )
    print("Export complete!")

def main():
    clear_scene()
    create_mannequin()
    saree = create_parametric_saree()
    simulate_and_bake(saree)
    export_glb()

if __name__ == "__main__":
    main()
