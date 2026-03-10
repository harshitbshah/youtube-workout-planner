"""Add classifier_batch_id to user_credentials

Revision ID: 003
Revises: 002
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_credentials",
        sa.Column("classifier_batch_id", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("user_credentials", "classifier_batch_id")
