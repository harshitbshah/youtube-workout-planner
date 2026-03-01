"""
planner.py — Generate a holistic weekly workout plan from the video library.

Selection logic (in priority order):
  1. Matches the day's required workout_type and body_focus
  2. Within the duration limit for that day
  3. Not used in the last HISTORY_WINDOW_WEEKS weeks
  4. Newer videos preferred (recency boost)
  5. Channel spread preferred (avoid all videos from same channel)
  6. Random jitter ensures the plan feels fresh even with identical scores

Fallback tiers (when strict query returns too few candidates):
  Tier 1 — Full constraints (type + focus + duration + history window)
  Tier 2 — Relax history window to 4 weeks
  Tier 3 — Relax body_focus to 'any' + 4 week history
  Tier 4 — No history restriction (always finds something if the library has it)
"""

import logging
import random
from datetime import date, datetime, timedelta, timezone

from .db import get_connection

logger = logging.getLogger(__name__)

# Don't reuse a video if it appeared in the plan within this many weeks
HISTORY_WINDOW_WEEKS = 8

# When scoring, pick randomly from the top N candidates (prevents repetition)
TOP_N_PICK = 3

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# ─── Date helpers ─────────────────────────────────────────────────────────────

def get_upcoming_monday() -> date:
    """
    Return the date of the upcoming Monday.
    If today is Sunday (GitHub Actions run day), this is tomorrow.
    If today is already Monday, this is next Monday.
    """
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


# ─── Candidate fetching ───────────────────────────────────────────────────────

def _fetch_candidates(workout_type: str, body_focus: str,
                      max_duration_sec: int, history_weeks: int) -> list[dict]:
    """
    Query the DB for classified videos that match the slot requirements
    and haven't been used within the history window.

    body_focus='any' in the slot config matches all videos.
    A video classified as body_focus='any' matches all slot requirements.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(weeks=history_weeks)).isoformat()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT  v.id,
                    v.channel_name,
                    v.title,
                    v.url,
                    v.published_at,
                    v.duration_sec,
                    c.workout_type,
                    c.body_focus,
                    c.difficulty,
                    c.has_warmup,
                    c.has_cooldown
            FROM    videos v
            JOIN    classifications c ON c.video_id = v.id
            WHERE   c.workout_type = ?
              AND   (
                      c.body_focus = ?          -- exact match
                   OR c.body_focus = 'any'      -- video is generic, fits any slot
                   OR ? = 'any'                 -- slot accepts any body focus
                    )
              AND   (v.duration_sec IS NULL OR v.duration_sec <= ?)
              AND   v.id NOT IN (
                        SELECT video_id
                        FROM   program_history
                        WHERE  week_start >= ?
                    )
            ORDER   BY v.published_at DESC
        """, (workout_type, body_focus, body_focus, max_duration_sec, cutoff)).fetchall()

    return [dict(r) for r in rows]


# ─── Candidate scoring ────────────────────────────────────────────────────────

def _score_candidate(video: dict, recency_boost_weeks: int,
                     used_channels: list[str]) -> float:
    """
    Score a candidate video. Higher = more likely to be picked.

    Scoring components:
      +100  if published within recency_boost_weeks (newer videos get priority)
      + 40  if from a channel not yet used this week (spread across channels)
      + 0–20 random jitter (prevents the same video winning every week)
    """
    score = random.uniform(0, 20)  # base jitter

    if video["published_at"]:
        pub_dt = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
        age_weeks = (datetime.now(timezone.utc) - pub_dt).days / 7
        if age_weeks <= recency_boost_weeks:
            score += 100.0

    if video["channel_name"] not in used_channels:
        score += 40.0

    return score


# ─── Slot picker ─────────────────────────────────────────────────────────────

