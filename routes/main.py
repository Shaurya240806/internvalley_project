"""Public pages: landing, dashboard, about, and a health check."""
import json
import uuid
from io import BytesIO
from pathlib import Path

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from extensions import db
from models import ActivityLog, EncryptedFile, Transfer, UploadedImage
from security.image_encryption import encrypt_image

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/about")
def about():
    return render_template("about.html")


@main_bp.get("/dashboard")
def dashboard():
    """A quick overview of saved uploads, ciphertext, and real transfers."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    encrypted_folder = current_app.config["ENCRYPTED_FOLDER"]
    summary = {
        "images": sum(1 for _ in upload_folder.glob("*.json")),
        "encrypted": sum(1 for _ in encrypted_folder.glob("*.cvlt")),
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
    """Validate and encrypt an image, keeping only ciphertext on disk."""
    uploaded = request.files.get("file")
    password = request.form.get("password", "")

    if not uploaded or not uploaded.filename:
        flash("Choose an image file before submitting the form.", "warning")
        return redirect(url_for("main.dashboard"))

    if len(password) < 8:
        flash("Use a password with at least 8 characters for stronger key protection.", "warning")
        return redirect(url_for("main.dashboard"))

    original_name = secure_filename(uploaded.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in current_app.config["ALLOWED_EXTENSIONS"]:
        flash("Choose a JPG, PNG, or WebP image.", "warning")
        return redirect(url_for("main.dashboard"))

    image_data = uploaded.read()
    try:
        image = Image.open(BytesIO(image_data))
        image_format = image.format
        width, height = image.size
        image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        flash("The selected file is not a valid image.", "warning")
        return redirect(url_for("main.dashboard"))

    expected_formats = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
    if image_format != expected_formats.get(extension):
        flash("The image content does not match its file extension.", "warning")
        return redirect(url_for("main.dashboard"))

    artifact_id = uuid.uuid4().hex
    encrypted_name = f"{artifact_id}.cvlt"
    metadata_name = f"{artifact_id}.json"
    encrypted_path = current_app.config["ENCRYPTED_FOLDER"] / encrypted_name
    metadata_path = current_app.config["UPLOAD_FOLDER"] / metadata_name

    try:
        encrypted_path.write_bytes(encrypt_image(image_data, password))
        metadata_path.write_text(json.dumps({
            "filename": original_name,
            "size_bytes": len(image_data),
            "width": width,
            "height": height,
            "encrypted_filename": encrypted_name,
        }), encoding="utf-8")
    except OSError:
        encrypted_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        current_app.logger.exception("Could not save encrypted upload")
        flash("The encrypted image could not be saved. Please try again.", "error")
        return redirect(url_for("main.dashboard"))

    flash("Image encrypted and saved successfully. No transfer was created because no recipient was selected.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.get("/health")
def health():
    """Used to confirm the app and database are alive."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:
        return jsonify(status="error", database="unreachable"), 503
