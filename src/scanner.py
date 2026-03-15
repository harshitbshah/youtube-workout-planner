"""
scanner.py - Fetch videos from YouTube channels and store in the database.

Two modes:
  full_scan()        Fetch ALL videos from a channel (run once per new channel)
  incremental_scan() Fetch only new uploads since a given date (run weekly)

Quota cost (YouTube Data API v3):
  - channels.list      → 1 unit  (resolve handle → channel ID)
  - playlistItems.list → 1 unit  per page of 50 videos
  - videos.list        → 1 unit  per batch of 50 (to get duration + tags)
  A 500-video channel costs ~20 units. Daily free quota is 10,000.
"""

import re
import time
import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .db import get_connection

logger = logging.getLogger(__name__)


# ─── YouTube client ───────────────────────────────────────────────────────────

def build_youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


# ─── Channel resolution ───────────────────────────────────────────────────────

def get_channel_info(youtube, url: str) -> tuple[str, str]:
    """
    Resolve a channel URL to (channel_id, uploads_playlist_id).

    Supports:
      https://www.youtube.com/@TIFFxDAN
      https://www.youtube.com/channel/UCxxxxxxxx
    """
    if "@" in url:
        handle = url.rstrip("/").split("@")[-1]
        resp = youtube.channels().list(
            part="id,contentDetails",
            forHandle=handle
        ).execute()
    elif "/channel/" in url:
        channel_id = url.rstrip("/").split("/channel/")[-1]
        resp = youtube.channels().list(
            part="id,contentDetails",
            id=channel_id
        ).execute()
    else:
        raise ValueError(f"Unrecognised channel URL format: {url}")

    if not resp.get("items"):
        raise ValueError(f"Channel not found for URL: {url}")

    item = resp["items"][0]
    channel_id = item["id"]
    uploads_playlist_id = item["contentDetails"]["relatedPlaylists"]["uploads"]
    return channel_id, uploads_playlist_id


# ─── Video detail fetching ────────────────────────────────────────────────────

def _fetch_video_details(youtube, video_ids: list[str]) -> dict[str, dict]:
    """
    Batch fetch duration and tags for up to 50 videos in one API call.
    Returns dict keyed by video_id.
    """
    resp = youtube.videos().list(
        part="contentDetails,snippet",
        id=",".join(video_ids)
    ).execute()

    details = {}
    for item in resp.get("items", []):
        details[item["id"]] = {
            "duration_sec": _parse_duration(item["contentDetails"]["duration"]),
            "tags": ",".join(item["snippet"].get("tags", [])),
        }
    return details


def _parse_duration(iso_duration: str) -> int:
    """Convert ISO 8601 duration string (e.g. PT1H2M3S) to total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds


# ─── Database write ───────────────────────────────────────────────────────────

def _save_videos(videos: list[dict]) -> int:
    """
    Insert videos into DB, silently skipping duplicates.
    Returns count of newly inserted rows.
    """
    with get_connection() as conn:
        cursor = conn.executemany("""
            INSERT OR IGNORE INTO videos
                (id, channel_id, channel_name, title, description,
                 duration_sec, published_at, url, tags)
            VALUES
                (:id, :channel_id, :channel_name, :title, :description,
                 :duration_sec, :published_at, :url, :tags)
        """, videos)
        return cursor.rowcount


# ─── Core pagination logic ────────────────────────────────────────────────────

def _scan_uploads(youtube, uploads_playlist_id: str, channel_id: str,
                  channel_name: str, since_date: datetime | None = None) -> int:
    """
    Paginate through a channel's uploads playlist and save videos to the DB.

    The uploads playlist is ordered newest-first, so for incremental scans
    we stop as soon as we encounter a video older than since_date.

    Returns total new videos saved.
    """
    total_new = 0
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
            logger.error(f"YouTube API error while scanning {channel_name}: {e}")
            raise

        items = resp.get("items", [])
        if not items:
            break

        batch = []
        stop_pagination = False

        for item in items:
            snippet = item["snippet"]
            published_at = snippet.get("publishedAt", "")
            video_id = snippet["resourceId"]["videoId"]

            # Incremental mode: stop when we reach videos older than since_date
            if since_date and published_at:
                pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if pub_dt < since_date:
                    stop_pagination = True
                    break

            # Skip deleted/private videos (title is "[Deleted video]" or "[Private video]")
            title = snippet.get("title", "")
            if title in ("[Deleted video]", "[Private video]"):
                continue

            batch.append({
                "id": video_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "title": title,
                "description": snippet.get("description", "")[:2000],  # cap length
                "duration_sec": None,   # enriched below
                "published_at": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "tags": None,           # enriched below
            })

        # Enrich batch with duration + tags in one API call
        if batch:
            video_ids = [v["id"] for v in batch]
            details = _fetch_video_details(youtube, video_ids)
            for v in batch:
                d = details.get(v["id"], {})
                v["duration_sec"] = d.get("duration_sec")
                v["tags"] = d.get("tags")

            new_count = _save_videos(batch)
            total_new += new_count
            logger.info(f"  [{channel_name}] page: {new_count} new / {len(batch)} fetched")

        page_token = resp.get("nextPageToken")
        if not page_token or stop_pagination:
            break

        time.sleep(0.1)  # stay well within API rate limits

    return total_new


# ─── Public API ───────────────────────────────────────────────────────────────

def full_scan(youtube, channel_name: str, channel_url: str) -> int:
    """
    Fetch ALL videos from a channel and save to DB.
    Run once when adding a new channel.

    Returns total videos saved.
    """
    logger.info(f"Starting full scan: {channel_name}")
    channel_id, uploads_playlist_id = get_channel_info(youtube, channel_url)
    total = _scan_uploads(youtube, uploads_playlist_id, channel_id, channel_name)
    logger.info(f"Full scan complete: {total} videos saved for {channel_name}")
    return total


def incremental_scan(youtube, channel_name: str, channel_url: str,
                     since_date: datetime) -> int:
    """
    Fetch only videos published after since_date and save to DB.
    Run weekly during the normal --run cycle.

    Returns count of new videos saved.
    """
    logger.info(f"Incremental scan: {channel_name} (since {since_date.date()})")
    channel_id, uploads_playlist_id = get_channel_info(youtube, channel_url)
    total = _scan_uploads(youtube, uploads_playlist_id, channel_id, channel_name,
                          since_date=since_date)
    logger.info(f"Incremental scan complete: {total} new videos for {channel_name}")
    return total


def scan_all_channels(youtube, channels: list[dict],
                      since_date: datetime | None = None) -> int:
    """
    Convenience wrapper to scan all channels from config.

    If since_date is None → full scan (first-time init).
    If since_date is set  → incremental scan (weekly run).

    channels: list of dicts with keys 'name' and 'url'
    Returns total new videos saved across all channels.
    """
    total = 0
    for ch in channels:
        if since_date:
            total += incremental_scan(youtube, ch["name"], ch["url"], since_date)
        else:
            total += full_scan(youtube, ch["name"], ch["url"])
    return total
