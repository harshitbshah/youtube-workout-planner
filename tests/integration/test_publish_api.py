"""
Integration tests for POST /plan/publish against a real PostgreSQL DB.

Google/YouTube API calls are mocked — we verify that:
  1. A successful publish returns playlist_url and video_count and persists the playlist ID
  2. A RefreshError marks credentials_valid=False in the DB
  3. A user with no plan gets 404
  4. GET /auth/me returns the new youtube_connected/credentials_valid fields
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import google.auth.exceptions
import pytest

from api.crypto import encrypt
from api.models import Channel, ProgramHistory, User, UserChannel, UserCredentials, Video


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def plan_user(db_session):
    """A user with a channel, video, credentials, and a plan for next Monday."""
    from src.planner import get_upcoming_monday

    user = User(
        google_id="pub-user",
        email="pub@example.com",
        display_name="Publisher",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.flush()

    channel = Channel(
        name="FitChannel",
        youtube_url="https://yt.com/@fit",
        added_at=datetime.now(timezone.utc),
    )
    db_session.add(channel)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=channel.id))
    db_session.flush()

    video = Video(
        id="pubvid1",
        channel_id=channel.id,
        title="Upper Body Strength",
        url="https://youtu.be/pubvid1",
    )
    db_session.add(video)
    db_session.flush()

    creds = UserCredentials(
        user_id=user.id,
        youtube_refresh_token=encrypt("fake-refresh-token"),
        credentials_valid=True,
    )
    db_session.add(creds)

    week_start = get_upcoming_monday()
    row = ProgramHistory(
        user_id=user.id,
        week_start=week_start,
        video_id="pubvid1",
        assigned_day="monday",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(user)
    return user, week_start


@pytest.fixture
def plan_client(db_session, plan_user):
    """TestClient authenticated as plan_user."""
    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user, get_db
    from api.main import app

    user, week_start = plan_user

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, user, week_start

    app.dependency_overrides.clear()


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_publish_success(plan_client, db_session):
    client, user, week_start = plan_client

    mock_youtube = MagicMock()
    mock_youtube.playlists.return_value.insert.return_value.execute.return_value = {
        "id": "PLintegration123"
    }
    # playlistItems.list — empty playlist to clear
    mock_youtube.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": []
    }
    mock_youtube.playlistItems.return_value.insert.return_value.execute.return_value = {}
    mock_youtube.playlists.return_value.update.return_value.execute.return_value = {}

    with patch("api.services.publisher.build_oauth_client", return_value=mock_youtube):
        resp = client.post("/plan/publish")

    assert resp.status_code == 200
    body = resp.json()
    assert "PLintegration123" in body["playlist_url"]
    assert body["video_count"] == 1

    # Playlist ID must be persisted so the next publish reuses the same playlist
    db_session.expire_all()
    creds = db_session.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    assert creds.youtube_playlist_id == "PLintegration123"


def test_publish_revoked_marks_invalid(plan_client, db_session):
    client, user, _ = plan_client

    with patch(
        "api.services.publisher.build_oauth_client",
        side_effect=google.auth.exceptions.RefreshError("Token revoked"),
    ):
        resp = client.post("/plan/publish")

    assert resp.status_code == 403
    assert "revoked" in resp.json()["detail"].lower()

    db_session.expire_all()
    creds = db_session.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    assert creds.credentials_valid is False


def test_publish_no_plan_returns_404(db_session):
    """A user with no plan rows gets 404."""
    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user, get_db
    from api.main import app

    user = User(
        google_id="noplan-user",
        email="noplan@example.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.post("/plan/publish")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_me_returns_youtube_fields(plan_client):
    """GET /auth/me includes youtube_connected and credentials_valid."""
    client, user, _ = plan_client
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["youtube_connected"] is True
    assert body["credentials_valid"] is True
