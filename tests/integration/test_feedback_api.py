"""
tests/integration/test_feedback_api.py - Integration tests for POST /feedback.

Runs against real PostgreSQL. send_feedback_email is mocked (no Resend calls).
"""

from unittest.mock import patch


# ─── POST /feedback ────────────────────────────────────────────────────────────

def test_submit_feedback_happy_path(auth_client):
    """Returns 204 on valid category + message."""
    client, user = auth_client
    with patch("api.routers.feedback.send_feedback_email") as mock_send:
        resp = client.post("/feedback", json={"category": "feedback", "message": "Loving it!"})
    assert resp.status_code == 204
    mock_send.assert_called_once_with(user, "feedback", "Loving it!")


def test_submit_feedback_unauthenticated(pg_engine):
    """Returns 401 with no session."""
    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        resp = c.post("/feedback", json={"category": "feedback", "message": "hello"})
    assert resp.status_code == 401


def test_submit_feedback_invalid_category(auth_client):
    """Returns 400 for unknown category."""
    client, user = auth_client
    resp = client.post("/feedback", json={"category": "praise", "message": "nice"})
    assert resp.status_code == 400


def test_submit_feedback_empty_message(auth_client):
    """Returns 400 for blank message."""
    client, user = auth_client
    resp = client.post("/feedback", json={"category": "bug", "message": "   "})
    assert resp.status_code == 400


def test_submit_feedback_all_categories_accepted(auth_client):
    """All three categories are accepted at the DB/integration level."""
    client, user = auth_client
    for category in ("feedback", "help", "bug"):
        with patch("api.routers.feedback.send_feedback_email"):
            resp = client.post("/feedback", json={"category": category, "message": "test"})
        assert resp.status_code == 204, f"Category {category!r} should be accepted"
