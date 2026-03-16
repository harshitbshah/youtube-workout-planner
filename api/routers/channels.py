"""
channels.py - Manage a user's YouTube channels and search for new ones.

Routes:
  GET    /channels          - list user's channels
  POST   /channels          - add channel (creates global Channel if needed, then links user)
  DELETE /channels/{id}     - unlink channel from user (channel + videos are preserved)
  GET    /channels/search?q= - search YouTube channels by name
"""

import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, User, UserChannel
from ..schemas import ChannelCreate, ChannelResponse, ChannelSearchResult
from ..services.channel_validator import validate_channel_fitness

router = APIRouter(prefix="/channels", tags=["channels"])

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ChannelResponse])
def list_channels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserChannel, Channel)
        .join(Channel, Channel.id == UserChannel.channel_id)
        .filter(UserChannel.user_id == current_user.id)
        .all()
    )
    return [
        ChannelResponse(
            id=ch.id,
            name=ch.name,
            youtube_url=ch.youtube_url,
            youtube_channel_id=ch.youtube_channel_id,
            thumbnail_url=ch.thumbnail_url,
            added_at=uc.added_at.isoformat() if uc.added_at else "",
        )
        for uc, ch in rows
    ]


# ─── Add ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=ChannelResponse, status_code=201)
def add_channel(
    body: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find existing global channel record
    channel = None
    if body.youtube_channel_id:
        channel = (
            db.query(Channel)
            .filter(Channel.youtube_channel_id == body.youtube_channel_id)
            .first()
        )
    if not channel:
        channel = db.query(Channel).filter(Channel.youtube_url == body.youtube_url).first()

    # Validate channel fits user's fitness profile BEFORE any DB writes
    if current_user.profile and current_user.goal:
        # Prefer cached description from DB; fall back to what the frontend sent
        desc = (channel.description if channel else None) or body.description or ""
        channel_name = channel.name if channel else body.name
        ok, label = validate_channel_fitness(
            channel_name=channel_name,
            channel_description=desc,
            profile=current_user.profile,
            goal=current_user.goal,
        )
        if not ok:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"This looks like a {label} channel. "
                    f"Your plan is focused on {current_user.goal.lower()}. "
                    f"Try adding a fitness channel instead."
                ),
            )

    # Create the global channel record if it doesn't exist yet
    if not channel:
        channel = Channel(
            name=body.name,
            youtube_url=body.youtube_url,
            youtube_channel_id=body.youtube_channel_id,
            description=body.description,
            thumbnail_url=body.thumbnail_url,
        )
        db.add(channel)
        db.flush()  # assign id without committing

    # Enforce per-user channel limit
    channel_count = (
        db.query(UserChannel)
        .filter(UserChannel.user_id == current_user.id)
        .count()
    )
    if channel_count >= 5:
        raise HTTPException(status_code=400, detail="Channel limit reached. You can add up to 5 channels.")

    # Check the user isn't already subscribed
    existing = (
        db.query(UserChannel)
        .filter(
            UserChannel.user_id == current_user.id,
            UserChannel.channel_id == channel.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Channel already added")

    uc = UserChannel(user_id=current_user.id, channel_id=channel.id)
    db.add(uc)
    db.commit()
    db.refresh(uc)

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        youtube_url=channel.youtube_url,
        youtube_channel_id=channel.youtube_channel_id,
        thumbnail_url=channel.thumbnail_url,
        added_at=uc.added_at.isoformat() if uc.added_at else "",
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the user's subscription to this channel. Channel and videos are preserved."""
    uc = (
        db.query(UserChannel)
        .filter(
            UserChannel.channel_id == channel_id,
            UserChannel.user_id == current_user.id,
        )
        .first()
    )
    if not uc:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.delete(uc)
    db.commit()


# ─── Suggestions ──────────────────────────────────────────────────────────────

# Curated 3-channel list per onboarding profile. These names are used to look up
# (or fetch-and-cache) the full channel data from YouTube once, then serve from
# the shared channels table forever.
_SUGGESTION_NAMES: dict[str, list[str]] = {
    "senior":   ["Grow Young Fitness", "HASfit", "SilverSneakers"],
    "beginner": ["Sydney Cummings Houdyshell", "Heather Robertson", "MommaStrong"],
    "adult":    ["Athlean-X", "Jeff Nippard", "Heather Robertson"],
    "athlete":  ["Athlean-X", "Jeff Nippard", "Renaissance Periodization"],
}
_GENERAL_SUGGESTIONS = _SUGGESTION_NAMES["adult"]


@router.get("/suggestions", response_model=list[ChannelSearchResult])
async def get_suggestions(
    profile: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return up to 3 curated channel cards for the given profile.

    Results are served from the shared channels table (DB cache). On a cache
    miss the YouTube API is called once and the result is stored for all future
    users. If the YouTube API key is missing, cached rows are still returned and
    uncached names are silently skipped.
    """
    names = _SUGGESTION_NAMES.get(profile or "", _GENERAL_SUGGESTIONS)
    results: list[ChannelSearchResult] = []

    async with httpx.AsyncClient() as client:
        for name in names:
            # Cache hit: channel already in DB with thumbnail
            ch = (
                db.query(Channel)
                .filter(
                    func.lower(Channel.name) == name.lower(),
                    Channel.thumbnail_url.isnot(None),
                )
                .first()
            )
            if ch:
                results.append(
                    ChannelSearchResult(
                        youtube_channel_id=ch.youtube_channel_id or "",
                        name=ch.name,
                        description=ch.description or "",
                        thumbnail_url=ch.thumbnail_url,
                    )
                )
                continue

            # Cache miss - fetch from YouTube and store
            if not YOUTUBE_API_KEY:
                continue  # no key: skip this suggestion silently

            try:
                resp = await client.get(
                    YOUTUBE_SEARCH_URL,
                    params={
                        "part": "snippet",
                        "type": "channel",
                        "q": name,
                        "maxResults": 1,
                        "key": YOUTUBE_API_KEY,
                    },
                    timeout=5.0,
                )
                if resp.status_code != 200:
                    continue

                items = resp.json().get("items", [])
                if not items:
                    continue

                snippet = items[0].get("snippet", {})
                channel_id = items[0].get("id", {}).get("channelId", "")
                ch_name = snippet.get("title", name)
                thumb_url = snippet.get("thumbnails", {}).get("default", {}).get("url")
                desc = snippet.get("description", "")

                # Upsert: prefer matching by youtube_channel_id, then by name
                existing = None
                if channel_id:
                    existing = (
                        db.query(Channel)
                        .filter(Channel.youtube_channel_id == channel_id)
                        .first()
                    )
                if not existing:
                    existing = (
                        db.query(Channel)
                        .filter(func.lower(Channel.name) == ch_name.lower())
                        .first()
                    )

                if existing:
                    existing.thumbnail_url = thumb_url
                    existing.description = desc
                    if channel_id and not existing.youtube_channel_id:
                        existing.youtube_channel_id = channel_id
                else:
                    existing = Channel(
                        name=ch_name,
                        youtube_url=f"https://www.youtube.com/channel/{channel_id}",
                        youtube_channel_id=channel_id,
                        thumbnail_url=thumb_url,
                        description=desc,
                    )
                    db.add(existing)
                db.commit()

                results.append(
                    ChannelSearchResult(
                        youtube_channel_id=channel_id,
                        name=ch_name,
                        description=desc,
                        thumbnail_url=thumb_url,
                    )
                )

            except Exception:
                continue  # network / parse error - skip this suggestion

    return results


# ─── Search ───────────────────────────────────────────────────────────────────

@router.get("/search", response_model=list[ChannelSearchResult])
async def search_channels(
    q: str,
    current_user: User = Depends(get_current_user),
):
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "type": "channel",
                "q": q,
                "maxResults": 10,
                "key": YOUTUBE_API_KEY,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="YouTube API request failed")

    items = resp.json().get("items", [])
    results = []
    for item in items:
        snippet = item.get("snippet", {})
        channel_id = item.get("id", {}).get("channelId", "")
        results.append(
            ChannelSearchResult(
                youtube_channel_id=channel_id,
                name=snippet.get("title", ""),
                description=snippet.get("description", ""),
                thumbnail_url=(
                    snippet.get("thumbnails", {}).get("default", {}).get("url")
                ),
            )
        )
    return results
