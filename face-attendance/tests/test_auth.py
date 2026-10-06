import pytest
from app import create_app
from app.extensions import db
from app.models import User

@pytest.fixture
def app():
    app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })

    with app.app_context():
        db.create_all()
        # Seed test user
        u = User(username='test_admin', role='admin')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_login(client):
    response = client.post('/auth/login', data={
        'username': 'test_admin',
        'password': 'password'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Admin Dashboard' in response.data

def test_login_invalid(client):
    response = client.post('/auth/login', data={
        'username': 'test_admin',
        'password': 'wrong'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data

def test_protected_route(client):
    response = client.get('/admin/', follow_redirects=True)
    # Should redirect to login since not authenticated
    assert b'Login' in response.data
