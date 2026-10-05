# generate_saree.py
import bpy
import math
import os

# --- CONFIGURATION ---
CONFIG = {
    "output_path": "output/standalone_saree.glb",
    "pleats": 16,           # Number of pleats in the skirt
    "fabric_mass": 0.3,     # Mass of the fabric
    "stiffness": 15.0,      # Fabric stiffness
    "air_damping": 1.0,     # Air resistance
    "simulation_frames": 120 # Duration of the simulation
}

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_mannequin():
    """Creates invisible collision shapes and animates them."""
    # Legs
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=1.0, location=(0, 0, 0.5))
    legs = bpy.context.active_object
    legs.name = "Mannequin_Legs"
    
    # Hips
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.6, location=(0, 0, 1.1))
    hips = bpy.context.active_object
    hips.name = "Mannequin_Hips"
    
    # Chest/Shoulders
    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=0.5, location=(0, 0, 1.7))
    chest = bpy.context.active_object
    chest.name = "Mannequin_Chest"
    
    # Right Arm (for the pallu to drape over)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.7, location=(0.4, 0, 1.7), rotation=(0, math.radians(90), 0))
    arm = bpy.context.active_object
    arm.name = "Mannequin_Arm"
    
    # Add collision physics
    for obj in [legs, hips, chest, arm]:
        obj.modifiers.new(name="Collision", type='COLLISION')
        obj.collision.thickness_outer = 0.02
        obj.collision.thickness_inner = 0.02

    # --- ANIMATE THE MANNEQUIN (To create swaying) ---
    # We will rotate the mannequin slightly to simulate walking/swaying hips
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = CONFIG["simulation_frames"]
    
    for frame in range(1, CONFIG["simulation_frames"] + 1, 10):
        bpy.context.scene.frame_set(frame)
        # Create a sine wave motion for the hips and chest
        angle = math.sin(frame * 0.1) * 0.15 # Rotate up to ~8 degrees
        hips.rotation_euler[2] = angle
        chest.rotation_euler[2] = angle * 0.5
        arm.rotation_euler[2] = angle * 0.2
        
        # Insert keyframes
        hips.keyframe_insert(data_path="rotation_euler", frame=frame)
        chest.keyframe_insert(data_path="rotation_euler", frame=frame)
        arm.keyframe_insert(data_path="rotation_euler", frame=frame)

def create_saree():
    """Generates a pre-wrapped saree mesh and adds a red material."""
    print("Generating Realistic Saree Mesh...")
    
    # 1. Create the Skirt (Cylinder)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.28, depth=1.2, location=(0, 0, 1.0))
    skirt = bpy.context.active_object
    skirt.name = "Saree_Skirt"
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='ONLY_FACE')
    bpy.ops.mesh.subdivide(number_cuts=20)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Radial Pleats
    mesh = skirt.data
    num_pleats = CONFIG["pleats"]
    for vert in mesh.vertices:
        angle = math.atan2(vert.co.y, vert.co.x)
        pleat_effect = math.sin(angle * num_pleats) * 0.03
        vert.co.x += math.cos(angle) * pleat_effect
        vert.co.y += math.sin(angle) * pleat_effect

    # 2. Create the Pallu (Flat Panel)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=1)
    pallu = bpy.context.active_object
    pallu.name = "Saree_Pallu"
    pallu.scale = (0.3, 1.2, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    pallu.location = (0.1, 0.1, 1.8)
    pallu.rotation_euler = (0, math.radians(30), 0)
    
    # 3. Join Skirt and Pallu
    bpy.ops.object.select_all(action='DESELECT')
    skirt.select_set(True)
    pallu.select_set(True)
    bpy.context.view_layer.objects.active = skirt
    bpy.ops.object.join()
    saree = bpy.context.active_object
    saree.name = "Saree"
    
    # --- ADD COLOR MATERIAL ---
    mat = bpy.data.materials.new(name="Saree_Red")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.05, 0.1, 1) # Deep Red
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.4
    mat.node_tree.nodes["Principled BSDF"].inputs["Sheen"].default_value = 0.5 # Silk-like shine
    saree.data.materials.append(mat)
    
    # 4. Add Cloth Physics
    cloth_mod = saree.modifiers.new(name="Cloth", type='CLOTH')
    cloth_mod.settings.quality = 10
    cloth_mod.settings.mass = CONFIG["fabric_mass"]
    cloth_mod.settings.tension_stiffness = CONFIG["stiffness"]
    cloth_mod.settings.air_damping = CONFIG["air_damping"]
    
    # 5. Pin Waist and Shoulder
    vgroup = saree.vertex_groups.new(name="PinGroup")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for vert in mesh.vertices:
        if 1.2 < vert.co.z < 1.5 or (vert.co.z > 1.7 and vert.co.y > 0):
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
