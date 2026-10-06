# Automated Facial Recognition Attendance System — Implementation Plan

Audience: an AI coding agent (Antigravity) building this for a BCA 8th-semester project.
Read this whole file before writing any code. Everything here has been decided with the client; do not re-ask settled items.

---

## 0. Agent operating rules

1. Work in the phases of Section 14, in order. Do not start a phase until the previous phase's **exit check** passes.
2. Keep a `PROGRESS.md` at the repo root: phase, what is done, what is broken, what is next. Update it after every phase.
3. Use Git. Commit at the end of every phase with a clear message.
4. Python venv, pinned `requirements.txt`, `.env` for secrets, `.env.example` committed (never commit `.env`).
5. No paid APIs and no cloud services. All models run locally.
6. Every threshold, URL, and time value comes from config/DB settings, never hard-coded.
7. Write tests as you go (Section 12). A phase is not done if its tests fail.
8. If something is ambiguous, choose the simplest option that satisfies this plan, record the choice in `PROGRESS.md`, and continue. Ask the user only for true blockers (missing credentials, a library that cannot install after the fallbacks listed here).
9. Priority is a **working end-to-end demo first**, polish second. The project deadline is very short. Section 14 marks MUST / SHOULD / COULD.

---

## 1. Goal and scope

A web system where a student stops in front of a camera at a classroom "kiosk", the system verifies they are a real, live, enrolled student, and records timestamped attendance in PostgreSQL. Teachers manage sessions and corrections, admins manage everything, students view their own attendance.

**Decisions already made (final):**

| Topic | Decision |
|---|---|
| Recognition mode | Kiosk style: one student pauses and looks at the camera |
| Kiosk hardware | None. "Kiosk" = a browser page, full screen, on a laptop |
| Main camera | Phone as IP camera (MJPEG over HTTP). Laptop webcam is a supported fallback, switchable in settings |
| Backend | Python + Flask |
| Frontend | HTML + CSS + vanilla JS (Jinja templates). No SPA framework |
| Database | PostgreSQL |
| Recognition model | InsightFace (SCRFD detector + ArcFace embeddings) |
| Liveness | Active challenge (blink + head turn) is the main check, plus a passive anti-spoof check |
| Unrecognized faces | Log the attempt, allow teacher manual marking with an audit log |
| Enrollment | Webcam capture in the web app AND bulk photo upload |
| Demo scale | Up to 10 enrolled students, 1 classroom demoed (design supports many) |
| Late/absent rules | Set by the teacher per class |
| Simulated time | Yes, admin-controlled clock override |
| Student portal | View own attendance only |
| Roles | admin, teacher, student |
| Reports | CSV and PDF |
| Timezone | Asia/Kathmandu |

**Out of scope:** mobile apps, cloud deployment, multi-camera simultaneous processing, student correction requests, email/SMS notifications, face search in large galleries (pgvector).

---

## 2. Algorithms (these must be implemented as described and documented in `docs/ALGORITHMS.md` for the viva)

### 2.1 Pipeline overview

```
Camera frame
  -> Face detection (SCRFD)            : where is the face + 5 landmarks
  -> Quality gate                      : size, sharpness, pose, detector score
  -> Passive anti-spoof                : photo / screen replay check
  -> Face alignment (5-point similarity transform to 112x112)
  -> Embedding (ArcFace, 512-d, L2-normalised)
  -> 1:N matching (cosine similarity) + threshold + margin rule
  -> Active liveness challenge (blink + head turn, random order, time limited)
  -> Re-verification (same identity again after challenge)
  -> Decision -> status by timetable rules -> write attendance
```

### 2.2 Face detection — SCRFD (via InsightFace)
- Single-stage detector that outputs boxes, confidence, and 5 facial landmarks (eyes, nose, mouth corners).
- Chosen because it is accurate, fast on CPU and GPU, and gives landmarks needed for alignment.
- Config: `DET_SIZE=640`, minimum detection score `0.6`.

### 2.3 Alignment
- Estimate a similarity transform (rotation, scale, translation) from the 5 detected landmarks to the standard ArcFace reference landmarks and warp to 112x112.
- Purpose: removes in-plane rotation and scale differences so the embedding network sees a normalised face.

