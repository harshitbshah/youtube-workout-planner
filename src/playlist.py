"""
playlist.py — Manage the weekly YouTube playlist via the Data API.

Requires OAuth 2.0 credentials (not just an API key) because writing
to a playlist requires user account access.

In GitHub Actions, credentials are passed as environment variables
(secrets). The refresh token is used to get a fresh access token
each run — no browser interaction needed.

Quota costs per weekly refresh (~6 videos):
  playlistItems.list    1 unit  (listing existing items)
  playlistItems.delete  50 units × N  (clearing old videos)
  playlistItems.insert  50 units × 6  (adding new videos)
  playlists.update      50 units  (updating description)
  Total ≈ 650 units — well within the 10,000/day free quota.
"""

import logging
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]


# ─── OAuth client ─────────────────────────────────────────────────────────────

def build_oauth_client(client_id: str, client_secret: str, refresh_token: str):
    """
    Build an authenticated YouTube client using a stored refresh token.

    Works headlessly (no browser) — suitable for GitHub Actions.
    The refresh token never expires unless explicitly revoked.
    """
    creds = Credentials(
        token=None,                                      # no access token yet
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=YOUTUBE_SCOPES,
    )
    # Exchange refresh token for a fresh access token immediately
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


# ─── Playlist item listing ────────────────────────────────────────────────────

def _list_playlist_item_ids(youtube, playlist_id: str) -> list[str]:
    """
    Return all playlistItem IDs currently in the playlist.

    Note: playlistItem ID ≠ video ID.
    The playlistItem ID is needed to delete an entry from a playlist.
    """
    item_ids = []
    page_token = None

    while True:
        resp = youtube.playlistItems().list(
            part="id",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        item_ids.extend(item["id"] for item in resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return item_ids


# ─── Clear ────────────────────────────────────────────────────────────────────

def clear_playlist(youtube, playlist_id: str):
    """
    Remove every video from the playlist.

    Deletes items one by one — the API does not support bulk delete.
    Adds a small delay between calls to stay within rate limits.
    """
    item_ids = _list_playlist_item_ids(youtube, playlist_id)

    if not item_ids:
        logger.info("Playlist is already empty.")
        return

    logger.info(f"Clearing {len(item_ids)} existing items from playlist...")

    for item_id in item_ids:
        try:
            youtube.playlistItems().delete(id=item_id).execute()
            time.sleep(0.3)
        except HttpError as e:
            logger.warning(f"Failed to delete playlist item {item_id}: {e}")


# ─── Populate ─────────────────────────────────────────────────────────────────

def populate_playlist(youtube, playlist_id: str, video_ids: list[str]):
    """
    Add videos to the playlist in the given order (position 0, 1, 2 ...).

    video_ids: ordered list of YouTube video IDs (Mon → Sun, skipping rest days)
    """
    logger.info(f"Adding {len(video_ids)} videos to playlist...")

    for position, video_id in enumerate(video_ids):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "position":   position,
                        "resourceId": {
                            "kind":    "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            ).execute()
            logger.info(f"  [{position + 1}/{len(video_ids)}] Added video {video_id}")
            time.sleep(0.3)
        except HttpError as e:
            logger.error(f"Failed to add video {video_id} at position {position}: {e}")


# ─── Update description ───────────────────────────────────────────────────────

def update_playlist_description(youtube, playlist_id: str,
                                 title: str, description: str):
    """
    Overwrite the playlist's title and description.

    Used to stamp the weekly summary into the playlist so you can
    see the full plan without opening each video.
    """
    try:
        youtube.playlists().update(
            part="snippet",
            body={
                "id": playlist_id,
                "snippet": {
                    "title":       title,
                    "description": description,
                },
            },
        ).execute()
        logger.info("Playlist description updated.")
    except HttpError as e:
        logger.error(f"Failed to update playlist description: {e}")


# ─── Full weekly refresh ──────────────────────────────────────────────────────

def refresh_playlist(youtube, playlist_id: str,
                     plan: list[dict], summary: str):
    """
    Full weekly refresh: clear → populate → update description.

    plan: output of planner.generate_weekly_plan()
    summary: output of planner.format_plan_summary()
    """
    # Extract ordered video IDs (skip Rest days where video is None)
    video_ids = [
        day["video"]["id"]
        for day in plan
        if day["video"] is not None
    ]

    if not video_ids:
        logger.error("Plan contains no videos — playlist not updated.")
        return

    clear_playlist(youtube, playlist_id)
    populate_playlist(youtube, playlist_id, video_ids)
    update_playlist_description(
        youtube,
        playlist_id,
        title="Weekly Workout Plan",
        description=summary,
    )

    logger.info(
        f"Playlist refreshed with {len(video_ids)} videos. "
        f"Open: https://youtube.com/playlist?list={playlist_id}"
    )
