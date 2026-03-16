"""
022_fix_non_workout_classifications

Fix misclassified videos: set workout_type = 'Other' for videos whose titles
match commentary, reaction, progress-tracking, or other non-follow-along patterns.
These slipped through the scanner title blocklist and were incorrectly classified
as Strength/HIIT/etc by the AI because workout-related words appear in the title.
"""

revision = "022"
down_revision = "021"

from alembic import op


_PATTERNS = [
    # commentary / reaction / critique
    "%critique%",
    "%react to%",
    "%reaction%",
    "%commentary%",
    "%scientists explain%",
    "%science explains%",
    "%debunking%",
    "%debunked%",
    "%roast%",
    # progress / challenge tracking
    "%365 days%",
    "%30 day%",
    "%90 day%",
    "%100 day%",
    "%how much muscle%",
    "%how much weight%",
    "%did i gain%",
    "%did i lose%",
    "%progress update%",
    "%my transformation%",
    "%natty or not%",
]


def upgrade():
    for pattern in _PATTERNS:
        op.execute(f"""
            UPDATE classifications
            SET workout_type = 'Other'
            WHERE video_id IN (
                SELECT id FROM videos WHERE LOWER(title) LIKE LOWER('{pattern}')
            )
            AND workout_type != 'Other'
        """)


def downgrade():
    pass
