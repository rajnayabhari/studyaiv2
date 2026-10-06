"""Phase 0 smoke tests: app boots, tables exist, login works. Uses TEST_DATABASE_URL."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402
from scripts.init_db import ensure_database  # noqa: E402


@pytest.fixture()
def app():
    ensure_database(TestConfig.SQLALCHEMY_DATABASE_URI)
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        u = User(username="admin", role="admin")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_tables_exist(app):
    names = set(db.inspect(db.engine).get_table_names())
    assert {"users", "students", "attendance", "class_sessions", "face_templates",
            "recognition_attempts", "audit_log", "settings"} <= names


def test_login_page_loads(app):
    r = app.test_client().get("/login")
    assert r.status_code == 200 and b"Sign in" in r.data


def test_login_success_and_failure(app):
    c = app.test_client()
    assert b"Invalid" in c.post("/login", data={"username": "admin", "password": "x"}).data
    r = c.post("/login", data={"username": "admin", "password": "pw"}, follow_redirects=True)
    assert b"Welcome, admin" in r.data


def test_unauthenticated_root_redirects(app):
    r = app.test_client().get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
