"""
Tests for api/crypto.py — encryption/decryption of credential fields.

Covers:
  - Round-trip integrity
  - Plaintext is never the ciphertext
  - Wrong key raises InvalidToken (not silent corruption)
  - Missing ENCRYPTION_KEY raises RuntimeError at call time
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from api.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    assert decrypt(encrypt("my-youtube-refresh-token")) == "my-youtube-refresh-token"


def test_encrypt_produces_non_plaintext():
    plaintext = "my-youtube-refresh-token"
    assert encrypt(plaintext) != plaintext


def test_two_encryptions_of_same_value_differ():
    # Fernet uses a random IV — same plaintext should produce different ciphertexts
    value = "my-token"
    assert encrypt(value) != encrypt(value)


def test_decrypt_wrong_key_raises_invalid_token():
    ciphertext = encrypt("my-token")
    wrong_key = Fernet.generate_key().decode()
    with patch.dict(os.environ, {"ENCRYPTION_KEY": wrong_key}):
        with pytest.raises(InvalidToken):
            decrypt(ciphertext)


def test_missing_encryption_key_raises_runtime_error():
    env = {k: v for k, v in os.environ.items() if k != "ENCRYPTION_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            encrypt("anything")


def test_missing_encryption_key_on_decrypt_raises_runtime_error():
    ciphertext = encrypt("my-token")
    env = {k: v for k, v in os.environ.items() if k != "ENCRYPTION_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            decrypt(ciphertext)
