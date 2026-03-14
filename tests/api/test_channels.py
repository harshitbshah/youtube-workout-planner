"""
Tests for /channels endpoints.

YouTube search calls are mocked — no real network calls.
"""

from unittest.mock import AsyncMock, patch

from api.models import Channel, UserChannel


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _add_channel(db_session, user, name="Jeff Nippard", url="https://youtube.com/@jeffnippard"):
    ch = Channel(name=name, youtube_url=url, youtube_channel_id="UCe0TLA0EsQbE-MjuHXevj2A")
    db_session.add(ch)
    db_session.flush()
    db_session.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db_session.commit()
    db_session.refresh(ch)
    return ch


# ─── List ─────────────────────────────────────────────────────────────────────

def test_list_channels_empty(auth_client):
    client, user = auth_client
    resp = client.get("/channels")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_channels_returns_users_channels(auth_client, db_session):
    client, user = auth_client
    _add_channel(db_session, user)
    resp = client.get("/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Jeff Nippard"


def test_list_channels_unauthenticated(client):
    resp = client.get("/channels")
    assert resp.status_code == 401


# ─── Add ──────────────────────────────────────────────────────────────────────

def test_add_channel(auth_client, db_session):
    client, user = auth_client
    payload = {
        "name": "Athlean-X",
        "youtube_url": "https://youtube.com/@athleanx",
        "youtube_channel_id": "UCe0TLA0EsQbE-MjuHXevj2B",
    }
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Athlean-X"
    assert data["youtube_url"] == "https://youtube.com/@athleanx"
    assert "id" in data

    # Persisted in DB — verify via UserChannel join
    uc = db_session.query(UserChannel).filter(UserChannel.user_id == user.id).first()
    assert uc is not None
    ch = db_session.query(Channel).filter(Channel.id == uc.channel_id).first()
    assert ch is not None
    assert ch.name == "Athlean-X"


def test_add_duplicate_channel_returns_409(auth_client, db_session):
    client, user = auth_client
    _add_channel(db_session, user)
    payload = {"name": "Jeff Nippard", "youtube_url": "https://youtube.com/@jeffnippard"}
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 409


def test_add_channel_unauthenticated(client):
    resp = client.post("/channels", json={"name": "x", "youtube_url": "https://youtube.com/@x"})
    assert resp.status_code == 401


# ─── Delete ───────────────────────────────────────────────────────────────────

def test_delete_channel(auth_client, db_session):
    client, user = auth_client
    ch = _add_channel(db_session, user)
    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 204

    # Channel row is preserved; only the user_channels link is removed
    assert db_session.query(UserChannel).filter(
        UserChannel.user_id == user.id, UserChannel.channel_id == ch.id
    ).first() is None
    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is not None


def test_delete_channel_not_found(auth_client):
    client, user = auth_client
    resp = client.delete("/channels/nonexistent-id")
    assert resp.status_code == 404


def test_delete_channel_other_user(auth_client, db_session):
    """A user cannot delete another user's channel."""
    from api.models import User as UserModel
    client, user = auth_client

    other_user = UserModel(google_id="other-g-id", email="other@example.com")
    db_session.add(other_user)
    db_session.commit()
    ch = _add_channel(db_session, other_user, url="https://youtube.com/@other")

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 404


# ─── Search ───────────────────────────────────────────────────────────────────

def test_search_channels(auth_client):
    client, user = auth_client

    mock_response = {
        "items": [
            {
                "id": {"channelId": "UC123"},
                "snippet": {
                    "title": "Jeff Nippard",
                    "description": "Science-based lifting",
                    "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                },
            }
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_response

    with patch("api.routers.channels.YOUTUBE_API_KEY", "fake-key"), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        resp = client.get("/channels/search?q=jeff+nippard")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Jeff Nippard"
    assert data[0]["youtube_channel_id"] == "UC123"


def test_search_channels_no_api_key(auth_client):
    client, user = auth_client
    with patch("api.routers.channels.YOUTUBE_API_KEY", ""):
        resp = client.get("/channels/search?q=test")
    assert resp.status_code == 503


# ─── Suggestions ──────────────────────────────────────────────────────────────

def test_suggestions_cache_hit(auth_client, db_session):
    """All 3 cached channels for a profile are returned without any YouTube call."""
    client, user = auth_client

    # Pre-cache all 3 adult suggestions
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
    names = {d["name"] for d in data}
    assert "Athlean-X" in names
    # YouTube API must NOT have been called — all served from cache
    mock_http.assert_not_called()


def test_suggestions_cache_miss_fetches_youtube(auth_client, db_session):
    """On cache miss the YouTube API is called and result stored in Channel table."""
    client, user = auth_client

    mock_response = {
        "items": [
            {
                "id": {"channelId": "UCnef2XH0pDcTUGMZOWBvxPg"},
                "snippet": {
                    "title": "HASfit",
                    "description": "Free workouts",
                    "thumbnails": {"default": {"url": "https://example.com/hasfit.jpg"}},
                },
            }
        ]
    }
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_response

    with patch("api.routers.channels.YOUTUBE_API_KEY", "fake-key"), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        resp = client.get("/channels/suggestions?profile=senior")

    assert resp.status_code == 200
    data = resp.json()
    hasfit = next((d for d in data if d["name"] == "HASfit"), None)
    assert hasfit is not None
    assert hasfit["thumbnail_url"] == "https://example.com/hasfit.jpg"

    # Result must be persisted in Channel table for future cache hits
    stored = db_session.query(Channel).filter(Channel.name == "HASfit").first()
    assert stored is not None
    assert stored.thumbnail_url == "https://example.com/hasfit.jpg"


def test_suggestions_no_api_key_returns_only_cached(auth_client, db_session):
    """Without a YouTube API key, only already-cached suggestions are returned."""
    client, user = auth_client

    ch = Channel(
        name="Jeff Nippard",
        youtube_url="https://www.youtube.com/channel/UCnHoKuB-RfcBQqFTXaQP5vg",
        youtube_channel_id="UCnHoKuB-RfcBQqFTXaQP5vg",
        thumbnail_url="https://example.com/jeff.jpg",
        description="Science-based lifting",
    )
    db_session.add(ch)
    db_session.commit()

    with patch("api.routers.channels.YOUTUBE_API_KEY", ""):
        resp = client.get("/channels/suggestions?profile=adult")

    assert resp.status_code == 200
    data = resp.json()
    # Only Jeff Nippard is cached; Athlean-X and Heather Robertson are not
    assert len(data) == 1
    assert data[0]["name"] == "Jeff Nippard"


def test_suggestions_general_list_when_no_profile(auth_client, db_session):
    """No profile param returns general suggestion list (not 404)."""
    client, user = auth_client
    with patch("api.routers.channels.YOUTUBE_API_KEY", ""):
        resp = client.get("/channels/suggestions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_suggestions_unknown_profile_falls_back_to_general(auth_client, db_session):
    """Unknown profile falls back to the general suggestion list gracefully."""
    client, user = auth_client
    with patch("api.routers.channels.YOUTUBE_API_KEY", ""):
        resp = client.get("/channels/suggestions?profile=unknown")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_suggestions_unauthenticated(client):
    resp = client.get("/channels/suggestions?profile=adult")
    assert resp.status_code == 401


# ─── Channel validation ───────────────────────────────────────────────────────

def test_add_channel_blocked_when_mismatch(auth_client, db_session):
    """When user has profile+goal and Claude returns no, the channel is rejected."""
    from unittest.mock import MagicMock, patch
    from api.dependencies import get_current_user
    from api.models import User

    user_with_profile = User(
        google_id="profile-user",
        email="profile@example.com",
        profile="adult",
        goal="Build muscle",
    )
    db_session.add(user_with_profile)
    db_session.commit()
    db_session.refresh(user_with_profile)

    # Override get_current_user to return user with profile
    from api.main import app
    app.dependency_overrides[get_current_user] = lambda: user_with_profile

    content_block = MagicMock()
    content_block.text = "no: cooking recipes"
    mock_response = MagicMock()
    mock_response.content = [content_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    try:
        with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            resp = auth_client[0].post("/channels", json={
                "name": "Gordon Ramsay",
                "youtube_url": "https://youtube.com/@gordonramsay",
                "youtube_channel_id": "UCabc123",
                "description": "Cooking and recipes for every meal",
            })
    finally:
        app.dependency_overrides[get_current_user] = lambda: auth_client[1]

    assert resp.status_code == 422
    assert "cooking recipes" in resp.json()["detail"]
    assert "Build muscle" in resp.json()["detail"]

    # Channel must NOT have been saved
    from api.models import Channel
    ch = db_session.query(Channel).filter(Channel.name == "Gordon Ramsay").first()
    assert ch is None


def test_add_channel_allowed_when_match(auth_client, db_session):
    """When Claude returns yes, the channel is added normally."""
    from unittest.mock import MagicMock, patch
    from api.dependencies import get_current_user
    from api.models import User

    user_with_profile = User(
        google_id="profile-user-2",
        email="profile2@example.com",
        profile="adult",
        goal="Build muscle",
    )
    db_session.add(user_with_profile)
    db_session.commit()
    db_session.refresh(user_with_profile)

    from api.main import app
    app.dependency_overrides[get_current_user] = lambda: user_with_profile

    content_block = MagicMock()
    content_block.text = "yes"
    mock_response = MagicMock()
    mock_response.content = [content_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    try:
        with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            resp = auth_client[0].post("/channels", json={
                "name": "Athlean-X",
                "youtube_url": "https://youtube.com/@athleanx",
                "youtube_channel_id": "UCfit123",
                "description": "Strength training workouts",
            })
    finally:
        app.dependency_overrides[get_current_user] = lambda: auth_client[1]

    assert resp.status_code == 201
    assert resp.json()["name"] == "Athlean-X"


def test_add_channel_skips_validation_when_no_profile(auth_client):
    """When user has no profile/goal set, validation is skipped and channel is added."""
    from unittest.mock import patch
    # auth_client user has no profile/goal (default None)
    client, user = auth_client
    assert user.profile is None

    with patch("api.services.channel_validator.validate_channel_fitness") as mock_validate:
        resp = client.post("/channels", json={
            "name": "Random Channel",
            "youtube_url": "https://youtube.com/@random",
            "youtube_channel_id": "UCrandom",
            "description": "Some content",
        })
        mock_validate.assert_not_called()

    assert resp.status_code == 201


def test_add_channel_validation_fails_open_on_error(auth_client, db_session):
    """If the validator raises an exception, the channel is still added (fail open)."""
    from unittest.mock import patch
    from api.dependencies import get_current_user
    from api.models import User
    from api.main import app

    user_with_profile = User(
        google_id="failopen-user",
        email="failopen@example.com",
        profile="adult",
        goal="Build muscle",
    )
    db_session.add(user_with_profile)
    db_session.commit()
    db_session.refresh(user_with_profile)

    app.dependency_overrides[get_current_user] = lambda: user_with_profile

    try:
        with patch(
            "api.services.channel_validator.validate_channel_fitness",
            side_effect=Exception("unexpected"),
        ):
            # validate_channel_fitness raising shouldn't bubble up — but actually
            # the validator already catches exceptions internally and returns (True, None).
            # This test patches the validator itself to raise to verify the router handles it.
            # Since the validator wraps exceptions, we instead patch the Anthropic client.
            pass

        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")

        with patch("api.services.channel_validator.anthropic.Anthropic", return_value=mock_client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            resp = auth_client[0].post("/channels", json={
                "name": "Fitness Channel",
                "youtube_url": "https://youtube.com/@fitness",
                "youtube_channel_id": "UCfitness",
                "description": "Workouts and exercise",
            })
    finally:
        app.dependency_overrides[get_current_user] = lambda: auth_client[1]

    assert resp.status_code == 201
