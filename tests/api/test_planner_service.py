"""
Tests for api/services/planner.py - plan generation against SQLAlchemy DB.
"""

import uuid
from datetime import date, timedelta

import pytest

from api.models import Channel, Classification, ProgramHistory, Schedule, User, UserChannel, Video
from api.services.planner import (
    _fetch_candidates_for_user,
    generate_weekly_plan_for_user,
    pick_video_for_slot_for_user,
)


# ─── Fixtures / helpers ───────────────────────────────────────────────────────

@pytest.fixture
def user(db_session):
    u = User(google_id="g1", email="u@test.com", display_name="Test")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def channel(db_session, user):
    ch = Channel(name="TestChannel", youtube_url="https://youtube.com/@test")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)
    return ch


def _add_video(db_session, channel, video_id=None, workout_type="HIIT", body_focus="full",
               duration_sec=1800, published_at="2025-01-01T00:00:00Z"):
    vid_id = video_id or str(uuid.uuid4())[:8]
    v = Video(
        id=vid_id,
        channel_id=channel.id,
        title="Test Workout",
        url=f"https://youtube.com/watch?v={vid_id}",
        duration_sec=duration_sec,
        published_at=published_at,
    )
    c = Classification(
        video_id=vid_id,
        workout_type=workout_type,
        body_focus=body_focus,
        difficulty="intermediate",
        has_warmup=False,
        has_cooldown=False,
    )
    db_session.add_all([v, c])
    db_session.commit()
    return v


def _slot_kwargs(session, user_id, **overrides):
    defaults = dict(
        session=session,
        user_id=user_id,
        workout_type="HIIT",
        body_focus="full",
        min_duration_sec=900,
        max_duration_sec=3600,
        difficulty="any",
        recency_boost_weeks=24,
        used_channel_names=[],
    )
    defaults.update(overrides)
    return defaults


# ─── _fetch_candidates_for_user ───────────────────────────────────────────────

def test_fetch_candidates_returns_matching_video(db_session, user, channel):
    _add_video(db_session, channel)
    results = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", 8
    )
    assert len(results) == 1
    assert results[0]["workout_type"] == "HIIT"


def test_fetch_candidates_empty_library(db_session, user):
    results = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", 8
    )
    assert results == []


def test_fetch_candidates_excludes_history(db_session, user, channel):
    v = _add_video(db_session, channel, video_id="vid1")
    recent_week = date.today() - timedelta(weeks=1)
    db_session.add(ProgramHistory(
        user_id=user.id, week_start=recent_week, video_id="vid1", assigned_day="monday"
    ))
    db_session.commit()

    results = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", history_weeks=8
    )
    assert results == []


def test_fetch_candidates_excludes_other_users_videos(db_session, channel):
    """Videos from another user's channels must not appear."""
    other_user = User(google_id="g2", email="other@test.com")
    db_session.add(other_user)
    db_session.commit()

    _add_video(db_session, channel)  # channel belongs to user fixture, not other_user

    results = _fetch_candidates_for_user(
        db_session, other_user.id, "HIIT", "full", 900, 3600, "any", 8
    )
    assert results == []


# ─── pick_video_for_slot_for_user ─────────────────────────────────────────────

def test_pick_video_returns_match(db_session, user, channel):
    _add_video(db_session, channel, video_id="vid1")
    result = pick_video_for_slot_for_user(**_slot_kwargs(db_session, user.id))
    assert result is not None
    assert result["id"] == "vid1"


def test_pick_video_returns_none_when_empty(db_session, user):
    result = pick_video_for_slot_for_user(**_slot_kwargs(db_session, user.id))
    assert result is None


def test_pick_video_fallback_relaxes_body_focus(db_session, user, channel):
    """Video with body_focus='lower' should be found via Tier 3 when slot needs 'upper'."""
    _add_video(db_session, channel, video_id="vid1", body_focus="lower")
    result = pick_video_for_slot_for_user(**_slot_kwargs(db_session, user.id, body_focus="upper"))
    assert result is not None
    assert result["id"] == "vid1"


def test_pick_video_avoids_recently_used(db_session, user, channel):
    _add_video(db_session, channel, video_id="vid1")
    _add_video(db_session, channel, video_id="vid2")
    # Mark vid1 in recent history
    db_session.add(ProgramHistory(
        user_id=user.id,
        week_start=date.today() - timedelta(weeks=1),
        video_id="vid1",
        assigned_day="monday",
    ))
    db_session.commit()

    result = pick_video_for_slot_for_user(**_slot_kwargs(db_session, user.id))
    assert result is not None
    assert result["id"] == "vid2"


def test_pick_video_never_picks_other_type(db_session, user, channel):
    """'Other' classified videos must never appear in a plan slot, even via Tier 6 fallback."""
    # Only video available is classified as 'Other' (e.g. a critique/progress video)
    _add_video(db_session, channel, video_id="other1", workout_type="Other")
    result = pick_video_for_slot_for_user(**_slot_kwargs(db_session, user.id))
    assert result is None  # no valid video, not the Other one


# ─── generate_weekly_plan_for_user ────────────────────────────────────────────

def _add_schedule(db_session, user, day, workout_type, body_focus="full", duration_min=30, duration_max=45):
    s = Schedule(
        user_id=user.id,
        day=day,
        workout_type=workout_type,
        body_focus=body_focus,
        duration_min=duration_min,
        duration_max=duration_max,
        difficulty="any",
    )
    db_session.add(s)
    db_session.commit()


def test_generate_plan_rest_day(db_session, user, channel):
    # Sunday = rest (no schedule entry)
    _add_video(db_session, channel)
    plan = generate_weekly_plan_for_user(db_session, user.id)
    sunday = next(d for d in plan if d["day"] == "sunday")
    assert sunday["video"] is None


def test_generate_plan_picks_video_for_scheduled_day(db_session, user, channel):
    _add_schedule(db_session, user, "monday", "HIIT")
    _add_video(db_session, channel, workout_type="HIIT")

    plan = generate_weekly_plan_for_user(db_session, user.id)

    monday = next(d for d in plan if d["day"] == "monday")
    assert monday["video"] is not None
    assert monday["video"]["workout_type"] == "HIIT"


def test_generate_plan_saves_to_history(db_session, user, channel):
    _add_schedule(db_session, user, "monday", "HIIT")
    _add_video(db_session, channel, workout_type="HIIT")

    generate_weekly_plan_for_user(db_session, user.id)

    history = db_session.query(ProgramHistory).filter(ProgramHistory.user_id == user.id).all()
    assert len(history) == 7  # one row per day always
    monday = next(h for h in history if h.assigned_day == "monday")
    assert monday.video_id is not None


def test_generate_plan_returns_7_days(db_session, user):
    plan = generate_weekly_plan_for_user(db_session, user.id)
    assert len(plan) == 7
    assert [d["day"] for d in plan] == [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
