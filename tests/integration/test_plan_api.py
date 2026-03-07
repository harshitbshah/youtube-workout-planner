"""
Integration tests for /plan endpoints against real PostgreSQL.

What these add over unit tests:
  - ProgramHistory rows written and read via real Postgres DATE columns
  - PATCH upsert behaviour verified at DB level
  - User isolation: one user's plan cannot bleed into another's
"""

from datetime import date, datetime, timezone

from api.models import Channel, Classification, ProgramHistory, Video
from src.planner import get_upcoming_monday


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _seed_channel(db_session, user, name="TestChannel", url="https://youtube.com/@test"):
    ch = Channel(user_id=user.id, name=name, youtube_url=url, added_at=datetime.now(timezone.utc))
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)
    return ch


def _seed_video(db_session, channel_id, video_id="vid1", title="Push Day"):
    video = Video(
        id=video_id,
        channel_id=channel_id,
        title=title,
        url=f"https://youtube.com/watch?v={video_id}",
        duration_sec=1800,
    )
    db_session.add(video)
    db_session.add(Classification(
        video_id=video_id,
        workout_type="strength",
        body_focus="upper",
        difficulty="intermediate",
    ))
    db_session.commit()
    return video


def _seed_history(db_session, user, video_id, day="monday", week_start=None):
    ws = week_start or get_upcoming_monday()
    row = ProgramHistory(user_id=user.id, week_start=ws, video_id=video_id, assigned_day=day)
    db_session.add(row)
    db_session.commit()
    return row


# ─── Upcoming ─────────────────────────────────────────────────────────────────

def test_upcoming_returns_404_when_no_plan(auth_client):
    client, user = auth_client
    resp = client.get("/plan/upcoming")
    assert resp.status_code == 404


def test_upcoming_reads_history_from_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "vid1", "Push Day")
    _seed_history(db_session, user, "vid1", "monday")

    resp = client.get("/plan/upcoming")
    assert resp.status_code == 200
    days = {d["day"]: d for d in resp.json()["days"]}
    assert days["monday"]["video"]["title"] == "Push Day"
    assert days["tuesday"]["video"] is None


def test_upcoming_returns_most_recent_week(auth_client, db_session):
    """When multiple weeks exist, /upcoming returns the latest one."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "old-vid", "Old Video")
    _seed_video(db_session, ch.id, "new-vid", "New Video")

    old_week = date(2025, 1, 6)
    upcoming = get_upcoming_monday()
    _seed_history(db_session, user, "old-vid", "monday", week_start=old_week)
    _seed_history(db_session, user, "new-vid", "monday", week_start=upcoming)

    resp = client.get("/plan/upcoming")
    assert resp.status_code == 200
    days = {d["day"]: d for d in resp.json()["days"]}
    assert days["monday"]["video"]["id"] == "new-vid"


def test_upcoming_does_not_show_other_users_plan(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    other = User(google_id="plan-other-g", email="planother@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    ch = _seed_channel(db_session, other, url="https://youtube.com/@other")
    _seed_video(db_session, ch.id, "other-vid", "Other Video")
    _seed_history(db_session, other, "other-vid", "monday")

    # Current user has no plan — should 404, not return other user's plan
    resp = client.get("/plan/upcoming")
    assert resp.status_code == 404


# ─── Generate ─────────────────────────────────────────────────────────────────

def _seed_schedule(db_session, user, day="monday", workout_type="strength", body_focus="upper"):
    from api.models import Schedule
    db_session.add(Schedule(
        user_id=user.id, day=day,
        workout_type=workout_type, body_focus=body_focus,
        duration_min=20, duration_max=60, difficulty="any",
    ))
    db_session.commit()


def test_generate_writes_history_to_postgres(auth_client, db_session):
    """Run the real planner against Postgres — verify history row types and content."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "vid1", "Push Day")
    _seed_schedule(db_session, user)

    resp = client.post("/plan/generate")
    assert resp.status_code == 201

    rows = db_session.query(ProgramHistory).filter(ProgramHistory.user_id == user.id).all()
    by_day = {r.assigned_day: r for r in rows}
    assert "monday" in by_day
    assert by_day["monday"].video_id == "vid1"
    # week_start must be a real DATE in Postgres, not a string
    assert isinstance(by_day["monday"].week_start, date)


def test_generate_replaces_existing_week_plan(auth_client, db_session):
    """Re-generating clears the old plan for that week — no duplicate rows."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "vid1", "Push Day")
    _seed_schedule(db_session, user)

    # First generation
    client.post("/plan/generate")
    # Second generation — should clear and replace
    resp = client.post("/plan/generate")
    assert resp.status_code == 201

    rows = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user.id,
        ProgramHistory.week_start == get_upcoming_monday(),
        ProgramHistory.assigned_day == "monday",
    ).all()
    assert len(rows) == 1
    assert rows[0].video_id == "vid1"


# ─── Patch day ────────────────────────────────────────────────────────────────

def test_patch_day_updates_history_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "vid1", "Push Day")
    _seed_video(db_session, ch.id, "vid2", "Pull Day")
    _seed_history(db_session, user, "vid1", "monday")

    resp = client.patch("/plan/monday", json={"video_id": "vid2"})
    assert resp.status_code == 200
    assert resp.json()["video"]["id"] == "vid2"

    row = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user.id,
        ProgramHistory.assigned_day == "monday",
    ).first()
    assert row.video_id == "vid2"


def test_patch_day_inserts_new_row_if_no_history(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "vid1")

    resp = client.patch("/plan/wednesday", json={"video_id": "vid1"})
    assert resp.status_code == 200

    row = db_session.query(ProgramHistory).filter(
        ProgramHistory.user_id == user.id,
        ProgramHistory.assigned_day == "wednesday",
    ).first()
    assert row is not None
    assert row.video_id == "vid1"


def test_patch_day_rejects_other_users_video(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    other = User(google_id="patch-other-g", email="patchother@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    ch = _seed_channel(db_session, other, url="https://youtube.com/@patchother")
    _seed_video(db_session, ch.id, "other-vid", "Other Video")

    resp = client.patch("/plan/monday", json={"video_id": "other-vid"})
    assert resp.status_code == 404
