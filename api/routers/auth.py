"""
auth.py - Google OAuth 2.0 login/logout routes.

Login flow (basic scopes only):
  1. GET /auth/google          → redirect to Google consent screen (openid, email, profile)
  2. GET /auth/google/callback → exchange code, upsert user, set session

YouTube connect flow (separate, incremental auth):
  3. GET /auth/youtube/connect  → redirect to Google with YouTube scope (requires login)
  4. GET /auth/youtube/callback → store YouTube refresh token, redirect to dashboard

Splitting scopes reduces initial login to 1-2 steps. YouTube permission is
requested only when the user explicitly connects YouTube.
"""

import os
import secrets
from urllib.parse import urlencode

from itsdangerous import URLSafeTimedSerializer

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..crypto import encrypt, decrypt
from ..dependencies import get_current_user, get_db
from ..models import User, UserCredentials
from ..schemas import MeResponse, PatchMeNotificationsRequest, PatchMeProfileRequest, PatchMeRequest

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)
YOUTUBE_REDIRECT_URI = os.getenv(
    "YOUTUBE_REDIRECT_URI", "http://localhost:8000/auth/youtube/callback"
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Basic login scopes - no YouTube, keeps initial sign-in to 1-2 steps
LOGIN_SCOPES = " ".join(["openid", "email", "profile"])

# YouTube scope requested separately via /auth/youtube/connect
YOUTUBE_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube",
])


async def _exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """POST to Google token endpoint and return the token response JSON."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
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
    """Redirect the user to Google's OAuth consent screen (basic scopes only)."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": LOGIN_SCOPES,
        "state": state,
        "prompt": "select_account",
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
        raise HTTPException(status_code=400, detail="Invalid OAuth state - possible CSRF")

    tokens = await _exchange_code_for_tokens(code, GOOGLE_REDIRECT_URI)
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

    db.commit()

    request.session["user_id"] = str(user.id)
    request.session.pop("oauth_state", None)

    # Pass a signed token in the redirect URL so the frontend can authenticate
    # across domains without relying on cross-domain cookies.
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    token = URLSafeTimedSerializer(secret).dumps(str(user.id))
    return RedirectResponse(f"{FRONTEND_URL}?token={token}")


@router.get("/youtube/connect")
async def youtube_connect(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Redirect the authenticated user to Google to grant YouTube access.

    Uses login_hint to skip the account chooser since the user is already
    signed in - reducing this to a single YouTube permission screen.
    """
    state = secrets.token_urlsafe(16)
    request.session["youtube_oauth_state"] = state

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": current_user.email,
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/youtube/callback")
async def youtube_callback(
    code: str,
    state: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store the YouTube refresh token and redirect back to the dashboard."""
    if state != request.session.get("youtube_oauth_state"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state - possible CSRF")

    tokens = await _exchange_code_for_tokens(code, YOUTUBE_REDIRECT_URI)

    creds = db.query(UserCredentials).filter(UserCredentials.user_id == current_user.id).first()
    if not creds:
        creds = UserCredentials(user_id=current_user.id)
        db.add(creds)

    if "refresh_token" in tokens:
        creds.youtube_refresh_token = encrypt(tokens["refresh_token"])
        creds.credentials_valid = True

    db.commit()
    request.session.pop("youtube_oauth_state", None)
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?youtube=connected")


def _me_response(user: User, db: Session) -> MeResponse:
    """Build a MeResponse for the given user."""
    creds = db.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    admin_email = os.getenv("ADMIN_EMAIL", "")
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        youtube_connected=bool(creds and creds.youtube_refresh_token),
        credentials_valid=creds.credentials_valid if creds else True,
        is_admin=bool(admin_email and user.email == admin_email),
        email_notifications=user.email_notifications,
        profile=user.profile,
        goal=user.goal,
        created_at=user.created_at.isoformat() if user.created_at else None,
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


VALID_PROFILES = {"beginner", "adult", "senior", "athlete"}
VALID_GOALS: dict[str, set[str]] = {
    "beginner": {"Build a habit", "Lose weight", "Feel more energetic"},
    "adult":    {"Build muscle", "Lose fat", "Improve cardio", "Stay consistent"},
    "senior":   {"Stay active & healthy", "Improve flexibility", "Build strength safely"},
    "athlete":  {"Strength & hypertrophy", "Endurance", "Athletic performance", "Cut weight"},
}


@router.patch("/me/profile", response_model=MeResponse)
def patch_me_profile(
    body: PatchMeProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's fitness profile and goal."""
    if body.profile not in VALID_PROFILES:
        raise HTTPException(status_code=400, detail="Invalid profile")
    if body.goal not in VALID_GOALS.get(body.profile, set()):
        raise HTTPException(status_code=400, detail="Invalid goal for this profile")
    current_user.profile = body.profile
    current_user.goal = body.goal
    db.commit()
    return _me_response(current_user, db)


@router.delete("/me", status_code=204)
async def delete_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete the current user and all their data."""
    # Revoke YouTube OAuth token with Google before deleting from DB.
    # Best-effort: never block account deletion if Google's endpoint fails.
    creds = current_user.credentials
    if creds and creds.youtube_refresh_token:
        try:
            token = decrypt(creds.youtube_refresh_token)
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=5,
                )
        except Exception:
            pass  # Deletion proceeds regardless

    db.delete(current_user)
    db.commit()
    request.session.clear()


@router.patch("/me/notifications", response_model=MeResponse)
def patch_me_notifications(
    body: PatchMeNotificationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's email notification preference."""
    current_user.email_notifications = body.email_notifications
    db.commit()
    return _me_response(current_user, db)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}
