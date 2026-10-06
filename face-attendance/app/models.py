from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

def now_utc():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin|teacher|student
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(64), unique=True, nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    
    section = db.relationship('Section', backref='students')
    user = db.relationship('User', backref='student', uselist=False)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120))
    
    user = db.relationship('User', backref='teacher', uselist=False)

class Section(db.Model):
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False) # e.g. "BCA 8th A"
    semester = db.Column(db.String(32))

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)

class Classroom(db.Model):
    __tablename__ = 'classrooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    camera_type = db.Column(db.String(20), default='ip') # ip|webcam
    camera_url = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=True)

class TimetableSlot(db.Model):
    __tablename__ = 'timetable_slots'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    weekday = db.Column(db.Integer, nullable=False) # 0-6
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    late_after_min = db.Column(db.Integer, default=10)
    absent_after_min = db.Column(db.Integer, default=30)
    
    course = db.relationship('Course')
    teacher = db.relationship('Teacher')
    section = db.relationship('Section')
    classroom = db.relationship('Classroom')

class ClassSession(db.Model):
    __tablename__ = 'class_sessions'
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('timetable_slots.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    end_at = db.Column(db.DateTime(timezone=True), nullable=False)
    late_after_min = db.Column(db.Integer, nullable=False)
    absent_after_min = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='scheduled') # scheduled|open|finalized
    finalized_at = db.Column(db.DateTime(timezone=True))
    
    __table_args__ = (db.UniqueConstraint('slot_id', 'start_at', name='uq_slot_start'),
                      db.Index('idx_sessions_classroom_start', 'classroom_id', 'start_at'))

    course = db.relationship('Course')
    teacher = db.relationship('Teacher')
    section = db.relationship('Section')
    classroom = db.relationship('Classroom')

class FaceTemplate(db.Model):
    __tablename__ = 'face_templates'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    embedding = db.Column(db.LargeBinary, nullable=False) # BYTEA 2048 bytes
    det_score = db.Column(db.Float)
    sharpness = db.Column(db.Float)
    source = db.Column(db.String(32)) # webcam|upload
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    is_active = db.Column(db.Boolean, default=True)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False) # present|late|absent|excused
    marked_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    method = db.Column(db.String(20), nullable=False) # face|manual|auto
    similarity = db.Column(db.Float)
    passive_score = db.Column(db.Float)
    marked_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    note = db.Column(db.String(256))
    
    __table_args__ = (db.UniqueConstraint('session_id', 'student_id', name='uq_session_student'),
                      db.Index('idx_attendance_session', 'session_id'),
                      db.Index('idx_attendance_student', 'student_id'))

    student = db.relationship('Student')
    session = db.relationship('ClassSession')

class RecognitionAttempt(db.Model):
    __tablename__ = 'recognition_attempts'
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    outcome = db.Column(db.String(64)) # success|unknown|ambiguous|spoof_suspected|...
    best_student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    best_score = db.Column(db.Float)
    second_score = db.Column(db.Float)
    passive_score = db.Column(db.Float)
    snapshot_path = db.Column(db.String(256))
    
    __table_args__ = (db.Index('idx_attempts_created_at', 'created_at'),)

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(64), nullable=False)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    before_json = db.Column(db.Text)
    after_json = db.Column(db.Text)
    reason = db.Column(db.String(256))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text)
