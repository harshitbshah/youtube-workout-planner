"""Add credentials_valid and youtube_playlist_id to user_credentials

Revision ID: 002
Revises: 001
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_credentials",
        sa.Column(
            "credentials_valid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_credentials",
        sa.Column("youtube_playlist_id", sa.String()),
    )


def downgrade():
    op.drop_column("user_credentials", "youtube_playlist_id")
    op.drop_column("user_credentials", "credentials_valid")
