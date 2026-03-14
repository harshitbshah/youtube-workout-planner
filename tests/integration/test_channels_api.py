"""
Integration tests for /channels endpoints against real PostgreSQL.

What these add over unit tests:
  - Real FK CASCADE: deleting a channel actually removes its videos
  - Real UNIQUE constraint on youtube_url per user
  - User isolation verified at the DB level
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from api.models import Channel, Classification, UserChannel, Video


def _make_anthropic_mock(reply: str) -> MagicMock:
    """Return a mock Anthropic client whose messages.create returns the given reply text."""
    content_block = MagicMock()
    content_block.text = reply
    response = MagicMock()
    response.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


# ─── List ─────────────────────────────────────────────────────────────────────

def test_list_channels_empty(auth_client):
    client, user = auth_client
    resp = client.get("/channels")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_channels_returns_only_current_users(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    # Another user's channel
    other = User(google_id="other-google", email="other@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()

    ch_other = Channel(name="Other Channel", youtube_url="https://youtube.com/@other")
    ch_mine = Channel(name="My Channel", youtube_url="https://youtube.com/@mine")
    db_session.add(ch_other)
    db_session.add(ch_mine)
    db_session.flush()
    db_session.add(UserChannel(user_id=other.id, channel_id=ch_other.id))
    db_session.add(UserChannel(user_id=user.id, channel_id=ch_mine.id))
    db_session.commit()

    resp = client.get("/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Channel"


# ─── Add ──────────────────────────────────────────────────────────────────────

def test_add_channel_persists_to_postgres(auth_client, db_session):
    client, user = auth_client
    payload = {"name": "Jeff Nippard", "youtube_url": "https://youtube.com/@jeffnippard", "youtube_channel_id": "UC123"}
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 201

    uc = db_session.query(UserChannel).filter(UserChannel.user_id == user.id).first()
    assert uc is not None
    row = db_session.query(Channel).filter(Channel.id == uc.channel_id).first()
    assert row is not None
    assert row.name == "Jeff Nippard"
    assert row.youtube_channel_id == "UC123"


def test_add_duplicate_url_returns_409(auth_client, db_session):
    client, user = auth_client
    ch = Channel(name="Jeff", youtube_url="https://youtube.com/@jeff")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()

    resp = client.post("/channels", json={"name": "Jeff Again", "youtube_url": "https://youtube.com/@jeff"})
    assert resp.status_code == 409

    # Still only one row
    assert db_session.query(UserChannel).filter(UserChannel.user_id == user.id).count() == 1


def test_same_url_allowed_for_different_users(auth_client, db_session):
    """Two users can both add the same channel URL."""
    from api.models import User
    client, user = auth_client

    other = User(google_id="other-g2", email="other2@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    ch = Channel(name="Shared Channel", youtube_url="https://youtube.com/@shared")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=other.id, channel_id=ch.id))
    db_session.commit()

    resp = client.post("/channels", json={"name": "Shared Channel", "youtube_url": "https://youtube.com/@shared"})
    assert resp.status_code == 201


# ─── Delete ───────────────────────────────────────────────────────────────────

def test_delete_channel_removes_user_link(auth_client, db_session):
    """Deleting a channel removes the user_channels link; channel row is preserved."""
    client, user = auth_client
    ch = Channel(name="To Delete", youtube_url="https://youtube.com/@delete")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 204
    # Link is gone
    assert db_session.query(UserChannel).filter(
        UserChannel.user_id == user.id, UserChannel.channel_id == ch.id
    ).first() is None
    # Channel and videos are preserved
    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is not None


def test_delete_channel_preserves_videos(auth_client, db_session):
    """Videos stay in DB when a user unsubscribes from a channel."""
    client, user = auth_client

    ch = Channel(name="PreserveTest", youtube_url="https://youtube.com/@preserve")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)

    video = Video(id="vid-preserve", channel_id=ch.id, title="Test Video", url="https://youtube.com/watch?v=vid-preserve")
    db_session.add(video)
    db_session.add(Classification(video_id="vid-preserve", workout_type="strength", body_focus="upper", difficulty="intermediate"))
    db_session.commit()

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 204

    # Videos and classifications are still in the DB
    assert db_session.query(Video).filter(Video.id == "vid-preserve").first() is not None
    assert db_session.query(Classification).filter(Classification.video_id == "vid-preserve").first() is not None


# ─── Suggestions ──────────────────────────────────────────────────────────────

def test_suggestions_cache_hit_no_youtube_call(auth_client, db_session):
    """All 3 cached channels for a profile are served from DB without hitting YouTube."""
    from unittest.mock import AsyncMock, patch

    client, user = auth_client

    for name, channel_id, thumb in [
        ("Athlean-X", "UCe0TLA0EsQbE-MjuHXevj2A", "https://example.com/athlean.jpg"),
        ("Jeff Nippard", "UCnHoKuB-RfcBQqFTXaQP5vg", "https://example.com/jeff.jpg"),
        ("Heather Robertson", "UCONtFkfpdUuL3RDdBMrx1_g", "https://example.com/heather.jpg"),
    ]:
        db_session.add(Channel(
            name=name,
            youtube_url=f"https://www.youtube.com/channel/{channel_id}",
            youtube_channel_id=channel_id,
            thumbnail_url=thumb,
            description="Fitness channel",
        ))
    db_session.commit()

    mock_http = AsyncMock()
    with patch("api.routers.channels.YOUTUBE_API_KEY", "fake-key"), \
         patch("httpx.AsyncClient.get", new=mock_http):
        resp = client.get("/channels/suggestions?profile=adult")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert any(d["name"] == "Athlean-X" for d in data)
    mock_http.assert_not_called()


def test_delete_other_users_channel_returns_404(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    other = User(google_id="other-g3", email="other3@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    ch = Channel(name="Not Yours", youtube_url="https://youtube.com/@notyours")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=other.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 404
    # Channel must still exist
    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is not None


# ─── Channel validation (integration) ────────────────────────────────────────

def test_add_channel_validation_mismatch_not_saved(auth_client, db_session):
    """On validation mismatch, the channel row is NOT written to the DB."""
    from unittest.mock import MagicMock, patch
    from api.dependencies import get_current_user
    from api.models import User
    from api.main import app

    client, _ = auth_client

    user_with_profile = User(
        google_id="val-test-google",
        email="valtest@example.com",
        display_name="Val User",
        profile="adult",
        goal="Build muscle",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_with_profile)
    db_session.commit()
    db_session.refresh(user_with_profile)

    app.dependency_overrides[get_current_user] = lambda: user_with_profile
    mock_client = _make_anthropic_mock("no: cooking channel")

    try:
        with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            resp = client.post("/channels", json={
                "name": "Cooking With Gordon",
                "youtube_url": "https://youtube.com/@gordonramsay",
                "youtube_channel_id": "UCcooking",
                "description": "Cooking and recipes",
            })
    finally:
        from api.dependencies import get_current_user as _gcu
        app.dependency_overrides[get_current_user] = lambda: auth_client[1]

    assert resp.status_code == 422
    assert "cooking channel" in resp.json()["detail"]

    # Verify nothing was written to the DB
    from api.models import Channel, UserChannel
    assert db_session.query(Channel).filter(Channel.name == "Cooking With Gordon").first() is None
    assert db_session.query(UserChannel).filter(UserChannel.user_id == user_with_profile.id).count() == 0


def test_add_channel_validation_match_is_saved(auth_client, db_session):
    """On validation pass, the channel row IS written to the DB."""
    from unittest.mock import MagicMock, patch
    from api.dependencies import get_current_user
    from api.models import User
    from api.main import app

    client, _ = auth_client

    user_with_profile = User(
        google_id="val-match-google",
        email="valmatch@example.com",
        display_name="Val Match User",
        profile="adult",
        goal="Build muscle",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_with_profile)
    db_session.commit()
    db_session.refresh(user_with_profile)

    app.dependency_overrides[get_current_user] = lambda: user_with_profile
    mock_client = _make_anthropic_mock("yes")

    try:
        with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            resp = client.post("/channels", json={
                "name": "Athlean-X",
                "youtube_url": "https://youtube.com/@athleanx",
                "youtube_channel_id": "UCathlean",
                "description": "Science-based strength training",
            })
    finally:
        app.dependency_overrides[get_current_user] = lambda: auth_client[1]

    assert resp.status_code == 201

    from api.models import Channel, UserChannel
    ch = db_session.query(Channel).filter(Channel.name == "Athlean-X").first()
    assert ch is not None
    assert ch.description == "Science-based strength training"
    uc = db_session.query(UserChannel).filter(UserChannel.user_id == user_with_profile.id).first()
    assert uc is not None


def test_schedule_update_saves_profile_and_goal(auth_client, db_session):
    """PUT /schedule with profile+goal persists them on the user row."""
    client, user = auth_client

    resp = client.put("/schedule", json={
        "schedule": [
            {"day": "monday", "workout_type": "strength", "body_focus": "full_body",
             "duration_min": 30, "duration_max": 45, "difficulty": "intermediate"},
        ],
        "profile": "adult",
        "goal": "Build muscle",
    })

    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.profile == "adult"
    assert user.goal == "Build muscle"


def test_schedule_update_without_profile_leaves_existing(auth_client, db_session):
    """PUT /schedule without profile/goal does NOT overwrite existing values."""
    client, user = auth_client
    user.profile = "athlete"
    user.goal = "Athletic performance"
    db_session.commit()

    resp = client.put("/schedule", json={
        "schedule": [
            {"day": "monday", "workout_type": "strength", "body_focus": "full_body",
             "duration_min": 30, "duration_max": 45, "difficulty": "intermediate"},
        ],
    })

    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.profile == "athlete"
    assert user.goal == "Athletic performance"
