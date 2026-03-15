"""
crypto.py - Symmetric encryption for sensitive credential fields.

Uses Fernet (AES-128-CBC + HMAC-SHA256 via the `cryptography` library).
The encryption key lives in the ENCRYPTION_KEY environment variable - never in the DB.

Key management:
  Generate:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  Store:     .env locally, Railway secret in production
  Rotate:    re-encrypt all rows with the new key before retiring the old one

Attack surface:
  DB leak alone → attacker gets ciphertext blobs, useless without the key
  Key leak alone → rotate key, re-encrypt; no tokens exposed yet
  Both leaked  → tokens exposed; revoke affected YouTube OAuth tokens immediately
"""

import os

from cryptography.fernet import Fernet, InvalidToken  # noqa: F401 - re-exported for callers


def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string → URL-safe base64 ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string → original plaintext.
    Raises cryptography.fernet.InvalidToken if the ciphertext is tampered or the wrong key is used.
    """
    return _get_fernet().decrypt(ciphertext.encode()).decode()