def pick_video_for_slot(workout_type: str, body_focus: str,
                        max_duration_sec: int, recency_boost_weeks: int,
                        used_channels: list[str]) -> dict | None:
    """
    Pick the best video for a single workout slot using tiered fallbacks.

    Returns a video dict, or None if the library has nothing suitable at all.
    """
    fallback_tiers = [
        # (history_weeks, body_focus_to_use)  — progressively relaxed
        (HISTORY_WINDOW_WEEKS, body_focus),   # Tier 1: strict
        (4,                   body_focus),    # Tier 2: shorter history window
        (4,                   "any"),         # Tier 3: relax body focus
        (0,                   "any"),         # Tier 4: no history restriction
    ]

    for history_weeks, effective_focus in fallback_tiers:
        candidates = _fetch_candidates(
            workout_type, effective_focus, max_duration_sec, history_weeks
        )
        if candidates:
            if history_weeks < HISTORY_WINDOW_WEEKS:
                label = f"tier fallback (history={history_weeks}w, focus={effective_focus})"
                logger.debug(f"    Using {label} — {len(candidates)} candidates")
            break
    else:
        return None

    # Score all candidates and pick randomly from the top N
    scored = sorted(
        candidates,
        key=lambda v: _score_candidate(v, recency_boost_weeks, used_channels),
        reverse=True,
    )
    top_candidates = scored[:TOP_N_PICK]
    return random.choice(top_candidates)


# ─── History persistence ──────────────────────────────────────────────────────

def save_plan_to_history(week_start: str, plan: list[dict]):
    """Record the generated plan in program_history so videos aren't repeated."""
    rows = [
        {
            "week_start":   week_start,
            "video_id":     day["video"]["id"],
            "assigned_day": day["day"],
        }
        for day in plan if day["video"] is not None
    ]
    if not rows:
        return
    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO program_history (week_start, video_id, assigned_day)
            VALUES (:week_start, :video_id, :assigned_day)
        """, rows)


# ─── Plan summary formatter ───────────────────────────────────────────────────

def format_plan_summary(plan: list[dict], week_start: str) -> str:
    """
    Return a human-readable weekly plan summary.
    Used for logging and as the YouTube playlist description.
    """
    lines = [f"Weekly Workout Plan — w/c {week_start}", ""]

    for day in plan:
        day_label = day["day"].capitalize()
        if day["video"] is None:
            lines.append(f"{day_label:12s}  Rest")
        else:
            v = day["video"]
            duration = f"{v['duration_sec'] // 60}min" if v["duration_sec"] else "?min"
            lines.append(
                f"{day_label:12s}  [{v['workout_type']} · {v['body_focus']} · {duration}]  "
                f"{v['title'][:55]}  ({v['channel_name']})"
            )

    return "\n".join(lines)


# ─── Main entry point ─────────────────────────────────────────────────────────

def generate_weekly_plan(config: dict) -> list[dict]:
    """
    Generate a full weekly workout plan based on the schedule in config.yaml.

    Returns a list of day dicts ordered Mon → Sun:
      [
        { "day": "monday",   "video": { ...video + classification fields... } },
        { "day": "tuesday",  "video": { ...                                  } },
        { "day": "wednesday","video": None },   ← Rest day
        ...
      ]

    Also persists the plan to program_history so videos aren't repeated.
    """
    week_start = get_upcoming_monday().isoformat()
    schedule = config["schedule"]
    recency_boost_weeks = config.get("recency_boost_weeks", 24)

    plan = []
    used_channels: list[str] = []

    for day in DAYS_OF_WEEK:
        slot = schedule.get(day)

        if not slot or slot.get("workout_type") == "Rest":
            plan.append({"day": day, "video": None})
            continue

        workout_type     = slot["workout_type"]
        body_focus       = slot["body_focus"]
        max_duration_sec = slot.get("duration_max_min", 60) * 60

        logger.info(f"  Picking {day}: {workout_type} / {body_focus} / ≤{max_duration_sec // 60}min")

        video = pick_video_for_slot(
            workout_type=workout_type,
            body_focus=body_focus,
            max_duration_sec=max_duration_sec,
            recency_boost_weeks=recency_boost_weeks,
            used_channels=used_channels,
        )

        if video:
            used_channels.append(video["channel_name"])
            logger.info(f"    ✓ {video['title'][:60]}  ({video['channel_name']})")
        else:
            logger.warning(
                f"    ✗ No video found for {day} ({workout_type}/{body_focus}) — "
                f"consider adding more videos or adjusting config.yaml"
            )

        plan.append({"day": day, "video": video})

    save_plan_to_history(week_start, plan)

    summary = format_plan_summary(plan, week_start)
    logger.info(f"\n{summary}")

    return plan
