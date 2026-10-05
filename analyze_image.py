# analyze_image.py
import cv2
import json
import mediapipe as mp
import numpy as np
import os
import glob

# --- CONFIGURATION ---
INPUT_DIR = "input/"
OUTPUT_DIR = "out_saree/"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "analysis.json")
OUTPUT_VIS = os.path.join(OUTPUT_DIR, "analysis_visualization.png")

def find_input_image():
    """Finds the first image file in the input directory."""
    patterns = ["*.jpg", "*.jpeg", "*.png"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(INPUT_DIR, p)))
        files.extend(glob.glob(os.path.join(INPUT_DIR, p.upper())))  # handle .JPG
    if not files:
        raise FileNotFoundError(f"No image file found in '{INPUT_DIR}' with extensions jpg, jpeg, png.")
    # Return the first one (you can sort for consistency)
    files.sort()
    return files[0]

# ============================================================
# COMPONENT 1: MediaPipe Pose (CPU, ~30ms)
# ============================================================
def extract_pose(image):
    print("[Component 1] Extracting body pose with MediaPipe...")
    mp_pose = mp.solutions.pose
    with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    
    if not results.pose_landmarks:
        raise ValueError("No pose detected in image.")
    
    h, w = image.shape[:2]
    landmarks = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks[mp_pose.PoseLandmark(idx).name] = {
            "x": lm.x * w,
            "y": lm.y * h,
            "visibility": lm.visibility
        }
    
    print(f"    Detected {len(landmarks)} landmarks")
    return landmarks

# ============================================================
# COMPONENT 2: Saree Segmentation (CPU, ~3s)
# ============================================================
def segment_saree(image):
    print("[Component 2] Segmenting saree with color analysis...")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat_channel = hsv[:, :, 1]
    val_channel = hsv[:, :, 2]
    
    _, mask_sat = cv2.threshold(sat_channel, 60, 255, cv2.THRESH_BINARY)
    _, mask_val = cv2.threshold(val_channel, 50, 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_and(mask_sat, mask_val)
    
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No saree region found.")
    
    largest = max(contours, key=cv2.contourArea)
    clean_mask = np.zeros_like(mask)
    cv2.drawContours(clean_mask, [largest], -1, 255, -1)
    
    print(f"    Saree occupies {np.sum(clean_mask > 0) / clean_mask.size * 100:.1f}% of image")
    return clean_mask, largest

# ============================================================
# COMPONENT 3: Drape Path Extraction (CPU, ~100ms)
# ============================================================
def extract_drape_paths(mask, pose_landmarks, image_shape):
    print("[Component 3] Extracting drape paths from silhouette...")
    h, w = image_shape[:2]
    
    l_shoulder = pose_landmarks["LEFT_SHOULDER"]
    r_shoulder = pose_landmarks["RIGHT_SHOULDER"]
    l_hip = pose_landmarks["LEFT_HIP"]
    r_hip = pose_landmarks["RIGHT_HIP"]
    
    rows_with_mask = np.where(np.any(mask > 0, axis=1))[0]
    if len(rows_with_mask) == 0:
        raise ValueError("Empty mask")
    
    hem_y = rows_with_mask.max()
    top_y = rows_with_mask.min()
    
    pallu_path = []
    for y in np.linspace(l_shoulder["y"], hem_y, 15):
        row = mask[int(y), :]
        cols = np.where(row > 0)[0]
        if len(cols) > 0:
            pallu_path.append({"x": float(cols[0]), "y": float(y)})
    
    waist_y = (l_hip["y"] + r_hip["y"]) / 2
    pleat_path = []
    for y in np.linspace(waist_y, hem_y, 10):
        row = mask[int(y), :]
        cols = np.where(row > 0)[0]
        if len(cols) > 0:
            pleat_path.append({"x": float((cols[0] + cols[-1]) / 2), "y": float(y)})
    
    def normalize(point):
        return {"x": point["x"] / w, "y": point["y"] / h}
    
    data = {
        "image_shape": {"width": w, "height": h},
        "pose": pose_landmarks,
        "pallu_path": [normalize(p) for p in pallu_path],
        "pleat_path": [normalize(p) for p in pleat_path],
        "shoulder_left": normalize(l_shoulder),
        "shoulder_right": normalize(r_shoulder),
        "hip_left": normalize(l_hip),
        "hip_right": normalize(r_hip)
    }
    
    print(f"    Pallu path: {len(pallu_path)} points")
    print(f"    Pleat path: {len(pleat_path)} points")
    return data

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 50)
    print(" STACKED SAREE ANALYZER - CPU ONLY ")
    print("=" * 50)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        input_path = find_input_image()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    
    print(f"Using input image: {input_path}")
    image = cv2.imread(input_path)
    print(f"Loaded image: {image.shape[1]}x{image.shape[0]}")
    
    pose = extract_pose(image)
    mask, contour = segment_saree(image)
    paths = extract_drape_paths(mask, pose, image.shape)
    
    # Save visualization
    vis = image.copy()
    cv2.drawContours(vis, [contour], -1, (0, 255, 0), 3)
    for p in paths["pallu_path"]:
        cv2.circle(vis, (int(p["x"] * image.shape[1]), int(p["y"] * image.shape[0])), 8, (0, 0, 255), -1)
    for p in paths["pleat_path"]:
        cv2.circle(vis, (int(p["x"] * image.shape[1]), int(p["y"] * image.shape[0])), 8, (255, 0, 0), -1)
    cv2.imwrite(OUTPUT_VIS, vis)
    print(f"Saved visualization to {OUTPUT_VIS}")
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(paths, f, indent=2)
    
    print(f"Saved analysis to {OUTPUT_JSON}")
    print("=" * 50)

if __name__ == "__main__":
    main()
