"""
api/services/scanner.py — Scan YouTube channels and save videos to PostgreSQL.

Reuses pure functions from src/scanner.py (YouTube API calls, duration parsing).
Only the DB layer is rewritten to use SQLAlchemy scoped to a user's channel.

Auto-detects full vs incremental:
  - No videos in DB for this channel → full scan (all videos)
  - Videos exist           → incremental scan (since most recent published_at)
"""

import logging
import os
import time
from datetime import datetime, timezone

from datetime import timedelta

from googleapiclient.errors import HttpError
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.scanner import _fetch_video_details, build_youtube_client, get_channel_info

from ..models import Channel, Video

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Max videos to fetch on a channel's first scan. Keeps the initial classification
# batch small. Subsequent incremental scans have no cap (only new videos are fetched).
FIRST_SCAN_LIMIT = int(os.getenv("FIRST_SCAN_LIMIT", "75"))

# Channels with no new videos for this many days are skipped during automated cron runs.
# Always scanned when the user triggers manually.
_INACTIVE_CHANNEL_DAYS = 60

# ─── Pre-classification filters ───────────────────────────────────────────────

# Titles containing any of these words are almost certainly not workout videos.
# Checked before fetching video details — no extra API calls needed.
_TITLE_BLOCKLIST = {
    # nutrition / food content
    "meal", "recipe", "nutrition", "grocery", "what i eat", "diet", "food",
    # lifestyle / non-workout
    "vlog", "day in my life", "life update", "story time", "haul",
    # talk / informational
    "q&a", "interview", "podcast", "questions and answers",
    # product / promotional
    "review", "unboxing", "giveaway",
    # results / meta
    "transformation", "before and after", "tour", "home gym",
    "behind the scenes",
}

# Videos longer than this are almost certainly livestreams, podcasts, or
# full-day challenges rather than standard workout sessions.
_MAX_DURATION_SEC = 2 * 60 * 60  # 2 hours


def _is_blocked_title(title: str) -> bool:
    """Return True if the title matches any non-workout keyword."""
    lower = title.lower()
    return any(kw in lower for kw in _TITLE_BLOCKLIST)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_since_date(session: Session, channel: Channel) -> datetime | None:
    """
    Return the published_at of the most recent video for this channel,
    or None if no videos exist (triggers a full scan).
    """
    latest = (
        session.query(Video.published_at)
        .filter(Video.channel_id == channel.id)
        .order_by(Video.published_at.desc())
        .first()
    )
    if not latest or not latest.published_at:
        return None
    return datetime.fromisoformat(latest.published_at.replace("Z", "+00:00"))


def _save_videos(session: Session, channel: Channel, videos: list[dict]) -> int:
    """Insert new videos, skipping duplicates. Returns count of new rows."""
    new_count = 0
    for v in videos:
        if session.get(Video, v["id"]) is None:
            session.add(Video(
                id=v["id"],
                channel_id=channel.id,
                title=v["title"],
                description=v.get("description"),
                duration_sec=v.get("duration_sec"),
                published_at=v.get("published_at"),
                url=v["url"],
                tags=v.get("tags"),
            ))
            new_count += 1
    session.commit()
    return new_count


def _scan_uploads(
    youtube,
    session: Session,
    channel: Channel,
    uploads_playlist_id: str,
    since_date: datetime | None = None,
    max_videos: int | None = None,
) -> int:
    """Paginate through uploads playlist and save new videos. Returns new video count."""
    total_new = 0
    total_fetched = 0
    page_token = None

    while True:
        try:
            resp = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            logger.error(f"YouTube API error scanning {channel.name}: {e}")
            raise

        items = resp.get("items", [])
        if not items:
            break

        batch = []
        stop_pagination = False

        for item in items:
            if max_videos and total_fetched >= max_videos:
                stop_pagination = True
                break

            snippet = item["snippet"]
            published_at = snippet.get("publishedAt", "")
            video_id = snippet["resourceId"]["videoId"]

            if since_date and published_at:
                pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if pub_dt <= since_date:
                    stop_pagination = True
                    break

            title = snippet.get("title", "")
            if title in ("[Deleted video]", "[Private video]"):
                continue

            # Layer 1: skip obvious Shorts by hashtag before fetching details
            if "#shorts" in title.lower():
                continue

            # Layer 2: skip livestreams and premieres (no extra API call needed)
            if snippet.get("liveBroadcastContent") in ("live", "upcoming"):
                continue

            # Layer 3: skip obvious non-workout titles before fetching details
            if _is_blocked_title(title):
                logger.debug(f"Skipping non-workout title: {title!r}")
                continue

            batch.append({
                "id": video_id,
                "title": title,
                "description": snippet.get("description", "")[:2000],
                "published_at": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "duration_sec": None,
                "tags": None,
            })
            total_fetched += 1

        if batch:
            details = _fetch_video_details(youtube, [v["id"] for v in batch])
            for v in batch:
                d = details.get(v["id"], {})
                v["duration_sec"] = d.get("duration_sec")
                v["tags"] = d.get("tags")

            # Layer 4: skip by duration after fetching details.
            # - < 3 min: Shorts (including those without the #shorts hashtag)
            # - > 2 hrs: likely a livestream, podcast, or multi-hour challenge
            # - None: unknown duration, can't verify — exclude to be safe
            batch = [
                v for v in batch
                if v.get("duration_sec")
                and 180 <= v["duration_sec"] <= _MAX_DURATION_SEC
            ]

            new_count = _save_videos(session, channel, batch)
            total_new += new_count
            logger.info(f"[{channel.name}] page: {new_count} new / {len(batch)} fetched")

        page_token = resp.get("nextPageToken")
        if not page_token or stop_pagination:
            break

        time.sleep(0.1)

    return total_new


