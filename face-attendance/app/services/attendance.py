from datetime import timedelta
from ..models import db, ClassSession, Attendance, AuditLog, Student
from .clock import Clock

def get_active_session(classroom_id, config):
    now = Clock.now()
    early_window = int(config.get('EARLY_WINDOW_MIN', 10))
    
    # Session must be open or scheduled, and within the time window
    sessions = ClassSession.query.filter_by(classroom_id=classroom_id).filter(
        ClassSession.status.in_(['scheduled', 'open'])
    ).order_by(ClassSession.start_at.desc()).all()
    
    for session in sessions:
        window_start = session.start_at - timedelta(minutes=early_window)
        # Assuming we can still mark late within absent window, but after end_at maybe the class is over?
        # Let's say checkin is allowed up to absent_after_min
        window_end = session.start_at + timedelta(minutes=session.absent_after_min)
        
        if window_start <= now <= window_end:
            if session.status == 'scheduled':
                session.status = 'open'
                db.session.commit()
            return session
            
    return None

def determine_status(session, now):
    t_minutes = (now - session.start_at).total_seconds() / 60.0
    
    if t_minutes <= session.late_after_min:
        return 'present'
    elif session.late_after_min < t_minutes <= session.absent_after_min:
        return 'late'
    else:
        return 'absent' # Or window_closed

def mark_attendance(session_id, student_id, method, similarity=None, passive_score=None, by_user_id=None, note=None):
    session = ClassSession.query.get(session_id)
    student = Student.query.get(student_id)
    
    if not session or not student:
        return False, "Invalid session or student", None
        
    if student.section_id != session.section_id:
        return False, "not_in_section", None
        
    existing = Attendance.query.filter_by(session_id=session_id, student_id=student_id).first()
    if existing:
        return False, "already_marked", None
        
    now = Clock.now()
    status = determine_status(session, now)
    if status == 'absent' and method == 'face':
        return False, "window_closed", None
        
    att = Attendance(
        session_id=session_id,
        student_id=student_id,
        status=status,
        method=method,
        marked_at=now,
        similarity=similarity,
        passive_score=passive_score,
        marked_by_user_id=by_user_id,
        note=note
    )
    db.session.add(att)
    db.session.commit()
    return True, "Marked successfully", status
