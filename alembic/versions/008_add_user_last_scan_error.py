"""Add users.last_scan_error

Revision ID: 008
Revises: 007
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("last_scan_error", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("users", "last_scan_error")
