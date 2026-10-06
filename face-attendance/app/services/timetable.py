from datetime import timedelta
from ..models import db, ClassSession, TimetableSlot
from .clock import Clock

def create_quick_session(course_id, teacher_id, section_id, classroom_id, duration_min=30, late_min=2, absent_min=30):
    now = Clock.now()
    end_at = now + timedelta(minutes=duration_min)
    
    session = ClassSession(
        slot_id=None,
        course_id=course_id,
        teacher_id=teacher_id,
        section_id=section_id,
        classroom_id=classroom_id,
        start_at=now,
        end_at=end_at,
        late_after_min=late_min,
        absent_after_min=absent_min,
        status='open'
    )
    db.session.add(session)
    db.session.commit()
    return session