### 2.4 Embedding — ArcFace
- ResNet-based network trained with Additive Angular Margin loss, so embeddings of the same person cluster tightly on a hypersphere and different people are separated by an angular margin.
- Output: 512-d vector, L2-normalised. Same-person comparison therefore reduces to a dot product (cosine similarity).
- Use the `buffalo_l` model pack (GPU available) with `buffalo_s` as a CPU fallback via config.

### 2.5 Matching
- Gallery = all stored embeddings of all active enrolled students (loaded into a NumPy matrix at startup, refreshed when enrollment changes).
- Score for a student = **max cosine similarity** over that student's stored embeddings.
- Accept rule: `best_score >= T_ACCEPT` **and** `best_score - second_best_student_score >= T_MARGIN`.
- Starting values (calibrate in Phase 6): `T_ACCEPT = 0.45`, `T_MARGIN = 0.05`.
- To make the decision robust to a bad frame, collect up to 5 quality-passing frames over about 1 second and average their embeddings (re-normalise) before matching.
- Complexity: O(N·512) per query, trivial for hundreds of students. Mention pgvector/ANN as future work only.

### 2.6 Active liveness — challenge-response
Uses MediaPipe Face Mesh landmarks on the same frames.
- **Blink detection (Eye Aspect Ratio):** `EAR = (|p2-p6| + |p3-p5|) / (2·|p1-p4|)` per eye using six landmarks. Right eye indices `[33,160,158,133,153,144]`, left eye `[362,385,387,263,373,380]`. A blink = EAR below `EAR_CLOSED=0.21` for at least 2 consecutive frames, then above `EAR_OPEN=0.25`. Require 2 blinks.
- **Head turn (yaw ratio):** `yaw = (x_nose - x_leftcheek) / (x_rightcheek - x_leftcheek)` using landmarks 1 (nose tip), 234 and 454 (cheeks). Centre ≈ 0.5. "Turn left/right" is satisfied when the ratio passes `YAW_LOW=0.35` or `YAW_HIGH=0.65` for 3 consecutive frames. The agent must test and flip the direction mapping if the camera image is not mirrored (the kiosk video is mirrored in CSS for user comfort, but all logic runs on raw frames).
- **Challenge sequence:** the server picks randomly from {blink x2, turn left, turn right}, requires **blink x2 plus one random head turn**, total time limit `CHALLENGE_TIMEOUT_S=12`. Randomness stops a pre-recorded video from passing.
- **Identity continuity:** after the challenge the user must look straight again; the system re-extracts an embedding and requires it to match the **same student** as before (blocks "swap the person mid-challenge").

### 2.7 Passive anti-spoof
- Backend option `PASSIVE_BACKEND` in config: `minifasnet` | `heuristic` | `off`.
- **minifasnet (preferred):** Silent-Face-Anti-Spoofing (MiniFASNetV2 + MiniFASNetV1SE, pretrained, from the open-source `minivision-ai/Silent-Face-Anti-Spoofing` repository). Takes the face crop at two scales, outputs real vs spoof probability. Average over 3 frames. Real if mean real-probability `>= PASSIVE_THRESHOLD` (start at `0.7`).
- **heuristic (fallback, must also be implemented):** texture features on the face crop: Laplacian variance (blur), colour/saturation statistics, and FFT high-frequency energy to detect Moiré patterns from screens. Combine with simple fixed rules; document its limits honestly.
- **`PASSIVE_ENFORCE` flag (default true):** if false, the passive result is logged but does not block. This is a demo-day safety valve if the phone camera makes the passive check misfire.
- Honest limitation to document: a high-quality 3D mask or a well-made video replay can defeat passive checks; this is why the active challenge is the main defence.

### 2.8 Quality gate (applied before enrollment and recognition)
- Exactly one face (largest face used if several, but show a warning).
- Detector score `>= 0.6`, face box width `>= 120 px`.
- Sharpness: Laplacian variance `>= BLUR_MIN` (calibrate, start 60).
- Pose: yaw ratio within 0.35–0.65 for frontal enrollment shots and for the identification frame.

### 2.9 Decision and status rules
Attendance is recorded only if **all** are true: quality passed, passive passed (or not enforced), match accepted, active challenge passed, re-verification matches the same student, a session is open for this classroom, and the student belongs to that session's section.

---

## 3. Architecture

