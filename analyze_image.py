# analyze_image.py
import cv2
import json
import numpy as np
import os
import glob
import sys
import mediapipe as mp
import torch
from PIL import Image
from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

# --- CONFIGURATION ---
INPUT_DIR = "inputs/"
OUTPUT_DIR = "out_saree/"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "analysis.json")
OUTPUT_VIS = os.path.join(OUTPUT_DIR, "analysis_visualization.png")
MODEL_NAME = "mattmdjaga/segformer_b2_clothes"

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
        return None
    h, w = image.shape[:2]
    landmarks = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks[mp_pose.PoseLandmark(idx).name] = {
            "x": lm.x * w, "y": lm.y * h, "visibility": lm.visibility
        }
    return landmarks

def segment_clothing(image):
    print("[Component 2] Segmenting clothing and skin with SegFormer...")
    processor = SegformerImageProcessor.from_pretrained(MODEL_NAME)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL_NAME)
    model.eval()
    
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    upsampled_logits = torch.nn.functional.interpolate(
        outputs.logits, size=image.shape[:2], mode="bilinear", align_corners=False
    )
    pred_seg = upsampled_logits.argmax(dim=1)[0].numpy()
    
    garment_mask = np.isin(pred_seg, [4, 5, 6, 7, 8]).astype(np.uint8) * 255
    blouse_mask = (pred_seg == 4).astype(np.uint8) * 255
    skin_mask = np.isin(pred_seg, [11, 12, 13, 14, 15]).astype(np.uint8) * 255
    
    clean_garment = cv2.bitwise_and(garment_mask, cv2.bitwise_not(skin_mask))
    kernel = np.ones((9, 9), np.uint8)
    clean_garment = cv2.morphologyEx(clean_garment, cv2.MORPH_CLOSE, kernel, iterations=4)
    clean_garment = cv2.morphologyEx(clean_garment, cv2.MORPH_OPEN, kernel, iterations=2)
    blouse_mask = cv2.morphologyEx(blouse_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    return {"garment": clean_garment, "blouse": blouse_mask, "skin": skin_mask}

def remove_hands_from_mask(garment_mask, pose_landmarks):
    """Explicitly removes hands by drawing circles around the wrists."""
    if not pose_landmarks:
        return garment_mask
    print("    [Hand Removal] Subtracting hands based on wrist coordinates...")
    hand_mask = np.zeros_like(garment_mask)
    for joint_name in ["LEFT_WRIST", "RIGHT_WRIST"]:
        joint = pose_landmarks.get(joint_name)
        if joint and joint["visibility"] > 0.2:
            cx, cy = int(joint["x"]), int(joint["y"])
            # Draw a large circle (80px radius) around each hand
            cv2.circle(hand_mask, (cx, cy), 80, 255, -1)
            
    clean_garment = cv2.bitwise_and(garment_mask, cv2.bitwise_not(hand_mask))
    return clean_garment

def extract_folds_with_hough(garment_mask, image):
    """Finds long vertical folds using Hough Line Transform."""
    print("    [Fold Detection] Finding vertical folds with Hough Transform...")
    kernel = np.ones((15, 15), np.uint8)
    inner_mask = cv2.erode(garment_mask, kernel, iterations=1)
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    edges = cv2.Canny(enhanced, 30, 100)
    edges_in_garment = cv2.bitwise_and(edges, edges, mask=inner_mask)
    
    lines = cv2.HoughLinesP(
        edges_in_garment, rho=1, theta=np.pi/180, threshold=30,
        minLineLength=50, maxLineGap=15
    )
    
    valid_folds = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if 60 < abs(angle) < 120: # Keep only mostly vertical lines
                valid_folds.append({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})
    
    print(f"    [Fold Detection] Found {len(valid_folds)} vertical folds.")
    return valid_folds

def extract_universal_paths(image, garment_mask, pose_landmarks, image_shape):
    print("[Component 3] Extracting drape paths dynamically...")
    h, w = image_shape[:2]
    
    rows_with_mask = np.where(np.any(garment_mask > 0, axis=1))[0]
    top_y = rows_with_mask.min()
    hem_y = rows_with_mask.max()
    
    left_path = []
    center_path = []
    
    if pose_landmarks:
        l_shoulder = pose_landmarks["LEFT_SHOULDER"]
        r_shoulder = pose_landmarks["RIGHT_SHOULDER"]
        l_hip = pose_landmarks["LEFT_HIP"]
        r_hip = pose_landmarks["RIGHT_HIP"]
        
        if l_shoulder["x"] < r_shoulder["x"]:
            left_shoulder = l_shoulder
        else:
            left_shoulder = r_shoulder
            
        start_y = max(top_y, left_shoulder["y"] + 20)
        center_x = (l_hip["x"] + r_hip["x"]) / 2
        
        for y in np.linspace(start_y, hem_y, 20):
            row = garment_mask[int(y), :]
            cols = np.where(row > 0)[0]
            if len(cols) > 0:
                left_path.append({"x": float(cols[0]), "y": float(y)})
                
        waist_y = max(top_y, (l_hip["y"] + r_hip["y"]) / 2)
        for y in np.linspace(waist_y, hem_y, 15):
            row = garment_mask[int(y), :]
            cols = np.where(row > 0)[0]
            if len(cols) > 0:
                closest_col = cols[np.argmin(np.abs(cols - center_x))]
                center_path.append({"x": float(closest_col), "y": float(y)})
    else:
        for y in np.linspace(top_y, hem_y, 20):
            row = garment_mask[int(y), :]
            cols = np.where(row > 0)[0]
            if len(cols) > 0:
                left_path.append({"x": float(cols[0]), "y": float(y)})
                center_path.append({"x": float((cols[0] + cols[-1]) / 2), "y": float(y)})

    valid_folds = extract_folds_with_hough(garment_mask, image)
    
    def normalize(point):
        return {"x": point["x"] / w, "y": point["y"] / h}
        
    return {
        "image_shape": {"width": w, "height": h},
        "left_path": [normalize(p) for p in left_path],
        "center_path": [normalize(p) for p in center_path],
        "fold_count": len(valid_folds),
        "folds": [{"x1": f["x1"]/w, "y1": f["y1"]/h, "x2": f["x2"]/w, "y2": f["y2"]/h} for f in valid_folds]
    }

def main():
    print("=" * 50)
    print(" UNIVERSAL OUTFIT ANALYZER - CPU ONLY ")
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
    masks = segment_clothing(image)
    
    # Explicitly remove hands from the garment mask using pose data
    masks["garment"] = remove_hands_from_mask(masks["garment"], pose)
    
    paths = extract_universal_paths(image, masks["garment"], pose, image.shape)
    
    # --- VISUALIZATION ---
    vis = image.copy()
    
    blouse_overlay = np.zeros_like(image)
    blouse_overlay[masks["blouse"] > 0] = [0, 255, 255] # Yellow
    garment_overlay = np.zeros_like(image)
    garment_overlay[masks["garment"] > 0] = [0, 255, 0] # Green
    
    vis = cv2.addWeighted(vis, 1.0, blouse_overlay, 0.4, 0)
    vis = cv2.addWeighted(vis, 1.0, garment_overlay, 0.4, 0)
    
    # Draw Folds (Cyan lines)
    for f in paths["folds"]:
        x1 = int(f["x1"] * image.shape[1]); y1 = int(f["y1"] * image.shape[0])
        x2 = int(f["x2"] * image.shape[1]); y2 = int(f["y2"] * image.shape[0])
        cv2.line(vis, (x1, y1), (x2, y2), (255, 255, 0), 3)
        
    # Draw Paths
    for p in paths["left_path"]:
        cv2.circle(vis, (int(p["x"] * image.shape[1]), int(p["y"] * image.shape[0])), 6, (0, 0, 255), -1)
    for p in paths["center_path"]:
        cv2.circle(vis, (int(p["x"] * image.shape[1]), int(p["y"] * image.shape[0])), 6, (255, 0, 0), -1)
        
    cv2.imwrite(OUTPUT_VIS, vis)
    print(f"Saved visualization to {OUTPUT_VIS}")
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(paths, f, indent=2)
    print(f"Saved analysis to {OUTPUT_JSON}")
    print("=" * 50)

if __name__ == "__main__":
    main()
