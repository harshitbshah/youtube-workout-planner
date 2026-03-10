"""
models.py — SQLAlchemy ORM models for the multi-user web app.

All UUID primary keys are stored as String(36) for SQLite compatibility in tests.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    google_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    display_name = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    history = relationship("ProgramHistory", back_populates="user", cascade="all, delete-orphan")
    credentials = relationship("UserCredentials", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    youtube_url = Column(String, nullable=False)
    youtube_channel_id = Column(String)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True)          # YouTube video ID
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    duration_sec = Column(Integer)
    published_at = Column(String)                  # ISO 8601 string
    url = Column(String, nullable=False)
    tags = Column(Text)

    channel = relationship("Channel", back_populates="videos")
    classification = relationship("Classification", back_populates="video", uselist=False, cascade="all, delete-orphan")


class Classification(Base):
    __tablename__ = "classifications"

    video_id = Column(String, ForeignKey("videos.id"), primary_key=True)
    workout_type = Column(String)
    body_focus = Column(String)
    difficulty = Column(String)
    has_warmup = Column(Boolean, default=False)
    has_cooldown = Column(Boolean, default=False)
    classified_at = Column(String)

    video = relationship("Video", back_populates="classification")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    day = Column(String, nullable=False)           # monday … sunday
    workout_type = Column(String)                  # None = rest day
    body_focus = Column(String)
    duration_min = Column(Integer)
    duration_max = Column(Integer)
    difficulty = Column(String, default="any")

    user = relationship("User", back_populates="schedules")


class ProgramHistory(Base):
    __tablename__ = "program_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    video_id = Column(String, ForeignKey("videos.id"))
    assigned_day = Column(String, nullable=False)
    completed = Column(Boolean, default=False)

    user = relationship("User", back_populates="history")


class UserCredentials(Base):
    __tablename__ = "user_credentials"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    youtube_refresh_token = Column(Text)
    anthropic_key = Column(Text)
    credentials_valid = Column(Boolean, default=True, nullable=False)
    youtube_playlist_id = Column(String)
    classifier_batch_id = Column(String)   # active Anthropic batch ID — cleared when done
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="credentials")


class BatchUsageLog(Base):
    __tablename__ = "batch_usage_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    batch_id = Column(String, nullable=False)
    videos_submitted = Column(Integer, nullable=False)
    classified = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ScanLog(Base):
    __tablename__ = "scan_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="running")  # running | done | failed
    videos_scanned = Column(Integer, nullable=True)             # total new videos found


class UserActivityLog(Base):
    __tablename__ = "user_activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    active_at = Column(DateTime(timezone=True), nullable=False)  # one row per 5-min active window
