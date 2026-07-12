"""Symmetric encryption for storing GitHub OAuth tokens in the DB.

The Fernet key is read from the FERNET_KEY env var. Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
and put it in .env. Never commit it.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.getenv("FERNET_KEY")
        if not key:
            raise RuntimeError(
                "FERNET_KEY env var is not set. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(token: str) -> bytes:
    if not token:
        return b""
    return _get_fernet().encrypt(token.encode())


def decrypt_token(blob) -> str:
    """Decrypt a stored token blob. Returns "" if the blob is empty/invalid
    (e.g. key was rotated). Callers should treat empty as 'no token' and
    force re-login."""
    if not blob:
        return ""
    if isinstance(blob, str):
        blob = blob.encode()
    try:
        return _get_fernet().decrypt(blob).decode()
    except InvalidToken:
        return ""
