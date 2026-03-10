"""
Unit tests for the admin stats, management, and announcements endpoints.
"""

import os

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.main import app
from api.models import Announcement, BatchUsageLog, Channel, Classification, ProgramHistory, User, UserCredentials, Video


# --- Fixtures ---


@pytest.fixture
def admin_client(db_session):
    """TestClient authenticated as an admin user."""
    from api.dependencies import get_db

    os.environ["ADMIN_EMAIL"] = "admin@example.com"

    def _override_get_db():
        yield db_session

    admin = User(google_id="admin-google-id", email="admin@example.com", display_name="Admin")
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    def _override_get_current_user():
        return admin

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, admin, db_session
    app.dependency_overrides.clear()
    os.environ.pop("ADMIN_EMAIL", None)


@pytest.fixture
def non_admin_client(db_session):
    """TestClient authenticated as a regular user."""
    from api.dependencies import get_db

    os.environ["ADMIN_EMAIL"] = "admin@example.com"

    def _override_get_db():
        yield db_session

    user = User(google_id="user-google-id", email="user@example.com", display_name="Regular User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, user
    app.dependency_overrides.clear()
    os.environ.pop("ADMIN_EMAIL", None)


# --- Stats ---


def test_admin_stats_returns_200(admin_client):
    client, _, _ = admin_client
    assert client.get("/admin/stats").status_code == 200


def test_admin_stats_shape(admin_client):
    client, _, _ = admin_client
    data = client.get("/admin/stats").json()
    for key in ("users", "library", "channels", "plans", "pipelines", "ai_usage", "user_rows"):
        assert key in data


def test_admin_stats_user_counts(admin_client):
    client, _, db = admin_client
    extra = User(google_id="extra-id", email="extra@example.com")
    db.add(extra)
    db.commit()
    data = client.get("/admin/stats").json()
    assert data["users"]["total"] == 2


def test_admin_stats_library_counts(admin_client):
    client, admin, db = admin_client
    channel = Channel(user_id=admin.id, name="Ch", youtube_url="https://youtube.com/c/test")
    db.add(channel)
    db.flush()
    video = Video(id="vid1", channel_id=channel.id, title="V", url="https://youtube.com/watch?v=vid1")
    db.add(video)
    db.flush()
    db.add(Classification(video_id="vid1", workout_type="Strength"))
    db.commit()
    data = client.get("/admin/stats").json()
    assert data["library"]["total_videos"] == 1
    assert data["library"]["classified"] == 1
    assert data["library"]["classification_pct"] == 100.0


def test_admin_stats_last_active_in_user_rows(admin_client):
    client, _, _ = admin_client
    data = client.get("/admin/stats").json()
    row = data["user_rows"][0]
    assert "last_active_at" in row


def test_admin_stats_ai_usage(admin_client):
    client, admin, db = admin_client
    db.add(BatchUsageLog(
        user_id=admin.id,
        batch_id="batch_abc",
        videos_submitted=10,
        classified=9,
        failed=1,
        input_tokens=5000,
        output_tokens=500,
    ))
    db.commit()
    data = client.get("/admin/stats").json()
    ai = data["ai_usage"]["all_time"]
    assert ai["batches"] == 1
    assert ai["videos_classified"] == 9
    assert ai["input_tokens"] == 5000
    assert ai["output_tokens"] == 500
    assert ai["est_cost_usd"] > 0


def test_non_admin_stats_403(non_admin_client):
    client, _ = non_admin_client
    assert client.get("/admin/stats").status_code == 403


def test_no_admin_email_env_gives_403(admin_client):
    client, _, _ = admin_client
    os.environ.pop("ADMIN_EMAIL", None)
    assert client.get("/admin/stats").status_code == 403


# --- Delete user ---


def test_admin_delete_user(admin_client):
    client, _, db = admin_client
    victim = User(google_id="victim-id", email="victim@example.com")
    db.add(victim)
    db.commit()
    db.refresh(victim)
    res = client.delete(f"/admin/users/{victim.id}")
    assert res.status_code == 204
    assert db.get(User, victim.id) is None


def test_admin_cannot_delete_self(admin_client):
    client, admin, _ = admin_client
    res = client.delete(f"/admin/users/{admin.id}")
    assert res.status_code == 400


def test_admin_delete_nonexistent_user_404(admin_client):
    client, _, _ = admin_client
    assert client.delete("/admin/users/nonexistent-id").status_code == 404


def test_non_admin_cannot_delete_user(non_admin_client, db_session):
    client, _ = non_admin_client
    victim = User(google_id="v2", email="v2@example.com")
    db_session.add(victim)
    db_session.commit()
    db_session.refresh(victim)
    assert client.delete(f"/admin/users/{victim.id}").status_code == 403


# --- Retry scan ---


def test_admin_retry_scan_no_channels_400(admin_client):
    client, _, db = admin_client
    user = User(google_id="u2", email="u2@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    res = client.post(f"/admin/users/{user.id}/scan")
    assert res.status_code == 400


def test_admin_retry_scan_with_channels_202(admin_client):
    client, _, db = admin_client
    user = User(google_id="u3", email="u3@example.com")
    db.add(user)
    db.flush()
    db.add(Channel(user_id=user.id, name="Ch", youtube_url="https://youtube.com/c/ch"))
    db.commit()
    db.refresh(user)
    res = client.post(f"/admin/users/{user.id}/scan")
    assert res.status_code == 202


# --- Announcements ---


def test_create_announcement(admin_client):
    client, _, _ = admin_client
    res = client.post("/admin/announcements", json={"message": "Hello everyone!"})
    assert res.status_code == 201
    data = res.json()
    assert data["message"] == "Hello everyone!"
    assert data["is_active"] is True


def test_list_announcements(admin_client):
    client, _, _ = admin_client
    client.post("/admin/announcements", json={"message": "Msg 1"})
    client.post("/admin/announcements", json={"message": "Msg 2"})
    data = client.get("/admin/announcements").json()
    assert len(data) == 2


def test_delete_announcement(admin_client):
    client, _, _ = admin_client
    ann_id = client.post("/admin/announcements", json={"message": "To delete"}).json()["id"]
    assert client.delete(f"/admin/announcements/{ann_id}").status_code == 204
    assert client.get("/admin/announcements").json() == []


def test_deactivate_announcement(admin_client):
    client, _, _ = admin_client
    ann_id = client.post("/admin/announcements", json={"message": "Active msg"}).json()["id"]
    res = client.patch(f"/admin/announcements/{ann_id}/deactivate")
    assert res.status_code == 200
    assert res.json()["is_active"] is False


# --- Active announcement (regular user) ---


def test_active_announcement_for_regular_user(non_admin_client, db_session):
    client, _ = non_admin_client
    db_session.add(Announcement(message="System update tonight", is_active=True))
    db_session.commit()
    res = client.get("/announcements/active")
    assert res.status_code == 200
    assert res.json()["message"] == "System update tonight"


def test_no_active_announcement_returns_null(non_admin_client):
    client, _ = non_admin_client
    res = client.get("/announcements/active")
    assert res.status_code == 200
    assert res.json() is None


def test_inactive_announcement_not_returned(non_admin_client, db_session):
    client, _ = non_admin_client
    db_session.add(Announcement(message="Old news", is_active=False))
    db_session.commit()
    res = client.get("/announcements/active")
    assert res.json() is None
