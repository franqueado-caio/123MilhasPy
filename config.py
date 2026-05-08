import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Configurações básicas
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-123milhas"

    # Banco de dados
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///123milhas.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }

    # Configurações de tracking
    TRACKING_TOKEN_EXPIRY = timedelta(days=30)
    TRACKING_COOKIE_NAME = "123milhas_track"

    # Configurações de sessão
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_SECURE", "False") == "True"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Timezone Brasil
    TIMEZONE = "America/Sao_Paulo"


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
