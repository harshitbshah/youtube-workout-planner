"""
jobs.py — Background job endpoints.

Routes:
  POST /jobs/scan                        — full pipeline: scan all channels → classify → generate plan
  POST /jobs/classify                    — classify unclassified videos only
  POST /jobs/channels/{channel_id}/scan  — scan a single channel for new videos then classify them
"""

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, User, UserChannel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# In-memory pipeline status per user. Lost on restart (acceptable — if the server
# restarts mid-scan the background task is killed anyway).
# Shape: {"stage": str, "total": int | None, "done": int | None}
# stage values: "scanning" | "classifying" | "generating" | "done" | "failed"
_pipeline_status: dict[str, dict] = {}


def get_all_pipeline_statuses() -> dict[str, dict]:
    """Return a snapshot of all active pipeline statuses. Used by the admin router."""
    return dict(_pipeline_status)


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
    from datetime import datetime, timezone

    from ..database import SessionLocal
    from ..models import ScanLog
    from ..services.classifier import classify_for_user
    from ..services.planner import generate_weekly_plan_for_user
    from ..services.scanner import scan_channel

    session = SessionLocal()
    scan_log_id: int | None = None
    try:
        # Record scan start
        scan_log = ScanLog(user_id=user_id, status="running")
        session.add(scan_log)
        session.commit()
        session.refresh(scan_log)
        scan_log_id = scan_log.id

        _pipeline_status[user_id] = {"stage": "scanning", "total": None, "done": None}
        channels = (
            session.query(Channel)
            .join(UserChannel, UserChannel.channel_id == Channel.id)
            .filter(UserChannel.user_id == user_id)
            .all()
        )

        total_new = 0
        for channel in channels:
            try:
                # User-triggered scan: never skip inactive channels
                new_videos = scan_channel(session, channel, skip_if_inactive=False)
                total_new += new_videos
                logger.info(f"[scan] {channel.name}: {new_videos} new videos")
            except Exception as e:
                logger.error(f"[scan] Failed for {channel.name}: {e}", exc_info=True)

        # Always classify — there may be previously unclassified videos from a
        # failed earlier run, even if this scan found no new videos (incremental).
        _pipeline_status[user_id] = {"stage": "classifying", "total": None, "done": None}

        def _on_classify_progress(total: int, done: int):
            _pipeline_status[user_id] = {"stage": "classifying", "total": total, "done": done}

        try:
            classified = classify_for_user(session, user_id, on_progress=_on_classify_progress)
            logger.info(f"[classify] {classified} videos classified for user {user_id}")
        except Exception as e:
            logger.error(f"[classify] Failed for user {user_id}: {e}", exc_info=True)

        _pipeline_status[user_id] = {"stage": "generating", "total": None, "done": None}
        try:
            generate_weekly_plan_for_user(session, user_id)
            logger.info(f"[plan] Generated plan for user {user_id}")
        except Exception as e:
            logger.error(f"[plan] Failed for user {user_id}: {e}", exc_info=True)

        _pipeline_status[user_id] = {"stage": "done", "total": None, "done": None}

        # Clear any previous scan error on success
        user = session.get(User, user_id)
        if user:
            user.last_scan_error = None
            session.commit()

        # Mark scan as done
        if scan_log_id:
            log = session.get(ScanLog, scan_log_id)
            if log:
                log.status = "done"
                log.completed_at = datetime.now(timezone.utc)
                log.videos_scanned = total_new
                session.commit()

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[pipeline] Unexpected failure for user {user_id}: {e}", exc_info=True)
        _pipeline_status[user_id] = {"stage": "failed", "total": None, "done": None, "error": error_msg}
        try:
            # Persist error so dashboard can show it even after server restart
            user = session.get(User, user_id)
            if user:
                user.last_scan_error = error_msg
                session.commit()
            if scan_log_id:
                log = session.get(ScanLog, scan_log_id)
                if log:
                    log.status = "failed"
                    log.completed_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception:
            pass
    finally:
        session.close()


@router.get("/status")
def get_pipeline_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current pipeline stage + progress for the authenticated user.

    Also includes any persistent scan error from the DB so the dashboard can
    show an error banner even after a server restart clears in-memory state.
    """
    status = _pipeline_status.get(str(current_user.id))
    if status:
        return status
    # Fall back to DB for persistent error state
    error = current_user.last_scan_error
    return {"stage": None, "total": None, "done": None, "error": error}


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

    channels = (
        db.query(Channel)
        .join(UserChannel, UserChannel.channel_id == Channel.id)
        .filter(UserChannel.user_id == current_user.id)
        .all()
    )
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
    uc = (
        db.query(UserChannel)
        .filter(UserChannel.channel_id == channel_id, UserChannel.user_id == current_user.id)
        .first()
    )
    if not uc:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    background_tasks.add_task(_run_scan_and_classify, channel_id, current_user.id, max_videos)
    return {"message": f"Scan started for {channel.name}", "channel_id": channel_id}
