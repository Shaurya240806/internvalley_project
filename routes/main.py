"""Public pages: landing, dashboard, about, and a health check."""
import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import login_required, current_user
from models import EncryptedFile, Transfer, User
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from extensions import db
from security.image_encryption import encrypt_image

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/about")
def about():
    return render_template("about.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    """Show upload, encryption, and transfer activity for the signed-in user."""
    user_files = EncryptedFile.query.filter_by(owner_id=current_user.id)
    user_transfers = Transfer.query.filter(
        (Transfer.sender_id == current_user.id) |
        (Transfer.recipient_id == current_user.id)
    )
    file_count = user_files.count()
    summary = {
        "images": file_count,
        "encrypted": file_count,
        "transfers": user_transfers.count(),
    }
    recent_activity = [
        SimpleNamespace(
            action="encrypt",
            detail=f"Encrypted {encrypted_file.original_filename}",
            created_at=encrypted_file.created_at,
        )
        for encrypted_file in user_files.order_by(
            EncryptedFile.created_at.desc()
        ).limit(5).all()
    ]
    users = User.query.all()
    remote_connections = user_transfers.order_by(
        Transfer.created_at.desc()
    ).limit(5).all()
    return render_template("dashboard.html", summary=summary,
                           recent_activity=recent_activity, username=current_user.username,
                           users=users, remote_connections=remote_connections)


@main_bp.post("/dashboard")
@login_required
def dashboard_submit():
    """Validate and encrypt an image, keeping only ciphertext on disk, and create a transfer."""
    uploaded = request.files.get("file")
    password = request.form.get("password", "")
    recipient_id = request.form.get("recipient_id")

    if not uploaded or not uploaded.filename:
        flash("Choose an image file before submitting the form.", "warning")
        return redirect(url_for("main.dashboard"))

    if len(password) < 8:
        flash("Use a password with at least 8 characters for stronger key protection.", "warning")
        return redirect(url_for("main.dashboard"))

    if not recipient_id or not recipient_id.isdigit():
        flash("Select a valid recipient.", "warning")
        return redirect(url_for("main.dashboard"))

    recipient = User.query.get(int(recipient_id))
    if not recipient or recipient.id == current_user.id:
        flash("Select a valid recipient (not yourself).", "warning")
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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")

        # Record the owner so dashboard activity stays account-specific.
        encrypted_file = EncryptedFile(
            owner_id=current_user.id,
            recipient_id=recipient.id,
            original_filename=original_name,
            encrypted_filename=encrypted_name,
            algorithm="AES-256-GCM",
            size_bytes=len(image_data),
        )
        db.session.add(encrypted_file)
        db.session.flush()  # get encrypted_file.id
        transfer = Transfer(
            encrypted_file_id=encrypted_file.id,
            sender_id=current_user.id,
            recipient_id=recipient.id,
        )
        db.session.add(transfer)
        db.session.commit()
    except OSError:
        encrypted_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        current_app.logger.exception("Could not save encrypted upload")
        flash("The encrypted image could not be saved. Please try again.", "error")
        return redirect(url_for("main.dashboard"))

    flash(f"Image encrypted and securely transferred to {recipient.username}.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.get("/health")
def health():
    """Used to confirm the app and database are alive."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:
        return jsonify(status="error", database="unreachable"), 503
