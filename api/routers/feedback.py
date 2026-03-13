"""
feedback.py — User feedback submission endpoint.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import User
from ..schemas import FeedbackRequest
from ..services.email import send_feedback_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

VALID_CATEGORIES = {"feedback", "help", "bug"}


@router.post("", status_code=204)
def submit_feedback(
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        send_feedback_email(current_user, body.category, body.message.strip())
    except RuntimeError as e:
        logger.error(f"[feedback] Email send failed: {e}")
        raise HTTPException(status_code=503, detail="Email service unavailable")
