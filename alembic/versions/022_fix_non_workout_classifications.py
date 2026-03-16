"""
022_fix_non_workout_classifications

Fix misclassified videos: set workout_type = 'Other' for videos whose titles
clearly indicate commentary/reaction/critique content. These slipped through
the scanner title blocklist and were incorrectly classified as workout types
by the AI because workout-related words appear in the title.

The AI classifier system prompt was also fixed (removed the "workout video"
framing that primed it to always return a workout type). This migration handles
videos that were already stored and classified under the old broken prompt.
"""

revision = "022"
down_revision = "021"

from alembic import op


# Only patterns that unambiguously indicate non-follow-along content.
# Deliberately conservative - the LLM handles everything else going forward.
_PATTERNS = [
    "%critique%",
    "%react to%",
    "% reaction%",   # leading space avoids matching e.g. "core reaction time"
    "%commentary%",
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
