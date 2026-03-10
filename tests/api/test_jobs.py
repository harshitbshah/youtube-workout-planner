"""
Tests for jobs endpoints:
  POST /jobs/scan                 — full pipeline (scan all channels → classify → generate plan)
  POST /jobs/channels/{id}/scan   — per-channel scan

YouTube API calls and the scan/classify pipeline are mocked — no real network calls.
"""

from unittest.mock import MagicMock, patch

from api.models import Channel


def _add_channel(db_session, user):
    ch = Channel(
        user_id=user.id,
        name="Jeff Nippard",
        youtube_url="https://youtube.com/@jeffnippard",
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)
    return ch


# ─── POST /jobs/scan — full pipeline ──────────────────────────────────────────

def test_full_pipeline_scan_returns_202(auth_client, db_session):
    """Returns 202 and enqueues background task when user has channels."""
    client, user = auth_client
    _add_channel(db_session, user)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_full_pipeline") as mock_pipeline:
        resp = client.post("/jobs/scan")

    assert resp.status_code == 202
    assert "Pipeline started" in resp.json()["message"]
    mock_pipeline.assert_called_once_with(str(user.id))


def test_full_pipeline_scan_no_channels_returns_400(auth_client):
    """Returns 400 when the user has no channels — nothing to scan."""
    client, user = auth_client
    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post("/jobs/scan")
    assert resp.status_code == 400
    assert "No channels" in resp.json()["detail"]


def test_full_pipeline_scan_no_api_key_returns_503(auth_client, db_session):
    """Returns 503 when YOUTUBE_API_KEY is not configured."""
    client, user = auth_client
    _add_channel(db_session, user)
    with patch("api.routers.jobs.YOUTUBE_API_KEY", ""):
        resp = client.post("/jobs/scan")
    assert resp.status_code == 503


def test_full_pipeline_scan_unauthenticated(client):
    """Returns 401 when not authenticated."""
    resp = client.post("/jobs/scan")
    assert resp.status_code == 401


def test_full_pipeline_scan_message_includes_channel_count(auth_client, db_session):
    """Response message includes how many channels were queued."""
    client, user = auth_client
    _add_channel(db_session, user)
    _add_channel(db_session, user)  # second channel

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_full_pipeline"):
        resp = client.post("/jobs/scan")

    assert resp.status_code == 202
    assert "2" in resp.json()["message"]


# ─── POST /channels/{id}/scan — per-channel ───────────────────────────────────

def test_trigger_scan_returns_202(auth_client, db_session):
    client, user = auth_client
    ch = _add_channel(db_session, user)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"), \
         patch("api.routers.jobs._run_scan_and_classify"):
        resp = client.post(f"/jobs/channels/{ch.id}/scan")

    assert resp.status_code == 202
    data = resp.json()
    assert data["channel_id"] == ch.id
    assert "Scan started" in data["message"]


def test_trigger_scan_channel_not_found(auth_client):
    client, user = auth_client
    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post("/jobs/channels/nonexistent-id/scan")
    assert resp.status_code == 404


def test_trigger_scan_other_users_channel(auth_client, db_session):
    from api.models import User
    client, user = auth_client

    other = User(google_id="other-scan-g", email="otherscan@example.com")
    db_session.add(other)
    db_session.commit()
    ch = Channel(user_id=other.id, name="Other", youtube_url="https://youtube.com/@other")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", "fake-key"):
        resp = client.post(f"/jobs/channels/{ch.id}/scan")
    assert resp.status_code == 404


def test_trigger_scan_no_api_key(auth_client, db_session):
    client, user = auth_client
    ch = _add_channel(db_session, user)

    with patch("api.routers.jobs.YOUTUBE_API_KEY", ""):
        resp = client.post(f"/jobs/channels/{ch.id}/scan")
    assert resp.status_code == 503


def test_trigger_scan_unauthenticated(client, db_session):
    resp = client.post("/jobs/channels/any-id/scan")
    assert resp.status_code == 401


# ─── Scanner service unit tests ───────────────────────────────────────────────

def test_scan_channel_full_scan_when_no_videos(db_session):
    """Full scan triggered when channel has no videos."""
    from api.models import Channel, User, Video
    from api.services.scanner import _get_since_date

    user = User(google_id="scanner-g", email="scanner@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="Test", youtube_url="https://youtube.com/@test")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    assert _get_since_date(db_session, ch) is None


def test_scan_channel_incremental_when_videos_exist(db_session):
    """Incremental scan triggered when videos already exist."""
    from api.models import Channel, User, Video
    from api.services.scanner import _get_since_date

    user = User(google_id="scanner-g2", email="scanner2@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="Test2", youtube_url="https://youtube.com/@test2")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    db_session.add(Video(
        id="vid-existing",
        channel_id=ch.id,
        title="Old Video",
        url="https://youtube.com/watch?v=vid-existing",
        published_at="2025-01-01T00:00:00Z",
    ))
    db_session.commit()

    since = _get_since_date(db_session, ch)
    assert since is not None
    assert since.year == 2025


