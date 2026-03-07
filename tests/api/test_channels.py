"""
Tests for /channels endpoints.

YouTube search calls are mocked — no real network calls.
"""

from unittest.mock import AsyncMock, patch

from api.models import Channel


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _add_channel(db_session, user, name="Jeff Nippard", url="https://youtube.com/@jeffnippard"):
    ch = Channel(user_id=user.id, name=name, youtube_url=url, youtube_channel_id="UCe0TLA0EsQbE-MjuHXevj2A")
    db_session.add(ch)
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

    # Persisted in DB
    ch = db_session.query(Channel).filter(Channel.user_id == user.id).first()
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

    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is None


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
