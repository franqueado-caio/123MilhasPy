# app/__init__.py
from flask import Flask
from flask_cors import CORS
import os

# Pega o diretório raiz do projeto (onde está o app.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )

    # Configuração básica
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "123milhas-secret-key")
    app.config["CORS_HEADERS"] = "Content-Type"

    CORS(app)

    # Registrar blueprints
    try:
        from app.routes.main_routes import main_bp
        from app.routes.tracking_routes import tracking_bp
        from app.routes.transfer_routes import transfer_bp
        from app.routes.chat_routes import chat_bp
        from app.routes.admin_routes import admin_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(tracking_bp, url_prefix="/api/tracking")
        app.register_blueprint(transfer_bp, url_prefix="/api/transfer")
        app.register_blueprint(chat_bp, url_prefix="/api/chat")
        app.register_blueprint(admin_bp, url_prefix="/api/admin")

        print("✅ Blueprints registrados com sucesso!")
        print(f"📁 Templates: {app.template_folder}")
        print(f"📁 Static: {app.static_folder}")
    except ImportError as e:
        print(f"⚠️ Erro ao importar blueprints: {e}")

    return app
