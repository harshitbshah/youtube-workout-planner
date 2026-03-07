"""
test_constraints.py — FK constraints, UNIQUE constraints, and CASCADE deletes.

SQLite doesn't enforce FK constraints by default, so these tests only pass
against real PostgreSQL — exactly why integration tests exist.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.models import Channel, Classification, Schedule, User, UserCredentials, Video


# ─── FK violations ────────────────────────────────────────────────────────────

def test_channel_without_valid_user_raises(db_session):
    """Cannot insert a channel referencing a non-existent user."""
    ch = Channel(
        user_id=str(uuid.uuid4()),   # random UUID — no such user in DB
        name="Ghost Channel",
        youtube_url="https://youtube.com/@ghost",
    )
    db_session.add(ch)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_video_without_valid_channel_raises(db_session):
    """Cannot insert a video referencing a non-existent channel."""
    v = Video(
        id="vid_orphan",
        channel_id=str(uuid.uuid4()),
        title="Orphan Video",
        url="https://youtube.com/watch?v=orphan",
    )
    db_session.add(v)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_classification_without_valid_video_raises(db_session):
    """Cannot insert a classification referencing a non-existent video."""
    c = Classification(
        video_id="nonexistent_video_id",
        workout_type="HIIT",
        body_focus="full",
        difficulty="intermediate",
    )
    db_session.add(c)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ─── UNIQUE constraints ───────────────────────────────────────────────────────

def test_duplicate_google_id_raises(db_session):
    """Two users with the same google_id must be rejected at DB level."""
    u1 = User(google_id="same_google_id", email="first@example.com")
    u2 = User(google_id="same_google_id", email="second@example.com")
    db_session.add(u1)
    db_session.flush()
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ─── CASCADE deletes ──────────────────────────────────────────────────────────

def test_delete_user_cascades_to_channels(db_session, make_user, make_channel):
    user = make_user()
    make_channel(user.id)
    make_channel(user.id, name="Second Channel")

    db_session.delete(user)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM channels WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()
    assert remaining == 0


def test_delete_user_cascades_to_credentials(db_session, make_user):
    user = make_user()
    creds = UserCredentials(user_id=user.id, youtube_refresh_token="encrypted_blob")
    db_session.add(creds)
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM user_credentials WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()
    assert remaining == 0


def test_delete_user_cascades_to_schedules(db_session, make_user):
    user = make_user()
    db_session.add(Schedule(
        user_id=user.id, day="monday",
        workout_type="HIIT", body_focus="full",
        duration_min=30, duration_max=45,
    ))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM schedules WHERE user_id = :uid"),
        {"uid": user.id},
    ).scalar()
    assert remaining == 0


def test_delete_channel_cascades_to_videos(db_session, make_user, make_channel):
    user = make_user()
    channel = make_channel(user.id)

    v = Video(
        id="vid_cascade",
        channel_id=channel.id,
        title="Cascade Test",
        url="https://youtube.com/watch?v=cascade",
        duration_sec=1800,
    )
    db_session.add(v)
    db_session.commit()

    db_session.delete(channel)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM videos WHERE channel_id = :cid"),
        {"cid": channel.id},
    ).scalar()
    assert remaining == 0
