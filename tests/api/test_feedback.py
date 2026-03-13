"""
tests/api/test_feedback.py — Unit tests for POST /feedback and send_feedback_email.

Mocks resend.Emails.send so no real network calls are made.
"""

import os
from unittest.mock import patch

import pytest

from tests.api.helpers import make_mock_user as _make_user

_FEEDBACK_ENV = {"RESEND_API_KEY": "re_test123", "ADMIN_EMAIL": "admin@example.com"}


# ─── POST /feedback — router tests ────────────────────────────────────────────

def test_submit_feedback_happy_path(auth_client):
    """Returns 204 on valid category + message."""
    client, user = auth_client
    with patch("api.routers.feedback.send_feedback_email") as mock_send:
        resp = client.post("/feedback", json={"category": "feedback", "message": "Great app!"})
    assert resp.status_code == 204
    mock_send.assert_called_once_with(user, "feedback", "Great app!")


def test_submit_feedback_all_valid_categories(auth_client):
    """All three valid categories return 204."""
    client, user = auth_client
    for category in ("feedback", "help", "bug"):
        with patch("api.routers.feedback.send_feedback_email"):
            resp = client.post("/feedback", json={"category": category, "message": "test"})
        assert resp.status_code == 204, f"Expected 204 for category={category}"


def test_submit_feedback_invalid_category(auth_client):
    """Returns 400 for an unrecognised category."""
    client, user = auth_client
    resp = client.post("/feedback", json={"category": "spam", "message": "hello"})
    assert resp.status_code == 400
    assert "Invalid category" in resp.json()["detail"]


def test_submit_feedback_empty_message(auth_client):
    """Returns 400 when message is blank or whitespace-only."""
    client, user = auth_client
    for msg in ("", "   ", "\t\n"):
        resp = client.post("/feedback", json={"category": "feedback", "message": msg})
        assert resp.status_code == 400, f"Expected 400 for message={repr(msg)}"


def test_submit_feedback_unauthenticated(client):
    """Returns 401 when not authenticated."""
    resp = client.post("/feedback", json={"category": "feedback", "message": "hello"})
    assert resp.status_code == 401


def test_submit_feedback_trims_whitespace(auth_client):
    """Message is trimmed before being forwarded."""
    client, user = auth_client
    with patch("api.routers.feedback.send_feedback_email") as mock_send:
        resp = client.post("/feedback", json={"category": "bug", "message": "  crash  "})
    assert resp.status_code == 204
    mock_send.assert_called_once_with(user, "bug", "crash")


def test_submit_feedback_email_failure_returns_503(auth_client):
    """Returns 503 when send_feedback_email raises RuntimeError."""
    client, user = auth_client
    with patch(
        "api.routers.feedback.send_feedback_email",
        side_effect=RuntimeError("Resend down"),
    ):
        resp = client.post("/feedback", json={"category": "help", "message": "Need help"})
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


# ─── send_feedback_email — service tests ──────────────────────────────────────

def test_feedback_email_sent_to_admin():
    """send_feedback_email sends to ADMIN_EMAIL, not the user."""
    with patch.dict(os.environ, _FEEDBACK_ENV), patch("api.services.email.resend") as mock_resend:
        from api.services.email import send_feedback_email
        send_feedback_email(_make_user(), "feedback", "Great app!")
    assert mock_resend.Emails.send.call_args[0][0]["to"] == "admin@example.com"


def test_feedback_email_reply_to_is_user_email():
    """reply_to is set to the user's email so admin can reply directly."""
    with patch.dict(os.environ, _FEEDBACK_ENV), patch("api.services.email.resend") as mock_resend:
        from api.services.email import send_feedback_email
        send_feedback_email(_make_user(email="user@example.com"), "help", "Need help")
    assert mock_resend.Emails.send.call_args[0][0]["reply_to"] == "user@example.com"


def test_feedback_email_subject_includes_category_label():
    """Subject line contains the human-readable category label."""
    with patch.dict(os.environ, _FEEDBACK_ENV), patch("api.services.email.resend") as mock_resend:
        from api.services.email import send_feedback_email
        send_feedback_email(_make_user(), "bug", "It crashed")
    subject = mock_resend.Emails.send.call_args[0][0]["subject"]
    assert "bug" in subject.lower() or "Found a bug" in subject


def test_feedback_email_html_contains_message():
    """HTML body includes the feedback message text."""
    with patch.dict(os.environ, _FEEDBACK_ENV), patch("api.services.email.resend") as mock_resend:
        from api.services.email import send_feedback_email
        send_feedback_email(_make_user(), "feedback", "This is my feedback message")
    assert "This is my feedback message" in mock_resend.Emails.send.call_args[0][0]["html"]


def test_feedback_email_raises_when_api_key_missing():
    """Raises RuntimeError when RESEND_API_KEY is not set."""
    env = {k: v for k, v in os.environ.items() if k != "RESEND_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        from api.services.email import send_feedback_email
        with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
            send_feedback_email(_make_user(), "feedback", "test")


def test_feedback_email_display_name_fallback():
    """When display_name is None, email prefix is used in the subject."""
    with patch.dict(os.environ, _FEEDBACK_ENV), patch("api.services.email.resend") as mock_resend:
        from api.services.email import send_feedback_email
        send_feedback_email(_make_user(email="jane@example.com", display_name=None), "help", "help me")
    assert "jane" in mock_resend.Emails.send.call_args[0][0]["subject"]
