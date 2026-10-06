"""Application factory."""
import logging
import os

from flask import Flask

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.makedirs(os.path.join(app.config["UPLOAD_DIR"], "attempts"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models)

    @login_manager.user_loader
    def load_user(user_id):
        u = db.session.get(models.User, int(user_id))
        return u if u and u.is_active else None

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    return app
