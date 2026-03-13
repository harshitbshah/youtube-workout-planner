"""Add users.email_notifications

Revision ID: 015
Revises: 008
Create Date: 2026-03-13

Note: Migrations 009–014 are planned for future phases (AI profile enrichment,
exercise breakdowns, channel thumbnails, video feedback, AI cost-reduction F7/F8).
This migration is independent and chains directly from 008.
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade():
    op.drop_column("users", "email_notifications")
