"""
jobs.py — Background job endpoints.

Routes:
  POST /channels/{channel_id}/scan — scan a channel for new videos then classify them
"""

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


def _run_scan_and_classify(channel_id: str, user_id: str):
    """
    Full scan + classify pipeline for one channel.
    Creates its own DB session since it runs in a background thread.
    """
    from ..database import SessionLocal
    from ..services.classifier import classify_for_user
    from ..services.scanner import scan_channel

    session = SessionLocal()
    try:
        channel = session.get(Channel, channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found in background task")
            return

        new_videos = scan_channel(session, channel)
        logger.info(f"Scan complete for {channel.name}: {new_videos} new videos")

        if new_videos > 0:
            classified = classify_for_user(session, user_id)
            logger.info(f"Classified {classified} videos for user {user_id}")

    except Exception as e:
        logger.error(f"Scan/classify failed for channel {channel_id}: {e}", exc_info=True)
    finally:
        session.close()


@router.post("/channels/{channel_id}/scan", status_code=202)
def trigger_channel_scan(
    channel_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger scan + classify for a channel. Returns 202 immediately;
    the pipeline runs in the background.
    """
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.user_id == current_user.id)
        .first()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    background_tasks.add_task(_run_scan_and_classify, channel_id, current_user.id)
    return {"message": f"Scan started for {channel.name}", "channel_id": channel_id}
