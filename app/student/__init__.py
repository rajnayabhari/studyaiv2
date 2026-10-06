from flask import Blueprint, render_template
from ..auth import role_required
bp = Blueprint("student", __name__)

@bp.before_request
@role_required('student')
def before_request():
    pass

@bp.route("/")
def index():
    return render_template("student/dashboard.html")
