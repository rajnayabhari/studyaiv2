"""Configuration loaded from environment (.env). Runtime-changeable values
are later overridden by the `settings` table."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    return int(os.getenv(name, default))


def _float(name, default):
    return float(os.getenv(name, default))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    KIOSK_KEY = os.getenv("KIOSK_KEY", "")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kathmandu")
    COLLEGE_NAME = os.getenv("COLLEGE_NAME", "College")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _int("PORT", 5001)

    UPLOAD_DIR = os.path.join(BASE_DIR, "instance", "uploads")
    MAX_CONTENT_LENGTH = _int("MAX_UPLOAD_MB", 50) * 1024 * 1024

    # Face pipeline
    FACE_MODEL_PACK = os.getenv("FACE_MODEL_PACK", "buffalo_l")
    DET_SIZE = _int("DET_SIZE", 640)
    DET_MIN_SCORE = _float("DET_MIN_SCORE", 0.6)
    T_ACCEPT = _float("T_ACCEPT", 0.45)
    T_MARGIN = _float("T_MARGIN", 0.05)
    PASSIVE_BACKEND = os.getenv("PASSIVE_BACKEND", "minifasnet")
    PASSIVE_THRESHOLD = _float("PASSIVE_THRESHOLD", 0.7)
    PASSIVE_ENFORCE = _bool("PASSIVE_ENFORCE", True)
    CHALLENGE_TIMEOUT_S = _int("CHALLENGE_TIMEOUT_S", 12)
    EAR_CLOSED = _float("EAR_CLOSED", 0.21)
    EAR_OPEN = _float("EAR_OPEN", 0.25)
    YAW_LOW = _float("YAW_LOW", 0.35)
    YAW_HIGH = _float("YAW_HIGH", 0.65)
    BLUR_MIN = _float("BLUR_MIN", 60)
    MIN_FACE_WIDTH = _int("MIN_FACE_WIDTH", 120)

    # Timetable
    EARLY_WINDOW_MIN = _int("EARLY_WINDOW_MIN", 10)
    DEFAULT_LATE_MIN = _int("DEFAULT_LATE_MIN", 10)
    DEFAULT_ABSENT_MIN = _int("DEFAULT_ABSENT_MIN", 30)
    ATTEMPT_RETENTION_DAYS = _int("ATTEMPT_RETENTION_DAYS", 30)


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
