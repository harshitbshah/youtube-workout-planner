"""
schedule.py — Get and update the user's weekly training schedule.

Routes:
  GET /schedule     — return all 7 days (rest days have workout_type=None)
  PUT /schedule     — replace the full schedule
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Schedule, User
from ..schemas import ScheduleResponse, ScheduleSlot, ScheduleUpdate

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _row_to_slot(row: Schedule) -> ScheduleSlot:
    return ScheduleSlot(
        day=row.day,
        workout_type=row.workout_type,
        body_focus=row.body_focus,
        duration_min=row.duration_min,
        duration_max=row.duration_max,
        difficulty=row.difficulty or "any",
    )


# ─── Get ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=ScheduleResponse)
def get_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Schedule).filter(Schedule.user_id == current_user.id).all()
    by_day = {row.day: row for row in rows}

    slots = []
    for day in DAYS_OF_WEEK:
        if day in by_day:
            slots.append(_row_to_slot(by_day[day]))
        else:
            slots.append(ScheduleSlot(day=day))  # rest day default

    return ScheduleResponse(schedule=slots)


# ─── Update ───────────────────────────────────────────────────────────────────

@router.put("", response_model=ScheduleResponse)
def update_schedule(
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Delete existing schedule for this user and replace entirely
    db.query(Schedule).filter(Schedule.user_id == current_user.id).delete()

    for slot in body.schedule:
        db.add(Schedule(
            user_id=current_user.id,
            day=slot.day,
            workout_type=slot.workout_type,
            body_focus=slot.body_focus,
            duration_min=slot.duration_min,
            duration_max=slot.duration_max,
            difficulty=slot.difficulty,
        ))

    db.commit()

    # Re-read to return the canonical state
    rows = db.query(Schedule).filter(Schedule.user_id == current_user.id).all()
    by_day = {row.day: row for row in rows}

    slots = []
    for day in DAYS_OF_WEEK:
        if day in by_day:
            slots.append(_row_to_slot(by_day[day]))
        else:
            slots.append(ScheduleSlot(day=day))

    return ScheduleResponse(schedule=slots)
