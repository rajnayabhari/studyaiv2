# PROGRESS

## Current phase: 0 — Setup (COMPLETE, all exit checks pass)

### Done
- Repo layout at repo root (plan's `face-attendance/` folder flattened into `c:\studyai_v2`).
- `.venv` (Python 3.11.9), pinned `requirements.txt`, `.env` (gitignored), `.env.example`.
- App factory, extensions (SQLAlchemy, Flask-Login, CSRF), config from env.
- All Section 4 models with CHECK/UNIQUE constraints and required indexes.
- `scripts/init_db.py` (creates DB `face_attendance` + tables), `scripts/seed_demo.py` (idempotent),
  `scripts/check_camera.py`.
- Minimal login/logout + login page. Tests: `tests/test_phase0.py` (4 pass, separate test DB).
- ML libs installed: insightface 2.1, mediapipe 1.0.1, opencv-contrib 5.0, onnxruntime-gpu.

### Exit check
| Check | Result |
|---|---|
| App starts | OK (port 5001) |
| DB tables exist | OK (13 tables) |
| Login page loads / admin login | OK |
| check_camera.py webcam (`0`) | OK 640x480 @ 28.7 fps |
| check_camera.py phone (`http://192.168.18.202:8080/video`) | OK 1920x1080 @ 5.2 fps |

### Decisions
- Port 5001 by default (5000 was occupied). Configurable via `PORT`.
- `opencv-contrib-python` instead of `opencv-python` (mediapipe requires contrib; both cannot coexist).
- Added `users.must_change_password` (plan 7.2).
- Webcam opened with `CAP_DSHOW` on Windows for fast startup.

### Broken / open
- Phone stream at 1080p gives only ~5 fps; set IP Webcam resolution to 1280x720 or 640x480 for the kiosk (target 6–8 fps processing).
- CUDA provider listed by onnxruntime but not yet verified with a real model (Phase 2).

### Next
- Phase 1: role decorators, base layout, admin CRUD.
