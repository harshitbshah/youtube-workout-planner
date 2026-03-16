"""
Tests for Google OAuth routes.

All HTTP calls to Google are mocked - no real network calls are made.
"""

import base64
import json
from unittest.mock import AsyncMock, patch

from api.crypto import decrypt, encrypt
from api.models import User, UserCredentials


def test_google_login_redirects_to_google(client):
    resp = client.get("/auth/google", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


def test_google_login_sets_state_in_session(client):
    resp = client.get("/auth/google", follow_redirects=False)
    location = resp.headers["location"]
    assert "state=" in location


def test_google_login_does_not_include_youtube_scope(client):
    resp = client.get("/auth/google", follow_redirects=False)
    location = resp.headers["location"]
    assert "youtube" not in location


def test_google_login_uses_select_account_prompt(client):
    resp = client.get("/auth/google", follow_redirects=False)
    location = resp.headers["location"]
    assert "select_account" in location


def _make_id_token(google_id="g123", email="user@example.com", name="Test User") -> str:
    """Build a minimal JWT id_token with the given claims (no real signature needed for tests)."""
    payload = base64.b64encode(
        json.dumps({"sub": google_id, "email": email, "name": name}).encode()
    ).decode().rstrip("=")
    return f"header.{payload}.sig"


def _mock_google(access_token="tok", refresh_token="ref", google_id="g123",
                 email="user@example.com", name="Test User") -> dict:
    """Return a token response dict that _exchange_code_for_tokens would return."""
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": _make_id_token(google_id, email, name),
    }


def test_callback_creates_user_and_sets_session(client, db_session):
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=_mock_google())):
        resp = client.get(f"/auth/google/callback?code=authcode&state={state}", follow_redirects=False)

    assert resp.status_code in (302, 307)

    user = db_session.query(User).filter(User.google_id == "g123").first()
    assert user is not None
    assert user.email == "user@example.com"

    # Login no longer stores YouTube credentials - they come from /auth/youtube/connect
    creds = db_session.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    assert creds is None


def test_callback_updates_existing_user(client, db_session):
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=_mock_google(name="Old Name"))):
        client.get(f"/auth/google/callback?code=c&state={state}", follow_redirects=False)

    login_resp2 = client.get("/auth/google", follow_redirects=False)
    state2 = login_resp2.headers["location"].split("state=")[1].split("&")[0]

    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=_mock_google(name="New Name"))):
        client.get(f"/auth/google/callback?code=c2&state={state2}", follow_redirects=False)

    users = db_session.query(User).filter(User.google_id == "g123").all()
    assert len(users) == 1
    assert users[0].display_name == "New Name"


def test_callback_rejects_invalid_state(client):
    resp = client.get("/auth/google/callback?code=x&state=wrong_state")
    assert resp.status_code == 400


# ─── YouTube connect tests ─────────────────────────────────────────────────────

def _make_auth_token(user_id: str) -> str:
    """Generate a valid Bearer token for the given user_id (matches dependencies.py)."""
    import os
    from itsdangerous import URLSafeTimedSerializer
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    return URLSafeTimedSerializer(secret).dumps(str(user_id))


def _make_youtube_state(user_id: str) -> str:
    """Generate a valid signed YouTube OAuth state for the given user_id."""
    import os
    from itsdangerous import URLSafeTimedSerializer
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    return URLSafeTimedSerializer(secret).dumps({"user_id": str(user_id), "nonce": "testnonce"})


def test_youtube_connect_requires_auth(client):
    # No token param - should 401
    resp = client.get("/auth/youtube/connect", follow_redirects=False)
    assert resp.status_code == 401


def test_youtube_connect_rejects_invalid_token(client):
    resp = client.get("/auth/youtube/connect?token=bad_token", follow_redirects=False)
    assert resp.status_code == 401


