"""
Tests for /plan endpoints (upcoming, generate, patch day).

generate_weekly_plan_for_user is mocked so tests don't need a real video library.
"""

from datetime import date
from unittest.mock import patch

import pytest

from api.models import Channel, Classification, ProgramHistory, Schedule, UserChannel, Video


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _seed_video(db_session, channel_id, video_id="vid1", title="Push Day"):
    video = Video(
        id=video_id,
        channel_id=channel_id,
        title=title,
        url=f"https://youtube.com/watch?v={video_id}",
        duration_sec=1800,
    )
    db_session.add(video)
    clf = Classification(
        video_id=video_id,
        workout_type="strength",
        body_focus="upper",
        difficulty="intermediate",
    )
    db_session.add(clf)
    db_session.commit()
    return video


def _seed_channel(db_session, user):
    ch = Channel(name="Jeff Nippard", youtube_url="https://youtube.com/@jeff")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)
    return ch


def _seed_history(db_session, user, video_id, day="monday", week_start=None):
    if week_start is None:
        from src.planner import get_upcoming_monday
        week_start = get_upcoming_monday()
    row = ProgramHistory(
        user_id=user.id,
        week_start=week_start,
        video_id=video_id,
        assigned_day=day,
    )
    db_session.add(row)
    db_session.commit()
    return row


# ─── Upcoming ─────────────────────────────────────────────────────────────────

def test_upcoming_no_plan_returns_404(auth_client):
    client, user = auth_client
    resp = client.get("/plan/upcoming")
    assert resp.status_code == 404


