import sys
import os
import cv2
import numpy as np

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.face_pipeline import get_pipeline
from app.services.quality import evaluate_quality

def main(img1_path, img2_path):
    print(f"Loading InsightFace models...")
    pipeline = get_pipeline()
    
    config = {'MIN_FACE_WIDTH': 20, 'BLUR_MIN': 10, 'YAW_LOW': 0.1, 'YAW_HIGH': 0.9} # Relaxed for testing
    
    img1 = cv2.imread(img1_path)
    if img1 is None:
        print(f"Failed to read {img1_path}")
        return
        
    img2 = cv2.imread(img2_path)
    if img2 is None:
        print(f"Failed to read {img2_path}")
        return
        
    print(f"Processing {img1_path}...")
    faces1 = pipeline.process_frame(img1)
    passed, face1, msg = evaluate_quality(img1, faces1, config)
    if not passed:
        print(f"Quality gate failed for img1: {msg}")
        return
        
    print(f"Processing {img2_path}...")
    faces2 = pipeline.process_frame(img2)
    passed, face2, msg = evaluate_quality(img2, faces2, config)
    if not passed:
        print(f"Quality gate failed for img2: {msg}")
        return
        
    emb1 = face1.embedding
    emb2 = face2.embedding
    
    # Cosine similarity
    similarity = np.dot(emb1, emb2)
    print(f"Cosine Similarity: {similarity:.4f}")
    
    if similarity >= 0.45:
        print("Verdict: MATCH (Same Person)")
    else:
        print("Verdict: NO MATCH (Different People)")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python similarity.py <img1_path> <img2_path>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
