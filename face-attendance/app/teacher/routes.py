from flask import Blueprint, render_template
from flask_login import login_required
from ..auth.decorators import role_required

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/')
@login_required
@role_required('teacher')
def dashboard():
    return render_template('teacher/dashboard.html')