```
 Phone (IP Webcam app)  ──MJPEG──►  Flask server (laptop)
 or laptop webcam                    ├─ CameraService  (reader thread, latest frame only)
                                     ├─ FacePipeline   (detect, quality, passive, embed, match)
                                     ├─ LivenessEngine (blink, yaw, challenge state machine)
                                     ├─ KioskController (per-classroom state machine)
                                     ├─ Clock          (real or simulated time)
                                     ├─ Services       (attendance, timetable, enrollment, reports)
                                     └─ REST + Jinja pages  ◄── Browser (kiosk / admin / teacher / student)
                                                │
                                           PostgreSQL
```

- **Server-side recognition.** The browser never does recognition. The kiosk page shows the camera feed proxied from Flask (`/kiosk/<classroom_id>/stream` as MJPEG, with overlay boxes optionally drawn server-side) and polls `/api/kiosk/<classroom_id>/state` every 300 ms for the state machine's current prompt/result.
- **CameraService:** one background thread per active classroom using `cv2.VideoCapture(url)`. It always keeps only the **latest** frame (drop stale frames to avoid lag), auto-reconnects on failure with backoff, and exposes `get_frame()` plus a health status. Source is `0` (webcam) or an `http://IP:8080/video` URL, set per classroom.
- **FacePipeline** is a singleton loaded once at startup (model load is slow) and used by both enrollment and kiosk. Use ONNX Runtime with the CUDA provider if available, else CPU, selected automatically with a log line stating which is in use.
- Process frames at most about 6–8 fps; the kiosk does not need more.

### Suggested project structure

```
face-attendance/
  app/
    __init__.py            # app factory
    config.py
    extensions.py          # db, login manager, csrf
    models.py              # SQLAlchemy models
    auth/                  # login, role decorators
    admin/                 # routes + templates
    teacher/
    student/
    kiosk/                 # kiosk routes, state machine, stream
    api/                   # JSON endpoints
    services/
      clock.py
      camera.py
      face_pipeline.py
      quality.py
      passive.py
      liveness.py
      matching.py
      enrollment.py
      timetable.py
      attendance.py
      reports.py
    static/ (css, js, vendored libs, no CDN dependence)
    templates/
  scripts/
    init_db.py  seed_demo.py  calibrate.py  import_students.py  check_camera.py
  tests/
  docs/                    # ARCHITECTURE.md, ALGORITHMS.md, DATABASE.md, TEST_REPORT.md, USER_GUIDE.md
  instance/uploads/        # enrollment photos (temp), attempt snapshots
  .env.example  requirements.txt  README.md  PROGRESS.md  run.py
```

### Libraries
`flask`, `flask-sqlalchemy`, `flask-login`, `flask-wtf` (CSRF), `psycopg2-binary`, `python-dotenv`, `numpy`, `opencv-python`, `insightface`, `onnxruntime` (or `onnxruntime-gpu`), `mediapipe`, `torch` (CPU build is fine, only for MiniFASNet), `pillow`, `reportlab`, `tzdata` (needed for `zoneinfo` on Windows), `pytest`.
Windows note: if `insightface` fails to build, install Microsoft C++ Build Tools, or use a prebuilt wheel for the user's Python version. If it still cannot install, report it as a blocker rather than silently swapping models.

---

## 4. Database design (PostgreSQL)

Use SQLAlchemy models; `scripts/init_db.py` calls `create_all` (no Alembic needed). All timestamps `timestamptz` stored in UTC, displayed in Asia/Kathmandu.

**users** — `id`, `username` (unique), `password_hash`, `role` (`admin|teacher|student`), `student_id` (nullable FK), `teacher_id` (nullable FK), `is_active`, `created_at`

**students** — `id`, `roll_no` (unique), `full_name`, `email`, `section_id` FK, `is_active`, `created_at`

**teachers** — `id`, `full_name`, `email`

**sections** — `id`, `name` (e.g. "BCA 8th A"), `semester`

**courses** — `id`, `code`, `name`

**classrooms** — `id`, `name`, `camera_type` (`ip|webcam`), `camera_url`, `is_active`

**timetable_slots** — `id`, `course_id`, `teacher_id`, `section_id`, `classroom_id`, `weekday` (0–6), `start_time`, `end_time`, `late_after_min`, `absent_after_min`
 - `late_after_min` and `absent_after_min` are the **teacher-editable per-class rules**. Constraint: `0 <= late_after_min < absent_after_min <= duration`.

