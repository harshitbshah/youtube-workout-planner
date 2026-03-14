"""
Phase D unit tests — AI Cost Reduction features 5 & 6.

F5: Adaptive payload trimming — descriptive titles skip transcript fetch and use
    a shorter description limit before submitting to the AI batch.
F6: Rule-based title pre-classifier — obvious titles are classified without any
    AI call; only ambiguous titles are sent to Anthropic.

All tests use SQLite in-memory; no real network calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.models import Channel, Classification, User, UserChannel, Video
from api.services.classifier import _title_is_descriptive, title_classify


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_user(db, suffix="d"):
    u = User(google_id=f"pd-{suffix}", email=f"pd{suffix}@test.com")
    db.add(u)
    db.commit()
    return u


def _make_channel(db, user, suffix="d"):
    ch = Channel(
        name=f"Channel-{suffix}",
        youtube_url=f"https://youtube.com/@ch{suffix}",
    )
    db.add(ch)
    db.flush()
    db.add(UserChannel(user_id=user.id, channel_id=ch.id))
    db.commit()
    db.refresh(ch)
    return ch


def _make_video(db, channel, vid_id, title="Workout", duration_sec=1800):
    v = Video(
        id=vid_id,
        channel_id=channel.id,
        title=title,
        url=f"https://youtube.com/watch?v={vid_id}",
        published_at="2025-06-01T00:00:00Z",
        duration_sec=duration_sec,
    )
    db.add(v)
    db.commit()
    return v


def _fake_batch(results=None):
    """Return a mock Anthropic client whose batch completes immediately."""
    batch = MagicMock()
    batch.id = "batch-pd"
    batch.processing_status = "ended"
    batch.request_counts = MagicMock(succeeded=0, errored=0, canceled=0, expired=0, processing=0)

    client = MagicMock()
    client.messages.batches.create.return_value = batch
    client.messages.batches.retrieve.return_value = batch
    client.messages.batches.results.return_value = results or []
    return client


# ─── F5: _title_is_descriptive ────────────────────────────────────────────────

def test_f5_descriptive_title_with_duration():
    assert _title_is_descriptive("30 Min Full Body Strength")

def test_f5_descriptive_title_hiit():
    assert _title_is_descriptive("45 Minute HIIT Cardio Workout")

def test_f5_descriptive_title_yoga():
    assert _title_is_descriptive("Morning Yoga Stretch Routine")

def test_f5_descriptive_title_body_part():
    assert _title_is_descriptive("Upper Body Dumbbell Workout")

def test_f5_descriptive_title_abs():
    assert _title_is_descriptive("10 Minute Abs and Core")

def test_f5_ambiguous_title_not_descriptive():
    assert not _title_is_descriptive("My Channel Update")

def test_f5_ambiguous_title_vlog():
    assert not _title_is_descriptive("What I Ate Today")

def test_f5_descriptive_title_skips_transcript_fetch(db_session):
    """Descriptive title → _fetch_transcript_intro never called for that video."""
    user = _make_user(db_session, "f5a")
    ch = _make_channel(db_session, user, "f5a")
    _make_video(db_session, ch, "f5-desc", title="30 Min Full Body HIIT Workout")

    fetched_transcripts = []

    def fake_fetch_transcript(video_id):
        fetched_transcripts.append(video_id)
        return "some transcript"

    with patch("api.services.classifier._fetch_transcript_intro", side_effect=fake_fetch_transcript), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=_fake_batch()):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert "f5-desc" not in fetched_transcripts


def test_f5_ambiguous_title_fetches_transcript(db_session):
    """Ambiguous title → _fetch_transcript_intro IS called for that video."""
    user = _make_user(db_session, "f5b")
    ch = _make_channel(db_session, user, "f5b")
    _make_video(db_session, ch, "f5-ambig", title="My Favourite Routine Ever")

    fetched_transcripts = []

    def fake_fetch_transcript(video_id):
        fetched_transcripts.append(video_id)
        return None

    with patch("api.services.classifier._fetch_transcript_intro", side_effect=fake_fetch_transcript), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=_fake_batch()):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert "f5-ambig" in fetched_transcripts


def test_f5_descriptive_title_uses_short_description(db_session):
    """Descriptive title → description is capped to 300 chars in the built message."""
    user = _make_user(db_session, "f5c")
    ch = _make_channel(db_session, user, "f5c")
    # "Beginner" triggers _DESCRIPTIVE_PATTERN but no F6 type rule → goes to AI batch
    v = _make_video(db_session, ch, "f5-shortdesc", title="Beginner Workout Routine")
    # Add a long description directly
    v.description = "x" * 1000
    db_session.commit()

    captured_videos = []

    def fake_build_message(video, transcript_intro):
        captured_videos.append(video)
        return "msg"

    with patch("api.services.classifier._fetch_transcript_intro", return_value=None), \
         patch("api.services.classifier._build_user_message", side_effect=fake_build_message), \
         patch("anthropic.Anthropic", return_value=_fake_batch()):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert len(captured_videos) == 1
    assert len(captured_videos[0]["description"]) == 300


# ─── F6: title_classify — type detection ──────────────────────────────────────

def test_f6_hiit_title():
    result = title_classify("30 Min HIIT Cardio Blast", 1800)
    assert result is not None
    assert result["workout_type"] == "HIIT"

def test_f6_interval_title():
    result = title_classify("Interval Training No Equipment", 1500)
    assert result is not None
    assert result["workout_type"] == "HIIT"

def test_f6_yoga_title():
    result = title_classify("Morning Yoga Flow for Beginners", 2400)
    assert result is not None
    assert result["workout_type"] == "Mobility"

def test_f6_pilates_title():
    result = title_classify("Core Pilates Full Body", 1800)
    assert result is not None
    assert result["workout_type"] == "Mobility"

def test_f6_strength_title():
    result = title_classify("Upper Body Dumbbell Strength", 2400)
    assert result is not None
    assert result["workout_type"] == "Strength"

def test_f6_cardio_title():
    result = title_classify("30 Minute Running Cardio Workout", 1800)
    assert result is not None
    assert result["workout_type"] == "Cardio"

def test_f6_ambiguous_title_returns_none():
    result = title_classify("What I Ate Today", 300)
    assert result is None

def test_f6_vlog_title_returns_none():
    result = title_classify("My Week in Review", 600)
    assert result is None


# ─── F6: title_classify — body focus detection ───────────────────────────────

def test_f6_upper_body_focus():
    result = title_classify("Upper Body Strength Workout", 1800)
    assert result["body_focus"] == "upper"

def test_f6_lower_body_focus():
    result = title_classify("Lower Body Strength Workout", 1800)
    assert result is not None
    assert result["body_focus"] == "lower"

def test_f6_core_focus():
    result = title_classify("Core and Abs HIIT Workout", 1200)
    assert result["body_focus"] == "core"

def test_f6_full_body_focus():
    result = title_classify("Full Body Strength Training", 2400)
    assert result["body_focus"] == "full"

def test_f6_default_full_body_when_no_focus_keyword():
    result = title_classify("30 Min HIIT Workout", 1800)
    assert result["body_focus"] == "full"


# ─── F6: title_classify — difficulty detection ────────────────────────────────

def test_f6_beginner_difficulty():
    result = title_classify("Beginner Yoga Flow", 2400)
    assert result["difficulty"] == "beginner"

def test_f6_advanced_difficulty():
    result = title_classify("Advanced HIIT Cardio", 1800)
    assert result["difficulty"] == "advanced"

def test_f6_default_intermediate_difficulty():
    result = title_classify("Full Body Strength Workout", 2400)
    assert result["difficulty"] == "intermediate"


# ─── F6: title_classify — warmup / cooldown flags ─────────────────────────────

def test_f6_warmup_detected():
    result = title_classify("HIIT Warm-Up and Full Body Workout", 1800)
    assert result["has_warmup"] is True

def test_f6_cooldown_detected():
    result = title_classify("Strength Training with Cool Down", 2400)
    assert result["has_cooldown"] is True

def test_f6_no_warmup_cooldown_by_default():
    result = title_classify("30 Min Cardio Workout", 1800)
    assert result["has_warmup"] is False
    assert result["has_cooldown"] is False


# ─── F6: end-to-end — rule-classified videos skip AI batch ────────────────────

def test_f6_obvious_videos_skip_ai_batch(db_session):
    """Videos with obvious titles are classified without an AI call."""
    user = _make_user(db_session, "f6a")
    ch = _make_channel(db_session, user, "f6a")
    _make_video(db_session, ch, "f6-hiit", title="30 Min HIIT Full Body Workout")
    _make_video(db_session, ch, "f6-yoga", title="Beginner Yoga Stretch Routine")

    mock_client = _fake_batch()

    with patch("api.services.classifier._fetch_transcript_intro", return_value=None), \
         patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.classifier import classify_for_user
        total = classify_for_user(db_session, user.id, api_key="fake-key")

    # Both classified by rules — AI batch never submitted
    mock_client.messages.batches.create.assert_not_called()
    assert total == 2

    clfs = db_session.query(Classification).all()
    assert len(clfs) == 2
    types = {c.workout_type for c in clfs}
    assert "HIIT" in types
    assert "Mobility" in types


def test_f6_ambiguous_video_sent_to_ai(db_session):
    """A video with an ambiguous title is still submitted to the AI batch."""
    user = _make_user(db_session, "f6b")
    ch = _make_channel(db_session, user, "f6b")
    _make_video(db_session, ch, "f6-ambig", title="My Favourite Workout")

    submitted = []

    def fake_create(requests):
        submitted.extend(requests)
        batch = MagicMock()
        batch.id = "batch-f6b"
        batch.processing_status = "ended"
        batch.request_counts = MagicMock(succeeded=0, errored=0, canceled=0, expired=0, processing=0)
        return batch

    mock_client = MagicMock()
    mock_client.messages.batches.create.side_effect = fake_create
    mock_client.messages.batches.retrieve.return_value = MagicMock(
        processing_status="ended",
        request_counts=MagicMock(succeeded=0, errored=0, canceled=0, expired=0),
    )
    mock_client.messages.batches.results.return_value = []

    with patch("api.services.classifier._fetch_transcript_intro", return_value=None), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert len(submitted) == 1
    assert submitted[0]["custom_id"] == "f6-ambig"


def test_f6_mixed_obvious_and_ambiguous(db_session):
    """Mix of 2 obvious + 1 ambiguous: obvious classified by rules, ambiguous sent to AI."""
    user = _make_user(db_session, "f6c")
    ch = _make_channel(db_session, user, "f6c")
    _make_video(db_session, ch, "f6-strength", title="Upper Body Strength Training")
    _make_video(db_session, ch, "f6-cardio",   title="30 Min Cardio Blast")
    _make_video(db_session, ch, "f6-mystery",  title="Sunday Workout")

    submitted = []

    def fake_create(requests):
        submitted.extend(requests)
        batch = MagicMock()
        batch.id = "batch-f6c"
        batch.processing_status = "ended"
        batch.request_counts = MagicMock(succeeded=0, errored=0, canceled=0, expired=0, processing=0)
        return batch

    mock_client = MagicMock()
    mock_client.messages.batches.create.side_effect = fake_create
    mock_client.messages.batches.retrieve.return_value = MagicMock(
        processing_status="ended",
        request_counts=MagicMock(succeeded=0, errored=0, canceled=0, expired=0),
    )
    mock_client.messages.batches.results.return_value = []

    with patch("api.services.classifier._fetch_transcript_intro", return_value=None), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.classifier import classify_for_user
        classify_for_user(db_session, user.id, api_key="fake-key")

    # Only the ambiguous video goes to AI
    assert len(submitted) == 1
    assert submitted[0]["custom_id"] == "f6-mystery"

    # The two obvious ones are already classified
    rule_clfs = db_session.query(Classification).filter(
        Classification.video_id.in_(["f6-strength", "f6-cardio"])
    ).count()
    assert rule_clfs == 2
