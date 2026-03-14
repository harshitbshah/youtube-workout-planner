"""
admin.py — Admin-only stats and management endpoints.

Access to /admin/* is restricted to the email set in the ADMIN_EMAIL env var.
GET /announcements/active is open to any authenticated user (dashboard banner).

Haiku 4.5 Batch API pricing used for cost estimates:
  Input:  $0.40 / 1M tokens
  Output: $2.00 / 1M tokens
"""

import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import (
    Announcement,
    BatchUsageLog,
    Channel,
    Classification,
    ProgramHistory,
    ScanLog,
    User,
    UserActivityLog,
    UserChannel,
    UserCredentials,
    Video,
)
from .jobs import get_all_pipeline_statuses

router = APIRouter(tags=["admin"])

# Haiku 4.5 Batch API pricing (USD per token)
_INPUT_COST_PER_TOKEN = 0.40 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 2.00 / 1_000_000


def _require_admin(current_user: User = Depends(get_current_user)):
    admin_email = os.getenv("ADMIN_EMAIL", "")
    if not admin_email or current_user.email != admin_email:
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


# ─── Active announcement (for dashboard — any authenticated user) ──────────────

@router.get("/announcements/active")
def get_active_announcement(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ann = (
        db.query(Announcement)
        .filter(Announcement.is_active.is_(True))
        .order_by(Announcement.created_at.desc())
        .first()
    )
    if not ann:
        return None
    return {"id": ann.id, "message": ann.message}


# ─── Admin: stats ──────────────────────────────────────────────────────────────

@router.get("/admin/stats")
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

    # --- AI usage ---
    all_batches = db.query(BatchUsageLog).all()
    def _is_within_7d(dt):
        if not dt:
            return False
        # Handle both timezone-aware (PostgreSQL) and naive (SQLite in tests)
        ts = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return ts >= seven_days_ago

    batches_7d = [b for b in all_batches if _is_within_7d(b.created_at)]

    def _usage_stats(batches):
        total_input = sum(b.input_tokens or 0 for b in batches)
        total_output = sum(b.output_tokens or 0 for b in batches)
        est_cost = round(
            total_input * _INPUT_COST_PER_TOKEN + total_output * _OUTPUT_COST_PER_TOKEN, 4
        )
        return {
            "batches": len(batches),
            "videos_classified": sum(b.classified for b in batches),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "est_cost_usd": est_cost,
        }

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
        db.query(UserChannel.user_id, func.count(UserChannel.channel_id))
        .group_by(UserChannel.user_id)
        .all()
    )

    video_counts = dict(
        db.query(UserChannel.user_id, func.count(Video.id))
        .join(Channel, Channel.id == UserChannel.channel_id)
        .join(Video, Video.channel_id == Channel.id)
        .group_by(UserChannel.user_id)
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
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
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
        "ai_usage": {
            "last_7d": _usage_stats(batches_7d),
            "all_time": _usage_stats(all_batches),
        },
        "user_rows": user_rows,
    }


# ─── Admin: charts ─────────────────────────────────────────────────────────────

def _to_date_key(dt) -> str:
    """Return 'YYYY-MM-DD' for a datetime that may be naive or tz-aware."""
    if dt is None:
        return ""
    if hasattr(dt, "date"):
        return dt.date().isoformat()
    return str(dt)[:10]


def _date_series(days: int) -> list[str]:
    """Return a list of 'YYYY-MM-DD' strings for the last `days` days (inclusive today)."""
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


