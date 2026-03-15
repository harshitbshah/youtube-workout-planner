"""
Integration tests for api/services/classifier.py against real PostgreSQL.

What these add over unit tests:
  - _fetch_unclassified_for_user uses real JOINs and FK relationships in Postgres
  - _save_classification INSERT and upsert verified at DB level
  - Shorts filter (duration_sec < 180) applied by real Postgres query
  - User isolation confirmed against real data
"""

from datetime import datetime, timezone

from api.models import Channel, Classification, UserChannel, Video
from api.services.classifier import _fetch_unclassified_for_user, _save_classification


def _seed_video(db_session, channel_id, video_id, duration_sec=1800,
                published_at="2025-06-01T00:00:00Z"):
    v = Video(
        id=video_id,
        channel_id=channel_id,
        title=f"Video {video_id}",
        url=f"https://youtube.com/watch?v={video_id}",
        duration_sec=duration_sec,
        published_at=published_at,
    )
    db_session.add(v)
    db_session.commit()
    return v


# ─── _fetch_unclassified_for_user ─────────────────────────────────────────────

def test_fetch_unclassified_returns_only_users_videos(db_session, make_user, make_channel):
    user_a = make_user(email="a@test.com")
    user_b = make_user(email="b@test.com")
    ch_a = make_channel(user_a.id, name="A", youtube_url="https://youtube.com/@a")
    ch_b = make_channel(user_b.id, name="B", youtube_url="https://youtube.com/@b")

    _seed_video(db_session, ch_a.id, "vid-a")
    _seed_video(db_session, ch_b.id, "vid-b")

    result = _fetch_unclassified_for_user(db_session, user_a.id)
    assert len(result) == 1
    assert result[0]["id"] == "vid-a"


def test_fetch_unclassified_excludes_classified_videos(db_session, make_user, make_channel):
    user = make_user()
    ch = make_channel(user.id)
    _seed_video(db_session, ch.id, "clf-vid")

    db_session.add(Classification(
        video_id="clf-vid", workout_type="Strength",
        body_focus="upper", difficulty="intermediate",
    ))
    db_session.commit()

    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []


def test_fetch_unclassified_excludes_shorts(db_session, make_user, make_channel):
    """Videos shorter than 3 minutes must be excluded by the Postgres query."""
    user = make_user()
    ch = make_channel(user.id)
    _seed_video(db_session, ch.id, "short-vid", duration_sec=120)  # 2 min
    _seed_video(db_session, ch.id, "long-vid", duration_sec=1800)  # 30 min

    result = _fetch_unclassified_for_user(db_session, user.id)
    ids = {v["id"] for v in result}
    assert "short-vid" not in ids
    assert "long-vid" in ids


def test_fetch_unclassified_excludes_null_duration(db_session, make_user, make_channel):
    """Videos with unknown duration (None) are excluded - can't verify they're not Shorts."""
    user = make_user()
    ch = make_channel(user.id)
    _seed_video(db_session, ch.id, "no-dur-vid", duration_sec=None)

    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []


def test_fetch_unclassified_empty_library(db_session, make_user, make_channel):
    user = make_user()
    make_channel(user.id)
    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []


# ─── _save_classification ─────────────────────────────────────────────────────

def test_save_classification_inserts_row(db_session, make_user, make_channel):
    user = make_user()
    ch = make_channel(user.id)
    _seed_video(db_session, ch.id, "clf-insert")

    clf = {"workout_type": "HIIT", "body_focus": "full",
           "difficulty": "intermediate", "has_warmup": 1, "has_cooldown": 0}
    _save_classification(db_session, "clf-insert", clf)

    row = db_session.get(Classification, "clf-insert")
    assert row is not None
    assert row.workout_type == "HIIT"
    assert row.body_focus == "full"
    assert row.has_warmup is True
    assert row.has_cooldown is False


def test_save_classification_upserts_existing(db_session, make_user, make_channel):
    """Calling _save_classification twice must update, not duplicate."""
    user = make_user()
    ch = make_channel(user.id)
    _seed_video(db_session, ch.id, "clf-upsert")

    clf1 = {"workout_type": "HIIT", "body_focus": "full",
            "difficulty": "beginner", "has_warmup": 0, "has_cooldown": 0}
    _save_classification(db_session, "clf-upsert", clf1)

    clf2 = {"workout_type": "Strength", "body_focus": "upper",
            "difficulty": "intermediate", "has_warmup": 1, "has_cooldown": 1}
    _save_classification(db_session, "clf-upsert", clf2)

    rows = db_session.query(Classification).filter(
        Classification.video_id == "clf-upsert"
    ).all()
    assert len(rows) == 1
    assert rows[0].workout_type == "Strength"
    assert rows[0].difficulty == "intermediate"
    assert rows[0].has_warmup is True


# ─── Scan endpoint ────────────────────────────────────────────────────────────

def test_scan_endpoint_returns_202(auth_client, db_session):
    from unittest.mock import patch
    client, user = auth_client

    ch = Channel(
        name="Jeff Nippard",
        youtube_url="https://youtube.com/@jeffnippard",
        added_at=datetime.now(timezone.utc),
    )
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_scan_and_classify"):
        resp = client.post(f"/jobs/channels/{ch.id}/scan")

    assert resp.status_code == 202
    assert resp.json()["channel_id"] == ch.id


def test_scan_endpoint_rejects_other_users_channel(auth_client, db_session):
    from unittest.mock import patch
    from api.models import User
    client, user = auth_client

    other = User(google_id="scan-other-g", email="scanother@test.com",
                 created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()

    ch = Channel(name="Other", youtube_url="https://youtube.com/@other",
                 added_at=datetime.now(timezone.utc))
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=other.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post(f"/jobs/channels/{ch.id}/scan")

    assert resp.status_code == 404
