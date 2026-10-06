from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from ..auth.decorators import role_required

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/')
@login_required
@role_required('teacher')
def dashboard():
    from ..models import ClassSession, Attendance, Course, Classroom, Section
    
    teacher_id = current_user.teacher_id
    sessions = ClassSession.query.filter_by(teacher_id=teacher_id).order_by(ClassSession.start_at.desc()).limit(10).all()
    active_session = ClassSession.query.filter_by(teacher_id=teacher_id, status='open').first()
    
    courses = Course.query.all()
    classrooms = Classroom.query.all()
    sections = Section.query.all()
    
    return render_template('teacher/dashboard.html', sessions=sessions, active_session=active_session, courses=courses, classrooms=classrooms, sections=sections)

@teacher_bp.route('/start_session', methods=['POST'])
@login_required
@role_required('teacher')
def start_session():
    from ..models import ClassSession, db
    classroom_id = request.form.get('classroom_id')
    course_id = request.form.get('course_id')
    section_id = request.form.get('section_id')
    
    # Close previous sessions
    open_sessions = ClassSession.query.filter_by(classroom_id=classroom_id, status='open').all()
    for s in open_sessions:
        s.status = 'finalized'
    db.session.commit()
    
    from ..services.timetable import create_quick_session
    create_quick_session(course_id, current_user.teacher_id, section_id, classroom_id)
    
    from flask import flash, redirect, url_for
    flash("Live class session started successfully!", "success")
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/stop_session/<int:session_id>', methods=['POST'])
@login_required
@role_required('teacher')
def stop_session(session_id):
    from ..models import ClassSession, db
    session = ClassSession.query.get_or_404(session_id)
    if session.teacher_id == current_user.teacher_id:
        session.status = 'finalized'
        db.session.commit()
        flash("Class session closed.", "success")
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/stop_session_by_classroom/<int:classroom_id>', methods=['POST'])
@login_required
@role_required('teacher')
def stop_session_by_classroom(classroom_id):
    from ..models import ClassSession, db
    # Find active session for this teacher in this classroom
    session = ClassSession.query.filter_by(teacher_id=current_user.teacher_id, classroom_id=classroom_id, status='open').first()
    if session:
        session.status = 'finalized'
        db.session.commit()
        flash("Class session closed successfully.", "success")
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/session/<int:session_id>')
@login_required
@role_required('teacher')
def view_session(session_id):
    from ..models import ClassSession, Attendance
    from flask import abort
    
    session = ClassSession.query.get_or_404(session_id)
    if session.teacher_id != current_user.teacher_id:
        abort(403)
        
    records = Attendance.query.filter_by(session_id=session.id).order_by(Attendance.marked_at.desc()).all()
    return render_template('teacher/session.html', session=session, records=records)

