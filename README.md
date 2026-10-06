# Face Attendance System

Automated facial recognition attendance (Flask + PostgreSQL + InsightFace). See `face_attendance_plan.md`.

## Setup (Windows)
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then edit DATABASE_URL, SECRET_KEY, KIOSK_KEY
.\.venv\Scripts\python scripts\init_db.py
.\.venv\Scripts\python scripts\seed_demo.py
.\.venv\Scripts\python run.py # http://127.0.0.1:5001
```
Demo logins: `admin/admin123`, `teacher/teacher123`, students `BCA001..BCA005` (password = roll number).

Tests: `.\.venv\Scripts\python -m pytest` (uses `TEST_DATABASE_URL`, created automatically).

## Phone camera setup
1. Install **IP Webcam** (Android), tap *Start server*.
2. Phone and laptop must be on the **same Wi-Fi** (same `192.168.x` subnet).
3. Check: `.\.venv\Scripts\python scripts\check_camera.py http://<phone-ip>:8080/video`
4. Paste that URL into the classroom's camera URL in admin. Laptop webcam = source `0`.
