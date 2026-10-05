# generate_saree.py
import bpy
import math
import os

# --- CONFIGURATION ---
CONFIG = {
    "output_path": "output/standalone_saree.glb",
    "fabric_mass": 0.3,
    "stiffness": 15.0,
    "air_damping": 1.0,
    "simulation_frames": 120
}

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_mannequin():
    """Creates a more human-like mannequin and animates it."""
    # Head
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0, 0, 1.9))
    head = bpy.context.active_object
    head.name = "Mannequin_Head"
    
    # Torso
    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=0.6, location=(0, 0, 1.5))
    torso = bpy.context.active_object
    torso.name = "Mannequin_Torso"
    
    # Hips
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.4, location=(0, 0, 1.1))
    hips = bpy.context.active_object
    hips.name = "Mannequin_Hips"
    
    # Legs
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=1.0, location=(0, 0, 0.5))
    legs = bpy.context.active_object
    legs.name = "Mannequin_Legs"
    
    # Left Arm (for the pallu to drape)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.7, location=(-0.3, 0, 1.5), rotation=(0, math.radians(90), 0))
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
        angle = math.sin(frame * 0.15) * 0.4 # Rotate up to ~23 degrees
        hips.rotation_euler[1] = angle # Tilt side to side (Y-axis)
        torso.rotation_euler[1] = angle * 0.5
        arm.rotation_euler[1] = angle * 0.2
        
        hips.keyframe_insert(data_path="rotation_euler", frame=frame)
        torso.keyframe_insert(data_path="rotation_euler", frame=frame)
        arm.keyframe_insert(data_path="rotation_euler", frame=frame)

def create_saree():
    """Generates a pleated skirt and a pallu panel."""
    print("Generating Structured Saree Mesh...")
    
    # 1. Create the Skirt (Pleated Cylinder)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.30, depth=1.2, location=(0, 0, 1.0))
    skirt = bpy.context.active_object
    skirt.name = "Saree_Skirt"
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='ONLY_FACE') # Open top and bottom
    bpy.ops.mesh.subdivide(number_cuts=30) # High res for pleats
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Apply deep radial pleats
    mesh = skirt.data
    for vert in mesh.vertices:
        angle = math.atan2(vert.co.y, vert.co.x)
        # A combination of high and low frequency sine waves for realistic pleats
        pleat_effect = (math.sin(angle * 24) * 0.03) + (math.sin(angle * 8) * 0.02)
        vert.co.x += math.cos(angle) * pleat_effect
        vert.co.y += math.sin(angle) * pleat_effect

    # 2. Create the Pallu (Flat Panel draped over shoulder)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=60, size=1)
    pallu = bpy.context.active_object
    pallu.name = "Saree_Pallu"
    # Scale and position to drape from waist, up over left shoulder, and down back
    pallu.scale = (0.4, 1.5, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    pallu.location = (0.1, 0.1, 1.6)
    pallu.rotation_euler = (math.radians(90), math.radians(45), math.radians(10))
    
    # 3. Join Skirt and Pallu
    bpy.ops.object.select_all(action='DESELECT')
    skirt.select_set(True)
    pallu.select_set(True)
    bpy.context.view_layer.objects.active = skirt
    bpy.ops.object.join()
    saree = bpy.context.active_object
    saree.name = "Saree"
    
    # --- ADD COLOR MATERIAL (Deep Red Silk) ---
    mat = bpy.data.materials.new(name="Saree_Red")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.7, 0.02, 0.05, 1) # Rich Red
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Sheen"].default_value = 0.8 # High Sheen for Silk
    saree.data.materials.append(mat)
    
    # 4. Add Cloth Physics
    cloth_mod = saree.modifiers.new(name="Cloth", type='CLOTH')
    cloth_mod.settings.quality = 10
    cloth_mod.settings.mass = CONFIG["fabric_mass"]
    cloth_mod.settings.tension_stiffness = CONFIG["stiffness"]
    cloth_mod.settings.air_damping = CONFIG["air_damping"]
    
    # 5. Pin the Waist and Shoulder
    vgroup = saree.vertex_groups.new(name="PinGroup")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Pin the waist (around Z=1.5) and the shoulder area (Z > 1.8)
    for vert in mesh.vertices:
        if 1.4 < vert.co.z < 1.6:
            vert.select = True
            vgroup.add([vert.index], 1.0, 'REPLACE')
        elif vert.co.z > 1.8:
            vert.select = True
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
    saree = create_saree()
    simulate_and_bake(saree)
    export_glb()

if __name__ == "__main__":
    main()
