"""Fix program_history.video_id FK to ON DELETE SET NULL

Revision ID: 016
Revises: 015
Create Date: 2026-03-13

Without ON DELETE SET NULL, deleting a channel cascades to delete its videos,
which fails with an FK constraint violation because program_history rows still
reference those video IDs. SET NULL preserves workout history while allowing
channels and their videos to be deleted cleanly.
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing FK, re-add with ON DELETE SET NULL
    op.drop_constraint(
        "program_history_video_id_fkey",
        "program_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "program_history_video_id_fkey",
        "program_history",
        "videos",
        ["video_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "program_history_video_id_fkey",
        "program_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "program_history_video_id_fkey",
        "program_history",
        "videos",
        ["video_id"],
        ["id"],
    )
