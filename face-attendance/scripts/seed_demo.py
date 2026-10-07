import os
import sys
import datetime

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import User, Teacher, Student, Section, Course, Classroom, TimetableSlot, Setting

def seed_db():
    app = create_app()
    with app.app_context():
        # Clear existing non-admin users/data if needed? Better to just check if exists.
        
        # 1. Settings
        defaults = {
            'sim_enabled': 'false',
            'sim_anchor_real': '',
            'sim_anchor_sim': '',
            't_accept': '0.45',
            't_margin': '0.05',
            'passive_backend': 'minifasnet',
            'passive_threshold': '0.7',
            'passive_enforce': 'true',
            'challenge_timeout_s': '12',
            'early_window_min': '10',
            'default_late_min': '10',
            'default_absent_min': '30',
        }
        for k, v in defaults.items():
            if not Setting.query.get(k):
                db.session.add(Setting(key=k, value=v))
        
        # 2. Admin User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', role='admin')
            admin.set_password('admin')
            db.session.add(admin)

        # 3. Teacher
        teacher = Teacher.query.filter_by(email='teacher@example.com').first()
        if not teacher:
            teacher = Teacher(full_name='Demo Teacher', email='teacher@example.com')
            db.session.add(teacher)
            db.session.flush()
            t_user = User(username='teacher', role='teacher', teacher_id=teacher.id)
            t_user.set_password('teacher')
            db.session.add(t_user)

        # 4. Section, Course, Classroom
        section = Section.query.filter_by(name='BCA 8th A').first()
        if not section:
            section = Section(name='BCA 8th A', semester='8')
            db.session.add(section)

        course = Course.query.filter_by(code='CS801').first()
        if not course:
            course = Course(code='CS801', name='Face Recognition')
            db.session.add(course)

        classroom = Classroom.query.filter_by(name='Room 101').first()
        if not classroom:
            classroom = Classroom(name='Room 101', camera_type='webcam', camera_url='0')
            db.session.add(classroom)
            
        db.session.flush()

        # 5. Demo Students
        demo_students = [
            {'roll': 'BCA001', 'name': 'Demo Student 1', 'email': 'student1@example.com'},
            {'roll': 'BCA002', 'name': 'Demo Student 2', 'email': 'student2@example.com'},
            {'roll': 'BCA003', 'name': 'Demo Student 3', 'email': 'student3@example.com'}
        ]
        for ds in demo_students:
            s = Student.query.filter_by(roll_no=ds['roll']).first()
            if not s:
                s = Student(roll_no=ds['roll'], full_name=ds['name'], email=ds['email'], section_id=section.id)
                db.session.add(s)
                db.session.flush()
                # Create student user
                su = User(username=ds['roll'], role='student', student_id=s.id)
                su.set_password('student')
                db.session.add(su)
        
        # 6. Sample Timetable Slot (Today)
        now = datetime.datetime.now()
        weekday = now.weekday()
        slot = TimetableSlot.query.filter_by(weekday=weekday, course_id=course.id).first()
        if not slot:
            # Create a slot spanning from 2 hours ago to 2 hours from now
            start = (now - datetime.timedelta(hours=2)).time()
            end = (now + datetime.timedelta(hours=2)).time()
            slot = TimetableSlot(
                course_id=course.id,
                teacher_id=teacher.id,
                section_id=section.id,
                classroom_id=classroom.id,
                weekday=weekday,
                start_time=start,
                end_time=end,
                late_after_min=10,
                absent_after_min=30
            )
            db.session.add(slot)

        db.session.commit()
        print("Demo data seeded successfully.")

if __name__ == '__main__':
    seed_db()
