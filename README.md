# CipherVault - Secure Image Encryption (Flask)

Full README is written in Phase 7. Quick start:

    python -m venv .venv
    # Windows:  .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    copy .env.example .env        (macOS/Linux: cp .env.example .env)
    python -m flask --app app init-db
    python app.py                 # open http://127.0.0.1:5000
    python -m pytest -q
