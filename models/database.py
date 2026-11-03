"""Database tables (SQLAlchemy models).

IMPORTANT security rule: this database never stores passwords, plaintext AES
keys, or plaintext RSA private keys. It stores only:
  * password HASHES,
  * public keys,
  * private keys that are already ENCRYPTED with the user's password,
  * AES keys that are already WRAPPED (encrypted) with an RSA public key.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Algorithm:
    AES_GCM = "AES-256-GCM"
    RSA_HYBRID = "RSA-OAEP + AES-256-GCM"
    DES_DEMO = "DES-CBC (demo, insecure)"


class TransferStatus:
    PENDING = "Pending"
    RECEIVED = "Received"
    DOWNLOADED = "Downloaded"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    keypair = db.relationship("RSAKeyPair", back_populates="user",
                              uselist=False, cascade="all, delete-orphan")
    images = db.relationship("UploadedImage", back_populates="owner",
                             cascade="all, delete-orphan")
    activities = db.relationship("ActivityLog", back_populates="user",
                                 cascade="all, delete-orphan")

    # Usernames/emails are stored lowercase so "Admin" and "admin" cannot
    # both exist (prevents look-alike impersonation).
    @validates("username", "email")
    def _normalise(self, _key, value):
        return value.strip().lower()

    def set_password(self, password: str) -> None:
        # Werkzeug uses a salted, slow hash (scrypt) - never plain text.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class RSAKeyPair(db.Model):
    __tablename__ = "rsa_keypairs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True,
                        nullable=False)
    public_key_pem = db.Column(db.Text, nullable=False)
    # Private key PEM, encrypted with a key derived from the user's password.
    encrypted_private_key = db.Column(db.LargeBinary, nullable=False)
    key_bits = db.Column(db.Integer, nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)  # SHA-256 of public key
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="keypair")


class UploadedImage(db.Model):
    __tablename__ = "uploaded_images"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                        index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(64), unique=True, nullable=False)  # random
    mime_type = db.Column(db.String(32), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="images")


class EncryptedFile(db.Model):
    __tablename__ = "encrypted_files"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                         index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    source_image_id = db.Column(db.Integer, db.ForeignKey("uploaded_images.id"))
    original_filename = db.Column(db.String(255), nullable=False)
    encrypted_filename = db.Column(db.String(64), unique=True, nullable=False)
    algorithm = db.Column(db.String(40), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    # RSA-wrapped AES key (safe to store: only the recipient's private key opens it)
    wrapped_key = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", foreign_keys=[owner_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


class Transfer(db.Model):
    __tablename__ = "transfers"

    id = db.Column(db.Integer, primary_key=True)
    encrypted_file_id = db.Column(db.Integer, db.ForeignKey("encrypted_files.id"),
                                  nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                          index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                             index=True)
    status = db.Column(db.String(12), default=TransferStatus.PENDING, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    received_at = db.Column(db.DateTime)
    downloaded_at = db.Column(db.DateTime)

    encrypted_file = db.relationship("EncryptedFile")
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


class ActivityLog(db.Model):
    """Audit trail shown on the dashboard. Never put secrets in `detail`."""
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                        index=True)
    action = db.Column(db.String(32), nullable=False)   # e.g. "login", "encrypt"
    detail = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="activities")


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login calls this on every request to turn the session's user id
    back into a User object."""
    return db.session.get(User, int(user_id))


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    # SQLite ignores foreign keys unless asked. This makes it enforce them.
    import sqlite3
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
