"""Shared channels: add user_channels join table, drop channels.user_id

Revision ID: 017
Revises: 016
Create Date: 2026-03-13

Channels become global (shared across users). A new user_channels join table
links users to the channels they've added. Deleting a channel subscription
removes only the user_channels row - the channel and its videos stay intact.

Migration steps:
  1. Create user_channels table
  2. Populate it from existing channels.user_id data
  3. Deduplicate channels by youtube_channel_id (merge duplicate rows that
     represent the same YouTube channel added by different users)
  4. Drop channels.user_id
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create user_channels join table
    op.create_table(
        "user_channels",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("channel_id", sa.String(36), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "channel_id"),
    )

    # 2. Populate user_channels from existing per-user channel rows
    op.execute("""
        INSERT INTO user_channels (user_id, channel_id, added_at)
        SELECT user_id, id, added_at
        FROM channels
        WHERE user_id IS NOT NULL
    """)

    # 3. Deduplicate channels that represent the same YouTube channel
    #    (same youtube_channel_id added by different users).
    #    Keep the oldest row as the canonical one.
    op.execute("""
        CREATE TEMP TABLE _canonical AS
        SELECT DISTINCT ON (youtube_channel_id)
            id AS canonical_id,
            youtube_channel_id
        FROM channels
        WHERE youtube_channel_id IS NOT NULL
        ORDER BY youtube_channel_id, added_at ASC NULLS LAST
    """)

    # Redirect videos from duplicate channels to their canonical channel
    op.execute("""
        UPDATE videos
        SET channel_id = _canonical.canonical_id
        FROM _canonical
        JOIN channels ON channels.youtube_channel_id = _canonical.youtube_channel_id
        WHERE videos.channel_id = channels.id
          AND channels.id != _canonical.canonical_id
    """)

    # Redirect user_channels rows from duplicates to canonical
    op.execute("""
        UPDATE user_channels
        SET channel_id = _canonical.canonical_id
        FROM _canonical
        JOIN channels ON channels.youtube_channel_id = _canonical.youtube_channel_id
        WHERE user_channels.channel_id = channels.id
          AND channels.id != _canonical.canonical_id
    """)

    # Remove any (user_id, channel_id) duplicates that arose from the redirect
    op.execute("""
        DELETE FROM user_channels
        WHERE ctid NOT IN (
            SELECT min(ctid)
            FROM user_channels
            GROUP BY user_id, channel_id
        )
    """)

    # Delete the now-orphaned duplicate channel rows
    op.execute("""
        DELETE FROM channels
        WHERE youtube_channel_id IS NOT NULL
          AND id NOT IN (SELECT canonical_id FROM _canonical)
    """)

    # 4. Drop user_id from channels
    op.drop_constraint("channels_user_id_fkey", "channels", type_="foreignkey")
    op.drop_column("channels", "user_id")


def downgrade():
    # Re-add user_id to channels (picks one arbitrary user per channel - lossy)
    op.add_column(
        "channels",
        sa.Column("user_id", sa.String(36), nullable=True),
    )
    op.execute("""
        UPDATE channels
        SET user_id = uc.user_id
        FROM (
            SELECT DISTINCT ON (channel_id) channel_id, user_id
            FROM user_channels
            ORDER BY channel_id, added_at ASC NULLS LAST
        ) uc
        WHERE channels.id = uc.channel_id
    """)
    op.create_foreign_key(
        "channels_user_id_fkey", "channels", "users", ["user_id"], ["id"]
    )
    op.drop_table("user_channels")