# ─── Public API ───────────────────────────────────────────────────────────────

def _update_last_video_published_at(session: Session, channel: Channel) -> None:
    """Update channel.last_video_published_at to the most recent video's published_at."""
    latest_str = (
        session.query(func.max(Video.published_at))
        .filter(Video.channel_id == channel.id)
        .scalar()
    )
    if latest_str:
        try:
            channel.last_video_published_at = datetime.fromisoformat(
                latest_str.replace("Z", "+00:00")
            )
            session.commit()
        except (ValueError, AttributeError):
            pass


def scan_channel(
    session: Session,
    channel: Channel,
    api_key: str = "",
    max_videos: int | None = None,
    skip_if_inactive: bool = False,
) -> int:
    """
    Scan a channel for new videos and save to PostgreSQL.
    Auto-detects full vs incremental based on existing videos.

    max_videos: override the fetch cap (useful for testing). None uses automatic logic:
                - first scan (first_scan_done=False): capped at FIRST_SCAN_LIMIT
                - subsequent scans: no cap (only new videos fetched)
    skip_if_inactive: if True, skip channels with no new videos in _INACTIVE_CHANNEL_DAYS
                      days (used by cron). Always False for user-triggered scans.

    Returns count of new videos saved.
    """
    key = api_key or YOUTUBE_API_KEY
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not configured")

    # F4: skip inactive channels during cron runs
    if skip_if_inactive and channel.last_video_published_at is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_INACTIVE_CHANNEL_DAYS)
        # Normalise to UTC-aware — SQLite returns naive datetimes; PostgreSQL returns aware
        last_pub = channel.last_video_published_at
        if last_pub.tzinfo is None:
            last_pub = last_pub.replace(tzinfo=timezone.utc)
        added_at = channel.added_at
        if added_at is None:
            added_at = datetime.now(timezone.utc)
        elif added_at.tzinfo is None:
            added_at = added_at.replace(tzinfo=timezone.utc)
        channel_age = datetime.now(timezone.utc) - added_at
        if last_pub < cutoff and channel_age.days >= 30:
            logger.info(f"Skipping inactive channel {channel.name} (no videos in {_INACTIVE_CHANNEL_DAYS}d)")
            return 0

    youtube = build_youtube_client(key)
    since_date = _get_since_date(session, channel)

    channel_yt_id, uploads_playlist_id = get_channel_info(youtube, channel.youtube_url)

    # Persist the resolved YouTube channel ID if not already stored
    if not channel.youtube_channel_id:
        channel.youtube_channel_id = channel_yt_id
        session.commit()

    # F3: cap first scan to avoid large classification batches on new channels
    if max_videos is None and not channel.first_scan_done:
        effective_max = FIRST_SCAN_LIMIT
    else:
        effective_max = max_videos  # None = unlimited for incremental scans

    mode = "incremental" if since_date else "full"
    limit_note = f", max {effective_max}" if effective_max else ""
    logger.info(
        f"Starting {mode} scan: {channel.name} "
        f"(since {since_date.date() if since_date else 'beginning'}{limit_note})"
    )

    total = _scan_uploads(youtube, session, channel, uploads_playlist_id, since_date, effective_max)

    # Mark first scan done so subsequent scans run uncapped
    if not channel.first_scan_done:
        channel.first_scan_done = True
        session.commit()

    # F4: update last_video_published_at for inactive-channel tracking
    _update_last_video_published_at(session, channel)

    logger.info(f"Scan complete: {total} new videos for {channel.name}")
    return total
