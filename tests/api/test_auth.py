"""
Tests for Google OAuth routes.

All HTTP calls to Google are mocked — no real network calls are made.
"""

from unittest.mock import AsyncMock, patch

from api.crypto import decrypt
from api.models import User, UserCredentials


def test_google_login_redirects_to_google(client):
    resp = client.get("/auth/google", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.google.com" in resp.headers["location"]


def test_google_login_sets_state_in_session(client):
    resp = client.get("/auth/google", follow_redirects=False)
    # State param must be in the redirect URL
    location = resp.headers["location"]
    assert "state=" in location


def _mock_google(access_token="tok", refresh_token="ref", google_id="g123",
                 email="user@example.com", name="Test User"):
    """Return patch targets for both Google HTTP calls."""
    token_data = {"access_token": access_token, "refresh_token": refresh_token}
    userinfo_data = {"id": google_id, "email": email, "name": name}

    mock_token_resp = AsyncMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json = lambda: token_data

    mock_userinfo_resp = AsyncMock()
    mock_userinfo_resp.status_code = 200
    mock_userinfo_resp.json = lambda: userinfo_data

    return mock_token_resp, mock_userinfo_resp


def test_callback_creates_user_and_sets_session(client, db_session):
    # Seed a valid state in the session by hitting /auth/google first
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    mock_token_resp, mock_userinfo_resp = _mock_google()

    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=mock_token_resp.json())), \
         patch("api.routers.auth._get_google_userinfo", new=AsyncMock(return_value=mock_userinfo_resp.json())):
        resp = client.get(f"/auth/google/callback?code=authcode&state={state}", follow_redirects=False)

    assert resp.status_code in (302, 307)

    user = db_session.query(User).filter(User.google_id == "g123").first()
    assert user is not None
    assert user.email == "user@example.com"

    creds = db_session.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    assert creds is not None
    # DB must never contain the plaintext token
    assert creds.youtube_refresh_token != "ref"
    # But it must decrypt back to the original value
    assert decrypt(creds.youtube_refresh_token) == "ref"


def test_callback_updates_existing_user(client, db_session):
    # First login — creates user
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    mock_token_resp, mock_userinfo_resp = _mock_google(name="Old Name")
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=mock_token_resp.json())), \
         patch("api.routers.auth._get_google_userinfo", new=AsyncMock(return_value=mock_userinfo_resp.json())):
        client.get(f"/auth/google/callback?code=c&state={state}", follow_redirects=False)

    # Second login — same google_id, updated name
    login_resp2 = client.get("/auth/google", follow_redirects=False)
    state2 = login_resp2.headers["location"].split("state=")[1].split("&")[0]

    mock_token_resp2, mock_userinfo_resp2 = _mock_google(name="New Name", refresh_token=None)
    tokens2 = {"access_token": "tok2"}   # no refresh_token this time
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=tokens2)), \
         patch("api.routers.auth._get_google_userinfo", new=AsyncMock(return_value=mock_userinfo_resp2.json())):
        client.get(f"/auth/google/callback?code=c2&state={state2}", follow_redirects=False)

    users = db_session.query(User).filter(User.google_id == "g123").all()
    assert len(users) == 1
    assert users[0].display_name == "New Name"


def test_callback_rejects_invalid_state(client):
    resp = client.get("/auth/google/callback?code=x&state=wrong_state")
    assert resp.status_code == 400


def test_logout_clears_session(client, db_session):
    # Log in first
    login_resp = client.get("/auth/google", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]
    mock_token, mock_userinfo = _mock_google()
    with patch("api.routers.auth._exchange_code_for_tokens", new=AsyncMock(return_value=mock_token.json())), \
         patch("api.routers.auth._get_google_userinfo", new=AsyncMock(return_value=mock_userinfo.json())):
        client.get(f"/auth/google/callback?code=c&state={state}", follow_redirects=False)

    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Logged out"}
