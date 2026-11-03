import pytest
from sqlalchemy.exc import IntegrityError

from config import CONFIG_MAP, DevelopmentConfig, ProductionConfig
from extensions import db
from models import (ActivityLog, Algorithm, EncryptedFile, RSAKeyPair,
                    Transfer, TransferStatus, UploadedImage, User)


# ---------- pages ----------
def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Secure Image Encryption" in r.data
    assert b"How it works" in r.data and b"Security features" in r.data


def test_about_page_has_comparison(client):
    r = client.get("/about")
    assert r.status_code == 200 and b"AES vs DES vs RSA" in r.data


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json == {"status": "ok", "database": "ok"}


def test_static_assets_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200


def test_404_page_is_friendly(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404 and b"does not exist" in r.data


def test_uploads_folders_not_web_accessible(client):
    assert client.get("/uploads/x.png").status_code == 404
    assert client.get("/encrypted_files/x.bin").status_code == 404


# ---------- security headers / config ----------
def test_security_headers(client):
    h = client.get("/").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in h["Content-Security-Policy"]


def test_no_inline_scripts_or_styles(client):
    html = client.get("/").get_data(as_text=True)
    assert "<script>" not in html and "style=" not in html  # CSP-friendly


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError):
        ProductionConfig.validate()


def test_dev_secret_key_is_random_not_hardcoded():
    assert len(DevelopmentConfig.SECRET_KEY) >= 32
    import inspect, config
    assert "dev-secret" not in inspect.getsource(config)


def test_cookie_and_csrf_settings():
    assert DevelopmentConfig.SESSION_COOKIE_HTTPONLY is True
    assert DevelopmentConfig.SESSION_COOKIE_SAMESITE == "Lax"
    assert DevelopmentConfig.WTF_CSRF_ENABLED is True
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert DevelopmentConfig.MAX_CONTENT_LENGTH == 10 * 1024 * 1024
    assert set(CONFIG_MAP) == {"development", "testing", "production"}


def test_oversized_upload_rejected(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 100
    r = client.post("/", data={"f": b"x" * 5000})
    assert r.status_code in (413, 405)


# ---------- database models ----------
def make_user(name="alice", email="alice@example.com", pw="Str0ng!Passw0rd"):
    u = User(username=name, email=email)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    return u


def test_password_is_hashed_and_verifiable(app):
    with app.app_context():
        u = make_user()
        assert u.password_hash != "Str0ng!Passw0rd"
        assert "Str0ng" not in u.password_hash
        assert u.check_password("Str0ng!Passw0rd")
        assert not u.check_password("wrong")


def test_same_password_gives_different_hashes(app):
    with app.app_context():
        a = make_user("a", "a@x.com")
        b = make_user("b", "b@x.com")
        assert a.password_hash != b.password_hash  # unique salts


def test_username_and_email_normalised(app):
    with app.app_context():
        u = make_user("  Alice ", "Alice@Example.COM ")
        assert u.username == "alice" and u.email == "alice@example.com"


def test_unique_username_and_email(app):
    with app.app_context():
        make_user()
        for name, email in (("alice", "other@x.com"), ("other", "alice@example.com"),
                            ("ALICE", "third@x.com")):
            dup = User(username=name, email=email)
            dup.set_password("x")
            db.session.add(dup)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


def test_all_relationships_round_trip(app):
    with app.app_context():
        a, b = make_user("a", "a@x.com"), make_user("b", "b@x.com")
        img = UploadedImage(user_id=a.id, original_filename="cat.png",
                            stored_filename="abc123", mime_type="image/png",
                            size_bytes=10)
        db.session.add(img); db.session.commit()
        enc = EncryptedFile(owner_id=a.id, recipient_id=b.id, source_image_id=img.id,
                            original_filename="cat.png", encrypted_filename="enc1",
                            algorithm=Algorithm.RSA_HYBRID, size_bytes=40,
                            wrapped_key=b"wrapped")
        db.session.add(enc); db.session.commit()
        t = Transfer(encrypted_file_id=enc.id, sender_id=a.id, recipient_id=b.id)
        db.session.add_all([t, ActivityLog(user_id=a.id, action="encrypt"),
                            RSAKeyPair(user_id=a.id, public_key_pem="pem",
                                       encrypted_private_key=b"blob", key_bits=3072,
                                       fingerprint="f" * 64)])
        db.session.commit()
        assert t.status == TransferStatus.PENDING
        assert t.sender.username == "a" and t.recipient.username == "b"
        assert a.keypair.key_bits == 3072 and len(a.images) == 1
        assert enc.created_at is not None


def test_foreign_keys_enforced(app):
    with app.app_context():
        db.session.add(UploadedImage(user_id=999, original_filename="x",
                                     stored_filename="y", mime_type="image/png",
                                     size_bytes=1))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_user_loader(app):
    with app.app_context():
        from models.database import load_user
        u = make_user()
        assert load_user(str(u.id)).id == u.id
        assert load_user("9999") is None
