from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..auth.decorators import role_required
from ..models import db, Student, Teacher, Classroom, Course, Section, TimetableSlot

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@role_required('admin')
def dashboard():
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from ..models import Section, Attendance
    
    students = Student.query.all()
    teachers = Teacher.query.all()
    classrooms = Classroom.query.all()
    sections = Section.query.all()
    
    total_students = len(students)
    total_sections = len(sections)
    
    # Overall present rate
    total_records = Attendance.query.count()
    present_records = Attendance.query.filter(Attendance.status.in_(['present', 'late'])).count()
    present_rate = (present_records / total_records * 100) if total_records > 0 else 0
    
    # Attach student count to sections
    for sec in sections:
        sec.student_count = Student.query.filter_by(section_id=sec.id).count()
    
    return render_template('admin/dashboard.html', 
                           students=students, teachers=teachers, classrooms=classrooms, 
                           sections=sections, total_students=total_students, 
                           total_sections=total_sections,
                           present_rate=round(present_rate, 1))

@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def manage_students():
    from ..models import Section, ClassSession, Attendance
    if request.method == 'POST':
        pass
    students = Student.query.all()
    sections = Section.query.all()
    
    # Pre-fetch total open/finalized sessions per section to avoid N+1 queries
    section_session_counts = {}
    for sec in sections:
        section_session_counts[sec.id] = ClassSession.query.filter_by(section_id=sec.id).filter(ClassSession.status.in_(['open', 'finalized'])).count()
        
    # Count templates and attendance for each student
    from ..models import FaceTemplate
    for s in students:
        s.template_count = FaceTemplate.query.filter_by(student_id=s.id).count()
        
        total_sessions = section_session_counts.get(s.section_id, 0)
        attended = Attendance.query.filter_by(student_id=s.id).filter(Attendance.status.in_(['present', 'late'])).count()
        
        # In case of data anomalies from testing (e.g. deleted sessions without cascading deletes), cap at 100%
        if total_sessions > 0:
            raw_percent = (attended / total_sessions) * 100
            s.attendance_percentage = min(raw_percent, 100.0)
        else:
            s.attendance_percentage = None
            
    return render_template('admin/students.html', students=students, sections=sections)

@admin_bp.route('/add_student', methods=['POST'])
@login_required
@role_required('admin')
def add_student():
    roll_no = request.form.get('roll_no')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    section_id = request.form.get('section_id')
    password = request.form.get('password')
    
    if roll_no and full_name and section_id:
        if Student.query.filter_by(roll_no=roll_no).first():
            flash('Roll number already exists!', 'error')
            return redirect(url_for('admin.manage_students'))
            
        from ..models import User
        if User.query.filter_by(username=roll_no).first():
            flash('A user with this roll number as username already exists!', 'error')
            return redirect(url_for('admin.manage_students'))
            
        student = Student(roll_no=roll_no, full_name=full_name, email=email, section_id=section_id)
        db.session.add(student)
        db.session.flush() # get student.id
        
        # Create User account using roll_no as username
        user = User(username=roll_no, role='student', student_id=student.id)
        user.set_password(password if password else 'password123')
        db.session.add(user)
        
        db.session.commit()
        flash('Student added and login credentials created (Username: Roll No).', 'success')
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_student(student_id):
    student = Student.query.get(student_id)
    if student:
        # Must delete FaceTemplates and Attendance first due to foreign keys
        from ..models import FaceTemplate, Attendance
        FaceTemplate.query.filter_by(student_id=student.id).delete()
        Attendance.query.filter_by(student_id=student.id).delete()
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        student.roll_no = request.form.get('roll_no')
        student.full_name = request.form.get('full_name')
        student.email = request.form.get('email')
        student.section_id = request.form.get('section_id')
        db.session.commit()
        flash('Student details updated successfully.', 'success')
        return redirect(url_for('admin.manage_students'))
        
    from ..models import Section, ClassSession, Attendance, Course
    sections = Section.query.all()
    
    course_stats = []
    courses = Course.query.all()
    for course in courses:
        total = ClassSession.query.filter_by(section_id=student.section_id, course_id=course.id).filter(ClassSession.status.in_(['open', 'finalized'])).count()
        if total > 0:
            attended = Attendance.query.join(ClassSession).filter(Attendance.student_id == student.id, ClassSession.course_id == course.id, Attendance.status.in_(['present', 'late'])).count()
            percent = min((attended / total) * 100, 100.0)
            course_stats.append({
                'course_name': course.name,
                'total': total,
                'attended': attended,
                'percentage': percent
            })
            
    return render_template('admin/edit_student.html', student=student, sections=sections, course_stats=course_stats)
