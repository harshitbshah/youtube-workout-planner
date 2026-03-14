"""Add thumbnail_url and description to channels table

Revision ID: 018
Revises: 017
Create Date: 2026-03-14

Caches YouTube channel metadata (thumbnail URL and description) on the global
channels table so the /channels/suggestions endpoint can serve curated channel
cards without hitting the YouTube API on every request.
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("channels", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("channels", sa.Column("description", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("channels", "description")
    op.drop_column("channels", "thumbnail_url")
