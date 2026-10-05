# analyze_image.py
import cv2
import json
import mediapipe as mp
import numpy as np
import os
import glob
import sys

# --- CONFIGURATION ---
INPUT_DIR = "inputs/"
OUTPUT_DIR = "out_saree/"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "analysis.json")
OUTPUT_VIS = os.path.join(OUTPUT_DIR, "analysis_visualization.png")

def list_input_dir():
    """Debug helper: list everything in the inputs folder."""
    print(f"--- Contents of '{INPUT_DIR}' ---")
    if not os.path.exists(INPUT_DIR):
        print(f"    Directory '{INPUT_DIR}' does NOT exist.")
        return
    for root, dirs, files in os.walk(INPUT_DIR):
        for name in files:
            path = os.path.join(root, name)
            size = os.path.getsize(path)
            print(f"    {path} ({size} bytes)")
    print("---------------------------------")

def find_input_image():
    """Finds the first image file in the inputs directory."""
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(INPUT_DIR, p)))
    if not files:
        raise FileNotFoundError(
            f"No image file found in '{INPUT_DIR}'. "
            f"Please upload a .jpg, .jpeg, or .png file."
        )
    files.sort()
    return files[0]

def extract_pose(image):
    print("[Component 1] Extracting body pose with MediaPipe...")
    mp_pose = mp.solutions.pose
    with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    if not results.pose_landmarks:
        raise ValueError("No pose detected in the image. Try a clearer photo with a full body visible.")
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
        raise ValueError("No saree region found. The image may not contain a saturated fabric.")
    largest = max(contours, key=cv2.contourArea)
    clean_mask = np.zeros_like(mask)
    cv2.drawContours(clean_mask, [largest], -1, 255, -1)
    print(f"    Saree occupies {np.sum(clean_mask > 0) / clean_mask.size * 100:.1f}% of image")
    return clean_mask, largest

def extract_drape_paths(mask, pose_landmarks, image_shape):
    print("[Component 3] Extracting drape paths from silhouette...")
    h, w = image_shape[:2]
    l_shoulder = pose_landmarks["LEFT_SHOULDER"]
    r_shoulder = pose_landmarks["RIGHT_SHOULDER"]
    l_hip = pose_landmarks["LEFT_HIP"]
    r_hip = pose_landmarks["RIGHT_HIP"]
    rows_with_mask = np.where(np.any(mask > 0, axis=1))[0]
    if len(rows_with_mask) == 0:
        raise ValueError("Empty mask after segmentation.")
    hem_y = rows_with_mask.max()
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

def main():
    print("=" * 50)
    print(" STACKED SAREE ANALYZER - CPU ONLY ")
    print("=" * 50)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    list_input_dir()
    try:
        input_path = find_input_image()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"Using input image: {input_path}")
    image = cv2.imread(input_path)
    if image is None:
        print(f"ERROR: Could not read image file '{input_path}'.")
        sys.exit(1)
    print(f"Loaded image: {image.shape[1]}x{image.shape[0]}")
    pose = extract_pose(image)
    mask, contour = segment_saree(image)
    paths = extract_drape_paths(mask, pose, image.shape)
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
