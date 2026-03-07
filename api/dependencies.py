"""
dependencies.py — FastAPI dependency functions shared across routers.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User


def get_db():
    """Yield a SQLAlchemy session, closing it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Return the authenticated user or raise 401."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
