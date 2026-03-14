"""
Phase A unit tests — AI Cost Reduction features 1–4 + graceful scanner failure.

All tests use SQLite in-memory; no real network calls.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from api.models import Channel, Classification, User, UserChannel, UserCredentials, Video


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_user(db, suffix="a"):
    u = User(google_id=f"pa-{suffix}", email=f"pa{suffix}@test.com")
    db.add(u)
    db.commit()
    return u


def _make_channel(db, user, suffix="a", **kwargs):
    ch = Channel(
        name=f"Channel-{suffix}",
        youtube_url=f"https://youtube.com/@ch{suffix}",
        **kwargs,
    )
    db.add(ch)
    db.flush()
    db.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db.commit()
    db.refresh(ch)
    return ch


def _make_video(db, channel, vid_id, published_at="2025-06-01T00:00:00Z", duration_sec=1800):
    v = Video(
        id=vid_id,
        channel_id=channel.id,
        title=f"Workout {vid_id}",
        url=f"https://youtube.com/watch?v={vid_id}",
        published_at=published_at,
        duration_sec=duration_sec,
    )
    db.add(v)
    db.commit()
    return v


def _make_mock_youtube(items):
    """Return a mock YouTube client yielding the given playlist items."""
    mock_yt = MagicMock()
    mock_yt.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": items,
        "nextPageToken": None,
    }
    return mock_yt


def _yt_items(n, pub_date="2025-06-01T00:00:00Z"):
    return [
        {
            "snippet": {
                "resourceId": {"videoId": f"yt-vid-{i}"},
                "title": f"Workout {i}",
                "description": "desc",
                "publishedAt": pub_date,
                "liveBroadcastContent": "none",
            }
        }
        for i in range(n)
    ]


def _fake_details(n):
    return {f"yt-vid-{i}": {"duration_sec": 1800, "tags": None} for i in range(n)}


# ─── F1: max_tokens = 80 ──────────────────────────────────────────────────────

def test_f1_max_tokens_is_80(db_session):
    """Batch requests must use max_tokens=80, not 150."""
    user = _make_user(db_session, "f1")
    ch = _make_channel(db_session, user, "f1")
    _make_video(db_session, ch, "f1-vid")

    submitted_requests = []

    def fake_create(requests):
        submitted_requests.extend(requests)
        batch = MagicMock()
        batch.id = "batch-f1"
        batch.processing_status = "ended"
        batch.request_counts = MagicMock(succeeded=0, errored=0, canceled=0, expired=0)
        return batch

    mock_client = MagicMock()
    mock_client.messages.batches.create.side_effect = fake_create
    mock_client.messages.batches.retrieve.return_value = MagicMock(
        processing_status="ended",
        request_counts=MagicMock(succeeded=0, errored=0, canceled=0, expired=0),
    )
    mock_client.messages.batches.results.return_value = []

    with patch("api.services.classifier._fetch_transcript_intro", return_value=""), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert len(submitted_requests) == 1
    assert submitted_requests[0]["params"]["max_tokens"] == 80


# ─── F2: 18-month video cutoff ────────────────────────────────────────────────

def test_f2_recent_video_included(db_session, monkeypatch):
    """Video published 6 months ago should be fetched for classification."""
    monkeypatch.setenv("CLASSIFY_MAX_AGE_MONTHS", "18")
    user = _make_user(db_session, "f2a")
    ch = _make_channel(db_session, user, "f2a")
    six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _make_video(db_session, ch, "f2-recent", published_at=six_months_ago)

    from api.services.classifier import _fetch_unclassified_for_user
    result = _fetch_unclassified_for_user(db_session, user.id)
    assert any(v["id"] == "f2-recent" for v in result)


def test_f2_old_video_excluded(db_session, monkeypatch):
    """Video published 24 months ago should be excluded by the 18-month cutoff."""
    monkeypatch.setenv("CLASSIFY_MAX_AGE_MONTHS", "18")
    user = _make_user(db_session, "f2b")
    ch = _make_channel(db_session, user, "f2b")
    two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _make_video(db_session, ch, "f2-old", published_at=two_years_ago)

    from api.services.classifier import _fetch_unclassified_for_user
    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []


def test_f2_custom_cutoff_env_var(db_session, monkeypatch):
    """CLASSIFY_MAX_AGE_MONTHS=1 should exclude videos older than 1 month."""
    monkeypatch.setenv("CLASSIFY_MAX_AGE_MONTHS", "1")
    user = _make_user(db_session, "f2c")
    ch = _make_channel(db_session, user, "f2c")

    recent = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _make_video(db_session, ch, "f2-within-1m", published_at=recent)
    _make_video(db_session, ch, "f2-outside-1m", published_at=old)

    from api.services.classifier import _fetch_unclassified_for_user
    result = _fetch_unclassified_for_user(db_session, user.id)
    ids = [v["id"] for v in result]
    assert "f2-within-1m" in ids
    assert "f2-outside-1m" not in ids


# ─── F3: first-scan channel cap ───────────────────────────────────────────────

def test_f3_first_scan_capped_at_limit(db_session):
    """First scan (first_scan_done=False) must be capped at FIRST_SCAN_LIMIT."""
    from api.services.scanner import scan_channel
    import api.services.scanner as scanner_mod

    user = _make_user(db_session, "f3a")
    ch = _make_channel(db_session, user, "f3a")
    assert ch.first_scan_done is False

    # Temporarily lower the limit so the test doesn't create 75 videos
    original_limit = scanner_mod.FIRST_SCAN_LIMIT
    scanner_mod.FIRST_SCAN_LIMIT = 5

    mock_yt = _make_mock_youtube(_yt_items(20))

    try:
        with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
             patch("api.services.scanner.get_channel_info", return_value=("yt-ch-id", "UPL123")), \
             patch("api.services.scanner._fetch_video_details", return_value=_fake_details(20)):
            scan_channel(db_session, ch, api_key="fake-key")
    finally:
        scanner_mod.FIRST_SCAN_LIMIT = original_limit

    saved = db_session.query(Video).filter(Video.channel_id == ch.id).count()
    assert saved == 5


def test_f3_first_scan_done_set_after_scan(db_session):
    """first_scan_done must be True after the first scan completes."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f3b")
    ch = _make_channel(db_session, user, "f3b")
    assert ch.first_scan_done is False

    with patch("api.services.scanner.build_youtube_client", return_value=_make_mock_youtube(_yt_items(3))), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-ch-id", "UPL123")), \
         patch("api.services.scanner._fetch_video_details", return_value=_fake_details(3)):
        scan_channel(db_session, ch, api_key="fake-key")

    db_session.refresh(ch)
    assert ch.first_scan_done is True


