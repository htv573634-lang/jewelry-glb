# generate_saree.py
import bpy
import bmesh
import math
import os
from mathutils import Vector

# --- CONFIGURATION ---
CONFIG = {
    "output_path": "output/standalone_saree.glb",
    "saree_color": (0.0, 0.6, 0.2, 1),   # Emerald Green
    "border_color": (0.8, 0.6, 0.1, 1),  # Gold
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
    
    # Torso
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

    # --- ANIMATE THE MANNEQUIN (To create dramatic swaying) ---
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = CONFIG["simulation_frames"]
    
    for frame in range(1, CONFIG["simulation_frames"] + 1, 10):
        bpy.context.scene.frame_set(frame)
        # Dramatic sine wave motion for the hips and torso
        angle = math.sin(frame * 0.15) * 0.4 
        hips.rotation_euler[1] = angle 
        torso.rotation_euler[1] = angle * 0.5
        arm.rotation_euler[1] = angle * 0.2
        
        hips.keyframe_insert(data_path="rotation_euler", frame=frame)
        torso.keyframe_insert(data_path="rotation_euler", frame=frame)
        arm.keyframe_insert(data_path="rotation_euler", frame=frame)

def create_parametric_saree():
    """Generates a structured Nivi drape saree mesh using bmesh."""
    print("Generating Parametric Nivi Drape Saree...")
    
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    bm = bmesh.new()
    
    # --- 1. Pleated Skirt (Front Pleats Only) ---
    waist_z = 1.3
    hem_z = 0.2
    num_segments = 64
    pleats = 12 # Fewer pleats, concentrated at the front
    
    verts_bottom = []
    verts_top = []
    
    for i in range(num_segments):
        angle = (2 * math.pi * i) / num_segments
        
        # Calculate pleat effect ONLY for the front half (angle between -pi/2 and pi/2)
        if -math.pi/2 < angle < math.pi/2:
            # Concentrate pleats in the center front
            pleat_offset = math.sin(angle * pleats) * 0.05
        else:
            # Smooth wrap at the back
            pleat_offset = 0
            
        radius = 0.28 + pleat_offset
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        # Flared hem
        hem_radius = 0.38 + pleat_offset
        hem_x = hem_radius * math.cos(angle)
        hem_y = hem_radius * math.sin(angle)
        
        verts_bottom.append(bm.verts.new((hem_x, hem_y, hem_z)))
        verts_top.append(bm.verts.new((x, y, waist_z)))
    
    # Create faces for the skirt
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        bm.faces.new((verts_bottom[i], verts_bottom[next_i], verts_top[next_i], verts_top[i]))
        
    # --- 2. Torso Wrap & Pallu (Swept Path) ---
    # Path mapped from the photo: Back waist -> over left shoulder -> front drop
    path_points = [
        Vector((0.0, -0.20, 1.2)),  # Back waist
        Vector((0.0, -0.18, 1.5)),  # Mid back
        Vector((0.0, -0.15, 1.7)),  # Upper back
        Vector((-0.15, -0.05, 1.8)), # Over left shoulder
        Vector((-0.18, 0.15, 1.6)),  # Front chest drop
        Vector((-0.18, 0.20, 1.0)),  # Lower front drop
        Vector((-0.18, 0.25, 0.5)),  # Hem of pallu
    ]
    
    # Interpolate the path to get a smooth mesh
    num_path_steps = len(path_points) * 5
    interpolated_points = []
    
    for i in range(len(path_points) - 1):
        p1 = path_points[i]
        p2 = path_points[i+1]
        for t in [j / 5 for j in range(5)]:
            interpolated_points.append(p1.lerp(p2, t))
    interpolated_points.append(path_points[-1])
    
    # Create the swept mesh (width of the pallu = 0.4)
    pallu_width = 0.4
    pallu_verts = []
    
    for i, center in enumerate(interpolated_points):
        row = []
        for j in range(3): # 3 segments across the width
            w = (j / 2 - 0.5) * pallu_width
            v = bm.verts.new((center.x + w, center.y, center.z))
            row.append(v)
        pallu_verts.append(row)
        
    # Create faces for the pallu
    for i in range(len(pallu_verts) - 1):
        for j in range(len(pallu_verts[i]) - 1):
            v1 = pallu_verts[i][j]
            v2 = pallu_verts[i][j+1]
            v3 = pallu_verts[i+1][j+1]
            v4 = pallu_verts[i+1][j]
            bm.faces.new((v1, v2, v3, v4))

    bm.to_mesh(mesh)
    bm.free()
    
    # --- ADD COLOR MATERIAL (Silk) ---
    mat = bpy.data.materials.new(name="Saree_Green")
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
        # Pin the waist area (top of the skirt)
        if 1.2 < vert.co.z < 1.4:
            vgroup.add([vert.index], 1.0, 'REPLACE')
        # Pin the shoulder area
        elif vert.co.z > 1.7 and vert.co.x < -0.1:
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
