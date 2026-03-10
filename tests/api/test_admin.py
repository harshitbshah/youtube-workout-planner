"""
Unit tests for the admin stats endpoint.
"""

import os

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.main import app
from api.models import Channel, Classification, ProgramHistory, User, UserCredentials, Video


# --- Fixtures ---


@pytest.fixture
def admin_client(db_session):
    """TestClient authenticated as an admin user (email matches ADMIN_EMAIL)."""
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
    """TestClient authenticated as a regular (non-admin) user."""
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
        yield c
    app.dependency_overrides.clear()
    os.environ.pop("ADMIN_EMAIL", None)


# --- Tests ---


def test_admin_stats_returns_200(admin_client):
    client, _, _ = admin_client
    res = client.get("/admin/stats")
    assert res.status_code == 200


def test_admin_stats_shape(admin_client):
    client, _, _ = admin_client
    data = client.get("/admin/stats").json()

    assert "users" in data
    assert "library" in data
    assert "channels" in data
    assert "plans" in data
    assert "pipelines" in data
    assert "user_rows" in data


def test_admin_stats_user_counts(admin_client):
    client, admin, db = admin_client

    # Add one more regular user
    extra = User(google_id="extra-id", email="extra@example.com")
    db.add(extra)
    db.commit()

    data = client.get("/admin/stats").json()
    assert data["users"]["total"] == 2


def test_admin_stats_library_counts(admin_client):
    client, admin, db = admin_client

    channel = Channel(user_id=admin.id, name="Test Channel", youtube_url="https://youtube.com/c/test")
    db.add(channel)
    db.flush()

    video = Video(id="vid1", channel_id=channel.id, title="Test Video", url="https://youtube.com/watch?v=vid1")
    db.add(video)
    db.flush()

    clf = Classification(video_id="vid1", workout_type="Strength")
    db.add(clf)
    db.commit()

    data = client.get("/admin/stats").json()
    assert data["library"]["total_videos"] == 1
    assert data["library"]["classified"] == 1
    assert data["library"]["unclassified"] == 0
    assert data["library"]["classification_pct"] == 100.0


def test_admin_stats_user_row_fields(admin_client):
    client, admin, db = admin_client

    channel = Channel(user_id=admin.id, name="Channel A", youtube_url="https://youtube.com/c/a")
    db.add(channel)
    db.commit()

    data = client.get("/admin/stats").json()
    row = next(r for r in data["user_rows"] if r["email"] == "admin@example.com")

    assert row["channels"] == 1
    assert row["email"] == "admin@example.com"
    assert row["youtube_connected"] is False
    assert row["last_plan"] is None


def test_admin_stats_youtube_connected(admin_client):
    client, admin, db = admin_client

    cred = UserCredentials(
        user_id=admin.id,
        youtube_refresh_token="tok",
        credentials_valid=True,
    )
    db.add(cred)
    db.commit()

    data = client.get("/admin/stats").json()
    assert data["users"]["youtube_connected"] == 1

    row = next(r for r in data["user_rows"] if r["email"] == "admin@example.com")
    assert row["youtube_connected"] is True


def test_non_admin_gets_403(non_admin_client):
    res = non_admin_client.get("/admin/stats")
    assert res.status_code == 403


def test_no_admin_email_env_gives_403(admin_client):
    client, _, _ = admin_client
    os.environ.pop("ADMIN_EMAIL", None)
    res = client.get("/admin/stats")
    assert res.status_code == 403