**class_sessions** — `id`, `slot_id` (nullable, null for ad-hoc demo sessions), `course_id`, `teacher_id`, `section_id`, `classroom_id`, `start_at`, `end_at`, `late_after_min`, `absent_after_min` (snapshot copied from the slot, overridable per session), `status` (`scheduled|open|finalized`), `finalized_at`
 - Unique `(slot_id, start_at)` to prevent duplicates.

**face_templates** — `id`, `student_id` FK, `embedding` (BYTEA, 512 float32 = 2048 bytes), `det_score`, `sharpness`, `source` (`webcam|upload`), `created_at`, `is_active`

**attendance** — `id`, `session_id` FK, `student_id` FK, `status` (`present|late|absent|excused`), `marked_at`, `method` (`face|manual|auto`), `similarity` (nullable), `passive_score` (nullable), `marked_by_user_id` (nullable), `note`
 - **Unique `(session_id, student_id)`**. Duplicate check-ins return a friendly "already marked" and write nothing.

**recognition_attempts** — `id`, `classroom_id`, `session_id` (nullable), `created_at`, `outcome` (`success|unknown|ambiguous|spoof_suspected|active_liveness_failed|reverify_failed|no_session|window_closed|already_marked|not_in_section|low_quality|timeout`), `best_student_id` (nullable), `best_score`, `second_score`, `passive_score`, `snapshot_path`

**audit_log** — `id`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `before_json`, `after_json`, `reason`, `created_at`

**settings** — `key` (PK), `value` (text). Keys: `sim_enabled`, `sim_anchor_real`, `sim_anchor_sim`, `t_accept`, `t_margin`, `passive_threshold`, `passive_enforce`, `passive_backend`, `challenge_timeout_s`, `early_window_min`, `default_late_min`, `default_absent_min`.

Indexes: `attendance(session_id)`, `attendance(student_id)`, `class_sessions(classroom_id, start_at)`, `recognition_attempts(created_at)`.

Also produce an ER diagram (Mermaid) in `docs/DATABASE.md`.

---

## 5. Time, timetable, and status logic

### 5.1 Clock (simulated time)
- `Clock.now()` is the **only** way the application gets the current time. Never call `datetime.now()` elsewhere.
- If `sim_enabled` is false: real time.
- If true: `now = sim_anchor_sim + (real_now - sim_anchor_real)` (simulated time keeps ticking forward from the set point).
- Admin UI: a settings card shows current effective time, a datetime picker "Set simulated time to…", "Turn off simulation", plus a visible banner on every page while simulation is on ("SIMULATED TIME: …").

### 5.2 Session creation
- Sessions are created from timetable slots lazily: `get_or_create_session(slot, date)` using the slot's weekday/time, copying `late_after_min`/`absent_after_min` into the session.
- **Demo session creator (MUST):** an admin/teacher button "Start a quick session now": pick classroom, course, section, teacher, duration (default 30 min), late/absent minutes. Creates an ad-hoc session starting at `Clock.now()`. This guarantees the demo never depends on the real timetable.

### 5.3 Which session does the kiosk use?
For classroom C at time `now`: the session with `classroom_id = C` and `start_at - early_window_min <= now <= end_at`. If none: kiosk shows "No class in session." and logs nothing except an optional `no_session` attempt.

### 5.4 Status calculation at check-in
Let `t = now - session.start_at` in minutes.
- `t <= late_after_min` (including early arrivals) → **present**
- `late_after_min < t <= absent_after_min` → **late**
- `t > absent_after_min` → check-in **rejected** (`window_closed`); kiosk says "Check-in window closed. Please ask your teacher." The teacher can manually mark.

### 5.5 Absent and finalization
- When a session passes `end_at`, it is finalized: every student in the session's section with no attendance row gets an `absent` row with `method='auto'` (so `attendance.method` allows `face|manual|auto`).
- Implement finalization as (a) a lightweight background thread checking every 30 seconds, and (b) a lazy call when a teacher/report page loads, and (c) a "Finalize now" button. Finalization must be idempotent.
- Until finalized, reports display not-yet-marked students as "pending".

### 5.6 Teacher-editable rules
- Teachers edit `late_after_min` / `absent_after_min` for **their own slots** (applies to future sessions) and can override for an **individual session** (applies immediately). Validate the constraint from Section 4. Log changes in `audit_log`.

---

