import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(BASE_DIR, "app")
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

# 1. Update app/auth/__init__.py to include decorators
AUTH_INIT = """from functools import wraps
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

def role_required(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                flash("You do not have access to this page.", "error")
                return redirect(url_for("auth.index"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.index'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.index'))
        elif current_user.role == 'student':
            return redirect(url_for('student.index'))
        return render_template("home.html")
    return redirect(url_for("auth.login"))

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            login_user(user)
            return redirect(url_for("auth.index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
"""

# 2. Update app/__init__.py to register blueprints
APP_INIT = """\"\"\"Application factory.\"\"\"
import logging
import os
from flask import Flask
from .config import Config
from .extensions import csrf, db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.makedirs(os.path.join(app.config["UPLOAD_DIR"], "attempts"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models)

    @login_manager.user_loader
    def load_user(user_id):
        u = db.session.get(models.User, int(user_id))
        return u if u and u.is_active else None

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from .teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix="/teacher")

    from .student import bp as student_bp
    app.register_blueprint(student_bp, url_prefix="/student")

    return app
"""

# 3. Create Admin Blueprint
ADMIN_INIT = """from flask import Blueprint, render_template, request, redirect, url_for, flash
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
"""

# 4. Create Teacher Blueprint
TEACHER_INIT = """from flask import Blueprint, render_template
from ..auth import role_required
bp = Blueprint("teacher", __name__)

@bp.before_request
@role_required('teacher')
def before_request():
    pass

@bp.route("/")
def index():
    return render_template("teacher/dashboard.html")
"""

# 5. Create Student Blueprint
STUDENT_INIT = """from flask import Blueprint, render_template
from ..auth import role_required
bp = Blueprint("student", __name__)

@bp.before_request
@role_required('student')
def before_request():
    pass

@bp.route("/")
def index():
    return render_template("student/dashboard.html")
"""

# Base HTML update for nav
BASE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Face Attendance{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
  <style>
    .nav { padding: 16px 24px; background: hsl(228 25% 10%); display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); }
    .nav a { color: var(--text); text-decoration: none; margin-right: 16px; }
    .nav a:hover { color: var(--accent2); }
    .nav-links { display: flex; gap: 10px; }
    .table-container { width: 100%; overflow-x: auto; margin-top: 20px; }
    table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 8px; overflow: hidden; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: hsl(228 30% 15%); }
    .form-group { margin-bottom: 15px; }
  </style>
</head>
<body>
  {% if current_user.is_authenticated %}
  <div class="nav">
    <div class="nav-links">
      <b>Face Attendance</b>
      {% if current_user.role == 'admin' %}
        <a href="{{ url_for('admin.index') }}">Dashboard</a>
        <a href="{{ url_for('admin.students') }}">Students</a>
        <a href="{{ url_for('admin.teachers') }}">Teachers</a>
        <a href="{{ url_for('admin.classrooms') }}">Classrooms</a>
        <a href="{{ url_for('admin.courses') }}">Courses</a>
        <a href="{{ url_for('admin.sections') }}">Sections</a>
        <a href="{{ url_for('admin.timetable') }}">Timetable</a>
      {% endif %}
    </div>
    <div>
      <span>{{ current_user.username }} ({{ current_user.role }})</span>
      <a href="{{ url_for('auth.logout') }}">Logout</a>
    </div>
  </div>
  {% endif %}
  <div style="padding: 24px;">
    {% for cat, msg in get_flashed_messages(with_categories=true) %}<div class="flash">{{ msg }}</div>{% endfor %}
    {% block body %}{% endblock %}
  </div>
</body>
</html>
"""

# Admin templates
ADMIN_DASHBOARD = """{% extends "base.html" %}
{% block title %}Admin Dashboard{% endblock %}
{% block body %}
<h1>Admin Dashboard</h1>
<div style="display: flex; gap: 20px; margin-top: 20px;">
    <div class="card" style="margin:0; padding: 20px;">
        <h3>Students</h3>
        <p style="font-size: 2rem;">{{ student_count }}</p>
    </div>
    <div class="card" style="margin:0; padding: 20px;">
        <h3>Teachers</h3>
        <p style="font-size: 2rem;">{{ teacher_count }}</p>
    </div>
    <div class="card" style="margin:0; padding: 20px;">
        <h3>Classrooms</h3>
        <p style="font-size: 2rem;">{{ classroom_count }}</p>
    </div>
