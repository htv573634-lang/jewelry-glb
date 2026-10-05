# generate_saree.py
import bpy
import math
import os

# --- CONFIGURATION ---
CONFIG = {
    "output_path": "output/standalone_saree.glb",
    "length": 5.5,          # Length of the saree in meters
    "width": 1.2,           # Width of the saree in meters
    "pleats": 12,           # Number of pleats
    "fabric_mass": 0.3,     # Mass of the fabric
    "stiffness": 15.0,      # Fabric stiffness
    "air_damping": 1.0,     # Air resistance
    "simulation_frames": 120 # Duration of the simulation
}

def clear_scene():
    """Deletes all default objects in the Blender scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_mannequin():
    """Creates invisible collision shapes for the saree to drape over."""
    # Lower body (hips and legs)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.0, location=(0, 0, 0.5))
    lower_body = bpy.context.active_object
    lower_body.name = "Mannequin_Lower"
    lower_body.modifiers.new(name="Collision", type='COLLISION')
    lower_body.collision.thickness_outer = 0.02
    lower_body.collision.thickness_inner = 0.02
    
    # Upper body (torso and shoulders)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=0.6, location=(0, 0, 1.3))
    upper_body = bpy.context.active_object
    upper_body.name = "Mannequin_Upper"
    upper_body.modifiers.new(name="Collision", type='COLLISION')
    upper_body.collision.thickness_outer = 0.02
    upper_body.collision.thickness_inner = 0.02

def create_saree():
    """Generates the saree mesh with pleats and cloth physics."""
    print("Generating Saree Mesh...")
    
    # Create a high-resolution grid for the fabric
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=100, y_subdivisions=100, size=1)
    saree = bpy.context.active_object
    saree.name = "Saree"
    
    # Scale to real dimensions
    saree.scale = (CONFIG["width"] / 2, CONFIG["length"] / 2, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Apply a sine wave to create the pleats
    mesh = saree.data
    num_pleats = CONFIG["pleats"]
    width = CONFIG["width"]
    
    for vert in mesh.vertices:
        x_norm = (vert.co.x / width) * num_pleats * math.pi
        vert.co.z += math.sin(x_norm) * 0.02
        
    # Position the saree around the mannequin
    saree.location = (0, 0, 1.0)
    
    # Add Cloth Physics
    cloth_mod = saree.modifiers.new(name="Cloth", type='CLOTH')
    cloth_mod.settings.quality = 10
    cloth_mod.settings.mass = CONFIG["fabric_mass"]
    cloth_mod.settings.tension_stiffness = CONFIG["stiffness"]
    cloth_mod.settings.air_damping = CONFIG["air_damping"]
    
    # Pin the top edge so it doesn't fall off the mannequin
    vgroup = saree.vertex_groups.new(name="PinGroup")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for vert in mesh.vertices:
        # Select vertices at the top of the grid (y near max)
        if vert.co.y > (CONFIG["length"] / 2) - 0.1:
            vert.select = True
            vgroup.add([vert.index], 1.0, 'REPLACE')
            
    cloth_mod.settings.vertex_group_mass = "PinGroup"
    return saree

def simulate_and_bake(saree):
    """Runs the cloth simulation and bakes it into animation keyframes."""
    print(f"Running Cloth Simulation for {CONFIG['simulation_frames']} frames...")
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = CONFIG["simulation_frames"]
    
    # Bake the physics simulation
    bpy.ops.ptcache.bake_all(bake=True)
    
    # Apply the modifier to permanently bake the animation into the mesh
    bpy.context.view_layer.objects.active = saree
    bpy.ops.object.modifier_apply(modifier="Cloth")
    print("Simulation baked and applied successfully.")

def export_glb():
    """Exports the final animated GLB without the mannequin."""
    print(f"Exporting GLB to {CONFIG['output_path']}...")
    os.makedirs(os.path.dirname(CONFIG["output_path"]), exist_ok=True)
    
    # Delete the mannequins before export so only the saree remains
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
