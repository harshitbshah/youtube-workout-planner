"""
Unit tests for GET /library endpoint.

Exercises filtering, pagination, user isolation, and field serialisation
against an SQLite in-memory database (no real PostgreSQL required).
"""

from api.models import Channel, Classification, Video


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _seed_channel(db_session, user, name="TestChannel"):
    ch = Channel(
        user_id=user.id,
        name=name,
        youtube_url=f"https://youtube.com/@{name.lower().replace(' ', '')}",
    )
    db_session.add(ch)
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
    duration_sec=1800,
    published_at="2024-06-01T00:00:00Z",
):
    video = Video(
        id=video_id,
        channel_id=channel_id,
        title=title,
        url=f"https://youtube.com/watch?v={video_id}",
        duration_sec=duration_sec,
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


# ─── Empty library ─────────────────────────────────────────────────────────────

def test_empty_library(auth_client):
    client, _ = auth_client
    resp = client.get("/library")
    assert resp.status_code == 200
    data = resp.json()
    assert data["videos"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 1


def test_unauthenticated_returns_401(client):
    assert client.get("/library").status_code == 401


# ─── Basic listing ─────────────────────────────────────────────────────────────

def test_returns_all_classified_videos(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", "Push Day")
    _seed_video(db_session, ch.id, "v2", "Pull Day")

    resp = client.get("/library")
    data = resp.json()
    assert data["total"] == 2
    assert {v["id"] for v in data["videos"]} == {"v1", "v2"}


def test_video_fields_are_serialised_correctly(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(
        db_session, ch.id, "v1", "Push Day",
        workout_type="strength", body_focus="upper", difficulty="intermediate",
        duration_sec=2100,
    )

    v = client.get("/library").json()["videos"][0]
    assert v["id"] == "v1"
    assert v["title"] == "Push Day"
    assert v["channel_name"] == "TestChannel"
    assert v["workout_type"] == "strength"
    assert v["body_focus"] == "upper"
    assert v["difficulty"] == "intermediate"
    assert v["duration_sec"] == 2100
    assert "youtube.com" in v["url"]


def test_videos_without_classification_are_excluded(auth_client, db_session):
    """Videos that have no Classification row should not appear (inner join)."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    # Add a video with no classification
    db_session.add(Video(
        id="bare",
        channel_id=ch.id,
        title="Unclassified",
        url="https://youtube.com/watch?v=bare",
    ))
    db_session.commit()
    # Add one with classification
    _seed_video(db_session, ch.id, "v1", "Classified")

    data = client.get("/library").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "v1"


# ─── User isolation ────────────────────────────────────────────────────────────

def test_cannot_see_other_users_videos(auth_client, db_session):
    from api.models import User as UserModel
    client, user = auth_client

    other = UserModel(google_id="lib-other-gid", email="other@example.com")
    db_session.add(other)
    db_session.commit()
    other_ch = _seed_channel(db_session, other, name="OtherChannel")
    _seed_video(db_session, other_ch.id, "other-v1", "Other Video")

    data = client.get("/library").json()
    assert data["total"] == 0


def test_multi_channel_user_sees_all_own_videos(auth_client, db_session):
    client, user = auth_client
    ch1 = _seed_channel(db_session, user, name="Channel A")
    ch2 = _seed_channel(db_session, user, name="Channel B")
    _seed_video(db_session, ch1.id, "v1", "Video from A")
    _seed_video(db_session, ch2.id, "v2", "Video from B")

    data = client.get("/library").json()
    assert data["total"] == 2


# ─── Filtering ─────────────────────────────────────────────────────────────────

def test_filter_by_workout_type(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", workout_type="strength")
    _seed_video(db_session, ch.id, "v2", workout_type="cardio")

    data = client.get("/library?workout_type=strength").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "v1"


def test_filter_by_body_focus(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", body_focus="upper")
    _seed_video(db_session, ch.id, "v2", body_focus="lower")

    data = client.get("/library?body_focus=lower").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "v2"


def test_filter_by_difficulty(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", difficulty="beginner")
    _seed_video(db_session, ch.id, "v2", difficulty="advanced")

    data = client.get("/library?difficulty=beginner").json()
    assert data["total"] == 1
    assert data["videos"][0]["difficulty"] == "beginner"


def test_filter_by_channel_id(auth_client, db_session):
    client, user = auth_client
    ch1 = _seed_channel(db_session, user, name="Channel1")
    ch2 = _seed_channel(db_session, user, name="Channel2")
    _seed_video(db_session, ch1.id, "v1")
    _seed_video(db_session, ch2.id, "v2")

    data = client.get(f"/library?channel_id={ch1.id}").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "v1"


def test_combined_filters_are_anded(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", workout_type="strength", body_focus="upper")
    _seed_video(db_session, ch.id, "v2", workout_type="strength", body_focus="lower")
    _seed_video(db_session, ch.id, "v3", workout_type="cardio", body_focus="upper")

    data = client.get("/library?workout_type=strength&body_focus=upper").json()
    assert data["total"] == 1
    assert data["videos"][0]["id"] == "v1"


def test_filter_with_no_match_returns_empty(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1", workout_type="strength")

    data = client.get("/library?workout_type=yoga").json()
    assert data["total"] == 0
    assert data["videos"] == []


def test_unknown_filter_value_returns_empty(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    _seed_video(db_session, ch.id, "v1")

    data = client.get("/library?difficulty=ultra-extreme").json()
    assert data["total"] == 0


def test_filter_is_case_insensitive(auth_client, db_session):
    """Classifier stores 'Strength'/'HIIT' — frontend sends lowercase, must still match."""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    # Seed with mixed-case values as the classifier writes them
    _seed_video(db_session, ch.id, "v-strength", workout_type="Strength")
    _seed_video(db_session, ch.id, "v-hiit", workout_type="HIIT")
    _seed_video(db_session, ch.id, "v-cardio", workout_type="Cardio")

    assert client.get("/library?workout_type=strength").json()["total"] == 1
    assert client.get("/library?workout_type=hiit").json()["total"] == 1
    assert client.get("/library?workout_type=HIIT").json()["total"] == 1
    assert client.get("/library?workout_type=cardio").json()["total"] == 1


# ─── Pagination ─────────────────────────────────────────────────────────────────

def test_pagination_limit_respected(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(5):
        _seed_video(db_session, ch.id, f"v{i}")

    data = client.get("/library?limit=2&page=1").json()
    assert len(data["videos"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3


def test_pagination_pages_calculation(auth_client, db_session):
    """pages = ceil(total / limit)"""
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(7):
        _seed_video(db_session, ch.id, f"v{i}")

    data = client.get("/library?limit=3").json()
    assert data["total"] == 7
    assert data["pages"] == 3  # ceil(7/3) = 3


def test_pagination_no_overlap_between_pages(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(6):
        _seed_video(db_session, ch.id, f"v{i}", published_at=f"2024-01-{i+1:02d}T00:00:00Z")

    p1_ids = {v["id"] for v in client.get("/library?limit=3&page=1").json()["videos"]}
    p2_ids = {v["id"] for v in client.get("/library?limit=3&page=2").json()["videos"]}
    assert len(p1_ids) == 3
    assert len(p2_ids) == 3
    assert p1_ids.isdisjoint(p2_ids)


def test_pagination_total_consistent_across_pages(auth_client, db_session):
    client, user = auth_client
    ch = _seed_channel(db_session, user)
    for i in range(5):
        _seed_video(db_session, ch.id, f"v{i}")

    p1 = client.get("/library?limit=2&page=1").json()
    p2 = client.get("/library?limit=2&page=2").json()
    assert p1["total"] == p2["total"] == 5


def test_pagination_invalid_page_returns_422(auth_client):
    client, _ = auth_client
    assert client.get("/library?page=0").status_code == 422


def test_pagination_limit_above_max_returns_422(auth_client):
    client, _ = auth_client
    assert client.get("/library?limit=101").status_code == 422
