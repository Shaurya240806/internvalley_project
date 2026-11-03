"""Public pages: landing, dashboard, about, and a health check."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import ActivityLog, EncryptedFile, Transfer, UploadedImage

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/about")
def about():
    return render_template("about.html")


@main_bp.get("/dashboard")
def dashboard():
    """A quick overview of files, transfers and recent activity."""
    summary = {
        "images": db.session.query(UploadedImage).count(),
        "encrypted": db.session.query(EncryptedFile).count(),
        "transfers": db.session.query(Transfer).count(),
    }
    recent_activity = (
        db.session.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("dashboard.html", summary=summary,
                           recent_activity=recent_activity)


@main_bp.post("/dashboard")
def dashboard_submit():
    """Lightweight demo upload flow used to validate the next-step UX."""
    uploaded = request.files.get("file")
    password = request.form.get("password", "")

    if not uploaded or not uploaded.filename:
        flash("Choose an image file before submitting the form.", "warning")
        return redirect(url_for("main.dashboard"))

    if len(password) < 8:
        flash("Use a password with at least 8 characters for stronger key protection.", "warning")
        return redirect(url_for("main.dashboard"))

    flash("Secure upload flow prepared successfully. Encryption and transfer logic can now be connected to the dashboard.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.get("/health")
def health():
    """Used to confirm the app and database are alive."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:
        return jsonify(status="error", database="unreachable"), 503