</div>
{% endblock %}"""

ADMIN_CRUD_LIST = """{% extends "base.html" %}
{% block title %}{{ title }}{% endblock %}
{% block body %}
<h1>{{ title }}</h1>

<div class="card" style="max-width: 600px; margin: 20px 0;">
    <h3>Add {{ title }}</h3>
    <form method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        
        {% if title == 'Classrooms' %}
        <label>Name</label><input type="text" name="name" required>
        <label>Camera Type</label>
        <select name="camera_type" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            <option value="webcam">Webcam</option>
            <option value="ip">IP Camera</option>
        </select>
        <label>Camera URL</label><input type="text" name="camera_url" placeholder="0 or http://...">
        
        {% elif title == 'Courses' %}
        <label>Code</label><input type="text" name="code" required>
        <label>Name</label><input type="text" name="name" required>
        
        {% elif title == 'Sections' %}
        <label>Name</label><input type="text" name="name" required>
        <label>Semester</label><input type="number" name="semester" required>
        
        {% elif title == 'Teachers' %}
        <label>Full Name</label><input type="text" name="full_name" required>
        <label>Email</label><input type="email" name="email" required>
        
        {% elif title == 'Students' %}
        <label>Roll No</label><input type="text" name="roll_no" required>
        <label>Full Name</label><input type="text" name="full_name" required>
        <label>Email</label><input type="email" name="email" required>
        <label>Section</label>
        <select name="section_id" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            {% for sec in extra_data.sections %}<option value="{{ sec.id }}">{{ sec.name }}</option>{% endfor %}
        </select>
        
        {% elif title == 'Timetable' %}
        <label>Course</label>
        <select name="course_id" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            {% for c in extra_data.courses %}<option value="{{ c.id }}">{{ c.name }}</option>{% endfor %}
        </select>
        <label>Teacher</label>
        <select name="teacher_id" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            {% for t in extra_data.teachers %}<option value="{{ t.id }}">{{ t.full_name }}</option>{% endfor %}
        </select>
        <label>Section</label>
        <select name="section_id" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            {% for s in extra_data.sections %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}
        </select>
        <label>Classroom</label>
        <select name="classroom_id" style="width:100%; padding:12px; border-radius:10px; background:hsl(228 30% 6% / .7); color:white; border:1px solid var(--border);">
            {% for cl in extra_data.classrooms %}<option value="{{ cl.id }}">{{ cl.name }}</option>{% endfor %}
        </select>
        <label>Weekday (0=Mon, 6=Sun)</label><input type="number" name="weekday" min="0" max="6" required>
        <label>Start Time (HH:MM)</label><input type="time" name="start_time" required>
        <label>End Time (HH:MM)</label><input type="time" name="end_time" required>
        {% endif %}
        
        <button class="btn" type="submit">Save</button>
    </form>
</div>

<div class="table-container">
    <table>
        <thead>
            <tr>{% for c in cols %}<th>{{ c }}</th>{% endfor %}</tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                {% for c in cols %}
                <td>{{ item[c] }}</td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}"""

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

write_file(os.path.join(APP_DIR, "auth", "__init__.py"), AUTH_INIT)
write_file(os.path.join(APP_DIR, "__init__.py"), APP_INIT)
write_file(os.path.join(APP_DIR, "admin", "__init__.py"), ADMIN_INIT)
write_file(os.path.join(APP_DIR, "teacher", "__init__.py"), TEACHER_INIT)
write_file(os.path.join(APP_DIR, "student", "__init__.py"), STUDENT_INIT)
write_file(os.path.join(TEMPLATES_DIR, "base.html"), BASE_HTML)
write_file(os.path.join(TEMPLATES_DIR, "admin", "dashboard.html"), ADMIN_DASHBOARD)
write_file(os.path.join(TEMPLATES_DIR, "admin", "crud_list.html"), ADMIN_CRUD_LIST)
write_file(os.path.join(TEMPLATES_DIR, "teacher", "dashboard.html"), "{% extends 'base.html' %}{% block body %}<h1>Teacher Dashboard</h1>{% endblock %}")
write_file(os.path.join(TEMPLATES_DIR, "student", "dashboard.html"), "{% extends 'base.html' %}{% block body %}<h1>Student Dashboard</h1>{% endblock %}")
print("Phase 1 scaffolded.")
