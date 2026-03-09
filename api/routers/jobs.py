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


def _run_scan_and_classify(channel_id: str, user_id: str, max_videos: int | None = None):
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

        new_videos = scan_channel(session, channel, max_videos=max_videos)
        logger.info(f"Scan complete for {channel.name}: {new_videos} new videos")

        if new_videos > 0:
            classified = classify_for_user(session, user_id)
            logger.info(f"Classified {classified} videos for user {user_id}")

    except Exception as e:
        logger.error(f"Scan/classify failed for channel {channel_id}: {e}", exc_info=True)
    finally:
        session.close()


def _run_full_pipeline(user_id: str):
    """
    Scan all channels + classify + generate plan for a user.
    Runs in a background thread; creates its own DB session.
    """
    from ..database import SessionLocal
    from ..services.classifier import classify_for_user
    from ..services.scanner import scan_channel
    from ..services.planner import generate_weekly_plan_for_user

    session = SessionLocal()
    try:
        channels = session.query(Channel).filter(Channel.user_id == user_id).all()

        total_new = 0
        for channel in channels:
            try:
                new_videos = scan_channel(session, channel)
                total_new += new_videos
                logger.info(f"[scan] {channel.name}: {new_videos} new videos")
            except Exception as e:
                logger.error(f"[scan] Failed for {channel.name}: {e}", exc_info=True)

        if total_new > 0:
            try:
                classified = classify_for_user(session, user_id)
                logger.info(f"[classify] {classified} videos classified for user {user_id}")
            except Exception as e:
                logger.error(f"[classify] Failed for user {user_id}: {e}", exc_info=True)

        try:
            generate_weekly_plan_for_user(session, user_id)
            logger.info(f"[plan] Generated plan for user {user_id}")
        except Exception as e:
            logger.error(f"[plan] Failed for user {user_id}: {e}", exc_info=True)

    finally:
        session.close()


@router.post("/scan", status_code=202)
def trigger_scan(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger full pipeline (scan → classify → generate plan) for all user channels.
    Returns 202 immediately; runs in the background.
    """
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    channels = db.query(Channel).filter(Channel.user_id == current_user.id).all()
    if not channels:
        raise HTTPException(status_code=400, detail="No channels added yet")

    background_tasks.add_task(_run_full_pipeline, str(current_user.id))
    return {"message": f"Pipeline started for {len(channels)} channel(s)"}


@router.post("/classify", status_code=202)
def trigger_classify(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Classify all unclassified videos for the current user's channels.
    Returns 202 immediately; classification runs in the background.
    Useful when videos were scanned but classification was interrupted.
    """
    def _run_classify(user_id: str):
        from ..database import SessionLocal
        from ..services.classifier import classify_for_user
        session = SessionLocal()
        try:
            classified = classify_for_user(session, user_id)
            logger.info(f"Classification complete: {classified} videos for user {user_id}")
        except Exception as e:
            logger.error(f"Classification failed for user {user_id}: {e}", exc_info=True)
        finally:
            session.close()

    background_tasks.add_task(_run_classify, current_user.id)
    return {"message": "Classification started"}


@router.post("/channels/{channel_id}/scan", status_code=202)
def trigger_channel_scan(
    channel_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    max_videos: int | None = None,
):
    """
    Trigger scan + classify for a channel. Returns 202 immediately;
    the pipeline runs in the background.

    max_videos: optionally cap the number of videos fetched (useful for testing).
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

    background_tasks.add_task(_run_scan_and_classify, channel_id, current_user.id, max_videos)
    return {"message": f"Scan started for {channel.name}", "channel_id": channel_id}
