from flask import Blueprint, render_template
from flask_login import login_required
from ..auth.decorators import role_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/')
@login_required
@role_required('student')
def dashboard():
    from ..models import Attendance
    from flask_login import current_user
    
    student_id = current_user.student_id
    records = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.marked_at.desc()).limit(20).all()
    
    total = Attendance.query.filter_by(student_id=student_id).count()
    present = Attendance.query.filter_by(student_id=student_id, status='present').count()
    late = Attendance.query.filter_by(student_id=student_id, status='late').count()
    
    # Consider 'late' as half-present or just present. Let's say present + late count towards attendance rate
    rate = ((present + late) / total * 100) if total > 0 else 0
    
    return render_template('student/dashboard.html', records=records, total=total, rate=rate)
