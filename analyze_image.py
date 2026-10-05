# analyze_image.py
import cv2
import json
import numpy as np
import os
import glob
import sys
import torch
from PIL import Image
from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
from ultralytics import YOLO
import mediapipe as mp

# --- CONFIGURATION ---
INPUT_DIR = "inputs/"
OUTPUT_DIR = "out_saree/"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "analysis.json")
OUTPUT_VIS = os.path.join(OUTPUT_DIR, "analysis_visualization.png")

# Model paths
YOLO_SEG_MODEL_PATH = "yolov8n-seg.pt" # Placeholder for a fashion-finetuned model
PARSING_MODEL_NAME = "mattmdjaga/segformer_b2_clothes" # We'll use this for parsing for now

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
        print("    [!] Warning: No pose detected.")
        return None
    h, w = image.shape[:2]
    landmarks = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks[mp_pose.PoseLandmark(idx).name] = {
            "x": lm.x * w, "y": lm.y * h, "visibility": lm.visibility
        }
    print(f"    Detected {len(landmarks)} landmarks")
    return landmarks

def segment_garments_with_yolo(image):
    """Uses a YOLO-seg model for precise garment segmentation."""
    print("[Component 2] Segmenting garments with YOLOv8-seg...")
    # In a real implementation, you'd load a model fine-tuned on a fashion dataset.
    # For this example, we use a general model.
    model = YOLO(YOLO_SEG_MODEL_PATH)
    results = model(image, device='cpu')
    
    garments = []
    if results and results[0].masks is not None:
        for i, mask in enumerate(results[0].masks.data):
            m = mask.cpu().numpy().astype(np.uint8) * 255
            garments.append({
                "class": results[0].names[i],
                "mask": m
            })
            print(f"    Found garment: {results[0].names[i]}")
            
    return garments

def parse_clothing_with_segformer(image):
    """Uses SegFormer for fine-grained clothing parsing."""
    print("[Component 3] Parsing clothing categories with SegFormer...")
    processor = SegformerImageProcessor.from_pretrained(PARSING_MODEL_NAME)
    model = SegformerForSemanticSegmentation.from_pretrained(PARSING_MODEL_NAME)
    model.eval()
    
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    upsampled_logits = torch.nn.functional.interpolate(
        outputs.logits, size=image.shape[:2], mode="bilinear", align_corners=False
    )
    pred_seg = upsampled_logits.argmax(dim=1)[0].numpy()
    
    # Extract masks for Blouse (4) and Saree/Dress (7)
    blouse_mask = (pred_seg == 4).astype(np.uint8) * 255
    saree_mask = (pred_seg == 7).astype(np.uint8) * 255
    
    # Clean up masks
    kernel = np.ones((7, 7), np.uint8)
    blouse_mask = cv2.morphologyEx(blouse_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    saree_mask = cv2.morphologyEx(saree_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    return {"blouse": blouse_mask, "saree": saree_mask}

def estimate_depth(image):
    """Estimates a depth map for fold detection."""
    print("[Component 4] Estimating depth for folds...")
    # Use a pre-trained depth estimation model (e.g., MiDaS) for CPU.
    # This is a placeholder for the actual implementation.
    # For now, we'll simulate a depth map.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    depth_map = cv2.GaussianBlur(gray, (21, 21), 0)
    return depth_map

def extract_universal_paths(image, masks, pose_landmarks, depth_map):
    """Extracts paths and folds using the new multi-model data."""
    print("[Component 5] Extracting paths and folds...")
    h, w = image.shape[:2]
    
    # Use the Saree mask from SegFormer
    saree_mask = masks["saree"]
    
    contours, _ = cv2.findContours(saree_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No saree region found.")
    
    rows_with_mask = np.where(np.any(saree_mask > 0, axis=1))[0]
    top_y = rows_with_mask.min()
    hem_y = rows_with_mask.max()
    
    left_path = []
    center_path = []
    
    # Use pose to guide the paths
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
            row = saree_mask[int(y), :]
            cols = np.where(row > 0)[0]
            if len(cols) > 0:
                left_path.append({"x": float(cols[0]), "y": float(y)})
                
        waist_y = max(top_y, (l_hip["y"] + r_hip["y"]) / 2)
        for y in np.linspace(waist_y, hem_y, 15):
            row = saree_mask[int(y), :]
            cols = np.where(row > 0)[0]
            if len(cols) > 0:
                closest_col = cols[np.argmin(np.abs(cols - center_x))]
                center_path.append({"x": float(closest_col), "y": float(y)})
    
    # --- FOLD DETECTION USING DEPTH ---
    # Find areas where the depth changes sharply within the saree mask
    # This is a simplified approach. Real implementation requires a proper depth model.
    depth_edges = cv2.Canny(depth_map, 30, 100)
    depth_edges_in_saree = cv2.bitwise_and(depth_edges, depth_edges, mask=saree_mask)
    fold_contours, _ = cv2.findContours(depth_edges_in_saree, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    valid_folds = [c for c in fold_contours if cv2.contourArea(c) > 30]
    
    def normalize(point):
        return {"x": point["x"] / w, "y": point["y"] / h}
        
    return {
        "image_shape": {"width": w, "height": h},
        "left_path": [normalize(p) for p in left_path],
        "center_path": [normalize(p) for p in center_path],
        "fold_count": len(valid_folds),
        "folds": [[normalize({"x": float(pt[0][0]), "y": float(pt[0][1])}) for pt in c] for c in valid_folds]
    }

def main():
    print("=" * 50)
    print(" ADVANCED OUTFIT ANALYZER - CPU ONLY ")
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
    
    # 1. Get the pose
    pose = extract_pose(image)
    
    # 2. Segment garments with YOLO (placeholder)
    # In a real pipeline, you'd merge the masks from YOLO and SegFormer.
    # For now, we'll rely on SegFormer for the final masks.
    garments_yolo = segment_garments_with_yolo(image)
    
    # 3. Parse clothing with SegFormer
    masks = parse_clothing_with_segformer(image)
    
    # 4. Estimate depth
    depth_map = estimate_depth(image)
    
    # 5. Extract paths and folds
    paths = extract_universal_paths(image, masks, pose, depth_map)
    
    # --- VISUALIZATION ---
    vis = image.copy()
    
    # Overlay Blouse (Yellow) and Saree (Green)
    blouse_overlay = np.zeros_like(image)
    blouse_overlay[masks["blouse"] > 0] = [0, 255, 255]
    saree_overlay = np.zeros_like(image)
    saree_overlay[masks["saree"] > 0] = [0, 255, 0]
    
    vis = cv2.addWeighted(vis, 1.0, blouse_overlay, 0.4, 0)
    vis = cv2.addWeighted(vis, 1.0, saree_overlay, 0.4, 0)
    
    # Draw Folds (Magenta)
    for fold in paths["folds"]:
        pts = np.array([[int(p["x"] * image.shape[1]), int(p["y"] * image.shape[0])] for p in fold], np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(vis, [pts], False, (255, 0, 255), 2)
        
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
