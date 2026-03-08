"""
publisher.py — Publish a user's weekly plan to their YouTube playlist.

Flow:
  1. Decrypt the stored YouTube refresh token
  2. Exchange it for an access token using google-auth
  3. Create a playlist if the user doesn't have one yet, else reuse it
  4. Clear existing items, populate with this week's video IDs, update description
  5. If the refresh token has been revoked, mark credentials_valid=False and raise

Quota cost per publish (~6 videos):
  playlistItems.list    1 unit
  playlistItems.delete  50 × N (clearing old items)
  playlistItems.insert  50 × 6 = 300 units
  playlists.update      50 units
  playlists.insert      50 units  (first publish only)
  Total ≈ 400–650 units — well within the 10,000/day free quota.
"""

import logging
import os

import google.auth.exceptions
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..crypto import decrypt
from ..models import ProgramHistory, UserCredentials
from src.playlist import (
    build_oauth_client,
    clear_playlist,
    populate_playlist,
    update_playlist_description,
)

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class YouTubeNotConnectedError(Exception):
    """User has no stored YouTube refresh token."""


class YouTubeAccessRevokedError(Exception):
    """Stored refresh token has been revoked by the user."""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _create_playlist(youtube, title: str, description: str) -> str:
    """Create a new private YouTube playlist and return its ID."""
    resp = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": "private"},
        },
    ).execute()
    return resp["id"]


def _mark_revoked(db: Session, creds: UserCredentials) -> None:
    creds.credentials_valid = False
    db.commit()


# ─── Main entry point ─────────────────────────────────────────────────────────

def publish_plan_for_user(db: Session, user_id: str, week_start) -> dict:
    """
    Publish the plan for `week_start` to the user's YouTube playlist.

    Returns {"playlist_url": str, "video_count": int}.

    Raises:
      YouTubeNotConnectedError  — no refresh token stored
      YouTubeAccessRevokedError — token revoked; credentials_valid set to False in DB
      ValueError                — no videos in the plan
      HttpError                 — unexpected YouTube API error
    """
    creds = db.query(UserCredentials).filter(UserCredentials.user_id == user_id).first()
    if not creds or not creds.youtube_refresh_token:
        raise YouTubeNotConnectedError("No YouTube credentials found for this user")

    try:
        refresh_token = decrypt(creds.youtube_refresh_token)
    except Exception as exc:
        raise YouTubeNotConnectedError(f"Failed to decrypt YouTube credentials: {exc}") from exc

    # Build OAuth client — raises RefreshError if token is revoked
    try:
        youtube = build_oauth_client(
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            refresh_token=refresh_token,
        )
    except google.auth.exceptions.RefreshError as exc:
        _mark_revoked(db, creds)
        raise YouTubeAccessRevokedError(str(exc)) from exc

    # Ordered list of video IDs for this week (skip rest/empty days)
    rows = (
        db.query(ProgramHistory)
        .filter(
            ProgramHistory.user_id == user_id,
            ProgramHistory.week_start == week_start,
        )
        .all()
    )
    by_day = {row.assigned_day: row for row in rows}
    video_ids = [
        by_day[day].video_id
        for day in DAYS_OF_WEEK
        if day in by_day and by_day[day].video_id
    ]

    if not video_ids:
        raise ValueError("No videos in the current plan — nothing to publish")

    # Publish
    try:
        if not creds.youtube_playlist_id:
            playlist_id = _create_playlist(
                youtube,
                title="Weekly Workout Plan",
                description="Auto-generated weekly workout plan",
            )
            creds.youtube_playlist_id = playlist_id
            db.commit()
        else:
            playlist_id = creds.youtube_playlist_id

        clear_playlist(youtube, playlist_id)
        populate_playlist(youtube, playlist_id, video_ids)
        update_playlist_description(
            youtube,
            playlist_id,
            title="Weekly Workout Plan",
            description=f"Week of {week_start} — {len(video_ids)} workout{'s' if len(video_ids) != 1 else ''}",
        )

    except HttpError as exc:
        if exc.resp.status in (401, 403):
            _mark_revoked(db, creds)
            raise YouTubeAccessRevokedError(str(exc)) from exc
        raise

    logger.info(f"[publish] user={user_id}: published {len(video_ids)} videos to {playlist_id}")
    return {
        "playlist_url": f"https://www.youtube.com/playlist?list={playlist_id}",
        "video_count": len(video_ids),
    }
