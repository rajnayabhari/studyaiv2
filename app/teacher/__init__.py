from flask import Blueprint, render_template
from ..auth import role_required
bp = Blueprint("teacher", __name__)

@bp.before_request
@role_required('teacher')
def before_request():
    pass

@bp.route("/")
def index():
    return render_template("teacher/dashboard.html")
