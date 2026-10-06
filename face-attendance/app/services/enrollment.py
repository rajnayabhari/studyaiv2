import cv2
import numpy as np
from ..models import FaceTemplate, Student, db
from .matching import get_gallery
from .face_pipeline import get_pipeline
from .quality import evaluate_quality
import base64

def process_enrollment_frame(student_id, img_bgr, config):
    pipeline = get_pipeline()
    faces = pipeline.process_frame(img_bgr)
    
    passed, face, msg = evaluate_quality(img_bgr, faces, config)
    if not passed:
        return False, msg, None
        
    gallery = get_gallery()
    best_sid, best_score, _ = gallery.match(face.embedding, config, enforce_margin=False)
    
    # Duplicate identity check
    if best_sid is not None and best_sid != student_id and best_score > 0.6:
        other = Student.query.get(best_sid)
        name = other.full_name if other else "Unknown"
        return False, f"Face matches another student ({name}) with high similarity.", None
        
    # Store
    t = FaceTemplate(
        student_id=student_id,
        embedding=face.embedding.tobytes(),
        det_score=float(face.det_score),
        sharpness=float(face.sharpness),
        source='webcam'
    )
    db.session.add(t)
    db.session.commit()
    
    # Refresh gallery
    gallery.refresh()
    
    return True, "Accepted", t.id

def decode_base64_image(b64_str):
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    img_data = base64.b64decode(b64_str)
    nparr = np.frombuffer(img_data, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img_bgr
