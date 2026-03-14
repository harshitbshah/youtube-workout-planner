"""
Integration tests for POST /jobs/scan against real PostgreSQL.

What these add over unit tests:
  - Channel rows queried via real Postgres FK constraints
  - Background task enqueued only when user's channels exist in DB
  - User isolation: cannot trigger scan for another user's channels
"""

from unittest.mock import patch

from api.models import Channel, UserChannel


def _add_channel(db_session, user, name="FitnessChannel", url="https://youtube.com/@fitness"):
    ch = Channel(name=name, youtube_url=url)
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)
    return ch


# ─── POST /jobs/scan ───────────────────────────────────────────────────────────

def test_full_scan_returns_202_with_channels(auth_client, db_session):
    """202 returned when user has at least one channel in Postgres."""
    client, user = auth_client
    _add_channel(db_session, user)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_full_pipeline") as mock:
        resp = client.post("/jobs/scan")

    assert resp.status_code == 202
    mock.assert_called_once_with(str(user.id))


def test_full_scan_400_when_no_channels(auth_client):
    """400 returned when user has no channels — verified against real Postgres query."""
    client, user = auth_client
    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post("/jobs/scan")
    assert resp.status_code == 400


def test_full_scan_does_not_trigger_for_other_users_channels(auth_client, db_session):
    """Channels belonging to a different user do not satisfy the channel check."""
    from datetime import datetime, timezone
    from api.models import User

    client, user = auth_client

    other = User(
        google_id="jobs-other-g",
        email="jobsother@example.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(other)
    db_session.commit()
    _add_channel(db_session, other, url="https://youtube.com/@other")

    # Current user has no channels, so even though other user does, this should 400
    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post("/jobs/scan")
    assert resp.status_code == 400


def test_full_scan_503_without_api_key(auth_client, db_session):
    """503 returned when YOUTUBE_API_KEY is not set."""
    client, user = auth_client
    _add_channel(db_session, user)
    with patch("api.routers.jobs.YOUTUBE_API_KEY", ""):
        resp = client.post("/jobs/scan")
    assert resp.status_code == 503


def test_full_scan_message_reflects_channel_count(auth_client, db_session):
    """Response message includes the number of channels found in Postgres."""
    client, user = auth_client
    _add_channel(db_session, user, name="Ch1", url="https://youtube.com/@ch1")
    _add_channel(db_session, user, name="Ch2", url="https://youtube.com/@ch2")

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_full_pipeline"):
        resp = client.post("/jobs/scan")

    assert resp.status_code == 202
    assert "2" in resp.json()["message"]
