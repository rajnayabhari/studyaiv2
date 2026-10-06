"""Authentication blueprint. Phase 0: login/logout only; role decorators come in Phase 1."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
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
