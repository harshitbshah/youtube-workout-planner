"""
Integration tests for GET/PUT /schedule against real PostgreSQL.

What these add over unit tests:
  - Full replace is atomic - no stale rows survive in real Postgres
  - User isolation at DB level
"""

from api.models import Schedule


# ─── Get ──────────────────────────────────────────────────────────────────────

def test_get_schedule_empty_returns_seven_rest_days(auth_client):
    client, user = auth_client
    resp = client.get("/schedule")
    assert resp.status_code == 200
    slots = resp.json()["schedule"]
    assert len(slots) == 7
    assert all(s["workout_type"] is None for s in slots)


def test_get_schedule_returns_persisted_rows(auth_client, db_session):
    client, user = auth_client
    db_session.add(Schedule(
        user_id=user.id, day="monday",
        workout_type="strength", body_focus="upper",
        duration_min=30, duration_max=60, difficulty="intermediate",
    ))
    db_session.add(Schedule(
        user_id=user.id, day="wednesday",
        workout_type="hiit", body_focus="full",
        duration_min=20, duration_max=30, difficulty="any",
    ))
    db_session.commit()

    resp = client.get("/schedule")
    assert resp.status_code == 200
    by_day = {s["day"]: s for s in resp.json()["schedule"]}

    assert by_day["monday"]["workout_type"] == "strength"
    assert by_day["monday"]["body_focus"] == "upper"
    assert by_day["wednesday"]["workout_type"] == "hiit"
    assert by_day["tuesday"]["workout_type"] is None  # rest


# ─── Put ──────────────────────────────────────────────────────────────────────

def test_put_schedule_persists_to_postgres(auth_client, db_session):
    client, user = auth_client
    payload = {"schedule": [
        {"day": "monday", "workout_type": "strength", "body_focus": "upper", "duration_min": 30, "duration_max": 60, "difficulty": "intermediate"},
        {"day": "friday", "workout_type": "cardio", "body_focus": "full", "duration_min": 30, "duration_max": 45, "difficulty": "any"},
    ]}
    resp = client.put("/schedule", json=payload)
    assert resp.status_code == 200

    rows = db_session.query(Schedule).filter(Schedule.user_id == user.id).all()
    by_day = {r.day: r for r in rows}
    assert by_day["monday"].workout_type == "strength"
    assert by_day["friday"].workout_type == "cardio"
    assert "tuesday" not in by_day  # rest days not stored


def test_put_schedule_fully_replaces_existing_rows(auth_client, db_session):
    """Old rows must be completely gone after PUT - no stale data."""
    client, user = auth_client

    # Seed initial schedule
    for day, wtype in [("monday", "strength"), ("tuesday", "hiit"), ("wednesday", "cardio")]:
        db_session.add(Schedule(user_id=user.id, day=day, workout_type=wtype))
    db_session.commit()

    # PUT with only one day
    resp = client.put("/schedule", json={"schedule": [
        {"day": "saturday", "workout_type": "yoga", "body_focus": "full", "duration_min": 30, "duration_max": 45, "difficulty": "any"},
    ]})
    assert resp.status_code == 200

    rows = db_session.query(Schedule).filter(Schedule.user_id == user.id).all()
    assert len(rows) == 1
    assert rows[0].day == "saturday"
    assert rows[0].workout_type == "yoga"


def test_put_schedule_does_not_affect_other_users(auth_client, db_session):
    from datetime import datetime, timezone
    from api.models import User
    client, user = auth_client

    other = User(google_id="sched-other-g", email="schedother@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    db_session.add(Schedule(user_id=other.id, day="monday", workout_type="yoga"))
    db_session.commit()

    client.put("/schedule", json={"schedule": [
        {"day": "monday", "workout_type": "strength"},
    ]})

    other_row = db_session.query(Schedule).filter(Schedule.user_id == other.id, Schedule.day == "monday").first()
    assert other_row is not None
    assert other_row.workout_type == "yoga"  # untouched
