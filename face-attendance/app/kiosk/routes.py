import cv2
import time
from flask import Blueprint, render_template, Response, jsonify, request, abort, current_app
from flask_login import current_user
from ..models import Classroom, db, RecognitionAttempt
from ..services.camera import get_camera_service
from ..services.face_pipeline import get_pipeline
from ..services.quality import evaluate_quality
from ..services.matching import get_gallery
from ..services.attendance import get_active_session, mark_attendance

kiosk_bp = Blueprint('kiosk', __name__, url_prefix='/kiosk')

# Simple in-memory state machine per classroom
# In a real app this would be more robust, but for demo it's fine.
_kiosk_states = {}

def get_kiosk_state(classroom_id):
    if classroom_id not in _kiosk_states:
        _kiosk_states[classroom_id] = {
            'state': 'IDLE',
            'prompt': 'Please look at the camera.',
            'student_name': None,
            'progress': 0,
            'countdown': 0,
            'result': None,
            'message': '',
            'last_active': time.time(),
            'denial_count': 0
        }
    return _kiosk_states[classroom_id]

@kiosk_bp.before_request
def require_kiosk_auth():
    if request.endpoint == 'kiosk.stream':
        return # Stream can be public if URL is known, or protect it
    # Check if logged in as admin/teacher OR has KIOSK_KEY
    if current_user.is_authenticated and current_user.role in ['admin', 'teacher']:
        return
    kiosk_key = current_app.config.get('KIOSK_KEY')
    if request.args.get('key') == kiosk_key and kiosk_key is not None:
        return
    abort(401)

@kiosk_bp.route('/<int:classroom_id>')
def index(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    return render_template('kiosk/index.html', classroom=classroom)

@kiosk_bp.route('/<int:classroom_id>/stream')
def stream(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    cam = get_camera_service(classroom_id, classroom.camera_url)
    
    def generate():
        while True:
            frame = cam.get_frame()
            if frame is not None:
                # We could draw boxes here based on state
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.05) # ~20 FPS limit
            
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@kiosk_bp.route('/<int:classroom_id>/state')
def get_state(classroom_id):
    state = get_kiosk_state(classroom_id)
    return jsonify(state)

# This route acts as the server-side processor for the state machine
# It will be polled by a background task, or we can just process on the stream frame?
# Actually, the plan says: "The kiosk page shows the camera feed proxied from Flask... and polls /api/kiosk/<classroom_id>/state every 300 ms for the state machine's current prompt/result."
# And "CameraService... FacePipeline... KioskController (per-classroom state machine)".
# Since we need a background thread to process frames for the state machine, I'll add it here.

import threading

def run_kiosk_controller(app, classroom_id):
    with app.app_context():
        classroom = Classroom.query.get(classroom_id)
        if not classroom: return
        cam = get_camera_service(classroom_id, classroom.camera_url)
        pipeline = get_pipeline()
        gallery = get_gallery()
        
        while True:
            state = get_kiosk_state(classroom_id)
            if state['state'] == 'IDLE':
                try:
                    frame = cam.get_frame()
                    if frame is not None:
                        faces = pipeline.process_frame(frame)
                        passed, face, msg = evaluate_quality(frame, faces, app.config)
                        if passed:
                            state['state'] = 'IDENTIFYING'
                            state['prompt'] = 'Identifying...'
                            
                            # In IDENTIFYING, we match the face
                            best_sid, best_score, second_score = gallery.match(face.embedding, app.config)
                            
                            if best_sid is None:
                                state['state'] = 'RESULT'
                                state['result'] = 'error'
                                state['message'] = 'Not recognized. Try again or ask your teacher.'
                                state['denial_count'] += 1
                                if state['denial_count'] >= 3:
                                    state['message'] += ' Need help? Ask your teacher to mark you manually.'
                                    
                                # Log attempt
                                att = RecognitionAttempt(classroom_id=classroom_id, outcome='unknown', best_score=best_score, second_score=second_score)
                                db.session.add(att)
                                db.session.commit()
                            else:
                                # Match found! Check session and section
                                session = get_active_session(classroom_id, app.config)
                                if not session:
                                    state['state'] = 'RESULT'
                                    state['result'] = 'error'
                                    state['message'] = 'No class in session right now.'
                                else:
                                    success, att_msg, status = mark_attendance(session.id, best_sid, 'face', similarity=best_score)
                                    if success:
                                        state['state'] = 'RESULT'
                                        state['result'] = 'success'
                                        from ..models import Student
                                        student = Student.query.get(best_sid)
                                        state['message'] = f'{status.capitalize()} - {student.full_name}'
                                        state['denial_count'] = 0
                                    else:
                                        state['state'] = 'RESULT'
                                        state['result'] = 'error'
                                        state['message'] = att_msg
                                        
                                # Log attempt
                                att = RecognitionAttempt(
                                    classroom_id=classroom_id, 
                                    session_id=session.id if session else None, 
                                    outcome='success' if state['result'] == 'success' else 'unknown', 
                                    best_student_id=best_sid, 
                                    best_score=best_score, 
                                    second_score=second_score
                                )
                                db.session.add(att)
                                db.session.commit()
                                
                            state['last_active'] = time.time()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    db.session.rollback()
                    state['state'] = 'RESULT'
                    state['result'] = 'error'
                    state['message'] = 'System Error: ' + str(e)
                    state['last_active'] = time.time()
                        
            elif state['state'] == 'RESULT':
                if time.time() - state['last_active'] > 3.0:
                    state['state'] = 'COOLDOWN'
                    state['last_active'] = time.time()
                    
            elif state['state'] == 'COOLDOWN':
                if time.time() - state['last_active'] > 4.0:
                    state['state'] = 'IDLE'
                    state['prompt'] = 'Please look at the camera.'
                    state['result'] = None
                    state['message'] = ''
                    
            time.sleep(0.3)

# Dictionary to keep track of running controller threads
_controllers = {}

@kiosk_bp.route('/<int:classroom_id>/start_controller')
def start_controller(classroom_id):
    if classroom_id not in _controllers:
        app = current_app._get_current_object()
        t = threading.Thread(target=run_kiosk_controller, args=(app, classroom_id), daemon=True)
        t.start()
        _controllers[classroom_id] = t
    return jsonify({'status': 'running'})
