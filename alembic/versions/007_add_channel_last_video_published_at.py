"""Add channels.last_video_published_at

Revision ID: 007
Revises: 006
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "channels",
        sa.Column("last_video_published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("channels", "last_video_published_at")
