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

import base64
import json
import os
import secrets
from urllib.parse import urlencode

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..crypto import encrypt, decrypt
from ..dependencies import get_current_user, get_db
from ..models import User, UserChannel, UserCredentials
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


def _decode_id_token(id_token: str) -> dict:
    """Decode the JWT id_token payload without a network call.

    The id_token is received directly from Google over HTTPS in the token
    exchange response, so we trust it without re-verifying the signature.
    It always contains sub (Google ID), email, and name when openid scope
    is requested.
    """
    payload = id_token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)  # restore base64 padding
    return json.loads(base64.b64decode(payload))


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
    # Decode id_token locally - avoids a second round-trip to Google /userinfo
    claims = _decode_id_token(tokens["id_token"])
    google_id = claims["sub"]
    email = claims.get("email", "")
    display_name = claims.get("name")

    # Upsert user
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            email=email,
            display_name=display_name,
        )
        db.add(user)
        db.flush()
    else:
        user.email = email
        user.display_name = display_name

    db.commit()

    request.session["user_id"] = str(user.id)
    request.session.pop("oauth_state", None)

    # Pass a signed token in the redirect URL so the frontend can authenticate
    # across domains without relying on cross-domain cookies.
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    token = URLSafeTimedSerializer(secret).dumps(str(user.id))
    # Redirect straight to the destination - skip the landing page as intermediary
    has_channels = db.query(UserChannel).filter(UserChannel.user_id == user.id).first() is not None
    route = "dashboard" if has_channels else "onboarding"
    return RedirectResponse(f"{FRONTEND_URL}/{route}?token={token}")


_TOKEN_MAX_AGE = 30 * 24 * 3600  # 30 days - matches dependencies.py
_STATE_MAX_AGE = 600              # 10 minutes for the OAuth round-trip


@router.get("/youtube/connect")
async def youtube_connect(
    token: str | None = None,
    db: Session = Depends(get_db),
):
    """Redirect the authenticated user to Google to grant YouTube access.

    Accepts the Bearer token as a query param so the flow never depends on
    session cookies surviving the multi-domain redirect chain.
    Signs user_id into the OAuth state so the callback can authenticate
    without a session either.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    try:
        user_id = URLSafeTimedSerializer(secret).loads(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Sign user_id into the state - callback decodes this instead of reading session
    state = URLSafeTimedSerializer(secret).dumps({
        "user_id": str(user_id),
        "nonce": secrets.token_urlsafe(16),
    })

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": user.email,
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/youtube/callback")
async def youtube_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Store the YouTube refresh token and redirect back to the dashboard."""
    secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    try:
        data = URLSafeTimedSerializer(secret).loads(state, max_age=_STATE_MAX_AGE)
        user_id = data["user_id"]
    except (BadSignature, SignatureExpired, KeyError):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    tokens = await _exchange_code_for_tokens(code, YOUTUBE_REDIRECT_URI)

    creds = db.query(UserCredentials).filter(UserCredentials.user_id == user.id).first()
    if not creds:
        creds = UserCredentials(user_id=user.id)
        db.add(creds)

    if "refresh_token" in tokens:
        creds.youtube_refresh_token = encrypt(tokens["refresh_token"])

    # Always clear the revoked flag on a successful OAuth callback - Google won't
    # return a new refresh_token on reconnect if the existing one is still valid,
    # but the callback succeeding means the user re-authorized, so the flag must reset.
    creds.credentials_valid = True

    db.commit()
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
        goal=json.loads(user.goal) if user.goal else None,
        equipment=json.loads(user.equipment) if user.equipment else None,
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
    "beginner": {"Build a habit", "Lose weight", "Feel more energetic", "Yoga & mindfulness", "Dance fitness"},
    "adult":    {"Build muscle", "Lose fat", "Improve cardio", "Stay consistent", "Dance fitness", "Yoga & mindfulness", "Pilates & core"},
    "senior":   {"Stay active & healthy", "Improve flexibility", "Build strength safely", "Yoga & mindfulness", "Pilates & core", "Dance fitness"},
    "athlete":  {"Strength & hypertrophy", "Endurance", "Athletic performance", "Cut weight", "Yoga & mindfulness", "Pilates & core"},
}
VALID_EQUIPMENT = {"mat", "dumbbells", "resistance_bands", "kettlebell", "barbell", "pull_up_bar", "reformer"}


@router.patch("/me/profile", response_model=MeResponse)
def patch_me_profile(
    body: PatchMeProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's fitness profile and goal."""
    if body.profile not in VALID_PROFILES:
        raise HTTPException(status_code=400, detail="Invalid profile")
    if not body.goal:
        raise HTTPException(status_code=400, detail="At least one goal is required")
    if len(body.goal) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 goals allowed")
    valid = VALID_GOALS.get(body.profile, set())
    for g in body.goal:
        if g not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid goal '{g}' for this profile")
    current_user.profile = body.profile
    current_user.goal = json.dumps(body.goal)
    if body.equipment is not None:
        invalid = [e for e in body.equipment if e not in VALID_EQUIPMENT]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid equipment: {invalid}")
        current_user.equipment = json.dumps(body.equipment)
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
