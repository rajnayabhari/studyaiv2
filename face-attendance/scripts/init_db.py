import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from urllib.parse import urlparse

# Add parent dir to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.config import Config

def create_database_if_not_exists(db_uri):
    # Parse DB URI
    result = urlparse(db_uri)
    username = result.username or 'postgres'
    password = result.password or 'postgres'
    database = result.path[1:]
    hostname = result.hostname or 'localhost'
    port = result.port or 5432

    # Connect to the default 'postgres' database to create the new database
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{database}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database {database}...")
            cursor.execute(f'CREATE DATABASE {database}')
            print("Database created successfully.")
        else:
            print(f"Database {database} already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to create database automatically: {e}")
        print("You may need to create it manually in psql or pgAdmin.")

def init_db():
    app = create_app()
    with app.app_context():
        # Models must be imported for create_all to find them
        from app import models
        print("Creating tables...")
        db.create_all()
        print("Database initialization complete.")

if __name__ == '__main__':
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    if db_uri:
        create_database_if_not_exists(db_uri)
    init_db()