def test_youtube_connect_redirects_to_google(auth_client):
    client, user = auth_client
    token = _make_auth_token(str(user.id))
    resp = client.get(f"/auth/youtube/connect?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


def test_youtube_connect_includes_youtube_scope(auth_client):
    client, user = auth_client
    token = _make_auth_token(str(user.id))
    resp = client.get(f"/auth/youtube/connect?token={token}", follow_redirects=False)
    location = resp.headers["location"]
    assert "youtube" in location


def test_youtube_connect_uses_login_hint(auth_client):
    from urllib.parse import unquote
    client, user = auth_client
    token = _make_auth_token(str(user.id))
    resp = client.get(f"/auth/youtube/connect?token={token}", follow_redirects=False)
    location = unquote(resp.headers["location"])
    assert user.email in location


def test_youtube_callback_stores_refresh_token(auth_client, db_session):
    client, user = auth_client

    # Build signed state directly - no session needed
    state = _make_youtube_state(str(user.id))

    tokens = {"access_token": "yt_access", "refresh_token": "yt_refresh"}
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=tokens)):
        resp = client.get(f"/auth/youtube/callback?code=ytcode&state={state}", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "/dashboard" in resp.headers["location"]

    db_session.expire_all()
    creds = db_session.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    assert creds is not None
    assert creds.credentials_valid is True
    assert decrypt(creds.youtube_refresh_token) == "yt_refresh"


def test_youtube_callback_rejects_invalid_state(client):
    tokens = {"access_token": "tok", "refresh_token": "ref"}
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=tokens)):
        resp = client.get("/auth/youtube/callback?code=x&state=bad_state")
    assert resp.status_code == 400


# ─── Account deletion ─────────────────────────────────────────────────────────

def _login_and_create_creds(client, db_session, refresh_token="refresh_tok"):
    """Helper: log in via OAuth and manually seed YouTube credentials."""
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=_mock_google())):
        client.get(f"/auth/google/callback?code=c&state={state}", follow_redirects=False)

    user = db_session.query(User).filter(User.google_id == "g123").first()
    creds = UserCredentials(user_id=user.id, youtube_refresh_token=encrypt(refresh_token))
    db_session.add(creds)
    db_session.commit()
    return user


def test_delete_me_revokes_token_and_deletes_user(client, db_session):
    _login_and_create_creds(client, db_session, refresh_token="refresh_tok")

    revoke_mock = AsyncMock()
    with patch("api.routers.auth.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(post=revoke_mock))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = client.delete("/auth/me")

    assert resp.status_code == 204
    revoke_mock.assert_called_once()
    call_kwargs = revoke_mock.call_args
    assert "revoke" in call_kwargs[0][0]
    assert call_kwargs[1]["params"]["token"] == "refresh_tok"
    db_session.expire_all()
    assert db_session.query(User).filter(User.google_id == "g123").first() is None


def test_delete_me_proceeds_if_revoke_fails(client, db_session):
    _login_and_create_creds(client, db_session)

    with patch("api.routers.auth.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(side_effect=Exception("network error"))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = client.delete("/auth/me")

    assert resp.status_code == 204
    db_session.expire_all()
    assert db_session.query(User).filter(User.google_id == "g123").first() is None


# ─── Fitness profile ───────────────────────────────────────────────────────────

def test_patch_me_profile_updates_profile_and_goal(auth_client, db_session):
    client, user = auth_client
    resp = client.patch("/auth/me/profile", json={"profile": "adult", "goal": ["Build muscle"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"] == "adult"
    assert data["goal"] == ["Build muscle"]
    db_session.refresh(user)
    assert user.profile == "adult"
    assert user.goal == '["Build muscle"]'


def test_patch_me_profile_rejects_invalid_profile(auth_client):
    client, user = auth_client
    resp = client.patch("/auth/me/profile", json={"profile": "ninja", "goal": ["Build muscle"]})
    assert resp.status_code == 400


def test_patch_me_profile_rejects_goal_mismatched_to_profile(auth_client):
    client, user = auth_client
    resp = client.patch("/auth/me/profile", json={"profile": "beginner", "goal": ["Strength & hypertrophy"]})
    assert resp.status_code == 400


def test_patch_me_profile_requires_auth(client):
    resp = client.patch("/auth/me/profile", json={"profile": "adult", "goal": ["Build muscle"]})
    assert resp.status_code == 401


def test_me_response_includes_profile_and_goal(auth_client, db_session):
    import json
    client, user = auth_client
    user.profile = "senior"
    user.goal = json.dumps(["Stay active & healthy"])
    db_session.commit()
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"] == "senior"
    assert data["goal"] == ["Stay active & healthy"]
    assert data["created_at"] is not None


def test_logout_clears_session(client, db_session):
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=_mock_google())):
        client.get(f"/auth/google/callback?code=c&state={state}", follow_redirects=False)

    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Logged out"}
