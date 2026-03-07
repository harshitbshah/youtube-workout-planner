"""
test_planner_integration.py — Plan generation against real PostgreSQL.

Key things SQLite can't verify that these tests do:
  - program_history.week_start is a real DATE column — comparisons are strict
  - History exclusion window works correctly with PostgreSQL date arithmetic
  - CASCADE: deleting a user removes their program_history
  - Full plan generation persists correct user_id on all history rows
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from api.models import Channel, Classification, ProgramHistory, Schedule, User, Video
from api.services.planner import (
    _fetch_candidates_for_user,
    generate_weekly_plan_for_user,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _seed_video(session, channel_id, video_id=None, workout_type="HIIT",
                body_focus="full", duration_sec=1800,
                published_at="2025-06-01T00:00:00Z"):
    vid_id = video_id or str(uuid.uuid4())[:8]
    v = Video(
        id=vid_id, channel_id=channel_id,
        title="Integration Test Workout",
        url=f"https://youtube.com/watch?v={vid_id}",
        duration_sec=duration_sec, published_at=published_at,
    )
    c = Classification(
        video_id=vid_id, workout_type=workout_type, body_focus=body_focus,
        difficulty="intermediate", has_warmup=False, has_cooldown=False,
        classified_at="2025-06-01T00:00:00Z",
    )
    session.add_all([v, c])
    session.commit()
    return v


# ─── DATE type: history window ────────────────────────────────────────────────

def test_history_window_excludes_recent_video(db_session, make_user, make_channel):
    """
    PostgreSQL DATE comparison: a video assigned 1 week ago must be excluded
    from candidates when history_weeks=8.
    """
    user = make_user()
    channel = make_channel(user.id)
    video = _seed_video(db_session, channel.id, video_id="vid_recent")

    recent_week = date.today() - timedelta(weeks=1)
    db_session.add(ProgramHistory(
        user_id=user.id, week_start=recent_week,
        video_id="vid_recent", assigned_day="monday",
    ))
    db_session.commit()

    candidates = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", history_weeks=8
    )
    assert candidates == []


def test_history_window_includes_old_video(db_session, make_user, make_channel):
    """
    A video assigned 10 weeks ago is outside the 8-week window and must
    appear as a candidate again.
    """
    user = make_user()
    channel = make_channel(user.id)
    _seed_video(db_session, channel.id, video_id="vid_old")

    old_week = date.today() - timedelta(weeks=10)
    db_session.add(ProgramHistory(
        user_id=user.id, week_start=old_week,
        video_id="vid_old", assigned_day="monday",
    ))
    db_session.commit()

    candidates = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", history_weeks=8
    )
    assert len(candidates) == 1
    assert candidates[0]["id"] == "vid_old"


def test_history_at_exact_boundary(db_session, make_user, make_channel):
    """
    A video assigned exactly 8 weeks ago sits on the boundary.
    The cutoff is `now - 8 weeks`; week_start must be >= cutoff to be excluded.
    A video at exactly the cutoff date is included in the exclusion window.
    """
    user = make_user()
    channel = make_channel(user.id)
    _seed_video(db_session, channel.id, video_id="vid_boundary")

    boundary_week = date.today() - timedelta(weeks=8)
    db_session.add(ProgramHistory(
        user_id=user.id, week_start=boundary_week,
        video_id="vid_boundary", assigned_day="monday",
    ))
    db_session.commit()

    candidates = _fetch_candidates_for_user(
        db_session, user.id, "HIIT", "full", 900, 3600, "any", history_weeks=8
    )
    # On the boundary → still within the window → excluded
    assert candidates == []


# ─── Full plan generation ─────────────────────────────────────────────────────

def test_generate_plan_writes_correct_user_id(db_session, make_user, make_channel):
    """All program_history rows for a plan must carry the correct user_id."""
    user = make_user()
    channel = make_channel(user.id)
    _seed_video(db_session, channel.id, workout_type="HIIT")

    db_session.add(Schedule(
        user_id=user.id, day="monday",
        workout_type="HIIT", body_focus="full",
        duration_min=20, duration_max=60, difficulty="any",
    ))
    db_session.commit()

    generate_weekly_plan_for_user(db_session, user.id)

    history = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user.id
    ).all()
    assert len(history) == 1
    assert history[0].assigned_day == "monday"
    assert str(history[0].user_id) == str(user.id)


def test_generate_plan_two_users_isolated(db_session, make_user, make_channel):
    """Plans generated for two users must not bleed into each other's history."""
    user_a = make_user(email="a@test.com")
    user_b = make_user(email="b@test.com")

    channel_a = make_channel(user_a.id, name="ChannelA")
    channel_b = make_channel(user_b.id, name="ChannelB")

    _seed_video(db_session, channel_a.id, video_id="vid_a", workout_type="HIIT")
    _seed_video(db_session, channel_b.id, video_id="vid_b", workout_type="Strength")

    db_session.add(Schedule(
        user_id=user_a.id, day="monday", workout_type="HIIT",
        body_focus="full", duration_min=20, duration_max=60, difficulty="any",
    ))
    db_session.add(Schedule(
        user_id=user_b.id, day="monday", workout_type="Strength",
        body_focus="full", duration_min=20, duration_max=60, difficulty="any",
    ))
    db_session.commit()

    generate_weekly_plan_for_user(db_session, user_a.id)
    generate_weekly_plan_for_user(db_session, user_b.id)

    history_a = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user_a.id
    ).all()
    history_b = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user_b.id
    ).all()

    assert all(str(h.user_id) == str(user_a.id) for h in history_a)
    assert all(str(h.user_id) == str(user_b.id) for h in history_b)
    # User A's history only contains their video
    assert all(h.video_id == "vid_a" for h in history_a)
    assert all(h.video_id == "vid_b" for h in history_b)


# ─── CASCADE: deleting user removes history ───────────────────────────────────

def test_delete_user_cascades_to_program_history(db_session, make_user, make_channel):
    user = make_user()
    channel = make_channel(user.id)
    _seed_video(db_session, channel.id, video_id="vid_hist")

    db_session.add(ProgramHistory(
        user_id=user.id, week_start=date.today(),
        video_id="vid_hist", assigned_day="monday",
    ))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM program_history WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()
    assert remaining == 0
