"""Seed demo data (idempotent): 1 admin, 1 teacher, 1 section, 1 course,
1 classroom, demo students, and one sample timetable slot.
Usage: python scripts/seed_demo.py
Default passwords: admin/admin123, teacher/teacher123, students = their roll number.
"""
import os
import sys
from datetime import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (Classroom, Course, Section, Student, Teacher,  # noqa: E402
                        TimetableSlot, User)

STUDENTS = [
    ("BCA001", "Aarav Sharma"), ("BCA002", "Sita Karki"), ("BCA003", "Bikash Thapa"),
    ("BCA004", "Anjali Gurung"), ("BCA005", "Rohan Shrestha"),
]


def get_or_create(model, defaults=None, **kw):
    obj = db.session.execute(db.select(model).filter_by(**kw)).scalar_one_or_none()
    if obj:
        return obj, False
    obj = model(**kw, **(defaults or {}))
    db.session.add(obj)
    db.session.flush()
    return obj, True


def ensure_user(username, password, role, **links):
    u = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
    if u is None:
        u = User(username=username, role=role, **links)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
    return u


def main():
    app = create_app()
    with app.app_context():
        cfg = app.config
        ensure_user("admin", "admin123", "admin")

        teacher, _ = get_or_create(Teacher, full_name="Ram Prasad Adhikari",
                                   defaults={"email": "teacher@example.com"})
        ensure_user("teacher", "teacher123", "teacher", teacher_id=teacher.id)

        section, _ = get_or_create(Section, name="BCA 8th A", defaults={"semester": 8})
        course, _ = get_or_create(Course, code="CACS401", defaults={"name": "Project Work"})
        classroom, _ = get_or_create(Classroom, name="Room 101",
                                     defaults={"camera_type": "webcam", "camera_url": "0"})

        for roll, name in STUDENTS:
            s, _ = get_or_create(Student, roll_no=roll,
                                 defaults={"full_name": name, "section_id": section.id,
                                           "email": f"{roll.lower()}@example.com"})
            u = ensure_user(roll, roll, "student", student_id=s.id)
            u.must_change_password = True

        get_or_create(TimetableSlot, course_id=course.id, section_id=section.id,
                      classroom_id=classroom.id, weekday=0,
                      defaults={"teacher_id": teacher.id, "start_time": time(10, 0),
                                "end_time": time(11, 0),
                                "late_after_min": cfg["DEFAULT_LATE_MIN"],
                                "absent_after_min": cfg["DEFAULT_ABSENT_MIN"]})
        db.session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    main()