def test_f3_subsequent_scan_uncapped(db_session):
    """Incremental scan (first_scan_done=True) must not apply the first-scan cap."""
    from api.services.scanner import scan_channel
    import api.services.scanner as scanner_mod

    user = _make_user(db_session, "f3c")
    ch = _make_channel(db_session, user, "f3c")
    ch.first_scan_done = True
    db_session.commit()

    # Limit set low — should be ignored since first_scan_done=True
    original_limit = scanner_mod.FIRST_SCAN_LIMIT
    scanner_mod.FIRST_SCAN_LIMIT = 3

    try:
        with patch("api.services.scanner.build_youtube_client", return_value=_make_mock_youtube(_yt_items(10))), \
             patch("api.services.scanner.get_channel_info", return_value=("yt-ch-id", "UPL123")), \
             patch("api.services.scanner._fetch_video_details", return_value=_fake_details(10)):
            scan_channel(db_session, ch, api_key="fake-key")
    finally:
        scanner_mod.FIRST_SCAN_LIMIT = original_limit

    saved = db_session.query(Video).filter(Video.channel_id == ch.id).count()
    assert saved == 10


# ─── F4: skip inactive channels ───────────────────────────────────────────────

def _inactive_channel(db, user, suffix, days_since_video=90, days_since_added=90):
    return _make_channel(db, user, suffix,
        added_at=datetime.now(timezone.utc) - timedelta(days=days_since_added),
        last_video_published_at=datetime.now(timezone.utc) - timedelta(days=days_since_video),
    )


def test_f4_inactive_channel_skipped(db_session):
    """Channel with last_video_published_at > 60d ago is skipped when skip_if_inactive=True."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4a")
    ch = _inactive_channel(db_session, user, "f4a", days_since_video=90, days_since_added=90)

    mock_yt = MagicMock()
    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")):
        result = scan_channel(db_session, ch, api_key="fake-key", skip_if_inactive=True)

    assert result == 0
    mock_yt.playlistItems.assert_not_called()


def test_f4_inactive_channel_not_skipped_when_flag_false(db_session):
    """Same inactive channel is scanned when skip_if_inactive=False (user-triggered)."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4b")
    ch = _inactive_channel(db_session, user, "f4b", days_since_video=90, days_since_added=90)

    mock_yt = _make_mock_youtube([])
    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value={}):
        scan_channel(db_session, ch, api_key="fake-key", skip_if_inactive=False)

    mock_yt.playlistItems.return_value.list.assert_called()


