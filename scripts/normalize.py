import os
import sys
import glob
import trimesh

def normalize_asset(input_path, output_path, target_size_m=0.02):
    """Scale any GLB/OBJ to a target real-world size and center at origin."""
    mesh = trimesh.load(input_path, force="mesh", process=False)
    if hasattr(mesh, "geometry"):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    extent = mesh.bounding_box.extents
    scale = target_size_m / max(extent.max(), 1e-6)
    mesh.apply_scale(scale)
    mesh.apply_translation(-mesh.bounding_box.centroid)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mesh.export(output_path)
    print(f"[OK] {input_path} -> {output_path} (scale={scale:.4f})")

def main():
    if len(sys.argv) < 3:
        print("Usage: python normalize.py <input_dir> <output_dir> [target_size_m]")
        sys.exit(1)
    input_dir, output_dir = sys.argv[1], sys.argv[2]
    target = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
    for ext in ("glb", "gltf", "obj", "fbx"):
        for f in glob.glob(os.path.join(input_dir, f"*.{ext}")):
            name = os.path.splitext(os.path.basename(f))[0]
            normalize_asset(f, os.path.join(output_dir, f"{name}.glb"), target)

if __name__ == "__main__":
    main()
