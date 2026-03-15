"""
Integration tests for GET /library against real PostgreSQL.

What these add over unit tests:
  - Real FK constraints - channel_id / video_id must exist
  - Real inner-join behaviour for Classification
  - User isolation enforced at DB level
  - Pagination counts verified on real data volumes
"""

from datetime import datetime, timezone

from api.models import Channel, Classification, UserChannel, Video


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _seed_channel(db_session, user, name="TestChannel"):
    ch = Channel(
        name=name,
        youtube_url=f"https://youtube.com/@{name.lower().replace(' ', '')}",
        added_at=datetime.now(timezone.utc),
    )
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)
    return ch


def _seed_video(
    db_session,
    channel_id,
    video_id,
    title="Test Video",
    workout_type="strength",
    body_focus="upper",
    difficulty="intermediate",
    published_at="2024-06-01T00:00:00Z",
):
    video = Video(
        id=video_id,
        channel_id=channel_id,
        title=title,
        url=f"https://youtube.com/watch?v={video_id}",
        duration_sec=1800,
        published_at=published_at,
    )
    db_session.add(video)
    db_session.add(Classification(
        video_id=video_id,
        workout_type=workout_type,
        body_focus=body_focus,
        difficulty=difficulty,
    ))
    db_session.commit()
    return video


# ─── Basic read ───────────────────────────────────────────────────────────────

def test_library_empty_for_new_user(auth_client):
    client, _ = auth_client
    resp = client.get("/library")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["videos"] == []
    assert data["pages"] == 1


def test_library_returns_videos_from_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "pg-v1", "Push Day", workout_type="strength")
    _seed_video(db_session, ch.id, "pg-v2", "HIIT Day", workout_type="hiit")

    data = client.get("/library").json()
    assert data["total"] == 2
    assert {v["id"] for v in data["videos"]} == {"pg-v1", "pg-v2"}


def test_library_video_fields_correct_from_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user, name="JeffNippard")
    _seed_video(
        db_session, ch.id, "v1", "Hypertrophy Upper",
        workout_type="strength", body_focus="upper", difficulty="intermediate",
    )

    v = client.get("/library").json()["videos"][0]
    assert v["id"] == "v1"
    assert v["title"] == "Hypertrophy Upper"
    assert v["channel_name"] == "JeffNippard"
    assert v["workout_type"] == "strength"
    assert v["body_focus"] == "upper"
    assert v["difficulty"] == "intermediate"
    assert v["duration_sec"] == 1800


# ─── User isolation ────────────────────────────────────────────────────────────

def test_user_isolation_in_postgres(auth_client, db_session):
    """Real FK + user_id filter: authenticated user cannot see another's videos."""
    from api.models import User as UserModel

    client, user = auth_client

    other = UserModel(
        google_id="lib-integ-other-gid",
        email="libother@integration.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(other)
    db_session.commit()
    other_ch = _seed_channel(db_session, other, name="OtherChannel")
    _seed_video(db_session, other_ch.id, "other-v1", "Other Video")

    # Authenticated user has no channels/videos
    data = client.get("/library").json()
    assert data["total"] == 0


def test_user_sees_own_videos_across_multiple_channels(auth_client, db_session):
    client, user = auth_client
    ch1 = _seed_channel(db_session, user, name="ChannelA")
    ch2 = _seed_channel(db_session, user, name="ChannelB")
    _seed_video(db_session, ch1.id, "a1", workout_type="strength")
    _seed_video(db_session, ch1.id, "a2", workout_type="hiit")
    _seed_video(db_session, ch2.id, "b1", workout_type="cardio")

    data = client.get("/library").json()
    assert data["total"] == 3


# ─── Filtering ─────────────────────────────────────────────────────────────────

def test_filter_workout_type_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "s1", workout_type="strength")
    _seed_video(db_session, ch.id, "c1", workout_type="cardio")
    _seed_video(db_session, ch.id, "h1", workout_type="hiit")

    data = client.get("/library?workout_type=cardio").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "c1"


def test_filter_body_focus_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "u1", body_focus="upper")
    _seed_video(db_session, ch.id, "l1", body_focus="lower")
    _seed_video(db_session, ch.id, "f1", body_focus="full")

    data = client.get("/library?body_focus=full").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "f1"


def test_filter_difficulty_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "beg", difficulty="beginner")
    _seed_video(db_session, ch.id, "adv", difficulty="advanced")

    data = client.get("/library?difficulty=advanced").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "adv"


def test_filter_channel_id_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch1 = _seed_channel(db_session, user, name="Alpha")
    ch2 = _seed_channel(db_session, user, name="Beta")
    _seed_video(db_session, ch1.id, "a1")
    _seed_video(db_session, ch2.id, "b1")
    _seed_video(db_session, ch2.id, "b2")

    data = client.get(f"/library?channel_id={ch2.id}").json()
    assert data["total"] == 2
    assert {v["id"] for v in data["videos"]} == {"b1", "b2"}


def test_multi_filter_combined_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "match", workout_type="strength", body_focus="upper", difficulty="beginner")
    _seed_video(db_session, ch.id, "no-1", workout_type="hiit", body_focus="upper", difficulty="beginner")
    _seed_video(db_session, ch.id, "no-2", workout_type="strength", body_focus="lower", difficulty="beginner")
    _seed_video(db_session, ch.id, "no-3", workout_type="strength", body_focus="upper", difficulty="advanced")

    data = client.get("/library?workout_type=strength&body_focus=upper&difficulty=beginner").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "match"


# ─── Pagination ─────────────────────────────────────────────────────────────────

def test_pagination_total_and_pages_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(10):
        _seed_video(db_session, ch.id, f"pg-{i}", published_at=f"2024-01-{i+1:02d}T00:00:00Z")

    data = client.get("/library?limit=4").json()
    assert data["total"] == 10
    assert data["pages"] == 3  # ceil(10/4)
    assert len(data["videos"]) == 4


def test_pagination_pages_are_non_overlapping_in_postgres(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(9):
        _seed_video(db_session, ch.id, f"pg-{i}", published_at=f"2024-01-{i+1:02d}T00:00:00Z")

    p1 = {v["id"] for v in client.get("/library?limit=3&page=1").json()["videos"]}
    p2 = {v["id"] for v in client.get("/library?limit=3&page=2").json()["videos"]}
    p3 = {v["id"] for v in client.get("/library?limit=3&page=3").json()["videos"]}

    assert len(p1) == len(p2) == len(p3) == 3
    assert p1.isdisjoint(p2)
    assert p1.isdisjoint(p3)
    assert p2.isdisjoint(p3)


def test_pagination_total_consistent_with_filter_in_postgres(auth_client, db_session):
    """total should reflect filtered count, not the full library size."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(6):
        _seed_video(db_session, ch.id, f"s{i}", workout_type="strength")
    for i in range(4):
        _seed_video(db_session, ch.id, f"c{i}", workout_type="cardio")

    data = client.get("/library?workout_type=strength&limit=2").json()
    assert data["total"] == 6
    assert data["pages"] == 3