## 6. Kiosk state machine (per classroom, server-side)

States and transitions:

1. **IDLE** — waiting. Prompt: "Please look at the camera." Move on when a quality-passing face has been present and stable for about 1 second.
2. **CHECKING** — passive anti-spoof on 3 frames while collecting up to 5 embeddings. If passive fails and enforced: outcome `spoof_suspected`, log + snapshot, go to RESULT (denied).
3. **IDENTIFYING** — average embeddings, run matching with threshold and margin.
   - No match → outcome `unknown` (or `ambiguous`), log + snapshot, RESULT (denied, message "Not recognized. Try again or ask your teacher").
   - Match found → check the student belongs to the session's section (else `not_in_section`), check not already marked (else `already_marked`, friendly message), check time window (else `window_closed`).
4. **CHALLENGE** — display "Hello, <name>. Blink twice", then "Now turn your head left/right" (random). Progress shown live. Timeout `CHALLENGE_TIMEOUT_S` → `active_liveness_failed`.
5. **REVERIFY** — "Look straight at the camera." Take frontal frames, embed, match; must return the same student and pass the accept threshold, else `reverify_failed`.
6. **RESULT** — show success ("Present — 10:03" or "Late — 10:14") or denial for 3 seconds, write the attendance row (on success) and the `recognition_attempts` row (always).
7. **COOLDOWN** — 4 seconds ignoring faces, then back to IDLE.

Rules:
- After **3 consecutive denials**, the kiosk additionally shows "Need help? Ask your teacher to mark you manually."
- Every transition and prompt is a field in the state JSON so the frontend is dumb: `{state, prompt, student_name, progress, countdown, result, message}`.
- Only one student is handled at a time. If several faces appear, use the largest and show "One person at a time."
- All attendance writes go through `attendance_service.mark(...)`, which enforces the unique constraint, transaction safety, and status rules.

---

## 7. Enrollment

### 7.1 Webcam enrollment (admin page)
- Admin chooses a student, clicks "Enroll face". The browser uses `getUserMedia` (works on `localhost`) and captures frames, POSTing JPEGs to `/api/enroll/<student_id>/capture`.
- Guided capture of about 8 images: front x3, slightly left, slightly right, slightly up, slightly down, with a different expression. The server runs the quality gate on each and replies accepted/rejected with the reason ("too blurry", "no face", "too small", "multiple faces").
- Require **at least 5 accepted** embeddings; store each in `face_templates`.

### 7.2 Bulk upload
- Admin uploads many images (or a ZIP). Filename convention `ROLLNO_anything.jpg` **or** folders named by roll number. The server maps each image to a student by roll number.
- Each image goes through the same quality gate; a result table shows accepted/rejected per file with reasons, and per-student counts.
- Also support CSV import of students: columns `roll_no, full_name, email, section`. Student login accounts are auto-created (username = roll number, initial password = roll number, flagged `must_change_password`; implementing the forced change screen is a COULD).

### 7.3 Safeguards
- **Duplicate-identity check:** if a new embedding matches a **different** student with similarity above `0.6`, reject and warn ("looks like <other student>").
- After any enrollment change, refresh the in-memory gallery.
- Store embeddings, not raw photos, after processing (delete uploaded files once processed). Keep only failed-attempt snapshots in `instance/uploads/attempts/`, with a retention cleanup setting (default 30 days).
- Provide a "Delete face data" action per student.

---

## 8. Web application features

### Authentication and security
- Login for all roles with hashed passwords (Werkzeug), Flask-Login sessions, CSRF protection on all POST forms and fetch calls, role-based decorators, `SECRET_KEY` from `.env`.
- Kiosk route `/kiosk/<classroom_id>` requires a login as admin/teacher **or** a `?key=<KIOSK_KEY>` from `.env`.
- Upload validation: allowed extensions (jpg, jpeg, png, zip), max size, image decode check. Use SQLAlchemy parameterised queries only. Escape all output (Jinja autoescape).

### Admin
- Dashboard: counts, today's attendance summary, camera health per classroom.
- CRUD: students, teachers (with user accounts), sections, courses, classrooms (including camera type/URL and a "Test camera" button showing a snapshot), timetable slots.
- Enrollment (7.1, 7.2), student CSV import.
- Settings: simulated time (5.1), thresholds, passive backend/enforce flag, early window, defaults.
- Quick session creator (5.2).
- Reports (Section 9), audit log viewer, recognition attempts viewer (with snapshots).

