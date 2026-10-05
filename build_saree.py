# build_saree.py
import bpy
import bmesh
import math
import os
from mathutils import Vector

# ============================================================
# CONFIGURATION - Real Saree Dimensions (meters)
# ============================================================
SAREE_LENGTH = 5.5      # Full saree length
SAREE_WIDTH = 1.15      # Fabric width
MESH_RES_X = 160        # Length segments (high-res for smooth folds)
MESH_RES_Y = 50         # Width segments
SIMULATION_FRAMES = 200
OUTPUT_GLB = "out_saree/realistic_saree.glb"
SAREE_COLOR = (0.72, 0.03, 0.08, 1)  # Deep silk red

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# ============================================================
# MANNEQUIN
# ============================================================
def create_mannequin():
    """A human-like collision body that the saree will drape over."""
    print("[1/5] Building mannequin...")
    parts = []
    
    def add_and_name(name, radius, depth, location, is_sphere=False):
        if is_sphere:
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=radius, location=location, segments=32, ring_count=16
            )
        else:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=radius, depth=depth, location=location, vertices=32
            )
        obj = bpy.context.active_object
        obj.name = name
        obj.modifiers.new(name="Collision", type='COLLISION')
        obj.collision.thickness_outer = 0.03
        obj.collision.thickness_inner = 0.03
        parts.append(obj)
        return obj

    # Body parts
    add_and_name("Mannequin_Head", 0.11, 0, (0, 0, 1.75), is_sphere=True)
    add_and_name("Mannequin_Chest", 0.17, 0.40, (0, 0, 1.50))
    add_and_name("Mannequin_Waist", 0.14, 0.20, (0, 0, 1.25))
    add_and_name("Mannequin_Hips", 0.20, 0.40, (0, 0, 1.00))
    add_and_name("Mannequin_Thighs", 0.14, 0.80, (0, 0, 0.40))
    
    # Left arm (for pallu to drape over)
    add_and_name("Mannequin_Arm", 0.055, 0.65, (-0.28, 0, 1.55))
    
    # Smooth the torso for realistic drape
    for obj in parts:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        subsurf.levels = 1
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
        
    return parts

