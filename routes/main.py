"""Public pages: landing, about, and a health check."""
from flask import Blueprint, jsonify, render_template

from extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/about")
def about():
    return render_template("about.html")


@main_bp.get("/health")
def health():
    """Used to confirm the app and database are alive."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:
        return jsonify(status="error", database="unreachable"), 503
