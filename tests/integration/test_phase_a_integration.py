"""
Phase A integration tests — run against real PostgreSQL.

Tests that DB-level behaviour is correct for migrations 006–008 and the
scanner/classifier logic that touches the new columns.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from api.models import Channel, Classification, User, UserChannel, Video


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_user(session, suffix):
    u = User(google_id=f"int-pa-{suffix}", email=f"intpa{suffix}@test.com")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _make_channel(session, user, suffix, **kwargs):
    ch = Channel(
        name=f"IntCh-{suffix}",
        youtube_url=f"https://youtube.com/@intch{suffix}",
        **kwargs,
    )
    session.add(ch)
    session.flush()
    session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    session.commit()
    session.refresh(ch)
    return ch


# ─── Migration 006: channels.first_scan_done ──────────────────────────────────

def test_first_scan_done_defaults_to_false(db_session):
    """New channels must have first_scan_done=False by default (migration 006)."""
    user = _make_user(db_session, "006a")
    ch = _make_channel(db_session, user, "006a")
    assert ch.first_scan_done is False


def test_first_scan_done_persists_true(db_session):
    """first_scan_done=True must persist to PostgreSQL."""
    user = _make_user(db_session, "006b")
    ch = _make_channel(db_session, user, "006b")
    ch.first_scan_done = True
    db_session.commit()
    db_session.refresh(ch)
    assert ch.first_scan_done is True


# ─── Migration 007: channels.last_video_published_at ──────────────────────────

def test_last_video_published_at_defaults_to_null(db_session):
    """New channels must have last_video_published_at=None by default (migration 007)."""
    user = _make_user(db_session, "007a")
    ch = _make_channel(db_session, user, "007a")
    assert ch.last_video_published_at is None


def test_last_video_published_at_persists(db_session):
    """last_video_published_at must persist a timezone-aware datetime."""
    user = _make_user(db_session, "007b")
    dt = datetime(2025, 11, 15, 0, 0, 0, tzinfo=timezone.utc)
    ch = _make_channel(db_session, user, "007b", last_video_published_at=dt)
    db_session.refresh(ch)
    assert ch.last_video_published_at is not None
    assert ch.last_video_published_at.year == 2025
    assert ch.last_video_published_at.month == 11


# ─── Migration 008: users.last_scan_error ─────────────────────────────────────

def test_last_scan_error_defaults_to_null(db_session):
    """New users must have last_scan_error=None by default (migration 008)."""
    user = _make_user(db_session, "008a")
    assert user.last_scan_error is None


def test_last_scan_error_persists(db_session):
    """last_scan_error must persist and be clearable."""
    user = _make_user(db_session, "008b")
    user.last_scan_error = "YouTube quota exceeded"
    db_session.commit()
    db_session.refresh(user)
    assert user.last_scan_error == "YouTube quota exceeded"

    user.last_scan_error = None
    db_session.commit()
    db_session.refresh(user)
    assert user.last_scan_error is None


# ─── F3: first-scan cap integration ───────────────────────────────────────────

def test_f3_first_scan_done_set_in_db(db_session):
    """After scan_channel completes, first_scan_done=True is persisted in PostgreSQL."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f3-int")
    ch = _make_channel(db_session, user, "f3-int")
    assert ch.first_scan_done is False

    mock_yt = MagicMock()
    mock_yt.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [],
        "nextPageToken": None,
    }

    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value={}):
        scan_channel(db_session, ch, api_key="fake-key")

    db_session.refresh(ch)
    assert ch.first_scan_done is True


# ─── F4: last_video_published_at updated after scan ───────────────────────────

def test_f4_last_video_published_at_updated_in_db(db_session):
    """last_video_published_at is updated in PostgreSQL after a scan saves videos."""
    from api.services.scanner import scan_channel

    user = _make_user(db_session, "f4-int")
    ch = _make_channel(db_session, user, "f4-int")
    assert ch.last_video_published_at is None

    pub_date = "2025-09-20T00:00:00Z"
    mock_yt = MagicMock()
    mock_yt.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [{
            "snippet": {
                "resourceId": {"videoId": "int-f4-vid"},
                "title": "Leg Day",
                "description": "desc",
                "publishedAt": pub_date,
                "liveBroadcastContent": "none",
            }
        }],
        "nextPageToken": None,
    }
    fake_details = {"int-f4-vid": {"duration_sec": 2400, "tags": None}}

    with patch("api.services.scanner.build_youtube_client", return_value=mock_yt), \
         patch("api.services.scanner.get_channel_info", return_value=("yt-id", "UPL")), \
         patch("api.services.scanner._fetch_video_details", return_value=fake_details):
        scan_channel(db_session, ch, api_key="fake-key")

    db_session.refresh(ch)
    assert ch.last_video_published_at is not None
    assert ch.last_video_published_at.year == 2025
    assert ch.last_video_published_at.month == 9


# ─── F2: 18-month cutoff integration ──────────────────────────────────────────

def test_f2_cutoff_filters_old_videos_in_postgres(db_session, monkeypatch):
    """18-month cutoff query works correctly against real PostgreSQL string comparison."""
    from api.services.classifier import _fetch_unclassified_for_user

    monkeypatch.setenv("CLASSIFY_MAX_AGE_MONTHS", "18")

    user = _make_user(db_session, "f2-int")
    ch = _make_channel(db_session, user, "f2-int")

    recent = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")

    db_session.add(Video(
        id="int-f2-recent", channel_id=ch.id, title="Recent Workout",
        url="https://youtube.com/watch?v=int-f2-recent",
        published_at=recent, duration_sec=1800,
    ))
    db_session.add(Video(
        id="int-f2-old", channel_id=ch.id, title="Old Workout",
        url="https://youtube.com/watch?v=int-f2-old",
        published_at=old, duration_sec=1800,
    ))
    db_session.commit()

    result = _fetch_unclassified_for_user(db_session, user.id)
    ids = [v["id"] for v in result]
    assert "int-f2-recent" in ids
    assert "int-f2-old" not in ids
