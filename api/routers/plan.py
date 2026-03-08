"""
plan.py — Weekly plan endpoints.

Routes:
  GET   /plan/upcoming      — return the most recently generated plan for the user
  POST  /plan/generate      — generate (or re-generate) next week's plan
  PATCH /plan/{day}         — swap the video assigned to one day
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, Classification, ProgramHistory, Video, User
from ..schemas import PatchDayRequest, PlanDay, PlanResponse, PublishResponse, VideoSummary
from ..services.planner import generate_weekly_plan_for_user, pick_video_for_slot_for_user
from ..services.publisher import (
    YouTubeAccessRevokedError,
    YouTubeNotConnectedError,
    publish_plan_for_user,
)
from src.planner import HISTORY_WINDOW_WEEKS, get_upcoming_monday

router = APIRouter(prefix="/plan", tags=["plan"])

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


def _history_to_plan_response(rows: list[ProgramHistory], week_start: date, db: Session) -> PlanResponse:
    """Convert ProgramHistory rows for a given week into a PlanResponse."""
    by_day: dict[str, ProgramHistory] = {row.assigned_day: row for row in rows}

    days = []
    for day in DAYS_OF_WEEK:
        row = by_day.get(day)
        if row and row.video_id:
            video = db.query(Video).filter(Video.id == row.video_id).first()
            if video:
                channel_name = video.channel.name if video.channel else ""
                days.append(PlanDay(day=day, video=_video_row_to_summary(video, channel_name)))
                continue
        days.append(PlanDay(day=day, video=None))

    return PlanResponse(week_start=week_start.isoformat(), days=days)


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
    return _history_to_plan_response(rows, latest_week, db)


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
            ))
        else:
            days.append(PlanDay(day=day, video=None))

    return PlanResponse(week_start=week_start.isoformat(), days=days)


# ─── Publish ──────────────────────────────────────────────────────────────────

@router.post("/publish", response_model=PublishResponse)
def publish_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish the current week's plan to the user's YouTube playlist."""
    latest_week = (
        db.query(func.max(ProgramHistory.week_start))
        .filter(ProgramHistory.user_id == current_user.id)
        .scalar()
    )
    if not latest_week:
        raise HTTPException(status_code=404, detail="No plan generated yet")

    try:
        result = publish_plan_for_user(db, current_user.id, latest_week)
    except YouTubeNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeAccessRevokedError:
        raise HTTPException(
            status_code=403,
            detail="YouTube access has been revoked. Please sign in again to reconnect.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PublishResponse(**result)


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
        .filter(Video.id == body.video_id, Channel.user_id == current_user.id)
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