# ============================================================
# SAREE FABRIC
# ============================================================
def create_saree_fabric():
    """
    Creates a single long rectangular saree fabric, positioned
    in an initial 'thrown around the body' shape.
    """
    print(f"[2/5] Creating saree fabric ({SAREE_LENGTH}m x {SAREE_WIDTH}m)...")
    
    mesh = bpy.data.meshes.new("Saree_Mesh")
    saree = bpy.data.objects.new("Saree", mesh)
    bpy.context.collection.objects.link(saree)
    
    bm = bmesh.new()
    
    # --- Build the fabric as a long rectangular grid ---
    # X axis = length (along the saree's long dimension)
    # Y axis = width (across the fabric)
    verts = []
    for x_i in range(MESH_RES_X + 1):
        t_x = x_i / MESH_RES_X  # 0.0 to 1.0 along the length
        row = []
        for y_i in range(MESH_RES_Y + 1):
            t_y = y_i / MESH_RES_Y  # 0.0 to 1.0 across the width
            row.append(bm.verts.new((t_x, t_y, 0)))
        verts.append(row)
    
    # Create faces
    for x_i in range(MESH_RES_X):
        for y_i in range(MESH_RES_Y):
            bm.faces.new((
                verts[x_i][y_i],
                verts[x_i + 1][y_i],
                verts[x_i + 1][y_i + 1],
                verts[x_i][y_i + 1]
            ))
    
    bm.to_mesh(mesh)
    bm.free()
    
    # --- Scale to real saree size ---
    saree.scale = (SAREE_LENGTH, SAREE_WIDTH, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # --- Position the saree around the body in a "starting drape" ---
    # The first 3.5m wraps around the hips (spiral)
    # The last 2.0m goes up and over the left shoulder as the pallu
    for v in mesh.vertices:
        x = v.co.x  # 0.0 to 5.5 (along length)
        y = v.co.y  # 0.0 to 1.15 (across width)
        
        if x < 3.5:
            # Lower portion: wrap around hips in a spiral
            # 3.5m wraps around ~1.3m circumference = ~2.7 turns
            angle = (x / 3.5) * (2 * math.pi * 2.5)  # 2.5 turns
            radius = 0.22 + (y / SAREE_WIDTH) * 0.03  # Slight taper
            z = 1.35 - (x / 3.5) * 0.95  # Descends from waist to hem
            v.co.x = radius * math.cos(angle)
            v.co.y = radius * math.sin(angle)
            v.co.z = z
        else:
            # Upper portion: the pallu
            pallu_t = (x - 3.5) / 2.0  # 0 to 1 along the pallu
            
            if pallu_t < 0.4:
                # Bring up across the front of the chest
                t = pallu_t / 0.4
                v.co.x = -0.15 * t + (y / SAREE_WIDTH - 0.5) * 0.15
                v.co.y = 0.10 - 0.05 * t
                v.co.z = 1.35 + 0.55 * t
            elif pallu_t < 0.55:
                # Over the left shoulder
                t = (pallu_t - 0.4) / 0.15
                v.co.x = -0.15 - 0.15 * t + (y / SAREE_WIDTH - 0.5) * 0.15
                v.co.y = 0.05 - 0.20 * t
                v.co.z = 1.90
            else:
                # Down the back as the pallu tail
                t = (pallu_t - 0.55) / 0.45
                v.co.x = -0.30 + (y / SAREE_WIDTH - 0.5) * 0.15
                v.co.y = -0.15 - 0.10 * t
                v.co.z = 1.90 - 1.35 * t
    
    # --- Material: Realistic silk ---
    mat = bpy.data.materials.new(name="Saree_Silk")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = SAREE_COLOR
    bsdf.inputs["Roughness"].default_value = 0.28
    bsdf.inputs["Sheen"].default_value = 0.9
    bsdf.inputs["Sheen Tint"].default_value = (1.0, 0.85, 0.55, 1)
    bsdf.inputs["Metallic"].default_value = 0.0
    saree.data.materials.append(mat)
    
    # --- Cloth Physics (Realistic Silk) ---
    cloth = saree.modifiers.new(name="Cloth", type='CLOTH')
    cs = cloth.settings
    cs.quality = 12
    cs.mass = 0.20                    # Lightweight silk
    cs.tension_stiffness = 15.0       # Resists stretching
    cs.compression_stiffness = 15.0
    cs.shear_stiffness = 10.0
    cs.bending_stiffness = 0.35       # LOW = soft, flowing drape
    cs.air_damping = 1.5
    cs.internal_friction = 20.0
    cs.effector_weights.gravity = 1.0
    cs.use_pressure = False
    
    # --- Pin waist and shoulder ---
    vgroup = saree.vertex_groups.new(name="PinGroup")
    for v in mesh.vertices:
        # Pin the waist-band region (first 0.3m of the saree length)
        if v.co.z > 1.30 and abs(v.co.x) < 0.30 and abs(v.co.y) < 0.30:
            vgroup.add([v.index], 1.0, 'REPLACE')
        # Pin the shoulder region (where the pallu goes over the left shoulder)
        elif v.co.z > 1.85 and v.co.x < -0.15:
            vgroup.add([v.index], 1.0, 'REPLACE')
    cs.vertex_group_mass = "PinGroup"
    
    return saree

# ============================================================
# ANIMATION - Make the mannequin move
# ============================================================
def animate_mannequin(parts):
    """Animate the mannequin to add realistic cloth sway."""
    print("[3/5] Animating mannequin for cloth sway...")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    hips = next((o for o in parts if "Hips" in o.name), None)
    chest = next((o for o in parts if "Chest" in o.name), None)
    waist = next((o for o in parts if "Waist" in o.name), None)
    
    for frame in range(1, SIMULATION_FRAMES + 1, 6):
        scene.frame_set(frame)
        # Walking-like sway
        angle = math.sin(frame * 0.10) * 0.30
        bob = math.sin(frame * 0.20) * 0.02
        
        if hips:
            hips.rotation_euler[2] = angle
            hips.location.z = 1.00 + bob
            hips.keyframe_insert(data_path="rotation_euler", frame=frame)
            hips.keyframe_insert(data_path="location", frame=frame)
        if waist:
            waist.rotation_euler[2] = -angle * 0.5
            waist.keyframe_insert(data_path="rotation_euler", frame=frame)
        if chest:
            chest.rotation_euler[2] = angle * 0.3
            chest.keyframe_insert(data_path="rotation_euler", frame=frame)

# ============================================================
# SIMULATE, BAKE, EXPORT
# ============================================================
def simulate_and_export(saree):
    print(f"[4/5] Running cloth simulation for {SIMULATION_FRAMES} frames...")
    print("      (This will take a few minutes on CPU)")
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = SIMULATION_FRAMES
    
    # Bake the cloth physics
    bpy.ops.ptcache.bake_all(bake=True)
    print("      Simulation baked.")
    
    # Apply the modifier to permanently lock the animation into the mesh
    bpy.context.view_layer.objects.active = saree
    saree.select_set(True)
    bpy.ops.object.modifier_apply(modifier="Cloth")
    print("      Modifier applied - motion is now part of the geometry.")
    
    # Delete mannequin before export (we only want the saree)
    for obj in list(bpy.data.objects):
        if "Mannequin" in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Export
    print(f"[5/5] Exporting GLB to {OUTPUT_GLB}...")
    os.makedirs(os.path.dirname(OUTPUT_GLB), exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_GLB,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True,
        export_animation_mode='NLA_TRACKS'
    )
    print(f"      Saved to {OUTPUT_GLB}")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print(" REALISTIC CLOTH SAREE BUILDER ")
    print(f" Saree: {SAREE_LENGTH}m x {SAREE_WIDTH}m silk ")
    print(f" Simulation: {SIMULATION_FRAMES} frames ")
    print("=" * 55)
    
    clear_scene()
    parts = create_mannequin()
    saree = create_saree_fabric()
    animate_mannequin(parts)
    simulate_and_export(saree)
    
    print("=" * 55)
    print(" DONE. Download the artifact to view the saree. ")
    print("=" * 55)

if __name__ == "__main__":
    main()
