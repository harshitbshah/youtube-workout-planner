"""
api/services/planner.py — Weekly plan generation scoped to a user.

Reuses pure functions from src/planner.py (scoring, formatting, date helpers).
All DB queries go through SQLAlchemy against PostgreSQL (or SQLite in tests).
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.planner import (
    DAYS_OF_WEEK,
    HISTORY_WINDOW_WEEKS,
    TOP_N_PICK,
    _score_candidate,
    format_plan_summary,
    get_upcoming_monday,
)

from ..models import Channel, Classification, ProgramHistory, Schedule, Video

logger = logging.getLogger(__name__)


# ─── Candidate fetching ───────────────────────────────────────────────────────

def _fetch_candidates_for_user(
    session: Session,
    user_id: str,
    workout_type: str,
    body_focus: str,
    min_duration_sec: int,
    max_duration_sec: int,
    difficulty: str,
    history_weeks: int,
    excluded_channel_ids: list[str] | None = None,
    excluded_video_ids: list[str] | None = None,
) -> list[dict]:
    """
    Query classified videos belonging to this user's channels that match
    the slot requirements and haven't been used within history_weeks.
    """
    from sqlalchemy import or_

    cutoff = (datetime.now(timezone.utc) - timedelta(weeks=history_weeks)).date()

    # Subquery: video IDs used within the history window for this user
    recent_video_ids = (
        session.query(ProgramHistory.video_id)
        .filter(ProgramHistory.user_id == user_id, ProgramHistory.week_start >= cutoff)
        .subquery()
        .select()
    )

    q = (
        session.query(Video, Classification, Channel)
        .join(Classification, Classification.video_id == Video.id)
        .join(Channel, Channel.id == Video.channel_id)
        .filter(
            Channel.user_id == user_id,
            Classification.workout_type == workout_type,
            or_(
                Classification.body_focus == body_focus,
                Classification.body_focus == "any",
                body_focus == "any",
            ),
            or_(Video.duration_sec.is_(None), Video.duration_sec >= min_duration_sec),
            or_(Video.duration_sec.is_(None), Video.duration_sec <= max_duration_sec),
            or_(difficulty == "any", Classification.difficulty == difficulty),
            Video.id.not_in(recent_video_ids),
        )
        .order_by(Video.published_at.desc())
    )

    if excluded_channel_ids:
        q = q.filter(Video.channel_id.not_in(excluded_channel_ids))
    if excluded_video_ids:
        q = q.filter(Video.id.not_in(excluded_video_ids))

    results = []
    for video, classification, channel in q.all():
        results.append({
            "id": video.id,
            "channel_id": channel.id,
            "channel_name": channel.name,
            "title": video.title,
            "url": video.url,
            "published_at": video.published_at,
            "duration_sec": video.duration_sec,
            "workout_type": classification.workout_type,
            "body_focus": classification.body_focus,
            "difficulty": classification.difficulty,
            "has_warmup": classification.has_warmup,
            "has_cooldown": classification.has_cooldown,
        })

    return results


# ─── Slot picker ─────────────────────────────────────────────────────────────

def pick_video_for_slot_for_user(
    session: Session,
    user_id: str,
    workout_type: str,
    body_focus: str,
    min_duration_sec: int,
    max_duration_sec: int,
    difficulty: str,
    recency_boost_weeks: int,
    used_channel_names: list[str],
    excluded_channel_ids: list[str] | None = None,
    excluded_video_ids: list[str] | None = None,
) -> dict | None:
    """
    Pick the best video for a slot using the same 5-tier fallback strategy
    as the CLI planner, but querying PostgreSQL scoped to a user.
    """
    fallback_tiers = [
        (HISTORY_WINDOW_WEEKS, body_focus, True),
        (4,                    body_focus, True),
        (4,                    "any",      True),
        (0,                    "any",      True),
        (0,                    "any",      False),
    ]

    excluded_channel_ids = excluded_channel_ids or []
    candidates = []

    for history_weeks, effective_focus, respect_limit in fallback_tiers:
        active_exclusions = excluded_channel_ids if respect_limit else []
        candidates = _fetch_candidates_for_user(
            session, user_id, workout_type, effective_focus,
            min_duration_sec, max_duration_sec, difficulty, history_weeks,
            active_exclusions, excluded_video_ids,
        )
        if candidates:
            break
    else:
        return None

    scored = sorted(
        candidates,
        key=lambda v: _score_candidate(v, recency_boost_weeks, used_channel_names),
        reverse=True,
    )
    return random.choice(scored[:TOP_N_PICK])


# ─── History persistence ──────────────────────────────────────────────────────

def _save_plan_to_history(session: Session, user_id: str, week_start, plan: list[dict]):
    for day in plan:
        if day["video"] is None:
            continue
        session.add(ProgramHistory(
            user_id=user_id,
            week_start=week_start,
            video_id=day["video"]["id"],
            assigned_day=day["day"],
        ))
    session.commit()


# ─── Main entry point ─────────────────────────────────────────────────────────

def generate_weekly_plan_for_user(
    session: Session,
    user_id: str,
    recency_boost_weeks: int = 24,
    max_channel_repeats: int = 2,
) -> list[dict]:
    """
    Generate a full weekly plan for the given user by reading their schedule
    from the DB and selecting videos from their channel library.

    Returns the same structure as src/planner.generate_weekly_plan():
      [{"day": "monday", "video": {...} | None}, ...]
    """
    week_start = get_upcoming_monday()

    # Load user's schedule keyed by day
    schedule_rows = (
        session.query(Schedule)
        .filter(Schedule.user_id == user_id)
        .all()
    )
    schedule = {row.day: row for row in schedule_rows}

    plan = []
    used_channel_names: list[str] = []
    used_video_ids: list[str] = []
    channel_usage: dict[str, int] = {}   # keyed by channel_id

    for day in DAYS_OF_WEEK:
        slot = schedule.get(day)

        if not slot or not slot.workout_type:
            plan.append({"day": day, "video": None})
            continue

        min_dur = (slot.duration_min or 0) * 60
        max_dur = (slot.duration_max or 60) * 60
        difficulty = slot.difficulty or "any"
        exhausted_ids = [ch_id for ch_id, n in channel_usage.items() if n >= max_channel_repeats]

        video = pick_video_for_slot_for_user(
            session=session,
            user_id=user_id,
            workout_type=slot.workout_type,
            body_focus=slot.body_focus or "any",
            min_duration_sec=min_dur,
            max_duration_sec=max_dur,
            difficulty=difficulty,
            recency_boost_weeks=recency_boost_weeks,
            used_channel_names=used_channel_names,
            excluded_channel_ids=exhausted_ids,
            excluded_video_ids=used_video_ids,
        )

        if video:
            used_channel_names.append(video["channel_name"])
            used_video_ids.append(video["id"])
            channel_usage[video["channel_id"]] = channel_usage.get(video["channel_id"], 0) + 1

        plan.append({"day": day, "video": video})

    _save_plan_to_history(session, user_id, week_start, plan)

    summary = format_plan_summary(plan, week_start.isoformat())
    logger.info(f"\n{summary}")

    return plan
