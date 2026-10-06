"""SQLAlchemy models (plan Section 4). All timestamps are timestamptz in UTC."""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


TS = db.DateTime(timezone=True)


class Section(db.Model):
    __tablename__ = "sections"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    semester = db.Column(db.Integer)


class Teacher(db.Model):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(40), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(TS, default=utcnow, nullable=False)
    section = db.relationship("Section", backref="students")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id", ondelete="CASCADE"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(TS, default=utcnow, nullable=False)
    student = db.relationship("Student")
    teacher = db.relationship("Teacher")
    __table_args__ = (
        db.CheckConstraint("role IN ('admin','teacher','student')", name="ck_users_role"),
    )

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)


class Classroom(db.Model):
    __tablename__ = "classrooms"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    camera_type = db.Column(db.String(10), default="webcam", nullable=False)
    camera_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    __table_args__ = (
        db.CheckConstraint("camera_type IN ('ip','webcam')", name="ck_classroom_camtype"),
    )


class TimetableSlot(db.Model):
    __tablename__ = "timetable_slots"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey("classrooms.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    late_after_min = db.Column(db.Integer, nullable=False)
    absent_after_min = db.Column(db.Integer, nullable=False)
    course = db.relationship("Course")
    teacher = db.relationship("Teacher")
    section = db.relationship("Section")
    classroom = db.relationship("Classroom")
    __table_args__ = (
        db.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_slot_weekday"),
        db.CheckConstraint("end_time > start_time", name="ck_slot_times"),
        db.CheckConstraint("0 <= late_after_min AND late_after_min < absent_after_min",
                           name="ck_slot_rules"),
    )


class ClassSession(db.Model):
    __tablename__ = "class_sessions"
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("timetable_slots.id"))
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey("classrooms.id"), nullable=False)
    start_at = db.Column(TS, nullable=False)
    end_at = db.Column(TS, nullable=False)
    late_after_min = db.Column(db.Integer, nullable=False)
    absent_after_min = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), default="scheduled", nullable=False)
    finalized_at = db.Column(TS)
    slot = db.relationship("TimetableSlot")
    course = db.relationship("Course")
    teacher = db.relationship("Teacher")
    section = db.relationship("Section")
    classroom = db.relationship("Classroom")
    __table_args__ = (
        db.UniqueConstraint("slot_id", "start_at", name="uq_session_slot_start"),
        db.CheckConstraint("status IN ('scheduled','open','finalized')", name="ck_session_status"),
        db.CheckConstraint("0 <= late_after_min AND late_after_min < absent_after_min",
                           name="ck_session_rules"),
        db.Index("ix_sessions_classroom_start", "classroom_id", "start_at"),
    )


class FaceTemplate(db.Model):
    __tablename__ = "face_templates"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    embedding = db.Column(db.LargeBinary, nullable=False)  # 512 x float32 = 2048 bytes
    det_score = db.Column(db.Float)
    sharpness = db.Column(db.Float)
    source = db.Column(db.String(10), nullable=False)
    created_at = db.Column(TS, default=utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    student = db.relationship("Student", backref="face_templates")
    __table_args__ = (
        db.CheckConstraint("source IN ('webcam','upload')", name="ck_template_source"),
    )


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    status = db.Column(db.String(10), nullable=False)
    marked_at = db.Column(TS, nullable=False)
    method = db.Column(db.String(10), nullable=False)
    similarity = db.Column(db.Float)
    passive_score = db.Column(db.Float)
    marked_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.Text)
    session = db.relationship("ClassSession", backref="attendance")
    student = db.relationship("Student")
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
        db.CheckConstraint("status IN ('present','late','absent','excused')", name="ck_att_status"),
        db.CheckConstraint("method IN ('face','manual','auto')", name="ck_att_method"),
    )


ATTEMPT_OUTCOMES = (
    "success", "unknown", "ambiguous", "spoof_suspected", "active_liveness_failed",
    "reverify_failed", "no_session", "window_closed", "already_marked", "not_in_section",
    "low_quality", "timeout",
)


class RecognitionAttempt(db.Model):
    __tablename__ = "recognition_attempts"
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey("classrooms.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id", ondelete="SET NULL"))
    created_at = db.Column(TS, default=utcnow, nullable=False, index=True)
    outcome = db.Column(db.String(30), nullable=False)
    best_student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="SET NULL"))
    best_score = db.Column(db.Float)
    second_score = db.Column(db.Float)
    passive_score = db.Column(db.Float)
    snapshot_path = db.Column(db.String(255))
    __table_args__ = (
        db.CheckConstraint(
            "outcome IN (" + ",".join(f"'{o}'" for o in ATTEMPT_OUTCOMES) + ")",
            name="ck_attempt_outcome"),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    before_json = db.Column(db.Text)
    after_json = db.Column(db.Text)
    reason = db.Column(db.Text)
    created_at = db.Column(TS, default=utcnow, nullable=False)


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text)
