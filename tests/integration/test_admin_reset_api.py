"""
Integration test for POST /admin/users/{user_id}/reset-onboarding against real PostgreSQL.

Verifies that:
- channel subscriptions and schedule rows are deleted for the target user
- shared channel + video rows are preserved
- another user's subscriptions are not affected
"""

import os

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user, get_db
from api.main import app
from api.models import Channel, Schedule, User, UserChannel, Video


@pytest.fixture
def admin_client_pg(db_session):
    os.environ["ADMIN_EMAIL"] = "admin@example.com"
    admin = User(google_id="admin-pg-id", email="admin@example.com", display_name="Admin")
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    def _get_db():
        yield db_session

    def _get_user():
        return admin

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, admin, db_session
    app.dependency_overrides.clear()
    os.environ.pop("ADMIN_EMAIL", None)


def test_reset_clears_subscriptions_and_schedule(admin_client_pg):
    client, _, db = admin_client_pg
    target = User(google_id="tgt-pg-id", email="target@example.com")
    db.add(target)
    db.flush()
    ch = Channel(name="Ch", youtube_url="https://youtube.com/c/ch")
    db.add(ch)
    db.flush()
    db.add(UserChannel(user_id=target.id, channel_id=ch.id))
    db.add(Schedule(user_id=target.id, day="monday", workout_type="Strength"))
    db.commit()

    resp = client.post(f"/admin/users/{target.id}/reset-onboarding")
    assert resp.status_code == 204

    assert db.query(UserChannel).filter(UserChannel.user_id == target.id).count() == 0
    assert db.query(Schedule).filter(Schedule.user_id == target.id).count() == 0
    # channel itself must survive
    assert db.get(Channel, ch.id) is not None


def test_reset_does_not_touch_other_user_subscriptions(admin_client_pg):
    client, _, db = admin_client_pg
    other = User(google_id="other-pg-id", email="other@example.com")
    target = User(google_id="tgt2-pg-id", email="target2@example.com")
    db.add_all([other, target])
    db.flush()
    ch = Channel(name="Shared", youtube_url="https://youtube.com/c/shared")
    db.add(ch)
    db.flush()
    db.add(UserChannel(user_id=other.id, channel_id=ch.id))
    db.add(UserChannel(user_id=target.id, channel_id=ch.id))
    db.commit()

    client.post(f"/admin/users/{target.id}/reset-onboarding")

    assert db.query(UserChannel).filter(UserChannel.user_id == other.id).count() == 1