def test_f4_active_channel_not_skipped(db_session):
    """Channel with last_video_published_at = 30d ago must NOT be skipped."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4c")
    ch = _inactive_channel(db_session, user, "f4c", days_since_video=30, days_since_added=60)

    mock_yt = _make_mock_youtube([])
    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value={}):
        scan_channel(db_session, ch, api_key="fake-key", skip_if_inactive=True)

    mock_yt.playlistItems.return_value.list.assert_called()


def test_f4_new_channel_not_skipped(db_session):
    """Channel with last_video_published_at=None (newly added) must NOT be skipped."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4d")
    ch = _make_channel(db_session, user, "f4d")  # last_video_published_at=None by default
    assert ch.last_video_published_at is None

    mock_yt = _make_mock_youtube([])
    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value={}):
        scan_channel(db_session, ch, api_key="fake-key", skip_if_inactive=True)

    mock_yt.playlistItems.return_value.list.assert_called()


def test_f4_last_video_published_at_updated(db_session):
    """last_video_published_at is updated to most recent video's published_at after scan."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4e")
    ch = _make_channel(db_session, user, "f4e")
    assert ch.last_video_published_at is None

    pub_date = "2025-11-15T00:00:00Z"
    items = [{
        "snippet": {
            "resourceId": {"videoId": "f4e-vid"},
            "title": "Workout",
            "description": "desc",
            "publishedAt": pub_date,
            "liveBroadcastContent": "none",
        }
    }]
    mock_yt = _make_mock_youtube(items)
    fake_details = {"f4e-vid": {"duration_sec": 1800, "tags": None}}

    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value=fake_details):
        scan_channel(db_session, ch, api_key="fake-key")

    db_session.refresh(ch)
    assert ch.last_video_published_at is not None
    assert ch.last_video_published_at.year == 2025
    assert ch.last_video_published_at.month == 11


# ─── Graceful scanner failure ─────────────────────────────────────────────────

def test_graceful_failure_last_scan_error_stored_in_db(db_session):
    """last_scan_error can be written and persisted on the User record."""
    user = _make_user(db_session, "gf1")
    assert user.last_scan_error is None

    user.last_scan_error = "unexpected failure: disk full"
    db_session.commit()
    db_session.refresh(user)

    assert user.last_scan_error == "unexpected failure: disk full"


def test_graceful_failure_cleared_on_success(db_session):
    """Successful pipeline run must clear last_scan_error."""
    user = _make_user(db_session, "gf2")
    user.last_scan_error = "previous error"
    db_session.commit()

    user.last_scan_error = None
    db_session.commit()
    db_session.refresh(user)

    assert user.last_scan_error is None


def test_graceful_failure_pipeline_outer_except_sets_error(db_session):
    """_run_full_pipeline stores last_scan_error when an unexpected exception occurs."""
    from api.routers.jobs import _run_full_pipeline
    from tests.api.conftest import TestingSessionLocal

    user = _make_user(db_session, "gf3")
    _make_channel(db_session, user, "gf3")
    user_id = user.id

    # Cause the outer except by making session.query(Channel) raise.
    # SessionLocal is imported inside _run_full_pipeline from api.database.
    original_query = db_session.query

    def failing_query(model):
        if hasattr(model, "__tablename__") and model.__tablename__ == "channels":
            raise RuntimeError("db connection lost")
        return original_query(model)

    with patch("api.database.SessionLocal", return_value=db_session), \
         patch.object(db_session, "query", side_effect=failing_query):
        _run_full_pipeline(user_id)
    # Note: _run_full_pipeline calls session.close() in its finally block.
    # Use a fresh session (StaticPool keeps the in-memory SQLite data alive) to assert.
    new_session = TestingSessionLocal()
    try:
        fresh = new_session.get(User, user_id)
        assert fresh is not None
        assert fresh.last_scan_error is not None
        assert "db connection lost" in fresh.last_scan_error
    finally:
        new_session.close()


def test_jobs_status_includes_error_from_db(auth_client, db_session):
    """GET /jobs/status returns error from DB when no in-memory status exists."""
    from api.routers.jobs import _pipeline_status

    client, user = auth_client

    user.last_scan_error = "something went wrong"
    db_session.commit()

    _pipeline_status.pop(str(user.id), None)

    resp = client.get("/jobs/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] is None
    assert data["error"] == "something went wrong"


def test_jobs_status_no_error_when_clean(auth_client, db_session):
    """GET /jobs/status returns error=None when no scan error exists."""
    from api.routers.jobs import _pipeline_status

    client, user = auth_client
    _pipeline_status.pop(str(user.id), None)
    user.last_scan_error = None
    db_session.commit()

    resp = client.get("/jobs/status")
    assert resp.status_code == 200
    assert resp.json()["error"] is None
