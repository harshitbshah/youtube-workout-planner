"""Convert users.goal from plain string to JSON array string

Revision ID: 020
Revises: 019
Create Date: 2026-03-15

Existing single-string goals (e.g. "Build muscle") are converted to
JSON arrays (e.g. '["Build muscle"]'). New writes always store a
JSON array. Null stays null.
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, goal FROM users WHERE goal IS NOT NULL"))
    for row in rows:
        goal = row.goal
        if goal and not goal.startswith("["):
            conn.execute(
                text("UPDATE users SET goal = :goal WHERE id = :id"),
                {"goal": json.dumps([goal]), "id": row.id},
            )


def downgrade():
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, goal FROM users WHERE goal IS NOT NULL"))
    for row in rows:
        goal = row.goal
        if goal and goal.startswith("["):
            try:
                goals = json.loads(goal)
                first = goals[0] if goals else None
                conn.execute(
                    text("UPDATE users SET goal = :goal WHERE id = :id"),
                    {"goal": first, "id": row.id},
                )
            except (json.JSONDecodeError, IndexError):
                pass
