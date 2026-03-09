"""
auth.py — Google OAuth 2.0 login/logout routes.

Flow:
  1. GET /auth/google         → redirect to Google consent screen
  2. GET /auth/google/callback → exchange code, upsert user, set session
  3. POST /auth/logout         → clear session
"""

import os
import secrets
from urllib.parse import urlencode

from itsdangerous import URLSafeTimedSerializer

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..crypto import encrypt
from ..dependencies import get_current_user, get_db
from ..models import User, UserCredentials
from ..schemas import MeResponse, PatchMeRequest

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Request YouTube access now so we don't need to re-prompt in Phase 5
SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube",
])


async def _exchange_code_for_tokens(code: str) -> dict:
    """POST to Google token endpoint and return the token response JSON."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
    return resp.json()


async def _get_google_userinfo(access_token: str) -> dict:
    """Fetch the authenticated user's Google profile."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
    return resp.json()


@router.get("/google")
async def google_login(request: Request):
    """Redirect the user to Google's OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange OAuth code for tokens, upsert user, and set session."""
    if state != request.session.get("oauth_state"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF")

    tokens = await _exchange_code_for_tokens(code)
    userinfo = await _get_google_userinfo(tokens["access_token"])

    # Upsert user
    user = db.query(User).filter(User.google_id == userinfo["id"]).first()
    if not user:
        user = User(
            google_id=userinfo["id"],
            email=userinfo["email"],
            display_name=userinfo.get("name"),
        )
        db.add(user)
        db.flush()
    else:
        user.email = userinfo["email"]
        user.display_name = userinfo.get("name")

    # Persist YouTube refresh token (only present on first consent)
    creds = db.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    if not creds:
        creds = UserCredentials(user_id=user.id)
        db.add(creds)
    if "refresh_token" in tokens:
        creds.youtube_refresh_token = encrypt(tokens["refresh_token"])

    db.commit()

    request.session["user_id"] = str(user.id)
    request.session.pop("oauth_state", None)

    # Pass a signed token in the redirect URL so the frontend can authenticate
    # across domains without relying on cross-domain cookies.
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    token = URLSafeTimedSerializer(secret).dumps(str(user.id))
    return RedirectResponse(f"{FRONTEND_URL}?token={token}")


def _me_response(user: User, db: Session) -> MeResponse:
    """Build a MeResponse for the given user."""
    creds = db.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        youtube_connected=bool(creds and creds.youtube_refresh_token),
        credentials_valid=creds.credentials_valid if creds else True,
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current user's profile, or 401 if not logged in."""
    return _me_response(current_user, db)


@router.patch("/me", response_model=MeResponse)
def patch_me(
    body: PatchMeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's display name."""
    current_user.display_name = body.display_name.strip() or None
    db.commit()
    return _me_response(current_user, db)


@router.delete("/me", status_code=204)
def delete_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete the current user and all their data."""
    db.delete(current_user)
    db.commit()
    request.session.clear()


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}
