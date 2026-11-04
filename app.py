"""Application factory and entry point.

An "app factory" is a function that builds a fresh Flask app. Tests use it to
get an isolated app with a throw-away in-memory database.

Run:   python app.py        (or)        flask --app app run
"""
import os

import click
from flask import Flask, render_template
from flask_wtf.csrf import generate_csrf

from config import CONFIG_MAP
from extensions import csrf, db, limiter, login_manager


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    config_cls = CONFIG_MAP.get(config_name, CONFIG_MAP["development"])
    config_cls.validate()

    app = Flask(__name__)
    app.config.from_object(config_cls)

    # Create the private folders (not under static/, so never served publicly)
    for folder in ("UPLOAD_FOLDER", "ENCRYPTED_FOLDER"):
        app.config[folder].mkdir(parents=True, exist_ok=True)
    (app.config["BASE_DIR"] / "instance").mkdir(exist_ok=True)

    # Attach extensions
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"   # blueprint arrives in Phase 2
    login_manager.session_protection = "strong"

    import models  # noqa: F401  (registers tables with SQLAlchemy)
    from routes.main import main_bp
    app.register_blueprint(main_bp)

    register_error_handlers(app)
    register_security_headers(app, config_cls)
    register_cli(app)

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {
            "app_name": app.config["APP_NAME"],
            "year": datetime.now().year,
            "csrf_token_value": generate_csrf(),
        }

    with app.app_context():
        db.create_all()   # creates any missing tables (safe to run repeatedly)

    return app


def register_security_headers(app: Flask, config_cls) -> None:
    @app.after_request
    def add_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
            "script-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        if config_cls.SESSION_COOKIE_SECURE:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        return resp


def register_error_handlers(app: Flask) -> None:
    messages = {
        403: "You do not have permission to access this resource.",
        404: "The page you requested does not exist.",
        413: "The uploaded file is too large (limit: 10 MB).",
        429: "Too many requests. Please slow down and try again later.",
    }

    def make_handler(code):
        def handler(_err):
            return render_template("error.html", code=code,
                                   message=messages[code]), code
        return handler

    for code in messages:
        app.register_error_handler(code, make_handler(code))

    @app.errorhandler(500)
    def server_error(_err):
        db.session.rollback()
        # Generic message: never leak stack traces or internals to users.
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables:  flask --app app init-db"""
        db.create_all()
        click.echo("Database initialised.")


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