### Teacher
- Dashboard: today's sessions for their courses.
- Edit late/absent rules (5.6) for slots and sessions.
- Live session view: roster with status chips updating every few seconds (polling), count of present/late/pending.
- **Manual marking:** set `present|late|absent|excused` for any student in the session. A **reason is mandatory**. Writes the attendance row with `method=manual`, `marked_by_user_id`, and an `audit_log` entry with before/after values.
- **Unknown attempts list** for the session with snapshots; teacher can "assign to student" which performs an audited manual mark.
- Reports for their own courses (Section 9).

### Student
- Login, then a read-only view of their own attendance: per course percentage and a table of date/time/status. No editing, no correction requests, no visibility into other students.

### Kiosk page (`/kiosk/<classroom_id>`)
- Full-screen layout: mirrored live video, an oval face guide, large prompt text, a progress bar for the challenge, a clear result panel (green/red), the classroom name and current class name, and the clock (showing the simulated clock banner when active).
- Large readable fonts, high contrast, works at a distance. Audio beep on success is a COULD.

---

## 9. Reports (CSV and PDF)

Reports to implement:
1. **Session report:** roster with status, time, method (face/manual), similarity.
2. **Course/section report by date range:** matrix of students x dates plus totals.
3. **Student summary:** per student per course, attended / late / absent counts and percentage.
4. **Recognition attempts report (admin):** outcomes and counts, including spoof and unknown attempts.

Rules: filters (course, section, date range, student); CSV via the standard library; PDF via ReportLab with title, college name, generated-at (Clock time), table, and totals. Teachers see only their courses; students only themselves (as a web view, PDF optional).

---

## 10. API outline (JSON unless noted; all except kiosk state require login + role)

```
POST /login   GET /logout
GET  /kiosk/<classroom_id>                 (page)
GET  /kiosk/<classroom_id>/stream          (MJPEG)
GET  /api/kiosk/<classroom_id>/state
POST /api/enroll/<student_id>/capture      (image)
POST /api/enroll/bulk                      (files/zip)
DELETE /api/enroll/<student_id>
GET/POST/PUT/DELETE /api/students, /api/teachers, /api/sections, /api/courses,
                    /api/classrooms, /api/timetable
POST /api/classrooms/<id>/test-camera
POST /api/sessions/quick
GET  /api/sessions/<id>/roster
POST /api/sessions/<id>/rules              (teacher override)
POST /api/sessions/<id>/finalize
POST /api/attendance/manual                (session_id, student_id, status, reason)
POST /api/attempts/<id>/assign             (student_id, reason)
GET/POST /api/settings                     (admin)
POST /api/settings/sim-time                (admin)
GET  /reports/...                          (html/csv/pdf)
GET  /student/me/attendance
```

---

## 11. Configuration (`.env.example`)

```
FLASK_ENV=development
SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/face_attendance
KIOSK_KEY=change-me-too
TIMEZONE=Asia/Kathmandu
FACE_MODEL_PACK=buffalo_l        # buffalo_s for CPU-only
DET_SIZE=640
T_ACCEPT=0.45
T_MARGIN=0.05
PASSIVE_BACKEND=minifasnet       # minifasnet | heuristic | off
PASSIVE_THRESHOLD=0.7
PASSIVE_ENFORCE=true
CHALLENGE_TIMEOUT_S=12
EAR_CLOSED=0.21
EAR_OPEN=0.25
YAW_LOW=0.35
YAW_HIGH=0.65
BLUR_MIN=60
MIN_FACE_WIDTH=120
EARLY_WINDOW_MIN=10
DEFAULT_LATE_MIN=10
DEFAULT_ABSENT_MIN=30
```
Runtime-changeable values live in the `settings` table (the table overrides `.env` defaults). Document the phone setup in the README: install an IP camera app (such as IP Webcam on Android), start the server, read the URL like `http://192.168.x.x:8080/video`, paste it into the classroom's camera URL, press "Test camera". Phone and laptop must be on the same Wi-Fi. `scripts/check_camera.py <url>` prints resolution and fps.

---

## 12. Testing plan

