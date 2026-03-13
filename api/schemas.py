"""
schemas.py — Pydantic request/response models for the Phase 2 API.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, HttpUrl


# ─── Channels ─────────────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str
    youtube_url: str
    youtube_channel_id: Optional[str] = None


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    youtube_url: str
    youtube_channel_id: Optional[str]
    added_at: str


class ChannelSearchResult(BaseModel):
    youtube_channel_id: str
    name: str
    description: str
    thumbnail_url: Optional[str]


# ─── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleSlot(BaseModel):
    day: str
    workout_type: Optional[str] = None   # None = rest day
    body_focus: Optional[str] = None
    duration_min: Optional[int] = None
    duration_max: Optional[int] = None
    difficulty: str = "any"


class ScheduleResponse(BaseModel):
    schedule: list[ScheduleSlot]


class ScheduleUpdate(BaseModel):
    schedule: list[ScheduleSlot]


# ─── Plan ─────────────────────────────────────────────────────────────────────

class VideoSummary(BaseModel):
    id: str
    title: str
    url: str
    channel_name: str
    duration_sec: Optional[int]
    workout_type: Optional[str]
    body_focus: Optional[str]
    difficulty: Optional[str]


class PlanDay(BaseModel):
    day: str
    video: Optional[VideoSummary]


class PlanResponse(BaseModel):
    week_start: str
    days: list[PlanDay]


class PatchDayRequest(BaseModel):
    video_id: str


# ─── Auth ──────────────────────────────────────────────────────────────────────

class PatchMeRequest(BaseModel):
    display_name: str


class PatchMeNotificationsRequest(BaseModel):
    email_notifications: bool


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    youtube_connected: bool
    credentials_valid: bool
    is_admin: bool = False
    email_notifications: bool = True


# ─── Publish ───────────────────────────────────────────────────────────────────

class PublishResponse(BaseModel):
    playlist_url: str
    video_count: int


# ─── Library ───────────────────────────────────────────────────────────────────

class LibraryResponse(BaseModel):
    videos: list[VideoSummary]
    total: int
    page: int
    pages: int
