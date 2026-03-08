"""
Integration tests for api/services/scanner.py against real PostgreSQL.

What these add over unit tests:
  - Real unique constraint: duplicate video IDs are rejected at DB level
  - _get_since_date reads the correct most-recent published_at from Postgres
  - youtube_channel_id is persisted back to the Channel row after resolution
  - Videos are correctly FK-linked to the channel UUID (not YouTube channel ID)
  - Shorts filtering (hashtag + duration) verified end-to-end via scan_channel mock
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from api.models import Channel, Video
from api.services.scanner import _get_since_date, _save_videos


# ─── _get_since_date ──────────────────────────────────────────────────────────

def test_get_since_date_returns_none_when_no_videos(db_session, make_user, make_channel):
    user = make_user()
    channel = make_channel(user.id)
    assert _get_since_date(db_session, channel) is None


def test_get_since_date_returns_most_recent(db_session, make_user, make_channel):
    user = make_user()
    channel = make_channel(user.id)

    db_session.add(Video(
        id="old-vid", channel_id=channel.id, title="Old",
        url="https://youtube.com/watch?v=old-vid",
        published_at="2025-01-01T00:00:00Z",
    ))
    db_session.add(Video(
        id="new-vid", channel_id=channel.id, title="New",
        url="https://youtube.com/watch?v=new-vid",
        published_at="2025-06-01T00:00:00Z",
    ))
    db_session.commit()

    since = _get_since_date(db_session, channel)
    assert since is not None
    assert since.year == 2025
    assert since.month == 6


def test_get_since_date_scoped_to_channel(db_session, make_user, make_channel):
    """since_date must only consider videos for the given channel."""
    user = make_user()
    ch_a = make_channel(user.id, name="A", youtube_url="https://youtube.com/@a")
    ch_b = make_channel(user.id, name="B", youtube_url="https://youtube.com/@b")

    # Only ch_b has a video
    db_session.add(Video(
        id="vid-b", channel_id=ch_b.id, title="B Video",
        url="https://youtube.com/watch?v=vid-b",
        published_at="2025-06-01T00:00:00Z",
    ))
    db_session.commit()

    # ch_a has no videos — should trigger full scan
    assert _get_since_date(db_session, ch_a) is None


# ─── _save_videos ─────────────────────────────────────────────────────────────

def test_save_videos_inserts_new_rows(db_session, make_user, make_channel):
    user = make_user()
    channel = make_channel(user.id)

    videos = [
        {"id": "v1", "title": "Push Day", "url": "https://youtube.com/watch?v=v1",
         "description": "Upper body", "duration_sec": 1800,
         "published_at": "2025-06-01T00:00:00Z", "tags": "strength,upper"},
        {"id": "v2", "title": "Pull Day", "url": "https://youtube.com/watch?v=v2",
         "description": "Back", "duration_sec": 2100,
         "published_at": "2025-06-08T00:00:00Z", "tags": None},
    ]
    count = _save_videos(db_session, channel, videos)
    assert count == 2

    rows = db_session.query(Video).filter(Video.channel_id == channel.id).all()
    assert len(rows) == 2
    ids = {r.id for r in rows}
    assert ids == {"v1", "v2"}


def test_save_videos_skips_duplicates_in_postgres(db_session, make_user, make_channel):
    """Real Postgres: inserting the same video ID twice must not raise and returns 0."""
    user = make_user()
    channel = make_channel(user.id)

    videos = [{"id": "dup", "title": "Dup", "url": "https://youtube.com/watch?v=dup"}]
    count1 = _save_videos(db_session, channel, videos)
    count2 = _save_videos(db_session, channel, videos)

    assert count1 == 1
    assert count2 == 0
    assert db_session.query(Video).filter(Video.id == "dup").count() == 1


def test_save_videos_links_to_channel_uuid(db_session, make_user, make_channel):
    """Videos must be stored with our internal channel UUID, not YouTube's channel ID."""
    user = make_user()
    channel = make_channel(user.id)

    _save_videos(db_session, channel, [
        {"id": "v-uuid", "title": "Test", "url": "https://youtube.com/watch?v=v-uuid"}
    ])

    video = db_session.query(Video).filter(Video.id == "v-uuid").first()
    assert video.channel_id == channel.id


def test_save_videos_different_channels_same_video_id(db_session, make_user, make_channel):
    """
    YouTube video IDs are globally unique — a video can only belong to one channel.
    Saving the same video ID for a second channel skips it.
    """
    user = make_user()
    ch_a = make_channel(user.id, name="A", youtube_url="https://youtube.com/@a")
    ch_b = make_channel(user.id, name="B", youtube_url="https://youtube.com/@b")

    videos = [{"id": "shared-vid", "title": "Shared", "url": "https://youtube.com/watch?v=shared-vid"}]
    count_a = _save_videos(db_session, ch_a, videos)
    count_b = _save_videos(db_session, ch_b, videos)

    assert count_a == 1
    assert count_b == 0


# ─── youtube_channel_id persistence ──────────────────────────────────────────

