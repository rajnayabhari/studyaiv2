from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..auth.decorators import role_required
from ..models import db, Student, Teacher, Classroom, Course, Section, TimetableSlot

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@role_required('admin')
def dashboard():
    students = Student.query.all()
    teachers = Teacher.query.all()
    classrooms = Classroom.query.all()
    from ..models import Section
    sections = Section.query.all()
    return render_template('admin/dashboard.html', students=students, teachers=teachers, classrooms=classrooms, sections=sections)

@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def manage_students():
    if request.method == 'POST':
        pass
    students = Student.query.all()
    from ..models import Section
    sections = Section.query.all()
    # Count templates for each student
    from ..models import FaceTemplate
    for s in students:
        s.template_count = FaceTemplate.query.filter_by(student_id=s.id).count()
    return render_template('admin/students.html', students=students, sections=sections)

@admin_bp.route('/add_student', methods=['POST'])
@login_required
@role_required('admin')
def add_student():
    roll_no = request.form.get('roll_no')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    section_id = request.form.get('section_id')
    
    if roll_no and full_name and section_id:
        # Check if roll no exists
        if Student.query.filter_by(roll_no=roll_no).first():
            flash('Roll number already exists!', 'error')
            return redirect(url_for('admin.manage_students'))
            
        student = Student(roll_no=roll_no, full_name=full_name, email=email, section_id=section_id)
        db.session.add(student)
        db.session.commit()
        flash('Student added successfully.', 'success')
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
        
    from ..models import Section
    sections = Section.query.all()
    return render_template('admin/edit_student.html', student=student, sections=sections)

@admin_bp.route('/students/<int:student_id>/clear_faces', methods=['POST'])
@login_required
@role_required('admin')
def clear_faces(student_id):
    from ..models import FaceTemplate
    FaceTemplate.query.filter_by(student_id=student_id).delete()
    db.session.commit()
    flash('Face data cleared for student.', 'success')
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/quick_session', methods=['POST'])
@login_required
@role_required('admin')
def quick_session():
    classroom_id = request.form.get('classroom_id')
    course = Course.query.first()
    teacher = Teacher.query.first()
    section = Section.query.first()
    
    # Close any existing open sessions in this classroom so they don't overlap
    from ..models import ClassSession
    open_sessions = ClassSession.query.filter_by(classroom_id=classroom_id).filter(ClassSession.status.in_(['scheduled', 'open'])).all()
    for s in open_sessions:
        s.status = 'finalized'
    db.session.commit()
    
    from ..services.timetable import create_quick_session
    session = create_quick_session(course.id, teacher.id, section.id, classroom_id)
    
    flash(f"Quick session started for {course.name} in Classroom ID {classroom_id}", "info")
    return redirect(url_for('admin.dashboard'))

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
    if name:
        t = Teacher(full_name=name, email=email)
        db.session.add(t)
        db.session.commit()
        flash('Teacher added.', 'success')
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

@admin_bp.route('/attendance', methods=['GET'])
@login_required
@role_required('admin')
def view_attendance():
    from ..models import Attendance
    records = Attendance.query.order_by(Attendance.marked_at.desc()).limit(100).all()
    return render_template('admin/attendance.html', records=records)
