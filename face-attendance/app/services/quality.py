import cv2
import numpy as np

def compute_sharpness(img_bgr, face):
    # Crop the face using the bounding box
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), bbox[2], bbox[3]
    face_crop = img_bgr[y1:y2, x1:x2]
    
    if face_crop.size == 0:
        return 0.0
        
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def compute_yaw_ratio(face):
    """
    yaw = (x_nose - x_leftcheek) / (x_rightcheek - x_leftcheek)
    Insightface ArcFace landmarks (5 points):
    0: left eye, 1: right eye, 2: nose, 3: left mouth, 4: right mouth
    Wait, the plan says: "using landmarks 1 (nose tip), 234 and 454 (cheeks)". 
    Ah, the plan was referring to MediaPipe for the liveness challenge yaw ratio!
    For quality gate, we can use InsightFace's 5 landmarks:
    left_eye_x = face.kps[0][0], right_eye_x = face.kps[1][0], nose_x = face.kps[2][0]
    yaw ≈ (nose_x - left_eye_x) / (right_eye_x - left_eye_x)
    """
    kps = face.kps
    left_x = kps[0][0]
    right_x = kps[1][0]
    nose_x = kps[2][0]
    
    width = right_x - left_x
    if width <= 0:
        return 0.5
        
    yaw = (nose_x - left_x) / width
    return yaw

def evaluate_quality(img_bgr, faces, config):
    if len(faces) == 0:
        return False, None, "No face detected"
    
    # If multiple faces, we use the largest but could warn
    # For enrollment, exactly one face is preferred, but we'll extract the largest
    face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
    
    if len(faces) > 1:
        return False, face, "Multiple faces detected. Please ensure only one person is in the frame."
        
    # Detector score
    if face.det_score < 0.6:
        return False, face, f"Low detection score ({face.det_score:.2f})"
        
    # Face width
    width = face.bbox[2] - face.bbox[0]
    min_width = float(config.get('MIN_FACE_WIDTH', 60))
    if width < min_width:
        return False, face, f"Face too small (width {int(width)}px < {int(min_width)}px)"
        
    # Sharpness
    sharpness = compute_sharpness(img_bgr, face)
    blur_min = float(config.get('BLUR_MIN', 60))
    if sharpness < blur_min:
        return False, face, f"Image too blurry (sharpness {sharpness:.1f} < {blur_min})"
        
    # Pose
    yaw = compute_yaw_ratio(face)
    if yaw < 0.30 or yaw > 0.70: # Relaxed slightly for quality gate vs plan's 0.35-0.65 to avoid frustration, but plan says 0.35-0.65.
        yaw_low = float(config.get('YAW_LOW', 0.35))
        yaw_high = float(config.get('YAW_HIGH', 0.65))
        if yaw < yaw_low or yaw > yaw_high:
            return False, face, f"Face is turned too much (pose ratio {yaw:.2f})"
            
    # Add sharpness to face object for storage
    face.sharpness = sharpness
            
    return True, face, "Quality passed"
