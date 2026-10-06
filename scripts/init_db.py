"""Create the database (if missing) and all tables.
Usage: python scripts/init_db.py [--drop]
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402


def ensure_database(url_str):
    url = make_url(url_str)
    conn = psycopg2.connect(dbname="postgres", user=url.username, password=url.password,
                            host=url.host or "localhost", port=url.port or 5432)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (url.database,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            print(f"Created database {url.database}")
    conn.close()


def main():
    ensure_database(Config.SQLALCHEMY_DATABASE_URI)
    app = create_app()
    with app.app_context():
        if "--drop" in sys.argv:
            db.drop_all()
            print("Dropped all tables")
        db.create_all()
        print("Tables:", ", ".join(sorted(db.metadata.tables)))


if __name__ == "__main__":
    main()
