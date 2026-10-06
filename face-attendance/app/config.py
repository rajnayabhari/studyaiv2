import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-default'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    KIOSK_KEY = os.environ.get('KIOSK_KEY')
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kathmandu')