def test_scan_channel_persists_youtube_channel_id(db_session, make_user, make_channel):
    """
    After a scan, the resolved YouTube channel ID must be saved back to the Channel row.
    Mocks the YouTube API to avoid real network calls.
    """
    from api.services.scanner import scan_channel

    user = make_user()
    channel = make_channel(user.id)
    assert channel.youtube_channel_id is None

    mock_youtube = MagicMock()
    mock_youtube.playlistItems().list().execute.return_value = {"items": []}

    with patch("api.services.scanner.build_youtube_client", return_value=mock_youtube), \
         patch("api.services.scanner.get_channel_info",
               return_value=("UC_real_channel_id", "UU_uploads_playlist")):
        scan_channel(db_session, channel, api_key="fake-key")

    db_session.refresh(channel)
    assert channel.youtube_channel_id == "UC_real_channel_id"


# ─── Shorts filtering ─────────────────────────────────────────────────────────

def _make_playlist_item(video_id: str, title: str, published_at: str = "2025-06-01T00:00:00Z"):
    return {
        "snippet": {
            "publishedAt": published_at,
            "title": title,
            "description": "desc",
            "resourceId": {"videoId": video_id},
        }
    }


def _make_mock_youtube(playlist_items: list, details: dict):
    """Return a mock YouTube client with the given playlist items and video details."""
    mock = MagicMock()
    mock.playlistItems().list().execute.return_value = {
        "items": playlist_items,
        "nextPageToken": None,
    }
    mock.videos().list().execute.return_value = {
        "items": [
            {
                "id": vid_id,
                "contentDetails": {"duration": f"PT{info['duration_sec']}S"},
                "snippet": {"tags": info.get("tags", [])},
            }
            for vid_id, info in details.items()
        ]
    }
    return mock


def test_scan_excludes_shorts_by_hashtag(db_session, make_user, make_channel):
    """Videos with #shorts in the title must never reach the DB."""
    from api.services.scanner import scan_channel

    user = make_user()
    channel = make_channel(user.id)

    items = [
        _make_playlist_item("full-vid", "Full Workout — Push Day"),
        _make_playlist_item("short-vid", "Quick tip #shorts"),
        _make_playlist_item("short-vid2", "60s Stretch #Shorts"),
    ]
    details = {
        "full-vid": {"duration_sec": 1800},
        # Shorts would be filtered before fetching details, but include them
        # in the mock so the test doesn't fail on missing detail keys.
        "short-vid": {"duration_sec": 45},
        "short-vid2": {"duration_sec": 58},
    }
    mock_youtube = _make_mock_youtube(items, details)

    with patch("api.services.scanner.build_youtube_client", return_value=mock_youtube), \
         patch("api.services.scanner.get_channel_info",
               return_value=("UC_test", "UU_test")), \
         patch("api.services.scanner._fetch_video_details",
               return_value={k: v for k, v in details.items()}):
        count = scan_channel(db_session, channel, api_key="fake-key")

    assert count == 1
    saved_ids = {v.id for v in db_session.query(Video).filter(Video.channel_id == channel.id).all()}
    assert "full-vid" in saved_ids
    assert "short-vid" not in saved_ids
    assert "short-vid2" not in saved_ids


def test_scan_excludes_shorts_by_duration(db_session, make_user, make_channel):
    """Videos under 3 minutes without the #shorts hashtag must also be excluded."""
    from api.services.scanner import scan_channel

    user = make_user()
    channel = make_channel(user.id)

    items = [
        _make_playlist_item("full-vid", "30 Minute Full Body Workout"),
        _make_playlist_item("borderline-vid", "2 Minute Stretch"),   # no hashtag, but < 180s
        _make_playlist_item("exactly-3min", "3 Minute Core Blast"),  # exactly 180s — included
    ]
    details = {
        "full-vid": {"duration_sec": 1800},
        "borderline-vid": {"duration_sec": 119},
        "exactly-3min": {"duration_sec": 180},
    }
    mock_youtube = _make_mock_youtube(items, details)

    with patch("api.services.scanner.build_youtube_client", return_value=mock_youtube), \
         patch("api.services.scanner.get_channel_info",
               return_value=("UC_test", "UU_test")), \
         patch("api.services.scanner._fetch_video_details",
               return_value=details):
        count = scan_channel(db_session, channel, api_key="fake-key")

    assert count == 2
    saved_ids = {v.id for v in db_session.query(Video).filter(Video.channel_id == channel.id).all()}
    assert "full-vid" in saved_ids
    assert "exactly-3min" in saved_ids
    assert "borderline-vid" not in saved_ids


def test_scan_excludes_null_duration(db_session, make_user, make_channel):
    """Videos where duration could not be resolved are excluded (can't verify not a Short)."""
    from api.services.scanner import scan_channel

    user = make_user()
    channel = make_channel(user.id)

    items = [
        _make_playlist_item("good-vid", "Good Workout"),
        _make_playlist_item("no-dur-vid", "Unknown Duration Video"),
    ]
    details = {
        "good-vid": {"duration_sec": 2400},
        "no-dur-vid": {"duration_sec": None},
    }
    mock_youtube = _make_mock_youtube(items, details)

    with patch("api.services.scanner.build_youtube_client", return_value=mock_youtube), \
         patch("api.services.scanner.get_channel_info",
               return_value=("UC_test", "UU_test")), \
         patch("api.services.scanner._fetch_video_details",
               return_value=details):
        count = scan_channel(db_session, channel, api_key="fake-key")

    assert count == 1
    saved_ids = {v.id for v in db_session.query(Video).filter(Video.channel_id == channel.id).all()}
    assert "good-vid" in saved_ids
    assert "no-dur-vid" not in saved_ids