### 12.1 Automated (pytest)
- **Clock:** real mode; simulated mode ticks forward from the anchor; turning it off returns to real time.
- **Status logic:** boundary tests at exactly `late_after`, `absent_after`, early arrival, and just after; invalid rule validation.
- **Matching:** synthetic embeddings: accept above threshold, reject below, ambiguity rejected by the margin rule, correct student chosen among many.
- **Liveness logic:** synthetic landmark sequences produce a blink, a non-blink (eyes stay open), and a head turn; challenge timeout works.
- **Attendance service:** unique constraint, duplicate check-in is a no-op, manual override writes an audit row, finalization is idempotent and marks absentees.
- **Auth:** each role can only reach its own routes; unauthenticated access redirects.
- **Enrollment:** quality gate rejects blurry/no-face/multi-face images; duplicate-identity warning fires.
Use a separate test database.

### 12.2 Calibration (`scripts/calibrate.py`)
- Using the enrolled photos of the demo students, compute **genuine** similarity scores (same person pairs) and **impostor** scores (different people pairs); output histograms and an ROC/DET style plot saved to `docs/figures/`; print the recommended `T_ACCEPT` at false accept rate <= 1% and the measured false reject rate. Use these numbers in the project report.

### 12.3 Manual test matrix (record results in `docs/TEST_REPORT.md`)

| # | Scenario | Expected |
|---|---|---|
| 1 | Enrolled student, good light, on time | Present, correct time |
| 2 | Same student, after late threshold | Late |
| 3 | After absent threshold | Window closed message, no row |
| 4 | Same student checks in twice | "Already marked", one row |
| 5 | Not-enrolled person | Unknown, attempt logged with snapshot |
| 6 | Printed photo of an enrolled student | Rejected (passive and/or no blink) |
| 7 | Phone screen showing the student's face | Rejected |
| 8 | Recorded video of the student on a phone screen | Rejected (random challenge) |
| 9 | Student fails to blink within the timeout | `active_liveness_failed` |
| 10 | Two people in frame | "One person at a time" |
| 11 | Dim light / backlight | Quality message, no false accept |
| 12 | Student from another section | `not_in_section` |
| 13 | Teacher marks manually | Row with method manual, reason, audit entry |
| 14 | Assign unknown attempt to student | Audited manual mark |
| 15 | Simulated time moved to start+12 min | Late behaviour reproducible |
| 16 | Session ends | Finalization marks absentees |
| 17 | Camera disconnect mid-session | Kiosk shows "Camera offline", recovers when back |
| 18 | Student login | Sees only own attendance |

### 12.4 Acceptance targets (10 enrolled people, normal indoor light)
- Genuine users accepted on the first try: `>= 90%`; within 3 tries: `>= 98%`.
- Impostor attempts (50 tries with non-enrolled faces or other students): **0 false accepts** after threshold calibration.
- Photo/screen spoof attempts rejected: `>= 90%` (report honestly what slips through).
- Total kiosk transaction time (face present to result): about 8–15 seconds including the challenge.
- Recognition step latency on CPU: under about 1.5 s per decision; GPU faster.

---

## 13. Documentation deliverables (for the BCA report and viva)

- `README.md`: setup, run, camera setup, demo script.
- `docs/ARCHITECTURE.md`: diagrams (Mermaid): system architecture, DFD level 0 and 1, use case diagram description, kiosk state machine, sequence diagram of one check-in.
- `docs/DATABASE.md`: ER diagram + table dictionary.
- `docs/ALGORITHMS.md`: each algorithm in Section 2 in plain language: what it does, why it was chosen, key formulas, parameters, known limitations, and likely examiner questions with short answers:
  - Why ArcFace/cosine similarity instead of comparing images or using a classifier?
  - How do you choose the threshold and what are FAR/FRR?
  - What happens with twins, masks, glasses, bad light?
  - How does liveness stop a photo? A video? A mask?
  - Why both active and passive checks?
  - How is privacy handled (embeddings only, retention, consent)?
  - How does it scale beyond 10 students?
- `docs/TEST_REPORT.md`: calibration plot, test matrix results, measured accuracy.
- `docs/USER_GUIDE.md`: short per-role guide with screenshots (screenshots added by the user).

---

## 14. Build phases (time-boxed; MUST = demo-critical, SHOULD = important, COULD = if time remains)

