"""
library.py — Video library browser endpoint.

Routes:
  GET /library  — list/filter classified videos from the user's channels
"""

from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, Classification, Video, User
from ..schemas import LibraryResponse, VideoSummary

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
def get_library(
    workout_type: str | None = Query(None),
    body_focus: str | None = Query(None),
    difficulty: str | None = Query(None),
    channel_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated, filtered videos from the user's classified library."""
    q = (
        db.query(Video)
        .join(Channel, Channel.id == Video.channel_id)
        .join(Classification, Classification.video_id == Video.id)
        .filter(Channel.user_id == current_user.id)
    )

    if workout_type:
        q = q.filter(func.lower(Classification.workout_type) == workout_type.lower())
    if body_focus:
        q = q.filter(func.lower(Classification.body_focus) == body_focus.lower())
    if difficulty:
        q = q.filter(func.lower(Classification.difficulty) == difficulty.lower())
    if channel_id:
        q = q.filter(Channel.id == channel_id)

    q = q.order_by(Video.published_at.desc())

    total = q.count()
    videos = q.offset((page - 1) * limit).limit(limit).all()

    return LibraryResponse(
        videos=[
            VideoSummary(
                id=v.id,
                title=v.title,
                url=v.url,
                channel_name=v.channel.name,
                duration_sec=v.duration_sec,
                workout_type=v.classification.workout_type,
                body_focus=v.classification.body_focus,
                difficulty=v.classification.difficulty,
            )
            for v in videos
        ],
        total=total,
        page=page,
        pages=ceil(total / limit) if total else 1,
    )
