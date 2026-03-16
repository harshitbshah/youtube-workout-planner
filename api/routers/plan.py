"""
plan.py - Weekly plan endpoints.

Routes:
  GET   /plan/upcoming      - return the most recently generated plan for the user
  POST  /plan/generate      - generate (or re-generate) next week's plan
  PATCH /plan/{day}         - swap the video assigned to one day
"""

from datetime import date, timedelta

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, Classification, ProgramHistory, Schedule, User, UserChannel, Video
from ..schemas import PatchDayRequest, PlanDay, PlanResponse, PublishResponse, PublishStatus, VideoSummary
from ..services.planner import generate_weekly_plan_for_user, get_gap_types, pick_video_for_slot_for_user
from ..services.publisher import (
    YouTubeAccessRevokedError,
    YouTubeNotConnectedError,
    publish_plan_for_user,
)
from src.planner import HISTORY_WINDOW_WEEKS, get_upcoming_monday

router = APIRouter(prefix="/plan", tags=["plan"])

# In-memory publish status per user. Lost on restart (acceptable).
# status values: "idle" | "publishing" | "done" | "failed"
_publish_status: dict[str, dict] = {}

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _video_row_to_summary(video: Video, channel_name: str) -> VideoSummary:
    clf = video.classification
    return VideoSummary(
        id=video.id,
        title=video.title,
        url=video.url,
        channel_name=channel_name,
        duration_sec=video.duration_sec,
        workout_type=clf.workout_type if clf else None,
        body_focus=clf.body_focus if clf else None,
        difficulty=clf.difficulty if clf else None,
    )


def _history_to_plan_response(rows: list[ProgramHistory], week_start: date, db: Session, user_id: str | None = None) -> PlanResponse:
    """Convert ProgramHistory rows for a given week into a PlanResponse."""
    by_day: dict[str, ProgramHistory] = {row.assigned_day: row for row in rows}

    # Load schedule to know which days are active vs rest
    schedule_wt: dict[str, str | None] = {}
    if user_id:
        for s in db.query(Schedule).filter(Schedule.user_id == user_id).all():
            schedule_wt[s.day] = s.workout_type

    days = []
    for day in DAYS_OF_WEEK:
        row = by_day.get(day)
        wt = schedule_wt.get(day)
        if row and row.video_id:
            video = db.query(Video).filter(Video.id == row.video_id).first()
            if video:
                channel_name = video.channel.name if video.channel else ""
                days.append(PlanDay(day=day, video=_video_row_to_summary(video, channel_name), scheduled_workout_type=wt))
                continue
        days.append(PlanDay(day=day, video=None, scheduled_workout_type=wt))

    return PlanResponse(week_start=week_start.isoformat(), days=days)


# ─── Gaps ─────────────────────────────────────────────────────────────────────

@router.get("/gaps")
def get_plan_gaps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return workout types that the user's schedule requires but their library
    cannot fill (fewer than MIN_PLAN_CANDIDATES classified videos).
    Returns {"gaps": ["HIIT", "Cardio"]} - empty list means all slots are covered.
    """
    gap_dicts = get_gap_types(db, current_user.id)
    gap_types = sorted({g["workout_type"] for g in gap_dicts})
    return {"gaps": gap_types}


# ─── Upcoming ─────────────────────────────────────────────────────────────────

@router.get("/upcoming", response_model=PlanResponse)
def get_upcoming_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recently generated plan. 404 if none exists yet."""
    latest_week = (
        db.query(func.max(ProgramHistory.week_start))
        .filter(ProgramHistory.user_id == current_user.id)
        .scalar()
    )
    if not latest_week:
        raise HTTPException(status_code=404, detail="No plan generated yet")

    rows = (
        db.query(ProgramHistory)
        .filter(
            ProgramHistory.user_id == current_user.id,
            ProgramHistory.week_start == latest_week,
        )
        .all()
    )
    return _history_to_plan_response(rows, latest_week, db, user_id=current_user.id)


