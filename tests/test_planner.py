from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import src.db as db_module
from src.planner import (
    HISTORY_WINDOW_WEEKS,
    _score_candidate,
    format_plan_summary,
    get_upcoming_monday,
    pick_video_for_slot,
)


# ─── Pure function tests ───────────────────────────────────────────────────────

def test_get_upcoming_monday_is_monday():
    assert get_upcoming_monday().weekday() == 0


def test_get_upcoming_monday_never_today():
    a_monday = date(2026, 3, 9)  # a known Monday
    with patch("src.planner.date") as mock_date_cls:
        mock_date_cls.today.return_value = a_monday
        result = get_upcoming_monday()
    # When today is Monday, must return the *next* Monday (7 days ahead)
    assert result == a_monday + timedelta(days=7)
    assert result.weekday() == 0


def test_score_candidate_recency_boost():
    """Recent video (within recency_boost_weeks) scores exactly +100 vs old video."""
    now = datetime.now(timezone.utc)
    recent = {"published_at": (now - timedelta(weeks=1)).isoformat(), "channel_name": "Ch"}
    old = {"published_at": (now - timedelta(weeks=52)).isoformat(), "channel_name": "Ch"}

    with patch("src.planner.random.uniform", return_value=0.0):
        recent_score = _score_candidate(recent, 24, [])
        old_score = _score_candidate(old, 24, [])

    assert recent_score - old_score == 100.0


def test_score_candidate_channel_spread():
    """Unused channel scores exactly +40 vs already-used channel."""
    video_unused = {"published_at": None, "channel_name": "NewCh"}
    video_used = {"published_at": None, "channel_name": "UsedCh"}

    with patch("src.planner.random.uniform", return_value=0.0):
        unused_score = _score_candidate(video_unused, 24, [])
        used_score = _score_candidate(video_used, 24, ["UsedCh"])

    assert unused_score - used_score == 40.0


def test_format_plan_summary_with_rest():
    plan = [{"day": "sunday", "video": None}]
    summary = format_plan_summary(plan, "2026-03-09")
    assert "Sunday" in summary
    assert "Rest" in summary


def test_format_plan_summary_with_video():
    plan = [
        {
            "day": "monday",
            "video": {
                "workout_type": "HIIT",
                "body_focus": "full",
                "duration_sec": 1800,
                "title": "30 Minute Full Body HIIT",
                "channel_name": "TIFFxDAN",
            },
        }
    ]
    summary = format_plan_summary(plan, "2026-03-09")
    assert "HIIT" in summary
    assert "30 Minute Full Body HIIT" in summary
    assert "30min" in summary
    assert "TIFFxDAN" in summary


# ─── DB-dependent tests ───────────────────────────────────────────────────────

def _insert_video(conn, video_id="vid1", channel_name="TestChannel",
                  workout_type="HIIT", body_focus="full",
                  duration_sec=1800, published_at="2025-01-01T00:00:00Z"):
    conn.execute(
        """
        INSERT INTO videos (id, channel_id, channel_name, title, description,
                            duration_sec, published_at, url, tags)
        VALUES (?, 'UC123', ?, 'Test Workout', 'Test', ?, ?,
                'https://youtube.com/watch?v=' || ?, NULL)
        """,
        (video_id, channel_name, duration_sec, published_at, video_id),
    )
    conn.execute(
        """
        INSERT INTO classifications (video_id, workout_type, body_focus, difficulty,
                                     has_warmup, has_cooldown, classified_at)
        VALUES (?, ?, ?, 'intermediate', 0, 0, '2025-01-01T00:00:00Z')
        """,
        (video_id, workout_type, body_focus),
    )


def _slot_kwargs(**overrides):
    defaults = dict(
        workout_type="HIIT",
        body_focus="full",
        min_duration_sec=900,
        max_duration_sec=3600,
        difficulty="any",
        recency_boost_weeks=24,
        used_channels=[],
    )
    defaults.update(overrides)
    return defaults


def test_pick_video_for_slot_basic(test_db):
    with db_module.get_connection() as conn:
        _insert_video(conn)

    result = pick_video_for_slot(**_slot_kwargs())
    assert result is not None
    assert result["id"] == "vid1"


def test_pick_video_for_slot_no_candidates(test_db):
    # Empty library → None
    result = pick_video_for_slot(**_slot_kwargs())
    assert result is None


def test_pick_video_for_slot_fallback_tiers(test_db):
    """When body_focus doesn't match strictly, falls back to tier 3 (any focus)."""
    with db_module.get_connection() as conn:
        _insert_video(conn, body_focus="lower")  # strict 'upper' won't match 'lower'

    result = pick_video_for_slot(**_slot_kwargs(body_focus="upper"))
    assert result is not None
    assert result["id"] == "vid1"


def test_pick_video_for_slot_avoids_history(test_db):
    """Video in recent history is excluded; only the non-history video is returned."""
    with db_module.get_connection() as conn:
        _insert_video(conn, video_id="vid1")
        _insert_video(conn, video_id="vid2", channel_name="OtherChannel")
        # Place vid1 in history within the window
        recent_week = (date.today() - timedelta(weeks=1)).isoformat()
        conn.execute(
            "INSERT INTO program_history (week_start, video_id, assigned_day) VALUES (?, ?, ?)",
            (recent_week, "vid1", "monday"),
        )

    result = pick_video_for_slot(**_slot_kwargs())
    assert result is not None
    assert result["id"] == "vid2"
