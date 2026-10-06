from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import User, Student, Teacher, Section, Course, Classroom, TimetableSlot
from ..auth import role_required

bp = Blueprint("admin", __name__)

@bp.before_request
@role_required('admin')
def before_request():
    pass

@bp.route("/")
def index():
    return render_template("admin/dashboard.html", 
        student_count=db.session.query(Student).count(),
        teacher_count=db.session.query(Teacher).count(),
        classroom_count=db.session.query(Classroom).count()
    )

@bp.route("/classrooms", methods=["GET", "POST"])
def classrooms():
    if request.method == "POST":
        name = request.form.get("name")
        camera_type = request.form.get("camera_type")
        camera_url = request.form.get("camera_url")
        c = Classroom(name=name, camera_type=camera_type, camera_url=camera_url)
        db.session.add(c)
        db.session.commit()
        flash("Classroom added.", "success")
        return redirect(url_for("admin.classrooms"))
    items = db.session.execute(db.select(Classroom)).scalars().all()
    return render_template("admin/crud_list.html", title="Classrooms", items=items, 
                           cols=["id", "name", "camera_type", "camera_url", "is_active"])

@bp.route("/courses", methods=["GET", "POST"])
def courses():
    if request.method == "POST":
        code = request.form.get("code")
        name = request.form.get("name")
        c = Course(code=code, name=name)
        db.session.add(c)
        db.session.commit()
        flash("Course added.", "success")
        return redirect(url_for("admin.courses"))
    items = db.session.execute(db.select(Course)).scalars().all()
    return render_template("admin/crud_list.html", title="Courses", items=items, 
                           cols=["id", "code", "name"])

@bp.route("/sections", methods=["GET", "POST"])
def sections():
    if request.method == "POST":
        name = request.form.get("name")
        sem = int(request.form.get("semester"))
        s = Section(name=name, semester=sem)
        db.session.add(s)
        db.session.commit()
        flash("Section added.", "success")
        return redirect(url_for("admin.sections"))
    items = db.session.execute(db.select(Section)).scalars().all()
    return render_template("admin/crud_list.html", title="Sections", items=items, 
                           cols=["id", "name", "semester"])

@bp.route("/teachers", methods=["GET", "POST"])
def teachers():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        t = Teacher(full_name=full_name, email=email)
        db.session.add(t)
        db.session.flush()
        u = User(username=email.split('@')[0], role='teacher', teacher_id=t.id)
        u.set_password(email.split('@')[0])
        db.session.add(u)
        db.session.commit()
        flash("Teacher added.", "success")
        return redirect(url_for("admin.teachers"))
    items = db.session.execute(db.select(Teacher)).scalars().all()
    return render_template("admin/crud_list.html", title="Teachers", items=items, 
                           cols=["id", "full_name", "email"])

@bp.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        roll_no = request.form.get("roll_no")
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        section_id = request.form.get("section_id")
        s = Student(roll_no=roll_no, full_name=full_name, email=email, section_id=section_id)
        db.session.add(s)
        db.session.flush()
        u = User(username=roll_no, role='student', student_id=s.id, must_change_password=True)
        u.set_password(roll_no)
        db.session.add(u)
        db.session.commit()
        flash("Student added.", "success")
        return redirect(url_for("admin.students"))
    items = db.session.execute(db.select(Student)).scalars().all()
    sections = db.session.execute(db.select(Section)).scalars().all()
    return render_template("admin/crud_list.html", title="Students", items=items, 
                           cols=["id", "roll_no", "full_name", "section_id"], extra_data={'sections': sections})

@bp.route("/timetable", methods=["GET", "POST"])
def timetable():
    if request.method == "POST":
        from datetime import time
        course_id = request.form.get("course_id")
        teacher_id = request.form.get("teacher_id")
        section_id = request.form.get("section_id")
        classroom_id = request.form.get("classroom_id")
        weekday = request.form.get("weekday")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        h1, m1 = map(int, start_time.split(':'))
        h2, m2 = map(int, end_time.split(':'))
        from flask import current_app
        t = TimetableSlot(course_id=course_id, teacher_id=teacher_id, section_id=section_id, 
                          classroom_id=classroom_id, weekday=int(weekday), 
                          start_time=time(h1, m1), end_time=time(h2, m2),
                          late_after_min=current_app.config['DEFAULT_LATE_MIN'],
                          absent_after_min=current_app.config['DEFAULT_ABSENT_MIN'])
        db.session.add(t)
        db.session.commit()
        flash("Timetable slot added.", "success")
        return redirect(url_for("admin.timetable"))
    
    items = db.session.execute(db.select(TimetableSlot)).scalars().all()
    courses = db.session.execute(db.select(Course)).scalars().all()
    teachers = db.session.execute(db.select(Teacher)).scalars().all()
    sections = db.session.execute(db.select(Section)).scalars().all()
    classrooms = db.session.execute(db.select(Classroom)).scalars().all()
    
    return render_template("admin/crud_list.html", title="Timetable", items=items, 
                           cols=["id", "course_id", "teacher_id", "section_id", "classroom_id", "weekday", "start_time", "end_time"],
                           extra_data={'courses': courses, 'teachers': teachers, 'sections': sections, 'classrooms': classrooms})