**Phase 0 — Setup (MUST).** Repo, venv, requirements, `.env`, app factory, DB connection, `init_db.py`, seed script (1 admin, 1 teacher, 1 section, 1 course, 1 classroom, demo students, sample timetable slot). 
*Exit check:* app starts, DB tables exist, login page loads, `check_camera.py` shows frames from the phone and the webcam.

**Phase 1 — Auth, roles, CRUD (MUST).** Login, role decorators, admin CRUD for students/teachers/sections/courses/classrooms/timetable, base layout.
*Exit check:* all three roles can log in and see only their own area; CRUD works; tests pass.

**Phase 2 — Face pipeline core (MUST).** `face_pipeline.py` (detect, align, embed), `quality.py`, `matching.py`, in-memory gallery. CLI sanity script that takes two images and prints similarity.
*Exit check:* same-person images score high, different people low; quality gate rejects bad images; GPU/CPU provider logged.

**Phase 3 — Enrollment (MUST).** Webcam capture page, bulk upload, CSV import, duplicate-identity check, gallery refresh.
*Exit check:* 5 test students enrolled with at least 5 templates each; bulk upload reports per-file results.

**Phase 4 — Clock, sessions, attendance rules (MUST).** `clock.py`, simulated time UI, timetable session creation, quick session creator, status logic, attendance service, finalization.
*Exit check:* status unit tests pass; quick session works; simulated time visibly changes late/present results.

**Phase 5 — Kiosk without liveness (MUST).** Camera service, MJPEG stream, kiosk page, state machine through IDENTIFYING and RESULT, attempt logging, cooldown.
*Exit check:* an enrolled student is marked present from the phone camera; an unknown face is logged and denied; duplicates handled. **Tag this commit `demo-safe-v1`.**

**Phase 6 — Active liveness (MUST).** MediaPipe landmarks, blink and yaw detectors, random challenge, re-verification, kiosk UI progress. Run `calibrate.py` and set thresholds.
*Exit check:* blink + turn challenge works live; a photo held up fails; thresholds tuned and recorded.

**Phase 7 — Passive anti-spoof (SHOULD).** MiniFASNet backend with the heuristic fallback and `PASSIVE_ENFORCE` flag.
*Exit check:* screen/photo spoofs lower the passive score; real faces pass; flag works.

**Phase 8 — Teacher tools (MUST).** Rule editing, live roster, manual marking with reason and audit, unknown-attempts assignment.
*Exit check:* manual override creates audit rows; teacher sees only their courses.

**Phase 9 — Student portal and reports (MUST for portal and session/summary reports; SHOULD for the rest).** Student read-only page; CSV and PDF exports.
*Exit check:* exports open correctly; the student sees only their own data.

**Phase 10 — Hardening and docs (SHOULD).** Camera offline/reconnect handling, upload validation, CSRF review, retention cleanup, README, docs, test report with real numbers, ER/DFD diagrams.
*Exit check:* full manual test matrix run and recorded; fresh-clone setup works from the README.

**COULD list (only if everything above is done):** forced password change, success beep, admin dashboard charts, pgvector, multiple simultaneous kiosks, dark mode.

**If time is nearly out, cut in this order:** COULD items, then PDF (keep CSV), then passive heuristic fallback polish, then reports beyond session/summary. **Never cut:** the Phase 5 demo-safe path, the active liveness, the audit log, and the quick session creator.

---

## 15. Demo script (rehearse this)

1. Show the admin dashboard and the classroom's camera test (phone feed).
2. Enroll one student live with the webcam (about 1 minute).
3. Start a quick session. Student walks to the kiosk: face, blink twice, head turn, "Present".
4. Same student again: "Already marked".
5. Unknown person tries: "Not recognized", then show the logged attempt with snapshot in the teacher view.
6. Hold up a photo / phone screen of the enrolled student: rejected.
7. Switch simulated time forward past the late threshold, another student checks in: "Late".
8. Teacher marks a student manually with a reason; show the audit log.
9. Finalize the session; show the absent student, then export the CSV/PDF report.
10. Log in as a student and show the personal view.

Prepare a backup: a screen recording of a successful run, and the laptop webcam path ready in case the phone stream drops.

---

## 16. Definition of done

- Phases marked MUST are complete with their exit checks passing.
- Automated tests pass; the manual test matrix is filled in with real results; calibration figures exist.
- A fresh clone can be set up from `README.md` in under 30 minutes.
- `docs/` contains everything listed in Section 13, written so the student can explain every component to an external examiner.
