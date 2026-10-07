from flask import Flask
from .config import Config
from .extensions import db, login_manager, csrf

def create_app(config_class=Config, test_config=None):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if test_config:
        app.config.update(test_config)

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from .admin import admin_bp
    app.register_blueprint(admin_bp)
    
    from .teacher import teacher_bp
    app.register_blueprint(teacher_bp)
    
    from .student import student_bp
    app.register_blueprint(student_bp)
    
    from .api import api_bp
    app.register_blueprint(api_bp)
    
    from .kiosk import kiosk_bp
    app.register_blueprint(kiosk_bp)
    
    @app.route('/health')
    def health():
        return {"status": "ok"}
        
    return app
