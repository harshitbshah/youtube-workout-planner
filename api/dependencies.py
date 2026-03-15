"""
dependencies.py - FastAPI dependency functions shared across routers.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User, UserActivityLog

_ACTIVE_THROTTLE = timedelta(minutes=5)

_TOKEN_MAX_AGE = 30 * 24 * 3600  # 30 days


def get_db():
    """Yield a SQLAlchemy session, closing it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Return the authenticated user or raise 401.

    Checks Authorization: Bearer <token> first (production cross-domain flow),
    then falls back to the session cookie (local dev, same-domain).
    """
    user_id: str | None = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
        try:
            user_id = URLSafeTimedSerializer(secret).loads(token, max_age=_TOKEN_MAX_AGE)
        except (BadSignature, SignatureExpired):
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    else:
        user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Update last_active_at at most once every 5 minutes to avoid excessive writes.
    # Also append a UserActivityLog row for time-series active-user charts.
    now = datetime.now(timezone.utc)
    if not user.last_active_at or (now - user.last_active_at) > _ACTIVE_THROTTLE:
        user.last_active_at = now
        db.add(UserActivityLog(user_id=user.id, active_at=now))
        db.commit()

    return user
