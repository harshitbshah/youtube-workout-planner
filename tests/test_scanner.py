import src.db as db_module
from src.scanner import _parse_duration, _save_videos


# ─── Pure function tests — no DB needed ───────────────────────────────────────

def test_parse_duration_full():
    assert _parse_duration("PT1H2M3S") == 3723


def test_parse_duration_minutes_only():
    assert _parse_duration("PT30M") == 1800


def test_parse_duration_seconds_only():
    assert _parse_duration("PT45S") == 45


def test_parse_duration_hours_only():
    assert _parse_duration("PT2H") == 7200


def test_parse_duration_invalid():
    assert _parse_duration("") == 0
    assert _parse_duration("garbage") == 0


# ─── DB tests ─────────────────────────────────────────────────────────────────

def _make_video(video_id="vid1"):
    return {
        "id": video_id,
        "channel_id": "UC123",
        "channel_name": "TestChannel",
        "title": "Test Workout",
        "description": "A test workout",
        "duration_sec": 1800,
        "published_at": "2024-01-01T00:00:00Z",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "tags": "workout,fitness",
    }


def test_save_videos_inserts(test_db):
    count = _save_videos([_make_video()])
    assert count == 1
    with db_module.get_connection() as conn:
        row = conn.execute("SELECT * FROM videos WHERE id = 'vid1'").fetchone()
    assert row is not None
    assert row["title"] == "Test Workout"


def test_save_videos_skips_duplicates(test_db):
    _save_videos([_make_video()])
    count = _save_videos([_make_video()])  # same video ID again
    assert count == 0
    with db_module.get_connection() as conn:
        rows = conn.execute("SELECT * FROM videos").fetchall()
    assert len(rows) == 1