# ─── Generate ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=PlanResponse, status_code=201)
def generate_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate next week's plan. Replaces any existing plan for that week."""
    week_start = get_upcoming_monday()

    # Remove any existing plan for this week so we get a clean re-generation
    db.query(ProgramHistory).filter(
        ProgramHistory.user_id == current_user.id,
        ProgramHistory.week_start == week_start,
    ).delete()
    db.commit()

    plan = generate_weekly_plan_for_user(db, current_user.id)

    rows = (
        db.query(ProgramHistory)
        .filter(
            ProgramHistory.user_id == current_user.id,
            ProgramHistory.week_start == week_start,
        )
        .all()
    )

    # Build response from generated plan list (handles rest days not in history)
    days = []
    history_by_day = {row.assigned_day: row for row in rows}
    for entry in plan:
        day = entry["day"]
        video_dict = entry.get("video")
        if video_dict:
            days.append(PlanDay(
                day=day,
                video=VideoSummary(
                    id=video_dict["id"],
                    title=video_dict["title"],
                    url=video_dict["url"],
                    channel_name=video_dict["channel_name"],
                    duration_sec=video_dict.get("duration_sec"),
                    workout_type=video_dict.get("workout_type"),
                    body_focus=video_dict.get("body_focus"),
                    difficulty=video_dict.get("difficulty"),
                ),
                scheduled_workout_type=entry.get("scheduled_workout_type"),
            ))
        else:
            days.append(PlanDay(day=day, video=None, scheduled_workout_type=entry.get("scheduled_workout_type")))

    return PlanResponse(week_start=week_start.isoformat(), days=days)


# ─── Publish ──────────────────────────────────────────────────────────────────

def _run_publish(user_id: str, week_start):
    """Publish plan to YouTube in a background thread. Creates its own DB session."""
    from ..database import SessionLocal
    session = SessionLocal()
    try:
        result = publish_plan_for_user(session, user_id, week_start)
        _publish_status[user_id] = {
            "status": "done",
            "playlist_url": result["playlist_url"],
            "video_count": result["video_count"],
            "error": None,
        }
    except YouTubeNotConnectedError as exc:
        _publish_status[user_id] = {"status": "failed", "playlist_url": None, "video_count": None, "error": str(exc)}
    except YouTubeAccessRevokedError as exc:
        _publish_status[user_id] = {"status": "failed", "playlist_url": None, "video_count": None, "error": "revoked"}
    except Exception as exc:
        _publish_status[user_id] = {"status": "failed", "playlist_url": None, "video_count": None, "error": str(exc)}
    finally:
        session.close()


@router.post("/publish", status_code=202)
def publish_plan(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start publishing the current week's plan to YouTube. Returns 202 immediately."""
    latest_week = (
        db.query(func.max(ProgramHistory.week_start))
        .filter(ProgramHistory.user_id == current_user.id)
        .scalar()
    )
    if not latest_week:
        raise HTTPException(status_code=404, detail="No plan generated yet")

    _publish_status[str(current_user.id)] = {"status": "publishing", "playlist_url": None, "video_count": None, "error": None}
    background_tasks.add_task(_run_publish, str(current_user.id), latest_week)
    return {"message": "Publishing started"}


@router.get("/publish/status", response_model=PublishStatus)
def get_publish_status(
    current_user: User = Depends(get_current_user),
):
    """Return the current publish status for the authenticated user."""
    status = _publish_status.get(str(current_user.id))
    if not status:
        return PublishStatus(status="idle")
    return PublishStatus(**status)


# ─── Patch day ────────────────────────────────────────────────────────────────

@router.patch("/{day}", response_model=PlanDay)
def patch_plan_day(
    day: str,
    body: PatchDayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Swap the video for a given day in the current week's plan."""
    if day not in DAYS_OF_WEEK:
        raise HTTPException(status_code=400, detail=f"Invalid day: {day}")

    week_start = get_upcoming_monday()

    # Verify the replacement video belongs to this user's channels
    video = (
        db.query(Video)
        .join(Channel, Channel.id == Video.channel_id)
        .join(UserChannel, (UserChannel.channel_id == Channel.id) & (UserChannel.user_id == current_user.id))
        .filter(Video.id == body.video_id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found in your library")

    # Upsert the history row for this day
    existing = (
        db.query(ProgramHistory)
        .filter(
            ProgramHistory.user_id == current_user.id,
            ProgramHistory.week_start == week_start,
            ProgramHistory.assigned_day == day,
        )
        .first()
    )
    if existing:
        existing.video_id = body.video_id
    else:
        db.add(ProgramHistory(
            user_id=current_user.id,
            week_start=week_start,
            video_id=body.video_id,
            assigned_day=day,
        ))
    db.commit()

    channel_name = video.channel.name if video.channel else ""
    return PlanDay(day=day, video=_video_row_to_summary(video, channel_name))
