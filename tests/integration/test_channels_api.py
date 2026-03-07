"""
Integration tests for /channels endpoints against real PostgreSQL.

What these add over unit tests:
  - Real FK CASCADE: deleting a channel actually removes its videos
  - Real UNIQUE constraint on youtube_url per user
  - User isolation verified at the DB level
"""

from datetime import datetime, timezone

from api.models import Channel, Classification, Video


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
    db_session.add(Channel(user_id=other.id, name="Other Channel", youtube_url="https://youtube.com/@other"))
    db_session.add(Channel(user_id=user.id, name="My Channel", youtube_url="https://youtube.com/@mine"))
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

    row = db_session.query(Channel).filter(Channel.user_id == user.id).first()
    assert row is not None
    assert row.name == "Jeff Nippard"
    assert row.youtube_channel_id == "UC123"


def test_add_duplicate_url_returns_409(auth_client, db_session):
    client, user = auth_client
    db_session.add(Channel(user_id=user.id, name="Jeff", youtube_url="https://youtube.com/@jeff"))
    db_session.commit()

    resp = client.post("/channels", json={"name": "Jeff Again", "youtube_url": "https://youtube.com/@jeff"})
    assert resp.status_code == 409

    # Still only one row
    assert db_session.query(Channel).filter(Channel.user_id == user.id).count() == 1


def test_same_url_allowed_for_different_users(auth_client, db_session):
    """Two users can both add the same channel URL."""
    from api.models import User
    client, user = auth_client

    other = User(google_id="other-g2", email="other2@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    db_session.add(Channel(user_id=other.id, name="Shared Channel", youtube_url="https://youtube.com/@shared"))
    db_session.commit()

    resp = client.post("/channels", json={"name": "Shared Channel", "youtube_url": "https://youtube.com/@shared"})
    assert resp.status_code == 201


# ─── Delete ───────────────────────────────────────────────────────────────────

def test_delete_channel_removes_from_postgres(auth_client, db_session):
    client, user = auth_client
    ch = Channel(user_id=user.id, name="To Delete", youtube_url="https://youtube.com/@delete")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 204
    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is None


def test_delete_channel_cascades_to_videos_and_classifications(auth_client, db_session):
    """Real PostgreSQL CASCADE: deleting a channel removes its videos and classifications."""
    client, user = auth_client

    ch = Channel(user_id=user.id, name="CascadeTest", youtube_url="https://youtube.com/@cascade")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    video = Video(id="vid-cascade", channel_id=ch.id, title="Test Video", url="https://youtube.com/watch?v=vid-cascade")
    db_session.add(video)
    db_session.add(Classification(video_id="vid-cascade", workout_type="strength", body_focus="upper", difficulty="intermediate"))
    db_session.commit()

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 204

    assert db_session.query(Video).filter(Video.id == "vid-cascade").first() is None
    assert db_session.query(Classification).filter(Classification.video_id == "vid-cascade").first() is None


def test_delete_other_users_channel_returns_404(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    other = User(google_id="other-g3", email="other3@example.com", created_at=datetime.now(timezone.utc))
    db_session.add(other)
    db_session.commit()
    ch = Channel(user_id=other.id, name="Not Yours", youtube_url="https://youtube.com/@notyours")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    resp = client.delete(f"/channels/{ch.id}")
    assert resp.status_code == 404
    # Channel must still exist
    assert db_session.query(Channel).filter(Channel.id == ch.id).first() is not None
