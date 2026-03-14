"""Add profile and goal columns to users table

Revision ID: 019
Revises: 018
Create Date: 2026-03-14

Stores the user's onboarding profile (beginner/adult/senior/athlete) and goal
(e.g. "Build muscle") so the channel validator can check fitness relevance.
Both are nullable — users who completed onboarding before this migration are
unaffected and simply skip validation.
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("profile", sa.String(), nullable=True))
    op.add_column("users", sa.Column("goal", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "goal")
    op.drop_column("users", "profile")
