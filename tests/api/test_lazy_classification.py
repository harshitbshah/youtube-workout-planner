"""
Unit tests for lazy classification — plan-first, classify-lazily.

Tests:
  - can_fill_plan / get_gap_types (planner.py)
  - rule_classify_for_user (classifier.py)
  - build_targeted_batch (classifier.py)
  - classify_for_user with preselected_videos (classifier.py)

All use SQLite in-memory; no real Anthropic or YouTube calls.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from api.models import Channel, Classification, Schedule, User, UserChannel, Video
from api.services.classifier import build_targeted_batch, rule_classify_for_user
from api.services.planner import MIN_PLAN_CANDIDATES, can_fill_plan, get_gap_types


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _user(db, suffix="a"):
    u = User(google_id=f"lz-{suffix}", email=f"lz{suffix}@test.com")
    db.add(u)
    db.commit()
    db_refresh = db.refresh(u)
    return u


def _channel(db, user, suffix="a"):
    ch = Channel(name=f"Ch-{suffix}", youtube_url=f"https://youtube.com/@lz{suffix}")
    db.add(ch)
    db.flush()
    db.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db.commit()
    db.refresh(ch)
    return ch


def _schedule_slot(db, user, day, workout_type, duration_min=20, duration_max=45):
    s = Schedule(
        user_id=user.id,
        day=day,
        workout_type=workout_type,
        body_focus="full",
        duration_min=duration_min,
        duration_max=duration_max,
        difficulty="any",
    )
    db.add(s)
    db.commit()
    return s


def _classified_video(db, channel, workout_type="HIIT", duration_sec=1800, vid_id=None):
    vid_id = vid_id or str(uuid.uuid4())[:8]
    v = Video(
        id=vid_id,
        channel_id=channel.id,
        title="Workout",
        url=f"https://youtube.com/watch?v={vid_id}",
        duration_sec=duration_sec,
        published_at="2025-06-01T00:00:00Z",
    )
    c = Classification(
        video_id=vid_id,
        workout_type=workout_type,
        body_focus="full",
        difficulty="intermediate",
        has_warmup=False,
        has_cooldown=False,
    )
    db.add_all([v, c])
    db.commit()
    return v


def _unclassified_video(db, channel, title="Workout", duration_sec=1800, vid_id=None):
    vid_id = vid_id or str(uuid.uuid4())[:8]
    v = Video(
        id=vid_id,
        channel_id=channel.id,
        title=title,
        url=f"https://youtube.com/watch?v={vid_id}",
        duration_sec=duration_sec,
        published_at="2025-06-01T00:00:00Z",
    )
    db.add(v)
    db.commit()
    return v


# ─── can_fill_plan ────────────────────────────────────────────────────────────

def test_can_fill_plan_true_when_all_slots_have_enough_candidates(db_session):
    u = _user(db_session, "b")
    ch = _channel(db_session, u, "b")
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)

    # Add MIN_PLAN_CANDIDATES videos matching the slot
    for _ in range(MIN_PLAN_CANDIDATES):
        _classified_video(db_session, ch, workout_type="HIIT", duration_sec=1800)

    assert can_fill_plan(db_session, str(u.id)) is True


def test_can_fill_plan_false_when_slot_has_too_few_candidates(db_session):
    u = _user(db_session, "c")
    ch = _channel(db_session, u, "c")
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)

    # Only MIN_PLAN_CANDIDATES - 1 matching videos
    for _ in range(MIN_PLAN_CANDIDATES - 1):
        _classified_video(db_session, ch, workout_type="HIIT", duration_sec=1800)

    assert can_fill_plan(db_session, str(u.id)) is False


def test_can_fill_plan_true_when_no_workout_slots(db_session):
    u = _user(db_session, "d")
    # No schedule at all — trivially fillable
    assert can_fill_plan(db_session, str(u.id)) is True


def test_can_fill_plan_false_when_one_of_two_slots_thin(db_session):
    u = _user(db_session, "e")
    ch = _channel(db_session, u, "e")
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)
    _schedule_slot(db_session, u, "wednesday", "Strength", duration_min=20, duration_max=45)

    # Fill HIIT slot adequately
    for _ in range(MIN_PLAN_CANDIDATES):
        _classified_video(db_session, ch, workout_type="HIIT", duration_sec=1800)

    # Strength slot has 0 candidates
    assert can_fill_plan(db_session, str(u.id)) is False


def test_can_fill_plan_respects_duration_range(db_session):
    u = _user(db_session, "f")
    ch = _channel(db_session, u, "f")
    # Slot wants 20–45 min (1200–2700 sec)
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)

    # Add enough HIIT videos but all too short (< 1200 sec)
    for _ in range(MIN_PLAN_CANDIDATES):
        _classified_video(db_session, ch, workout_type="HIIT", duration_sec=600)

    assert can_fill_plan(db_session, str(u.id)) is False


# ─── get_gap_types ────────────────────────────────────────────────────────────

def test_get_gap_types_returns_slots_below_threshold(db_session):
    u = _user(db_session, "g")
    ch = _channel(db_session, u, "g")
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)
    _schedule_slot(db_session, u, "wednesday", "Strength", duration_min=20, duration_max=45)

    # Fill Strength adequately
    for _ in range(MIN_PLAN_CANDIDATES):
        _classified_video(db_session, ch, workout_type="Strength", duration_sec=1800)

    gaps = get_gap_types(db_session, str(u.id))
    assert len(gaps) == 1
    assert gaps[0]["workout_type"] == "HIIT"


def test_get_gap_types_empty_when_all_slots_filled(db_session):
    u = _user(db_session, "h")
    ch = _channel(db_session, u, "h")
    _schedule_slot(db_session, u, "monday", "HIIT", duration_min=20, duration_max=45)

    for _ in range(MIN_PLAN_CANDIDATES):
        _classified_video(db_session, ch, workout_type="HIIT", duration_sec=1800)

    gaps = get_gap_types(db_session, str(u.id))
    assert gaps == []


def test_get_gap_types_skips_rest_days(db_session):
    u = _user(db_session, "i")
    # Schedule slot with no workout_type (rest day)
    s = Schedule(user_id=u.id, day="sunday", workout_type=None, body_focus=None,
                 duration_min=None, duration_max=None, difficulty=None)
    db_session.add(s)
    db_session.commit()

    gaps = get_gap_types(db_session, str(u.id))
    assert gaps == []


# ─── rule_classify_for_user ───────────────────────────────────────────────────

def test_rule_classify_saves_obvious_titles(db_session):
    u = _user(db_session, "j")
    ch = _channel(db_session, u, "j")
    _unclassified_video(db_session, ch, title="30 Min HIIT Workout", duration_sec=1800, vid_id="hiit1")
    _unclassified_video(db_session, ch, title="Beginner Yoga Flow", duration_sec=1800, vid_id="yoga1")

    count = rule_classify_for_user(db_session, str(u.id))

    assert count == 2
    hiit_clf = db_session.get(Classification, "hiit1")
    yoga_clf = db_session.get(Classification, "yoga1")
    assert hiit_clf is not None and hiit_clf.workout_type == "HIIT"
    assert yoga_clf is not None and yoga_clf.workout_type == "Mobility"


def test_rule_classify_skips_ambiguous_titles(db_session):
    u = _user(db_session, "k")
    ch = _channel(db_session, u, "k")
    _unclassified_video(db_session, ch, title="My Channel Update", duration_sec=1800, vid_id="vlog1")

    count = rule_classify_for_user(db_session, str(u.id))

    assert count == 0
    assert db_session.get(Classification, "vlog1") is None


def test_rule_classify_returns_zero_when_no_unclassified(db_session):
    u = _user(db_session, "l")
    ch = _channel(db_session, u, "l")
    # Video already classified
    _classified_video(db_session, ch, workout_type="HIIT")

    count = rule_classify_for_user(db_session, str(u.id))
    assert count == 0


# ─── build_targeted_batch ─────────────────────────────────────────────────────

def test_build_targeted_batch_targets_gap_type_videos(db_session):
    u = _user(db_session, "m")
    ch = _channel(db_session, u, "m")
    _unclassified_video(db_session, ch, title="HIIT Cardio Blast", vid_id="hiit1")
    _unclassified_video(db_session, ch, title="My Vlog Today", vid_id="vlog1")

    gap_types = [{"workout_type": "HIIT", "duration_min": 20, "duration_max": 45}]
    targeted, remainder = build_targeted_batch(str(u.id), gap_types, db_session)

    targeted_ids = [v["id"] for v in targeted]
    remainder_ids = [v["id"] for v in remainder]
    assert "hiit1" in targeted_ids
    assert "vlog1" in remainder_ids


def test_build_targeted_batch_cap(db_session):
    u = _user(db_session, "n")
    ch = _channel(db_session, u, "n")

    # Add 20 HIIT videos for a single gap type
    for i in range(20):
        _unclassified_video(db_session, ch, title=f"HIIT Workout {i}", vid_id=f"hiit{i:02d}")

    gap_types = [{"workout_type": "HIIT", "duration_min": 20, "duration_max": 45}]
    targeted, remainder = build_targeted_batch(str(u.id), gap_types, db_session)

    # Cap = max(1 gap * 5 multiplier, 10) = 10
    assert len(targeted) <= 10
    assert len(targeted) + len(remainder) == 20


def test_build_targeted_batch_remainder_gets_non_matching(db_session):
    u = _user(db_session, "o")
    ch = _channel(db_session, u, "o")
    _unclassified_video(db_session, ch, title="Yoga Morning Flow", vid_id="yoga1")
    _unclassified_video(db_session, ch, title="Random Vlog", vid_id="vlog1")

    # Gap is HIIT — neither video matches
    gap_types = [{"workout_type": "HIIT", "duration_min": 20, "duration_max": 45}]
    targeted, remainder = build_targeted_batch(str(u.id), gap_types, db_session)

    assert targeted == []
    assert len(remainder) == 2


def test_build_targeted_batch_empty_when_no_unclassified(db_session):
    u = _user(db_session, "p")
    ch = _channel(db_session, u, "p")
    _classified_video(db_session, ch, workout_type="HIIT")

    gap_types = [{"workout_type": "HIIT", "duration_min": 20, "duration_max": 45}]
    targeted, remainder = build_targeted_batch(str(u.id), gap_types, db_session)

    assert targeted == []
    assert remainder == []


# ─── classify_for_user with preselected_videos ────────────────────────────────

def _fake_anthropic_client(results=None):
    batch = MagicMock()
    batch.id = "batch-lazy-test"
    batch.processing_status = "ended"
    batch.request_counts = MagicMock(succeeded=0, errored=0, canceled=0, expired=0, processing=0)
    client = MagicMock()
    client.messages.batches.create.return_value = batch
    client.messages.batches.retrieve.return_value = batch
    client.messages.batches.results.return_value = results or []
    return client


def test_classify_for_user_preselected_skips_fetch_and_rule_classify(db_session):
    """When preselected_videos provided, only those videos are submitted — no DB fetch."""
    from api.services.classifier import classify_for_user

    u = _user(db_session, "q")
    ch = _channel(db_session, u, "q")
    # Add an unclassified video in DB — should NOT be fetched when preselected used
    _unclassified_video(db_session, ch, title="HIIT Blast", vid_id="db_vid")

    targeted = [{"id": "ext_vid", "title": "Strength Training", "description": "", "duration_sec": 1800, "tags": None}]
    fake_client = _fake_anthropic_client()

    with patch("anthropic.Anthropic", return_value=fake_client):
        classify_for_user(db_session, str(u.id), api_key="fake", preselected_videos=targeted)

    # Batch should be created with only the 1 preselected video
    call_args = fake_client.messages.batches.create.call_args
    submitted_ids = [r["custom_id"] for r in call_args.kwargs.get("requests", call_args.args[0] if call_args.args else [])]
    assert "ext_vid" in submitted_ids
    assert "db_vid" not in submitted_ids


def test_classify_for_user_preselected_empty_returns_zero(db_session):
    """classify_for_user with empty preselected list returns 0 without API call."""
    from api.services.classifier import classify_for_user

    u = _user(db_session, "r")
    fake_client = _fake_anthropic_client()

    with patch("anthropic.Anthropic", return_value=fake_client):
        result = classify_for_user(db_session, str(u.id), api_key="fake", preselected_videos=[])

    assert result == 0
    fake_client.messages.batches.create.assert_not_called()
