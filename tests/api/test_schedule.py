"""
Tests for GET/PUT /schedule endpoints.
"""

from api.models import Schedule


def test_get_schedule_empty_returns_seven_rest_days(auth_client):
    client, user = auth_client
    resp = client.get("/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["schedule"]) == 7
    for slot in data["schedule"]:
        assert slot["workout_type"] is None


def test_get_schedule_returns_existing_rows(auth_client, db_session):
    client, user = auth_client
    db_session.add(Schedule(
        user_id=user.id,
        day="monday",
        workout_type="strength",
        body_focus="upper",
        duration_min=30,
        duration_max=60,
        difficulty="intermediate",
    ))
    db_session.commit()

    resp = client.get("/schedule")
    assert resp.status_code == 200
    schedule = {s["day"]: s for s in resp.json()["schedule"]}
    assert schedule["monday"]["workout_type"] == "strength"
    assert schedule["monday"]["body_focus"] == "upper"
    assert schedule["tuesday"]["workout_type"] is None  # rest day


def test_get_schedule_unauthenticated(client):
    resp = client.get("/schedule")
    assert resp.status_code == 401


def test_put_schedule_replaces_all(auth_client, db_session):
    client, user = auth_client

    # Seed an existing entry
    db_session.add(Schedule(user_id=user.id, day="monday", workout_type="cardio"))
    db_session.commit()

    payload = {
        "schedule": [
            {"day": "monday", "workout_type": "strength", "body_focus": "upper", "duration_min": 30, "duration_max": 60, "difficulty": "intermediate"},
            {"day": "tuesday", "workout_type": None},
            {"day": "wednesday", "workout_type": "hiit", "body_focus": "full", "duration_min": 20, "duration_max": 30, "difficulty": "any"},
        ]
    }
    resp = client.put("/schedule", json=payload)
    assert resp.status_code == 200

    schedule = {s["day"]: s for s in resp.json()["schedule"]}
    assert schedule["monday"]["workout_type"] == "strength"
    assert schedule["wednesday"]["workout_type"] == "hiit"
    # Days not in the PUT body are returned as rest days
    assert schedule["thursday"]["workout_type"] is None

    # Old cardio entry is gone — replaced by strength
    rows = db_session.query(Schedule).filter(Schedule.user_id == user.id).all()
    by_day = {r.day: r for r in rows}
    assert by_day["monday"].workout_type == "strength"
    assert "tuesday" not in by_day or by_day["tuesday"].workout_type is None


def test_put_schedule_unauthenticated(client):
    resp = client.put("/schedule", json={"schedule": []})
    assert resp.status_code == 401


def test_put_schedule_returns_full_seven_days(auth_client):
    client, user = auth_client
    payload = {
        "schedule": [
            {"day": "saturday", "workout_type": "yoga", "body_focus": "full", "duration_min": 30, "duration_max": 45, "difficulty": "any"},
        ]
    }
    resp = client.put("/schedule", json=payload)
    assert resp.status_code == 200
    assert len(resp.json()["schedule"]) == 7
