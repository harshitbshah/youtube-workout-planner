"""021 - Add equipment to users; data migration for yoga/pilates/dance split from mobility.

Revision ID: 021
Revises: 020
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    # ── Schema: add equipment column to users ─────────────────────────────────
    op.add_column("users", sa.Column("equipment", sa.Text(), nullable=True))

    # ── Data: reclassify Mobility videos whose titles clearly indicate yoga,
    #    pilates, barre, or dance. Order matters: dance is checked against both
    #    mobility AND cardio classifications to catch dance cardio misclassified
    #    as cardio. Yoga and pilates are checked only against mobility. ──────────

    # Dance: title contains Zumba, Bollywood dance, dance fitness, bhangra, etc.
    # Reclassify from Mobility OR Cardio
    op.execute("""
        UPDATE classifications
        SET workout_type = 'Dance'
        FROM videos
        WHERE classifications.video_id = videos.id
          AND LOWER(classifications.workout_type) IN ('mobility', 'cardio')
          AND videos.title ~* '\\m(zumba|bollywood[\\s_-]*dance|dance[\\s_-]*fitness|bhangra|salsa[\\s_-]*workout|hip[\\s_-]*hop[\\s_-]*dance|aerobic[\\s_-]*dance)\\M'
    """)

    # Yoga: title contains yoga, vinyasa, hatha, yin yoga, ashtanga, etc.
    # Reclassify from Mobility only
    op.execute("""
        UPDATE classifications
        SET workout_type = 'Yoga'
        FROM videos
        WHERE classifications.video_id = videos.id
          AND LOWER(classifications.workout_type) = 'mobility'
          AND videos.title ~* '\\m(yoga|vinyasa|hatha|yin[\\s_-]*yoga|ashtanga|kundalini|sun[\\s_-]*salutation|pranayama)\\M'
    """)

    # Pilates/Barre: title contains pilates, reformer, or barre
    # Reclassify from Mobility only
    op.execute("""
        UPDATE classifications
        SET workout_type = 'Pilates'
        FROM videos
        WHERE classifications.video_id = videos.id
          AND LOWER(classifications.workout_type) = 'mobility'
          AND videos.title ~* '\\m(pilates|reformer|barre)\\M'
    """)


def downgrade():
    op.drop_column("users", "equipment")

    # Revert yoga/pilates/barre/dance back to Mobility (approximate - some
    # dance that was Cardio before cannot be perfectly restored)
    op.execute("""
        UPDATE classifications
        SET workout_type = 'Mobility'
        WHERE LOWER(workout_type) IN ('yoga', 'pilates')
    """)
    op.execute("""
        UPDATE classifications
        SET workout_type = 'Cardio'
        WHERE LOWER(workout_type) = 'dance'
    """)
