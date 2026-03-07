"""
Tests for /plan endpoints (upcoming, generate, patch day).

generate_weekly_plan_for_user is mocked so tests don't need a real video library.
"""

from datetime import date
from unittest.mock import patch

import pytest

from api.models import Channel, Classification, ProgramHistory, Schedule, Video


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
    ch = Channel(user_id=user.id, name="Jeff Nippard", youtube_url="https://youtube.com/@jeff")
    db_session.add(ch)
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

    # History for this week exists — generate should clear and replace it
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
