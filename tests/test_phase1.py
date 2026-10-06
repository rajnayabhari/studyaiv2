"""Phase 1 tests: role access and basic CRUD."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, Section
from scripts.init_db import ensure_database

@pytest.fixture()
def app():
    ensure_database(TestConfig.SQLALCHEMY_DATABASE_URI)
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        u1 = User(username="admin", role="admin")
        u1.set_password("pw")
        u2 = User(username="teacher", role="teacher")
        u2.set_password("pw")
        u3 = User(username="student", role="student")
        u3.set_password("pw")
        db.session.add_all([u1, u2, u3])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

def test_role_access(app):
    c = app.test_client()
    # Login as teacher
    c.post("/login", data={"username": "teacher", "password": "pw"})
    # Try to access admin area
    r = c.get("/admin/")
    assert r.status_code == 302 and "/login" not in r.headers["Location"]
    # Access teacher area
    r = c.get("/teacher/")
    assert r.status_code == 200

def test_admin_crud(app):
    c = app.test_client()
    c.post("/login", data={"username": "admin", "password": "pw"})
    # Create section
    r = c.post("/admin/sections", data={"name": "Test Section", "semester": "1"}, follow_redirects=True)
    assert b"Section added" in r.data
    assert b"Test Section" in r.data