def test_save_videos_skips_duplicates(db_session):
    """_save_videos should not insert a video that already exists."""
    from api.models import Channel, User, Video
    from api.services.scanner import _save_videos

    user = User(google_id="scanner-g3", email="scanner3@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="Test3", youtube_url="https://youtube.com/@test3")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    videos = [{"id": "dup-vid", "title": "Dup", "url": "https://youtube.com/watch?v=dup-vid"}]
    count1 = _save_videos(db_session, ch, videos)
    count2 = _save_videos(db_session, ch, videos)

    assert count1 == 1
    assert count2 == 0
    assert db_session.query(Video).filter(Video.id == "dup-vid").count() == 1


# ─── GET /jobs/status ─────────────────────────────────────────────────────────

def test_jobs_status_no_pipeline(auth_client):
    """Returns null stage when no pipeline has run for this user."""
    client, user = auth_client
    resp = client.get("/jobs/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] is None
    assert data["total"] is None
    assert data["done"] is None


def test_jobs_status_unauthenticated(client):
    """Returns 401 when not authenticated."""
    resp = client.get("/jobs/status")
    assert resp.status_code == 401


def test_jobs_status_reflects_pipeline_state(auth_client):
    """Status reflects what _pipeline_status holds for this user."""
    from api.routers.jobs import _pipeline_status
    client, user = auth_client

    _pipeline_status[str(user.id)] = {"stage": "classifying", "total": 100, "done": 42}
    try:
        resp = client.get("/jobs/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "classifying"
        assert data["total"] == 100
        assert data["done"] == 42
    finally:
        _pipeline_status.pop(str(user.id), None)


# ─── Duration filter unit tests ───────────────────────────────────────────────

def test_upper_duration_cap():
    """Videos over 2 hours must be excluded."""
    from api.services.scanner import _MAX_DURATION_SEC
    assert _MAX_DURATION_SEC == 2 * 60 * 60

    # Simulate the filter logic used in _scan_uploads
    videos = [
        {"id": "ok", "duration_sec": 3600},       # 1 hour — keep
        {"id": "too-long", "duration_sec": 7201},  # > 2 hours — drop
        {"id": "too-short", "duration_sec": 60},   # < 3 min — drop
        {"id": "none-dur", "duration_sec": None},  # unknown — drop
    ]
    kept = [v for v in videos if v.get("duration_sec") and 180 <= v["duration_sec"] <= _MAX_DURATION_SEC]
    assert [v["id"] for v in kept] == ["ok"]


# ─── Classifier cap unit tests ─────────────────────────────────────────────────

def test_classify_cap_limits_batch(db_session):
    """classify_for_user should only process up to MAX_CLASSIFY_PER_RUN videos."""
    from unittest.mock import MagicMock, patch
    from api.models import Channel, User, Video
    from api.services.classifier import classify_for_user, MAX_CLASSIFY_PER_RUN

    user = User(google_id="cap-test-g", email="cap@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="BigCh", youtube_url="https://youtube.com/@bigch")
    db_session.add(ch)
    db_session.commit()

    # Add MAX_CLASSIFY_PER_RUN + 10 videos — only the first batch should be classified
    for i in range(MAX_CLASSIFY_PER_RUN + 10):
        db_session.add(Video(
            id=f"cap-vid-{i}", channel_id=ch.id, title=f"Video {i}",
            url=f"https://youtube.com/watch?v=cap-vid-{i}", duration_sec=1800,
        ))
    db_session.commit()

    submitted_count = []

    def fake_create(requests):
        submitted_count.append(len(requests))
        batch = MagicMock()
        batch.id = "batch-123"
        batch.processing_status = "ended"
        batch.request_counts.succeeded = 0
        batch.request_counts.errored = 0
        batch.request_counts.canceled = 0
        batch.request_counts.expired = 0
        return batch

    mock_client = MagicMock()
    mock_client.messages.batches.create.side_effect = fake_create
    mock_client.messages.batches.retrieve.return_value = MagicMock(
        processing_status="ended",
        request_counts=MagicMock(succeeded=0, errored=0, canceled=0, expired=0),
    )
    mock_client.messages.batches.results.return_value = []

    with patch("api.services.classifier._fetch_transcript_intro", return_value=""), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=mock_client):
        classify_for_user(db_session, user.id, api_key="fake-key")

    assert submitted_count == [MAX_CLASSIFY_PER_RUN]


def test_classify_on_progress_called_during_polling(db_session):
    """on_progress callback is called during batch polling with total and done counts."""
    from unittest.mock import MagicMock, patch
    from api.models import Channel, User, Video
    from api.services.classifier import classify_for_user

    user = User(google_id="prog-test-g", email="prog@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="ProgCh", youtube_url="https://youtube.com/@progch")
    db_session.add(ch)
    db_session.commit()
    db_session.add(Video(id="prog-vid", channel_id=ch.id, title="Workout",
                         url="https://youtube.com/watch?v=prog-vid", duration_sec=1800))
    db_session.commit()

    progress_calls = []

    mock_batch = MagicMock()
    mock_batch.id = "batch-prog"
    mock_batch.processing_status = "ended"
    mock_batch.request_counts.succeeded = 1
    mock_batch.request_counts.errored = 0
    mock_batch.request_counts.canceled = 0
    mock_batch.request_counts.expired = 0

    mock_client = MagicMock()
    mock_client.messages.batches.create.return_value = mock_batch
    mock_client.messages.batches.retrieve.return_value = mock_batch
    mock_client.messages.batches.results.return_value = []

    with patch("api.services.classifier._fetch_transcript_intro", return_value=""), \
         patch("api.services.classifier._build_user_message", return_value="msg"), \
         patch("anthropic.Anthropic", return_value=mock_client):
        classify_for_user(db_session, user.id, api_key="fake-key",
                          on_progress=lambda t, d: progress_calls.append((t, d)))

    assert len(progress_calls) >= 1
    assert all(t == 1 for t, d in progress_calls)


# ─── Title blocklist unit tests ───────────────────────────────────────────────

def test_is_blocked_title_rejects_non_workout():
    from api.services.scanner import _is_blocked_title
    assert _is_blocked_title("My Meal Prep for the Week") is True
    assert _is_blocked_title("Weekly Grocery Haul") is True
    assert _is_blocked_title("Q&A — Your Questions Answered") is True
    assert _is_blocked_title("Vlog: Day In My Life") is True
    assert _is_blocked_title("Unboxing: New Home Gym Gear") is True


def test_is_blocked_title_allows_workout():
    from api.services.scanner import _is_blocked_title
    assert _is_blocked_title("30 Min Full Body Workout") is False
    assert _is_blocked_title("HIIT Cardio Beginner Training") is False
    assert _is_blocked_title("Upper Body Strength — No Equipment") is False
    assert _is_blocked_title("10 Min Core Workout for Beginners") is False


def test_is_blocked_title_case_insensitive():
    from api.services.scanner import _is_blocked_title
    assert _is_blocked_title("MEAL PREP SUNDAY") is True
    assert _is_blocked_title("Recipe for Pre-Workout Shake") is True


# ─── Classifier service unit tests ────────────────────────────────────────────

def test_fetch_unclassified_for_user_scoped(db_session):
    """Only returns videos from the target user's channels."""
    from api.models import Channel, Classification, User, Video
    from api.services.classifier import _fetch_unclassified_for_user

    user_a = User(google_id="clf-a", email="clfa@test.com")
    user_b = User(google_id="clf-b", email="clfb@test.com")
    db_session.add_all([user_a, user_b])
    db_session.commit()

    ch_a = Channel(user_id=user_a.id, name="A", youtube_url="https://youtube.com/@a")
    ch_b = Channel(user_id=user_b.id, name="B", youtube_url="https://youtube.com/@b")
    db_session.add_all([ch_a, ch_b])
    db_session.commit()

    db_session.add(Video(id="vid-a", channel_id=ch_a.id, title="A Video",
                         url="https://youtube.com/watch?v=vid-a", duration_sec=1800))
    db_session.add(Video(id="vid-b", channel_id=ch_b.id, title="B Video",
                         url="https://youtube.com/watch?v=vid-b", duration_sec=1800))
    db_session.commit()

    result = _fetch_unclassified_for_user(db_session, user_a.id)
    assert len(result) == 1
    assert result[0]["id"] == "vid-a"


def test_fetch_unclassified_excludes_already_classified(db_session):
    """Classified videos must not appear in the unclassified list."""
    from api.models import Channel, Classification, User, Video
    from api.services.classifier import _fetch_unclassified_for_user

    user = User(google_id="clf-c", email="clfc@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="C", youtube_url="https://youtube.com/@c")
    db_session.add(ch)
    db_session.commit()

    db_session.add(Video(id="vid-classified", channel_id=ch.id, title="Done",
                         url="https://youtube.com/watch?v=vid-classified", duration_sec=1800))
    db_session.add(Classification(video_id="vid-classified", workout_type="Strength",
                                  body_focus="upper", difficulty="intermediate"))
    db_session.commit()

    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []


def test_fetch_unclassified_excludes_shorts(db_session):
    """Videos shorter than 3 minutes (Shorts) must be excluded."""
    from api.models import Channel, User, Video
    from api.services.classifier import _fetch_unclassified_for_user

    user = User(google_id="clf-d", email="clfd@test.com")
    db_session.add(user)
    db_session.commit()

    ch = Channel(user_id=user.id, name="D", youtube_url="https://youtube.com/@d")
    db_session.add(ch)
    db_session.commit()

    db_session.add(Video(id="short-vid", channel_id=ch.id, title="Short",
                         url="https://youtube.com/watch?v=short-vid", duration_sec=60))
    db_session.commit()

    result = _fetch_unclassified_for_user(db_session, user.id)
    assert result == []