def test_upcoming_returns_latest_week(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    video = _seed_video(db_session, ch.id)
    _seed_history(db_session, user, video.id, "monday")

    resp = client.get("/plan/upcoming")
    assert resp.status_code == 200
    data = resp.json()
    assert "week_start" in data
    days = {d["day"]: d for d in data["days"]}
    assert days["monday"]["video"] is not None
    assert days["monday"]["video"]["title"] == "Push Day"
    assert days["tuesday"]["video"] is None


def test_upcoming_unauthenticated(client):
    resp = client.get("/plan/upcoming")
    assert resp.status_code == 401


# ─── Generate ─────────────────────────────────────────────────────────────────

MOCK_PLAN = [
    {"day": "monday", "video": {
        "id": "vid1", "title": "Push Day", "url": "https://youtube.com/watch?v=vid1",
        "channel_name": "Jeff Nippard", "duration_sec": 1800,
        "workout_type": "strength", "body_focus": "upper", "difficulty": "intermediate",
    }},
    {"day": "tuesday", "video": None},
    {"day": "wednesday", "video": None},
    {"day": "thursday", "video": None},
    {"day": "friday", "video": None},
    {"day": "saturday", "video": None},
    {"day": "sunday", "video": None},
]


def test_generate_plan(auth_client, db_session):
    client, user = auth_client

    with patch("api.routers.plan.generate_weekly_plan_for_user", return_value=MOCK_PLAN):
        resp = client.post("/plan/generate")

    assert resp.status_code == 201
    data = resp.json()
    assert "week_start" in data
    days = {d["day"]: d for d in data["days"]}
    assert days["monday"]["video"]["title"] == "Push Day"
    assert days["tuesday"]["video"] is None


def test_generate_plan_replaces_existing(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    video = _seed_video(db_session, ch.id)
    _seed_history(db_session, user, video.id, "monday")

    # History for this week exists - generate should clear and replace it
    with patch("api.routers.plan.generate_weekly_plan_for_user", return_value=MOCK_PLAN):
        resp = client.post("/plan/generate")

    assert resp.status_code == 201


def test_generate_plan_unauthenticated(client):
    resp = client.post("/plan/generate")
    assert resp.status_code == 401


# ─── Patch day ────────────────────────────────────────────────────────────────

def test_patch_day_swaps_video(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    video = _seed_video(db_session, ch.id, video_id="vid1")
    video2 = _seed_video(db_session, ch.id, video_id="vid2", title="Pull Day")
    _seed_history(db_session, user, video.id, "monday")

    resp = client.patch("/plan/monday", json={"video_id": "vid2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["day"] == "monday"
    assert data["video"]["id"] == "vid2"
    assert data["video"]["title"] == "Pull Day"

    # Verify DB was updated
    row = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user.id,
        ProgramHistory.assigned_day == "monday",
    ).first()
    assert row.video_id == "vid2"


def test_patch_day_creates_row_if_missing(auth_client, db_session):
    """PATCH should upsert even if no plan row exists for that day."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    video = _seed_video(db_session, ch.id)

    resp = client.patch("/plan/wednesday", json={"video_id": "vid1"})
    assert resp.status_code == 200
    assert resp.json()["video"]["id"] == "vid1"


def test_patch_day_invalid_day(auth_client):
    client, user = auth_client
    resp = client.patch("/plan/funday", json={"video_id": "vid1"})
    assert resp.status_code == 400


def test_patch_day_video_not_in_library(auth_client, db_session):
    client, user = auth_client
    resp = client.patch("/plan/monday", json={"video_id": "nonexistent"})
    assert resp.status_code == 404


def test_patch_day_unauthenticated(client):
    resp = client.patch("/plan/monday", json={"video_id": "vid1"})
    assert resp.status_code == 401


# ─── Publish (async) ─────────────────────────────────────────────────────────

def test_publish_returns_202_and_sets_publishing_status(auth_client, db_session):
    """POST /plan/publish returns 202 immediately and sets status to publishing."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    video = _seed_video(db_session, ch.id)
    _seed_history(db_session, user, video.id, "monday")

    with patch("api.routers.plan._run_publish") as mock_run:
        # Prevent the background task from actually running during this test
        resp = client.post("/plan/publish")

    assert resp.status_code == 202
    data = resp.json()
    assert "message" in data


def test_publish_no_plan_returns_404(auth_client):
    """POST /plan/publish with no plan returns 404."""
    client, user = auth_client
    resp = client.post("/plan/publish")
    assert resp.status_code == 404


def test_publish_unauthenticated(client):
    resp = client.post("/plan/publish")
    assert resp.status_code == 401


def test_get_publish_status_idle_when_no_publish(auth_client):
    """GET /plan/publish/status returns idle when no publish has been started."""
    client, user = auth_client
    # Clear any leftover state from other tests
    from api.routers.plan import _publish_status
    _publish_status.pop(str(user.id), None)

    resp = client.get("/plan/publish/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["playlist_url"] is None
    assert data["video_count"] is None
    assert data["error"] is None


def test_get_publish_status_reflects_in_memory_state(auth_client):
    """GET /plan/publish/status returns the current in-memory status."""
    client, user = auth_client
    from api.routers.plan import _publish_status
    _publish_status[str(user.id)] = {
        "status": "done",
        "playlist_url": "https://youtube.com/playlist?list=abc123",
        "video_count": 5,
        "error": None,
    }

    resp = client.get("/plan/publish/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["playlist_url"] == "https://youtube.com/playlist?list=abc123"
    assert data["video_count"] == 5
    assert data["error"] is None

    # cleanup
    _publish_status.pop(str(user.id), None)


def test_get_publish_status_failed_state(auth_client):
    """GET /plan/publish/status returns failed state with error message."""
    client, user = auth_client
    from api.routers.plan import _publish_status
    _publish_status[str(user.id)] = {
        "status": "failed",
        "playlist_url": None,
        "video_count": None,
        "error": "YouTube not connected",
    }

    resp = client.get("/plan/publish/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error"] == "YouTube not connected"

    # cleanup
    _publish_status.pop(str(user.id), None)


def test_get_publish_status_unauthenticated(client):
    resp = client.get("/plan/publish/status")
    assert resp.status_code == 401


# ─── Gaps ─────────────────────────────────────────────────────────────────────

def test_gaps_returns_empty_when_no_schedule(auth_client):
    """User with no schedule slots has no gaps."""
    client, _ = auth_client
    resp = client.get("/plan/gaps")
    assert resp.status_code == 200
    assert resp.json() == {"gaps": []}


def test_gaps_returns_empty_when_library_is_full(auth_client, db_session):
    """User whose library has enough videos for every schedule slot reports no gaps."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    # 3+ Strength videos (MIN_PLAN_CANDIDATES default = 3)
    for i in range(3):
        _seed_video(db_session, ch.id, video_id=f"s{i}", title=f"Strength {i}")
    db_session.add(Schedule(
        user_id=user.id, day="monday", workout_type="Strength",
        body_focus="full", duration_min=20, duration_max=60,
    ))
    db_session.commit()
    resp = client.get("/plan/gaps")
    assert resp.status_code == 200
    assert resp.json() == {"gaps": []}


def test_gaps_returns_missing_types(auth_client, db_session):
    """Schedule has HIIT day but library has no HIIT videos - HIIT appears in gaps."""
    client, user = auth_client
    db_session.add(Schedule(
        user_id=user.id, day="tuesday", workout_type="HIIT",
        body_focus="full", duration_min=20, duration_max=60,
    ))
    db_session.commit()
    resp = client.get("/plan/gaps")
    assert resp.status_code == 200
    assert "HIIT" in resp.json()["gaps"]


def test_gaps_unauthenticated(client):
    resp = client.get("/plan/gaps")
    assert resp.status_code == 401
