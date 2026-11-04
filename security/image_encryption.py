"""Password-based authenticated encryption for uploaded image bytes."""
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_MAGIC = b"CVLT1"
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KEY_SIZE = 32
_ITERATIONS = 600_000


def encrypt_image(data: bytes, password: str) -> bytes:
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_SIZE,
        salt=salt,
        iterations=_ITERATIONS,
    ).derive(password.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(nonce, data, _MAGIC)
    return _MAGIC + salt + nonce + ciphertext