"""
Unit tests for POST /plan/publish.

The publisher service makes real Google API calls, so we mock
`api.routers.plan.publish_plan_for_user` at the router's import site.
"""

from datetime import date
from unittest.mock import patch

import pytest

from api.crypto import encrypt
from api.models import ProgramHistory, UserChannel, UserCredentials, Video, Channel
from api.services.publisher import YouTubeAccessRevokedError, YouTubeNotConnectedError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_user_with_plan(db_session):
    """Create a user, channel, video, and a current-week plan row."""
    from api.models import User
    from src.planner import get_upcoming_monday

    user = User(google_id="g-publish", email="pub@test.com")
    db_session.add(user)
    db_session.flush()

    channel = Channel(name="FitCh", youtube_url="https://yt.com/c/FitCh")
    db_session.add(channel)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=channel.id))
    db_session.flush()

    video = Video(
        id="vid1",
        channel_id=channel.id,
        title="Leg Day",
        url="https://youtu.be/vid1",
    )
    db_session.add(video)
    db_session.flush()

    row = ProgramHistory(
        user_id=user.id,
        week_start=get_upcoming_monday(),
        video_id="vid1",
        assigned_day="monday",
    )
    db_session.add(row)
    db_session.commit()
    return user


def _add_credentials(db_session, user, valid=True):
    creds = UserCredentials(
        user_id=user.id,
        youtube_refresh_token=encrypt("fake-refresh-token"),
        credentials_valid=valid,
    )
    db_session.add(creds)
    db_session.commit()
    return creds


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_publish_requires_auth(client):
    resp = client.post("/plan/publish")
    assert resp.status_code == 401


def test_publish_no_plan(auth_client):
    client, user = auth_client
    # No plan in DB - should 404
    resp = client.post("/plan/publish")
    assert resp.status_code == 404


def test_publish_returns_202(auth_client, db_session):
    """POST /plan/publish returns 202 immediately (async publish)."""
    client, user = auth_client
    _make_user_with_plan(db_session)

    from api.dependencies import get_current_user
    from api.main import app
    from api.models import User

    plan_user = db_session.query(User).filter(User.google_id == "g-publish").first()
    app.dependency_overrides[get_current_user] = lambda: plan_user

    with patch("api.routers.plan._run_publish"):
        resp = client.post("/plan/publish")

    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 202
    assert "message" in resp.json()


def test_publish_sets_publishing_status(auth_client, db_session):
    """POST /plan/publish sets in-memory status to publishing for the user."""
    client, user = auth_client
    _make_user_with_plan(db_session)

    from api.dependencies import get_current_user
    from api.main import app
    from api.models import User
    from api.routers.plan import _publish_status

    plan_user = db_session.query(User).filter(User.google_id == "g-publish").first()
    app.dependency_overrides[get_current_user] = lambda: plan_user

    with patch("api.routers.plan._run_publish"):
        client.post("/plan/publish")

    app.dependency_overrides.pop(get_current_user, None)
    # Status should be "publishing" (background task blocked by mock)
    assert _publish_status.get(str(plan_user.id), {}).get("status") == "publishing"
    # cleanup
    _publish_status.pop(str(plan_user.id), None)


def test_run_publish_sets_done_status(db_session):
    """_run_publish sets status to done after successful publish."""
    from api.routers.plan import _run_publish, _publish_status

    user = _make_user_with_plan(db_session)
    from src.planner import get_upcoming_monday
    week_start = get_upcoming_monday()

    with patch("api.routers.plan.publish_plan_for_user") as mock_pub:
        mock_pub.return_value = {
            "playlist_url": "https://www.youtube.com/playlist?list=PLtest123",
            "video_count": 1,
        }
        with patch("api.database.SessionLocal", return_value=db_session):
            # Prevent session.close() from breaking the test session
            db_session.close = lambda: None
            _run_publish(str(user.id), week_start)

    status = _publish_status.get(str(user.id))
    assert status is not None
    assert status["status"] == "done"
    assert status["playlist_url"] == "https://www.youtube.com/playlist?list=PLtest123"
    assert status["video_count"] == 1
    # cleanup
    _publish_status.pop(str(user.id), None)


def test_run_publish_sets_failed_on_not_connected(db_session):
    """_run_publish sets status to failed with error when YouTube not connected."""
    from api.routers.plan import _run_publish, _publish_status

    user = _make_user_with_plan(db_session)
    from src.planner import get_upcoming_monday
    week_start = get_upcoming_monday()

    with patch("api.routers.plan.publish_plan_for_user") as mock_pub:
        mock_pub.side_effect = YouTubeNotConnectedError("No YouTube credentials")
        with patch("api.database.SessionLocal", return_value=db_session):
            db_session.close = lambda: None
            _run_publish(str(user.id), week_start)

    status = _publish_status.get(str(user.id))
    assert status is not None
    assert status["status"] == "failed"
    assert "credentials" in status["error"].lower()
    # cleanup
    _publish_status.pop(str(user.id), None)


def test_run_publish_sets_revoked_error(db_session):
    """_run_publish sets error='revoked' on YouTubeAccessRevokedError."""
    from api.routers.plan import _run_publish, _publish_status

    user = _make_user_with_plan(db_session)
    from src.planner import get_upcoming_monday
    week_start = get_upcoming_monday()

    with patch("api.routers.plan.publish_plan_for_user") as mock_pub:
        mock_pub.side_effect = YouTubeAccessRevokedError("Token revoked")
        with patch("api.database.SessionLocal", return_value=db_session):
            db_session.close = lambda: None
            _run_publish(str(user.id), week_start)

    status = _publish_status.get(str(user.id))
    assert status is not None
    assert status["status"] == "failed"
    assert status["error"] == "revoked"
    # cleanup
    _publish_status.pop(str(user.id), None)


# ─── GET /auth/me includes youtube fields ─────────────────────────────────────

def test_me_includes_youtube_fields(auth_client, db_session):
    """GET /auth/me should include youtube_connected and credentials_valid."""
    client, user = auth_client
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert "youtube_connected" in body
    assert "credentials_valid" in body
    # Fresh user has no credentials row → not connected, but valid defaults true
    assert body["youtube_connected"] is False
    assert body["credentials_valid"] is True


def test_me_connected_when_token_stored(auth_client, db_session):
    client, user = auth_client
    _add_credentials(db_session, user, valid=True)

    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["youtube_connected"] is True
    assert body["credentials_valid"] is True


def test_me_credentials_invalid_when_revoked(auth_client, db_session):
    client, user = auth_client
    _add_credentials(db_session, user, valid=False)

    resp = client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["youtube_connected"] is True
    assert body["credentials_valid"] is False
