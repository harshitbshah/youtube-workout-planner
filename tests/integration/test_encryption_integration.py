"""
test_encryption_integration.py — Encryption round-trip through real PostgreSQL.

Verifies that:
  - What goes into the DB column is a Fernet ciphertext, never plaintext
  - Reading back the raw column value and decrypting returns the original token
  - The plaintext token is unrecoverable without the ENCRYPTION_KEY

These tests require a real DB because they inspect the raw column bytes as
stored by the PostgreSQL driver, not what SQLAlchemy returns to Python.
"""

from sqlalchemy import text

from api.crypto import decrypt, encrypt
from api.models import UserCredentials


PLAINTEXT_TOKEN = "1//test-refresh-token-plaintext"


def test_stored_token_is_not_plaintext(db_session, make_user):
    """The raw DB column must never contain the plaintext token."""
    user = make_user()
    creds = UserCredentials(
        user_id=user.id,
        youtube_refresh_token=encrypt(PLAINTEXT_TOKEN),
    )
    db_session.add(creds)
    db_session.commit()

    raw = db_session.execute(
        text("SELECT youtube_refresh_token FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()

    assert raw != PLAINTEXT_TOKEN
    assert PLAINTEXT_TOKEN not in (raw or "")


def test_stored_token_is_fernet_ciphertext(db_session, make_user):
    """Fernet ciphertexts always start with 'gAAAAA' (base64-encoded version byte)."""
    user = make_user()
    creds = UserCredentials(
        user_id=user.id,
        youtube_refresh_token=encrypt(PLAINTEXT_TOKEN),
    )
    db_session.add(creds)
    db_session.commit()

    raw = db_session.execute(
        text("SELECT youtube_refresh_token FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()

    assert raw.startswith("gAAAAA")


def test_encrypted_token_decrypts_correctly(db_session, make_user):
    """Reading back the ciphertext and decrypting must return the original token."""
    user = make_user()
    creds = UserCredentials(
        user_id=user.id,
        youtube_refresh_token=encrypt(PLAINTEXT_TOKEN),
    )
    db_session.add(creds)
    db_session.commit()

    raw = db_session.execute(
        text("SELECT youtube_refresh_token FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()

    assert decrypt(raw) == PLAINTEXT_TOKEN


def test_anthropic_key_stored_encrypted(db_session, make_user):
    """anthropic_key column follows the same encryption contract."""
    plaintext_key = "sk-ant-api03-test-key"
    user = make_user()
    creds = UserCredentials(
        user_id=user.id,
        anthropic_key=encrypt(plaintext_key),
    )
    db_session.add(creds)
    db_session.commit()

    raw = db_session.execute(
        text("SELECT anthropic_key FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()

    assert raw != plaintext_key
    assert decrypt(raw) == plaintext_key


def test_null_token_stored_as_null(db_session, make_user):
    """If no refresh token was provided, the column must be NULL, not an empty string."""
    user = make_user()
    creds = UserCredentials(user_id=user.id)   # no token
    db_session.add(creds)
    db_session.commit()

    raw = db_session.execute(
        text("SELECT youtube_refresh_token FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()

    assert raw is None