@admin_bp.route('/attendance/export', methods=['GET'])
@login_required
@role_required('admin')
def export_attendance():
    from ..models import Attendance, Student, Section
    import csv
    from flask import Response
    from io import StringIO
    
    student_id = request.args.get('student_id')
    section_id = request.args.get('section_id')
    semester = request.args.get('semester')
    
    query = Attendance.query.join(Student)
    
    if student_id: query = query.filter(Attendance.student_id == student_id)
    if section_id: query = query.filter(Student.section_id == section_id)
    if semester: query = query.join(Section).filter(Section.semester == semester)
    
    records = query.order_by(Attendance.marked_at.desc()).all()
    
    data = StringIO()
    writer = csv.writer(data)
    writer.writerow(('Time', 'Student Name', 'Roll No', 'Status', 'Method', 'Confidence Score'))
    
    for r in records:
        writer.writerow((
            r.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.student.full_name if r.student else 'Unknown',
            r.student.roll_no if r.student else 'N/A',
            r.status,
            r.method,
            f"{r.similarity*100:.1f}%" if r.similarity else "N/A"
        ))

    response = Response(data.getvalue(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="attendance_report.csv")
    return response

@admin_bp.route('/students/<int:student_id>/clear_faces', methods=['POST'])
@login_required
@role_required('admin')
def clear_faces(student_id):
    from ..models import FaceTemplate
    FaceTemplate.query.filter_by(student_id=student_id).delete()
    db.session.commit()
    flash('Face data cleared for student.', 'success')
    return redirect(url_for('admin.manage_students'))



@admin_bp.route('/update_classroom', methods=['POST'])
@login_required
@role_required('admin')
def update_classroom():
    classroom_id = request.form.get('classroom_id')
    camera_url = request.form.get('camera_url')
    room = Classroom.query.get(classroom_id)
    if room:
        room.camera_url = camera_url
        db.session.commit()
        flash(f'Camera URL updated for {room.name}.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/add_classroom', methods=['POST'])
@login_required
@role_required('admin')
def add_classroom():
    name = request.form.get('name')
    camera_url = request.form.get('camera_url', '0')
    if name:
        room = Classroom(name=name, camera_url=camera_url)
        db.session.add(room)
        db.session.commit()
        flash('Classroom added.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/add_teacher', methods=['POST'])
@login_required
@role_required('admin')
def add_teacher():
    name = request.form.get('name')
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')
    
    if name and username and password:
        from ..models import User
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return redirect(url_for('admin.dashboard'))
            
        t = Teacher(full_name=name, email=email)
        db.session.add(t)
        db.session.flush() # get t.id
        
        user = User(username=username, role='teacher', teacher_id=t.id)
        user.set_password(password)
        db.session.add(user)
        
        db.session.commit()
        flash('Teacher added and login credentials created.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/add_section', methods=['POST'])
@login_required
@role_required('admin')
def add_section():
    name = request.form.get('name')
    semester = request.form.get('semester')
    if name:
        from ..models import Section
        sec = Section(name=name, semester=semester)
        db.session.add(sec)
        db.session.commit()
        flash('Section added.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/add_course', methods=['POST'])
@login_required
@role_required('admin')
def add_course():
    name = request.form.get('name')
    if name:
        from ..models import Course
        c = Course(name=name, code=name[:5].upper())
        db.session.add(c)
        db.session.commit()
        flash('Course added.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/attendance', methods=['GET'])
@login_required
@role_required('admin')
def view_attendance():
    from ..models import Attendance, Student, Section
    
    student_id = request.args.get('student_id')
    section_id = request.args.get('section_id')
    semester = request.args.get('semester')
    
    query = Attendance.query.join(Student)
    
    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if section_id:
        query = query.filter(Student.section_id == section_id)
    if semester:
        query = query.join(Section).filter(Section.semester == semester)
        
    records = query.order_by(Attendance.marked_at.desc()).limit(200).all()
    
    students = Student.query.order_by(Student.full_name).all()
    sections = Section.query.order_by(Section.name).all()
    semesters = db.session.query(Section.semester).distinct().all()
    
    return render_template('admin/attendance.html', records=records, students=students, sections=sections, semesters=[s[0] for s in semesters])

@admin_bp.route('/teachers', methods=['GET'])
@login_required
@role_required('admin')
def manage_teachers():
    teachers = Teacher.query.all()
    return render_template('admin/teachers.html', teachers=teachers)

@admin_bp.route('/edit_teacher/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if request.method == 'POST':
        teacher.full_name = request.form.get('full_name')
        teacher.email = request.form.get('email')
        
        password = request.form.get('password')
        if password and teacher.user:
            teacher.user.set_password(password)
            
        db.session.commit()
        flash('Teacher details updated successfully.', 'success')
        return redirect(url_for('admin.manage_teachers'))
        
    return render_template('admin/edit_teacher.html', teacher=teacher)

@admin_bp.route('/delete_teacher/<int:teacher_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    from ..models import ClassSession, Attendance
    
    sessions = ClassSession.query.filter_by(teacher_id=teacher.id).all()
    for s in sessions:
        Attendance.query.filter_by(session_id=s.id).delete()
    ClassSession.query.filter_by(teacher_id=teacher.id).delete()
    
    if teacher.user:
        db.session.delete(teacher.user)
        
    db.session.delete(teacher)
    db.session.commit()
    flash('Teacher deleted.', 'success')
    return redirect(url_for('admin.manage_teachers'))
