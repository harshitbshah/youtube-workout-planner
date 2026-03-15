"""Initial schema - users, channels, videos, classifications, schedules, history, credentials

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("google_id", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("youtube_url", sa.String(), nullable=False),
        sa.Column("youtube_channel_id", sa.String()),
        sa.Column("added_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("duration_sec", sa.Integer()),
        sa.Column("published_at", sa.String()),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("tags", sa.Text()),
    )

    op.create_table(
        "classifications",
        sa.Column("video_id", sa.String(), sa.ForeignKey("videos.id"), primary_key=True),
        sa.Column("workout_type", sa.String()),
        sa.Column("body_focus", sa.String()),
        sa.Column("difficulty", sa.String()),
        sa.Column("has_warmup", sa.Boolean()),
        sa.Column("has_cooldown", sa.Boolean()),
        sa.Column("classified_at", sa.String()),
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.String(), nullable=False),
        sa.Column("workout_type", sa.String()),
        sa.Column("body_focus", sa.String()),
        sa.Column("duration_min", sa.Integer()),
        sa.Column("duration_max", sa.Integer()),
        sa.Column("difficulty", sa.String()),
    )

    op.create_table(
        "program_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("video_id", sa.String(), sa.ForeignKey("videos.id")),
        sa.Column("assigned_day", sa.String(), nullable=False),
        sa.Column("completed", sa.Boolean(), default=False),
    )

    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("youtube_refresh_token", sa.Text()),
        sa.Column("anthropic_key", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("user_credentials")
    op.drop_table("program_history")
    op.drop_table("schedules")
    op.drop_table("classifications")
    op.drop_table("videos")
    op.drop_table("channels")
    op.drop_table("users")
