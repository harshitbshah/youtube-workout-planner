"""
channels.py — Manage a user's YouTube channels and search for new ones.

Routes:
  GET    /channels          — list user's channels
  POST   /channels          — add channel (creates global Channel if needed, then links user)
  DELETE /channels/{id}     — unlink channel from user (channel + videos are preserved)
  GET    /channels/search?q= — search YouTube channels by name
"""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Channel, User, UserChannel
from ..schemas import ChannelCreate, ChannelResponse, ChannelSearchResult

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
    # Find or create the global channel record
    channel = None
    if body.youtube_channel_id:
        channel = (
            db.query(Channel)
            .filter(Channel.youtube_channel_id == body.youtube_channel_id)
            .first()
        )
    if not channel:
        channel = db.query(Channel).filter(Channel.youtube_url == body.youtube_url).first()
    if not channel:
        channel = Channel(
            name=body.name,
            youtube_url=body.youtube_url,
            youtube_channel_id=body.youtube_channel_id,
        )
        db.add(channel)
        db.flush()  # assign id without committing

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
