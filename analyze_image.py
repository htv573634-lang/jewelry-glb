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
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(INPUT_DIR, p)))
    if not files:
        raise FileNotFoundError(f"No image file found in '{INPUT_DIR}'.")
    files.sort()
    return files[0]

def extract_pose(image):
    print("[Component 1] Extracting body pose with MediaPipe...")
    mp_pose = mp.solutions.pose
    with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    if not results.pose_landmarks:
        raise ValueError("No pose detected. Try a clearer photo with a full body visible.")
    h, w = image.shape[:2]
    landmarks = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks[mp_pose.PoseLandmark(idx).name] = {
            "x": lm.x * w, "y": lm.y * h, "visibility": lm.visibility
        }
    print(f"    Detected {len(landmarks)} landmarks")
    return landmarks

def segment_saree(image):
    print("[Component 2] Segmenting saree with AI Selfie Segmentation...")
    h, w = image.shape[:2]
    
    # 1. Person Mask (AI-based)
    mp_selfie = mp.solutions.selfie_segmentation
    with mp_selfie.SelfieSegmentation(model_selection=1) as selfie:
        results = selfie.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    person_mask = (results.segmentation_mask > 0.5).astype(np.uint8) * 255
    
    # 2. Skin Mask (HSV-based)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 20, 70], dtype=np.uint8)
    upper_skin = np.array([20, 255, 255], dtype=np.uint8)
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    
    # 3. Clothes = Person AND NOT Skin
    clothes_mask = cv2.bitwise_and(person_mask, cv2.bitwise_not(skin_mask))
    
    # 4. Morphological cleanup
    kernel = np.ones((15, 15), np.uint8)
    clothes_mask = cv2.morphologyEx(clothes_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    clothes_mask = cv2.morphologyEx(clothes_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # 5. Find the largest connected component (the saree)
    contours, _ = cv2.findContours(clothes_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No clothing region found.")
    largest = max(contours, key=cv2.contourArea)
    clean_mask = np.zeros_like(clothes_mask)
    cv2.drawContours(clean_mask, [largest], -1, 255, -1)
    
    print(f"    Saree occupies {np.sum(clean_mask > 0) / clean_mask.size * 100:.1f}% of image")
    return clean_mask, largest

def extract_drape_paths(mask, pose_landmarks, image_shape):
    print("[Component 3] Extracting drape paths from silhouette...")
    h, w = image_shape[:2]
    l_shoulder = pose_landmarks["LEFT_SHOULDER"]
    l_hip = pose_landmarks["LEFT_HIP"]
    r_hip = pose_landmarks["RIGHT_HIP"]
    
    rows_with_mask = np.where(np.any(mask > 0, axis=1))[0]
    if len(rows_with_mask) == 0:
        raise ValueError("Empty mask.")
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
        
    return {
        "image_shape": {"width": w, "height": h},
        "pose": pose_landmarks,
        "pallu_path": [normalize(p) for p in pallu_path],
        "pleat_path": [normalize(p) for p in pleat_path],
        "shoulder_left": normalize(l_shoulder),
        "shoulder_right": normalize(pose_landmarks["RIGHT_SHOULDER"]),
        "hip_left": normalize(l_hip),
        "hip_right": normalize(r_hip)
    }

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
