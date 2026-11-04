"""Application configuration, read from environment variables.

Why this file exists: secrets (like SECRET_KEY) must never be hard-coded in
source code. They live in a ".env" file or the server's environment instead.
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    BASE_DIR = BASE_DIR
    APP_NAME = "CypherVault"

    # Development fallback: a random key per run (sessions reset on restart).
    # It is random, never a fixed string in the source code.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + (BASE_DIR / "instance" / "app.db").as_posix()
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Folders for user files (outside static/, so they are never served directly)
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    ENCRYPTED_FOLDER = BASE_DIR / "encrypted_files"

    # Upload limits: Flask rejects larger requests with HTTP 413
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MiB
    ALLOWED_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})

    # Cookie / session hardening
    SESSION_COOKIE_HTTPONLY = True      # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"     # blocks most cross-site request forgery
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    REMEMBER_COOKIE_HTTPONLY = True

    WTF_CSRF_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_ENABLED = True

    # Cryptographic parameters (used from Phase 3)
    RSA_KEY_BITS = 3072

    @classmethod
    def validate(cls) -> None:
        """Hook for configs that need to refuse to start when misconfigured."""


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_SECURE = True  # HTTPS only

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in production.")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