@teacher_bp.route('/session/<int:session_id>/export_csv')
@login_required
@role_required('teacher')
def export_session_csv(session_id):
    from ..models import ClassSession, Attendance
    import csv
    from flask import Response, abort
    from io import StringIO
    
    session = ClassSession.query.get_or_404(session_id)
    if session.teacher_id != current_user.teacher_id: abort(403)
        
    records = Attendance.query.filter_by(session_id=session.id).order_by(Attendance.marked_at.desc()).all()
    
    data = StringIO()
    writer = csv.writer(data)
    writer.writerow(('Time', 'Student Name', 'Roll No', 'Status', 'Method'))
    
    for r in records:
        writer.writerow((
            r.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.student.full_name,
            r.student.roll_no,
            r.status,
            r.method
        ))

    response = Response(data.getvalue(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename=f"attendance_{session.course.name.replace(' ', '_')}_{session.start_at.strftime('%Y%m%d')}.csv")
    return response

@teacher_bp.route('/session/<int:session_id>/export_pdf')
@login_required
@role_required('teacher')
def export_session_pdf(session_id):
    from ..models import ClassSession, Attendance
    from flask import Response, abort
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    session = ClassSession.query.get_or_404(session_id)
    if session.teacher_id != current_user.teacher_id: abort(403)
        
    records = Attendance.query.filter_by(session_id=session.id).order_by(Attendance.marked_at.desc()).all()
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"Attendance Report: {session.course.name}")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, 730, f"Section: {session.section.name} | Teacher: {current_user.username}")
    c.drawString(50, 710, f"Date: {session.start_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Headers
    y = 670
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Time")
    c.drawString(150, y, "Roll No")
    c.drawString(250, y, "Student Name")
    c.drawString(450, y, "Status")
    c.drawString(520, y, "Method")
    
    y -= 20
    c.setFont("Helvetica", 11)
    
    for r in records:
        if y < 50:
            c.showPage()
            y = 750
            c.setFont("Helvetica", 11)
            
        c.drawString(50, y, r.marked_at.strftime('%H:%M'))
        c.drawString(150, y, str(r.student.roll_no))
        c.drawString(250, y, str(r.student.full_name))
        c.drawString(450, y, str(r.status).capitalize())
        c.drawString(520, y, str(r.method).capitalize())
        y -= 20
        
    c.save()
    buffer.seek(0)
    
    response = Response(buffer.getvalue(), mimetype='application/pdf')
    response.headers.set("Content-Disposition", "attachment", filename=f"attendance_{session.course.name.replace(' ', '_')}_{session.start_at.strftime('%Y%m%d')}.pdf")
    return response

@teacher_bp.route('/generate_report', methods=['POST'])
@login_required
@role_required('teacher')
def generate_report():
    from ..models import ClassSession, Attendance
    import csv
    from flask import Response
    from io import StringIO, BytesIO
    from datetime import datetime
    
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    format_type = request.form.get('format', 'csv')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str + " 23:59:59", '%Y-%m-%d %H:%M:%S')
    except:
        flash("Invalid dates provided.", "error")
        return redirect(url_for('teacher.dashboard'))
        
    sessions = ClassSession.query.filter_by(teacher_id=current_user.teacher_id).filter(
        ClassSession.start_at >= start_date,
        ClassSession.start_at <= end_date
    ).all()
    
    session_ids = [s.id for s in sessions]
    if not session_ids:
        flash("No classes found in that date range.", "error")
        return redirect(url_for('teacher.dashboard'))
        
    records = Attendance.query.filter(Attendance.session_id.in_(session_ids)).order_by(Attendance.marked_at.desc()).all()
    
    if format_type == 'csv':
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(('Date/Time', 'Course', 'Student Name', 'Roll No', 'Status', 'Method'))
        for r in records:
            writer.writerow((
                r.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
                r.session.course.name if r.session else 'N/A',
                r.student.full_name,
                r.student.roll_no,
                r.status,
                r.method
            ))
        response = Response(data.getvalue(), mimetype='text/csv')
        response.headers.set("Content-Disposition", "attachment", filename=f"report_{start_date_str}_to_{end_date_str}.csv")
        return response
        
    elif format_type == 'pdf':
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, f"Custom Attendance Report")
        c.setFont("Helvetica", 12)
        c.drawString(50, 730, f"Teacher: {current_user.username}")
        c.drawString(50, 710, f"Period: {start_date_str} to {end_date_str}")
        
        y = 670
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Time")
        c.drawString(130, y, "Course")
        c.drawString(250, y, "Roll No")
        c.drawString(320, y, "Student")
        c.drawString(480, y, "Status")
        
        y -= 20
        c.setFont("Helvetica", 10)
        
        for r in records:
            if y < 50:
                c.showPage()
                y = 750
                c.setFont("Helvetica", 10)
            c.drawString(50, y, r.marked_at.strftime('%m/%d %H:%M'))
            c.drawString(130, y, str(r.session.course.name)[:15] if r.session else 'N/A')
            c.drawString(250, y, str(r.student.roll_no))
            c.drawString(320, y, str(r.student.full_name)[:20])
            c.drawString(480, y, str(r.status).capitalize())
            y -= 20
            
        c.save()
        buffer.seek(0)
        response = Response(buffer.getvalue(), mimetype='application/pdf')
        response.headers.set("Content-Disposition", "attachment", filename=f"report_{start_date_str}_to_{end_date_str}.pdf")
        return response
