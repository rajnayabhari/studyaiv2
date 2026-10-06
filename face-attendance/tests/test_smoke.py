import pytest
import datetime
import base64
import cv2
import numpy as np
from app import create_app
from app.extensions import db
from app.models import User, Student, Teacher, Classroom, Course, Section, ClassSession, RecognitionAttempt

@pytest.fixture
def app():
    app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "FACE_MODEL_PACK": "buffalo_s" # Faster for tests
    })

    with app.app_context():
        db.create_all()
        # Seed test users
        admin = User(username='admin', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        
        teacher = Teacher(full_name='Test Teacher', email='t@example.com')
        db.session.add(teacher)
        db.session.flush()
        
        t_user = User(username='teacher', role='teacher', teacher_id=teacher.id)
        t_user.set_password('teacher')
        db.session.add(t_user)
        
        section = Section(name='A', semester='1')
        db.session.add(section)
        course = Course(code='101', name='Test Course')
        db.session.add(course)
        room = Classroom(name='Room 1', camera_url='0')
        db.session.add(room)
        
        db.session.flush()
        
        student = Student(roll_no='S1', full_name='Test Student', section_id=section.id)
        db.session.add(student)
        db.session.flush()
        
        s_user = User(username='S1', role='student', student_id=student.id)
        s_user.set_password('student')
        db.session.add(s_user)
        
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def create_dummy_face_image_b64():
    # Create a dummy image (just a black square, face pipeline will return no faces)
    # This is a smoke test to check API structure, not the ML accuracy
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    ret, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

def test_smoke_end_to_end(client):
    # 1. Login Admin
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin'})
    
    # 2. Quick Session
    res = client.post('/admin/quick_session', data={'classroom_id': 1}, follow_redirects=True)
    assert res.status_code == 200
    
    # 3. Kiosk State
    res = client.get('/kiosk/1/state')
    assert res.status_code == 200
    state = res.get_json()
    assert state['state'] == 'IDLE'
    
    # 4. Enroll (will fail quality gate since dummy image has no face, but API shouldn't crash)
    b64 = create_dummy_face_image_b64()
    res = client.post('/api/enroll/1/capture', json={'image': b64})
    assert res.status_code == 200
    assert res.get_json()['success'] == False
    
    # 5. Teacher login
    client.get('/auth/logout')
    client.post('/auth/login', data={'username': 'teacher', 'password': 'teacher'})
    res = client.get('/teacher/')
    assert res.status_code == 200
    
    # 6. Student login
    client.get('/auth/logout')
    client.post('/auth/login', data={'username': 'S1', 'password': 'student'})
    res = client.get('/student/')
    assert res.status_code == 200
