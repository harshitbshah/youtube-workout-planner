"""
admin.py — Admin-only stats endpoint.

Access is restricted to the email set in the ADMIN_EMAIL environment variable.
Returns aggregate stats + per-user breakdown for monitoring the app's health.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, Classification, ProgramHistory, User, UserCredentials, Video
from .jobs import get_all_pipeline_statuses

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user: User = Depends(get_current_user)):
    admin_email = os.getenv("ADMIN_EMAIL", "")
    if not admin_email or current_user.email != admin_email:
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # --- Users ---
    total_users = db.query(func.count(User.id)).scalar() or 0
    new_7d = db.query(func.count(User.id)).filter(User.created_at >= seven_days_ago).scalar() or 0
    new_30d = db.query(func.count(User.id)).filter(User.created_at >= thirty_days_ago).scalar() or 0

    yt_connected = (
        db.query(func.count(UserCredentials.user_id))
        .filter(
            UserCredentials.youtube_refresh_token.isnot(None),
            UserCredentials.credentials_valid.is_(True),
        )
        .scalar()
        or 0
    )

    # --- Library ---
    total_videos = db.query(func.count(Video.id)).scalar() or 0
    classified_videos = db.query(func.count(Classification.video_id)).scalar() or 0
    unclassified = total_videos - classified_videos

    # --- Channels ---
    total_channels = db.query(func.count(Channel.id)).scalar() or 0

    # --- Plans this week ---
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    plans_this_week = (
        db.query(func.count(func.distinct(ProgramHistory.user_id)))
        .filter(ProgramHistory.week_start == week_start)
        .scalar()
        or 0
    )

    # --- Active pipelines ---
    pipeline_statuses = get_all_pipeline_statuses()
    active_pipelines = [
        {"user_id": uid, **status}
        for uid, status in pipeline_statuses.items()
        if status.get("stage") not in (None, "done", "failed")
    ]

    # --- Per-user breakdown ---
    users = db.query(User).order_by(User.created_at.desc()).all()

    channel_counts = dict(
        db.query(Channel.user_id, func.count(Channel.id))
        .group_by(Channel.user_id)
        .all()
    )

    video_counts = dict(
        db.query(Channel.user_id, func.count(Video.id))
        .join(Video, Video.channel_id == Channel.id)
        .group_by(Channel.user_id)
        .all()
    )

    last_plans = dict(
        db.query(ProgramHistory.user_id, func.max(ProgramHistory.week_start))
        .group_by(ProgramHistory.user_id)
        .all()
    )

    creds = {c.user_id: c for c in db.query(UserCredentials).all()}

    user_rows = []
    for u in users:
        cred = creds.get(u.id)
        pipeline = pipeline_statuses.get(u.id, {})
        user_rows.append({
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "channels": channel_counts.get(u.id, 0),
            "videos": video_counts.get(u.id, 0),
            "youtube_connected": bool(
                cred and cred.youtube_refresh_token and cred.credentials_valid
            ),
            "last_plan": str(last_plans[u.id]) if u.id in last_plans else None,
            "pipeline_stage": pipeline.get("stage"),
        })

    return {
        "users": {
            "total": total_users,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "youtube_connected": yt_connected,
        },
        "library": {
            "total_videos": total_videos,
            "classified": classified_videos,
            "unclassified": unclassified,
            "classification_pct": round(
                (classified_videos / total_videos * 100) if total_videos else 0, 1
            ),
        },
        "channels": {
            "total": total_channels,
            "avg_per_user": round(total_channels / total_users, 1) if total_users else 0,
        },
        "plans": {
            "users_with_plan_this_week": plans_this_week,
        },
        "pipelines": {
            "active": active_pipelines,
            "active_count": len(active_pipelines),
        },
        "user_rows": user_rows,
    }
