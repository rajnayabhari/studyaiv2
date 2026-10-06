import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.extensions import db
from app.models import User

def reset():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        for u in users:
            print(f"Resetting password for {u.username}")
            if u.username == 'admin':
                u.set_password('admin')
            elif u.username == 'teacher':
                u.set_password('teacher')
            elif u.role == 'student':
                u.set_password('student')
            else:
                u.set_password(u.username) # fallback
        db.session.commit()
        print("Passwords reset successfully.")

if __name__ == '__main__':
    reset()