@router.get("/admin/charts")
def get_admin_charts(
    days: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """
    Return daily time-series data for admin charts.
    All series cover the last `days` days (default 30), with a data point for every day.
    """
    if days < 1 or days > 365:
        days = 30

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    series = _date_series(days)

    # ── User signups ──────────────────────────────────────────────────────────
    signups_raw = db.query(User).filter(User.created_at >= cutoff).all()
    signups_by_day: dict[str, int] = defaultdict(int)
    for u in signups_raw:
        signups_by_day[_to_date_key(u.created_at)] += 1

    # ── Active users (distinct per day from UserActivityLog) ──────────────────
    activity_raw = db.query(UserActivityLog).filter(UserActivityLog.active_at >= cutoff).all()
    # count distinct user_ids per day
    active_by_day: dict[str, set] = defaultdict(set)
    for row in activity_raw:
        active_by_day[_to_date_key(row.active_at)].add(row.user_id)

    # ── AI usage (tokens + cost per day from BatchUsageLog) ───────────────────
    batches_raw = db.query(BatchUsageLog).filter(BatchUsageLog.created_at >= cutoff).all()
    ai_by_day: dict[str, dict] = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})
    for b in batches_raw:
        key = _to_date_key(b.created_at)
        ai_by_day[key]["input_tokens"] += b.input_tokens or 0
        ai_by_day[key]["output_tokens"] += b.output_tokens or 0

    # ── Scans (count per day from ScanLog) ────────────────────────────────────
    scans_raw = db.query(ScanLog).filter(ScanLog.started_at >= cutoff).all()
    scans_by_day: dict[str, int] = defaultdict(int)
    for s in scans_raw:
        scans_by_day[_to_date_key(s.started_at)] += 1

    # ── Build uniform series (every day in window, zero-filled) ──────────────
    def _signups_point(d: str):
        return {"date": d, "count": signups_by_day.get(d, 0)}

    def _active_point(d: str):
        return {"date": d, "count": len(active_by_day.get(d, set()))}

    def _ai_point(d: str):
        inp = ai_by_day.get(d, {}).get("input_tokens", 0)
        out = ai_by_day.get(d, {}).get("output_tokens", 0)
        return {
            "date": d,
            "input_tokens": inp,
            "output_tokens": out,
            "est_cost_usd": round(
                inp * _INPUT_COST_PER_TOKEN + out * _OUTPUT_COST_PER_TOKEN, 4
            ),
        }

    def _scans_point(d: str):
        return {"date": d, "count": scans_by_day.get(d, 0)}

    return {
        "signups": [_signups_point(d) for d in series],
        "active_users": [_active_point(d) for d in series],
        "ai_usage": [_ai_point(d) for d in series],
        "scans": [_scans_point(d) for d in series],
    }


# ─── Admin: delete user ────────────────────────────────────────────────────────

@router.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(_require_admin),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


# ─── Admin: retry pipeline for a user ─────────────────────────────────────────

@router.post("/admin/users/{user_id}/scan", status_code=202)
def admin_retry_scan(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    channels = (
        db.query(Channel)
        .join(UserChannel, UserChannel.channel_id == Channel.id)
        .filter(UserChannel.user_id == user_id)
        .all()
    )
    if not channels:
        raise HTTPException(status_code=400, detail="User has no channels")

    from .jobs import _run_full_pipeline
    background_tasks.add_task(_run_full_pipeline, user_id)
    return {"message": f"Pipeline started for user {user.email}"}


# ─── Admin: announcements ──────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    message: str


@router.get("/admin/announcements")
def list_announcements(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    announcements = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "message": a.message,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat(),
        }
        for a in announcements
    ]


@router.post("/admin/announcements", status_code=201)
def create_announcement(
    body: AnnouncementCreate,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    ann = Announcement(message=body.message.strip(), is_active=True)
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"id": ann.id, "message": ann.message, "is_active": ann.is_active}


@router.delete("/admin/announcements/{ann_id}", status_code=204)
def delete_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    ann = db.get(Announcement, ann_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(ann)
    db.commit()


@router.patch("/admin/announcements/{ann_id}/deactivate", status_code=200)
def deactivate_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    ann = db.get(Announcement, ann_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    ann.is_active = False
    db.commit()
    return {"id": ann.id, "is_active": ann.is_active}
